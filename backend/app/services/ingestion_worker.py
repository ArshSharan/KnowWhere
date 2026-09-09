"""
Document ingestion worker — Phase 2 upgrade (performance-optimised).

Performance improvements over original:
  - LLM extraction batches run CONCURRENTLY (asyncio.gather + semaphore)
  - Entity names are deduplicated before embedding — one batch embed call
    instead of one embed_one() call per fact
  - Reconciliation pairs run concurrently (asyncio.gather + semaphore)
  - Granular status updates so the frontend can show real progress

Full pipeline:
  PDF bytes → page extraction → concurrent LLM extraction
  → quote validation → batch embed entities → entity canonicalization
  → fact embedding → DB persistence → concurrent reconciliation → done
"""

from __future__ import annotations
import asyncio
import hashlib
import logging
from typing import Optional

import asyncpg
from openai import AsyncOpenAI

from app.config import get_settings
from app.db import crud
from app.services.embedder import embed_texts, embed_one, fact_embedding_text
from app.services.entity_canonicalizer import resolve_entity
from app.services.fact_type_registry import resolve_fact_type
from app.services.llm_extractor import extract_facts_from_batch
from app.services.pdf_extractor import extract_pages, pages_to_batches
from app.services.quote_validator import validate_batch
from app.services.reconciler import reconcile_pair

logger = logging.getLogger(__name__)

# Concurrency limits — tuned to stay within OpenAI rate limits
_LLM_SEMAPHORE = asyncio.Semaphore(5)   # max 5 concurrent LLM extraction calls
_REC_SEMAPHORE = asyncio.Semaphore(8)   # max 8 concurrent reconciliation LLM calls


def compute_content_hash(pdf_bytes: bytes) -> str:
    """SHA-256 hash of raw PDF bytes — idempotency key."""
    return hashlib.sha256(pdf_bytes).hexdigest()


async def _extract_batch_safe(batch, client, sem: asyncio.Semaphore):
    """Run one batch extraction under the semaphore."""
    async with sem:
        return await extract_facts_from_batch(batch, client)


