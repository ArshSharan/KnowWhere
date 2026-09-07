"""
Document ingestion worker — Phase 2 upgrade.

Full pipeline:
  PDF bytes → page extraction → LLM extraction → quote validation
  → entity canonicalization (embedding-aware) → fact-type registry
  → fact embedding → DB persistence → reconciliation

Replaces the Phase 1 version. The key additions are:
  - Uses entity_canonicalizer.resolve_entity() (embedding similarity)
  - Uses fact_type_registry.resolve_fact_type() (embedding similarity)
  - Embeds each fact after insertion (for candidate generation)
  - Calls reconcile_document_facts() after all facts are stored
"""

from __future__ import annotations
import hashlib
import logging
from typing import Optional

import asyncpg
from openai import AsyncOpenAI

from app.config import get_settings
from app.db import crud
from app.services.embedder import embed_texts, fact_embedding_text
from app.services.entity_canonicalizer import resolve_entity
from app.services.fact_type_registry import resolve_fact_type
from app.services.llm_extractor import extract_all_facts
from app.services.pdf_extractor import extract_pages
from app.services.quote_validator import validate_batch
from app.services.reconciler import reconcile_document_facts

logger = logging.getLogger(__name__)


def compute_content_hash(pdf_bytes: bytes) -> str:
    """SHA-256 hash of raw PDF bytes — idempotency key."""
    return hashlib.sha256(pdf_bytes).hexdigest()


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
            pool, doc_id, f"extracting: 0/{page_count}", page_count=page_count
        )
        logger.info(f"[{doc_id}] Extracted {page_count} pages.")

        # ── 3. Build page_text map ─────────────────────────────────────────
        page_texts: dict[int, str] = {p.page_number: p.text for p in pages}

        # ── 4. LLM extraction ─────────────────────────────────────────────
        all_extracted = await extract_all_facts(pages, client, batch_size=8)
        raw_facts = [f.to_dict() for f in all_extracted]
        logger.info(f"[{doc_id}] LLM returned {len(raw_facts)} raw facts.")

        # ── 5. Quote validation ────────────────────────────────────────────
        validated_facts = validate_batch(raw_facts, page_texts)
        high_conf = sum(1 for f in validated_facts if f.get("evidence_confidence") == "high")
        logger.info(f"[{doc_id}] Quote validation: {high_conf}/{len(validated_facts)} high-confidence.")

        # ── 6. Persist facts + embed ───────────────────────────────────────
        await crud.update_document_status(pool, doc_id, "storing_facts")

        # Prepare embedding texts for all facts (batched API call)
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
            logger.warning(f"[{doc_id}] Batch embedding failed: {e} — facts stored without embeddings.")
            embeddings = [None] * len(validated_facts)

        facts_count = 0
        stored_fact_ids: list[str] = []

        for i, fact_data in enumerate(validated_facts):
            try:
                # Entity resolution (embedding-aware in Phase 2)
                entity_id = await resolve_entity(pool, client, fact_data.get("entity", "Unknown Entity"))

                # Fact-type resolution (dynamic registry)
                fact_type_id = await resolve_fact_type(pool, client, fact_data.get("fact_type", "unknown"))

                # Insert fact
                fact_id = await crud.create_fact(
                    pool,
                    document_id=doc_id,
                    entity_id=entity_id,
                    fact_type_id=fact_type_id,
                    fact_data=fact_data,
                )

                # Store embedding on the fact row
                emb = embeddings[i] if embeddings[i] is not None else None
                if emb:
                    async with pool.acquire() as conn:
                        await conn.execute(
                            "UPDATE facts SET embedding = $1::vector WHERE id = $2",
                            str(emb),
                            fact_id,
                        )

                stored_fact_ids.append(fact_id)
                facts_count += 1

            except Exception as e:
                logger.warning(
                    f"[{doc_id}] Skipped fact: {e} | "
                    f"entity={fact_data.get('entity')} attribute={fact_data.get('attribute')}"
                )

        logger.info(f"[{doc_id}] Stored {facts_count} facts with embeddings.")

        # ── 7. Reconciliation ──────────────────────────────────────────────
        await crud.update_document_status(pool, doc_id, "reconciling", facts_count=facts_count)

        try:
            rel_count = await reconcile_document_facts(
                pool, client, doc_id,
                skip_same_document=True,  # cross-document only
            )
            logger.info(f"[{doc_id}] Reconciliation: {rel_count} relationships stored.")
        except Exception as e:
            logger.error(f"[{doc_id}] Reconciliation phase failed: {e} — facts are still stored.")

        # ── 8. Mark done ───────────────────────────────────────────────────
        await crud.update_document_status(pool, doc_id, "done", facts_count=facts_count)
        logger.info(f"[{doc_id}] Ingestion complete.")

    except Exception as e:
        logger.exception(f"[{doc_id}] Ingestion pipeline failed: {e}")
        await crud.update_document_status(pool, doc_id, "failed", error_message=str(e))
