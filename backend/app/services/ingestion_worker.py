"""
Document ingestion worker.

Orchestrates the full pipeline for one document:
  PDF bytes → page extraction → LLM extraction → quote validation
  → entity resolution → fact_type registration → DB persistence

Runs as a FastAPI BackgroundTask (no queue needed for Phase 1).
Progress is written back to documents.status so callers can poll.

Error handling: individual fact insertion failures are logged and skipped;
the overall pipeline failure updates status to "failed" with the error.
"""

from __future__ import annotations
import hashlib
import logging
from typing import Optional

import asyncpg
from openai import AsyncOpenAI

from app.config import get_settings
from app.db import crud
from app.services.llm_extractor import extract_all_facts
from app.services.pdf_extractor import extract_pages
from app.services.quote_validator import validate_batch

logger = logging.getLogger(__name__)


async def ingest_document(
    doc_id: str,
    pdf_bytes: bytes,
    pool: asyncpg.Pool,
) -> None:
    """
    Full ingestion pipeline for one document.
    Called as a background task from POST /documents.
    Updates documents.status throughout so the caller can poll.
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

        # ── 3. Build page_text map for quote validation ────────────────────
        page_texts: dict[int, str] = {p.page_number: p.text for p in pages}

        # ── 4. LLM extraction (all pages, batched internally) ───────────────
        all_facts = await extract_all_facts(pages, client, batch_size=8)
        raw_facts = [f.model_dump() for f in all_facts]
        logger.info(f"[{doc_id}] LLM returned {len(raw_facts)} raw facts.")

        # ── 5. Quote validation ────────────────────────────────────────────
        validated_facts = validate_batch(raw_facts, page_texts)
        high_conf = sum(1 for f in validated_facts if f.get("evidence_confidence") == "high")
        logger.info(
            f"[{doc_id}] Quote validation: {high_conf}/{len(validated_facts)} high-confidence."
        )

        # ── 6. Persist facts ───────────────────────────────────────────────
        facts_count = 0
        for fact_data in validated_facts:
            try:
                # Entity resolution (Phase 1: string match; Phase 2: embedding similarity)
                entity_id = await crud.get_or_create_entity(
                    pool, fact_data.get("entity", "Unknown Entity")
                )

                # Fact type registration
                fact_type_id = await crud.get_or_create_fact_type(
                    pool, fact_data.get("fact_type", "unknown")
                )

                # Insert fact
                await crud.create_fact(
                    pool,
                    document_id=doc_id,
                    entity_id=entity_id,
                    fact_type_id=fact_type_id,
                    fact_data=fact_data,
                )
                facts_count += 1

            except Exception as e:
                logger.warning(
                    f"[{doc_id}] Skipped fact (insert error): {e} | "
                    f"entity={fact_data.get('entity')} attribute={fact_data.get('attribute')}"
                )
                continue

        # ── 7. Mark done ───────────────────────────────────────────────────
        await crud.update_document_status(
            pool, doc_id, "done", facts_count=facts_count
        )
        logger.info(f"[{doc_id}] Ingestion complete. {facts_count} facts stored.")

    except Exception as e:
        logger.exception(f"[{doc_id}] Ingestion pipeline failed: {e}")
        await crud.update_document_status(
            pool, doc_id, "failed", error_message=str(e)
        )


def compute_content_hash(pdf_bytes: bytes) -> str:
    """SHA-256 hash of raw PDF bytes — used as the idempotency key."""
    return hashlib.sha256(pdf_bytes).hexdigest()