async def ingest_document(
    doc_id: str,
    pdf_bytes: bytes,
    pool: asyncpg.Pool,
) -> None:
    """
    Full ingestion pipeline for one document.
    Called as a FastAPI BackgroundTask from POST /documents.
    """
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    try:
        # ── 1. Mark as processing ──────────────────────────────────────────
        await crud.update_document_status(pool, doc_id, "processing")
        logger.info(f"[{doc_id}] Ingestion started.")

        # ── 2. Extract pages ───────────────────────────────────────────────
        pages = extract_pages(pdf_bytes)
        page_count = len(pages)
        await crud.update_document_status(
            pool, doc_id, f"extracting: 0/{page_count} pages", page_count=page_count
        )
        logger.info(f"[{doc_id}] Extracted {page_count} pages.")

        # Filter to pages with text
        text_pages = [p for p in pages if p.has_text_layer]
        skipped = page_count - len(text_pages)
        if skipped:
            logger.info(f"[{doc_id}] Skipping {skipped} image-only pages.")

        # ── 3. Build page_text map ─────────────────────────────────────────
        page_texts: dict[int, str] = {p.page_number: p.text for p in pages}

        # ── 4. CONCURRENT LLM extraction ──────────────────────────────────
        batches = pages_to_batches(text_pages, batch_size=8)
        total_batches = len(batches)
        done_batches = 0

        async def _extract_and_track(batch, idx):
            nonlocal done_batches
            result = await _extract_batch_safe(batch, client, _LLM_SEMAPHORE)
            done_batches += 1
            page_range = f"{batch[0].page_number}–{batch[-1].page_number}"
            progress_status = (
                f"extracting: {min(batch[-1].page_number, page_count)}/{page_count} pages"
            )
            await crud.update_document_status(pool, doc_id, progress_status)
            logger.info(f"[{doc_id}] Batch {done_batches}/{total_batches} done (pages {page_range}): {len(result)} facts")
            return result

        batch_results = await asyncio.gather(
            *[_extract_and_track(batch, i) for i, batch in enumerate(batches)],
            return_exceptions=True,
        )

        all_extracted = []
        for br in batch_results:
            if isinstance(br, Exception):
                logger.warning(f"[{doc_id}] A batch failed: {br}")
            else:
                all_extracted.extend(br)

        raw_facts = [f.to_dict() for f in all_extracted]
        logger.info(f"[{doc_id}] LLM returned {len(raw_facts)} raw facts.")

        # ── 5. Quote validation ────────────────────────────────────────────
        await crud.update_document_status(pool, doc_id, "validating quotes")
        validated_facts = validate_batch(raw_facts, page_texts)
        high_conf = sum(1 for f in validated_facts if f.get("evidence_confidence") == "high")
        logger.info(f"[{doc_id}] Quote validation: {high_conf}/{len(validated_facts)} high-confidence.")

        # ── 6. Batch embed ALL facts at once ───────────────────────────────
        await crud.update_document_status(pool, doc_id, "computing embeddings")

        embedding_texts = [
            fact_embedding_text(
                f.get("entity", ""),
                f.get("attribute", "")
            )
            for f in validated_facts
        ]
        try:
            embeddings = await embed_texts(embedding_texts, client)
        except Exception as e:
            logger.warning(f"[{doc_id}] Batch embedding failed: {e} — storing without embeddings.")
            embeddings = [None] * len(validated_facts)

        # ── 7. Batch resolve UNIQUE entities (major speedup) ───────────────
        #
        # Instead of calling embed_one() per fact (N OpenAI calls), collect all
        # unique entity strings, embed them in ONE batch call, then resolve each.
        # For a 50-fact doc with 5 unique entities this goes from 50 → 1 embed call.
        #
        unique_entity_names = list({f.get("entity", "Unknown Entity") for f in validated_facts})
        logger.info(f"[{doc_id}] Resolving {len(unique_entity_names)} unique entities (batch embed).")

        try:
            entity_embeddings_list = await embed_texts(unique_entity_names, client)
            entity_embedding_map: dict[str, list[float]] = dict(
                zip(unique_entity_names, entity_embeddings_list)
            )
        except Exception as e:
            logger.warning(f"[{doc_id}] Entity batch embed failed: {e} — falling back to per-entity embeds.")
            entity_embedding_map = {}

        # Similarly for fact_types
        unique_fact_types = list({f.get("fact_type", "unknown") for f in validated_facts})

        # ── 8. Persist facts ───────────────────────────────────────────────
        await crud.update_document_status(pool, doc_id, "storing facts")

        facts_count = 0
        stored_fact_ids: list[str] = []

        for i, fact_data in enumerate(validated_facts):
            try:
                entity_name = fact_data.get("entity", "Unknown Entity")

                # Use pre-computed embedding for this entity if available
                entity_emb = entity_embedding_map.get(entity_name)
                entity_id = await _resolve_entity_with_embedding(
                    pool, client, entity_name, entity_emb
                )

                fact_type_id = await resolve_fact_type(pool, client, fact_data.get("fact_type", "unknown"))

                fact_id = await crud.create_fact(
                    pool,
                    document_id=doc_id,
                    entity_id=entity_id,
                    fact_type_id=fact_type_id,
                    fact_data=fact_data,
                )

                emb = embeddings[i] if i < len(embeddings) and embeddings[i] is not None else None
                if emb:
                    async with pool.acquire() as conn:
                        await conn.execute(
                            "UPDATE facts SET embedding = $1::vector WHERE id = $2",
                            str(emb),
                            fact_id,
                        )

                stored_fact_ids.append(fact_id)
                facts_count += 1

                # Update status every 10 facts
                if facts_count % 10 == 0:
                    await crud.update_document_status(
                        pool, doc_id,
                        f"storing: {facts_count}/{len(validated_facts)} facts",
                        facts_count=facts_count,
                    )

            except Exception as e:
                logger.warning(
                    f"[{doc_id}] Skipped fact: {e} | "
                    f"entity={fact_data.get('entity')} attribute={fact_data.get('attribute')}"
                )

        logger.info(f"[{doc_id}] Stored {facts_count} facts with embeddings.")

        # ── 9. CONCURRENT reconciliation ──────────────────────────────────
        await crud.update_document_status(pool, doc_id, "reconciling", facts_count=facts_count)

        try:
            rel_count = await _reconcile_concurrent(pool, client, doc_id)
            logger.info(f"[{doc_id}] Reconciliation: {rel_count} relationships stored.")
        except Exception as e:
            logger.error(f"[{doc_id}] Reconciliation phase failed: {e} — facts are still stored.")

        # ── 10. Done ───────────────────────────────────────────────────────
        await crud.update_document_status(pool, doc_id, "done", facts_count=facts_count)
        logger.info(f"[{doc_id}] Ingestion complete.")

    except Exception as e:
        logger.exception(f"[{doc_id}] Ingestion pipeline failed: {e}")
        await crud.update_document_status(pool, doc_id, "failed", error_message=str(e))


async def _resolve_entity_with_embedding(
    pool: asyncpg.Pool,
    client: AsyncOpenAI,
    raw_name: str,
    pre_embedding: Optional[list[float]] = None,
) -> str:
    """
    Resolve entity using a pre-computed embedding vector to avoid redundant API calls.
    Falls back to the standard resolve_entity() path if pre_embedding is None.
    """
    if pre_embedding is None:
        return await resolve_entity(pool, client, raw_name)

    from app.services.entity_canonicalizer import normalize_entity_name, ENTITY_MERGE_THRESHOLD, _CORPORATE_ANAPHORS
    from app.db.crud import add_entity_alias, get_or_create_entity
    from uuid import UUID

    normalized = normalize_entity_name(raw_name)

    # Step 1: exact string match
    async with pool.acquire() as conn:
        if normalized in _CORPORATE_ANAPHORS:
            row = await conn.fetchrow(
                """
                SELECT id, canonical_name FROM entities
                WHERE LOWER(canonical_name) NOT IN (
                    'company', 'the company', 'our company', 'this company',
                    'the group', 'our group', 'the issuer', 'the registrant',
                    'the corporation', 'the entity'
                )
                ORDER BY array_length(aliases, 1) DESC NULLS LAST, created_at ASC
                LIMIT 1
                """
            )
            if row:
                entity_id = str(row["id"])
                await add_entity_alias(pool, entity_id, raw_name)
                return entity_id


        row = await conn.fetchrow(
            """
            SELECT id, canonical_name FROM entities
            WHERE LOWER(canonical_name) = LOWER($2)
               OR LOWER(canonical_name) = $1
               OR LOWER(REGEXP_REPLACE(canonical_name, '\\s+(limited|ltd\\.?|private|pvt\\.?|inc\\.?|llc|llp)\\b', '', 'gi')) = $1
               OR $2 = ANY(aliases)
               OR $1 = ANY(aliases)
            LIMIT 1
            """,
            normalized,
            raw_name,
        )
        if row:
            entity_id = str(row["id"])
            if raw_name.lower() != row["canonical_name"].lower():
                await add_entity_alias(pool, entity_id, raw_name)
            return entity_id

    # Step 2: vector similarity with pre-computed embedding
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, canonical_name,
                       1 - (embedding <=> $1::vector) AS similarity
                FROM entities
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> $1::vector
                LIMIT 5
                """,
                str(pre_embedding),
            )
        for row in rows:
            if row["similarity"] >= ENTITY_MERGE_THRESHOLD:
                entity_id = str(row["id"])
                await add_entity_alias(pool, entity_id, raw_name)
                return entity_id
    except Exception as e:
        logger.warning(f"Entity vector lookup failed for '{raw_name}': {e}")

    # Step 3: create new entity with pre-computed embedding
    entity_id = await get_or_create_entity(pool, raw_name)
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE entities SET embedding = $1::vector WHERE id = $2",
                str(pre_embedding),
                entity_id,
            )
    except Exception as e:
        logger.warning(f"Failed to store embedding for new entity '{raw_name}': {e}")

    return entity_id


async def _reconcile_concurrent(
    pool: asyncpg.Pool,
    client: AsyncOpenAI,
    document_id: str,
    skip_same_document: bool = True,
) -> int:
    """
    Concurrent reconciliation — fetches all (fact_a, candidate) pairs first,
    then fires all reconcile_pair() calls concurrently under a semaphore.
    """
    from app.services.reconciler import generate_candidates
    from app.db import crud

    async with pool.acquire() as conn:
        doc_facts = await conn.fetch(
            """
            SELECT f.*, e.canonical_name AS entity_name, ft.label AS fact_type_label
            FROM facts f
            JOIN entities   e  ON e.id  = f.entity_id
            JOIN fact_types ft ON ft.id = f.fact_type_id
            WHERE f.document_id = $1
              AND f.embedding IS NOT NULL
            """,
            document_id,
        )

    from app.db.crud import _record_to_dict
    doc_fact_dicts = [_record_to_dict(r) for r in doc_facts]

    # Collect all unique pairs to reconcile
    pairs_to_reconcile: list[tuple[dict, dict]] = []

    for fact_a in doc_fact_dicts:
        embedding_a = fact_a.get("embedding")
        if embedding_a is None:
            continue
        if isinstance(embedding_a, str):
            embedding_a = [float(x) for x in embedding_a.strip("[]").split(",")]

        candidates = await generate_candidates(pool, fact_a["id"], fact_a["entity_id"], embedding_a)

        for fact_b in candidates:
            if skip_same_document and fact_b.get("document_id") == document_id:
                continue

            async with pool.acquire() as conn:
                existing = await conn.fetchval(
                    """
                    SELECT id FROM fact_relationships
                    WHERE (fact_a_id = $1 AND fact_b_id = $2)
                       OR (fact_a_id = $2 AND fact_b_id = $1)
                    """,
                    fact_a["id"],
                    fact_b["id"],
                )
            if existing:
                continue

            pairs_to_reconcile.append((fact_a, fact_b))

    logger.info(f"[{document_id}] Reconciling {len(pairs_to_reconcile)} candidate pairs concurrently.")

    async def _do_one_pair(fact_a: dict, fact_b: dict):
        async with _REC_SEMAPHORE:
            result = await reconcile_pair(fact_a, fact_b, client)
            await crud.upsert_fact_relationship(
                pool,
                fact_a_id=fact_a["id"],
                fact_b_id=fact_b["id"],
                relationship=result.relationship.value,
                basis=result.reconciliation_basis.value,
                explanation=result.explanation,
                confidence=result.confidence,
            )
            return 1

    results = await asyncio.gather(
        *[_do_one_pair(a, b) for a, b in pairs_to_reconcile],
        return_exceptions=True,
    )

    successful = sum(1 for r in results if r == 1)
    failed = sum(1 for r in results if isinstance(r, Exception))
    if failed:
        logger.warning(f"[{document_id}] {failed} reconciliation pairs failed.")
    return successful
