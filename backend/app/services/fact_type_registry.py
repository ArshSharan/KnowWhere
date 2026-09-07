"""
Fact-type registry service.

Implements the "schema evolution as data" brownie point (TRD §2.3):
  - fact_type labels are proposed by the extraction LLM (free-form strings)
  - each new label is embedded and compared against existing registered types
  - if similarity > threshold → reuse existing type (deduplication)
  - if no match → register as a new type (schema grows from data, not code)

This means a new PDF that introduces a "board_resolution" or "regulatory_filing"
fact type will automatically register it — no code changes, no migrations.
"""

from __future__ import annotations
import logging

import asyncpg
from openai import AsyncOpenAI

from app.db import crud
from app.services.embedder import embed_one

logger = logging.getLogger(__name__)

# Similarity threshold for fact-type deduplication.
# Lower than entity threshold (0.85) because fact-type labels are short and
# two different labels can be legitimately similar without being the same.
FACT_TYPE_MERGE_THRESHOLD = 0.88


async def resolve_fact_type(
    pool: asyncpg.Pool,
    client: AsyncOpenAI,
    proposed_label: str,
) -> str:
    """
    Resolve a proposed fact_type label to an existing or new fact_type_id.

    1. Normalize label (lowercase, strip whitespace).
    2. Exact DB match.
    3. Embedding similarity search against registered types.
    4. Register new type if no match.

    Returns fact_type_id as str.
    """
    normalized = proposed_label.strip().lower().replace(" ", "_")

    # ── Step 1: Exact match ───────────────────────────────────────────────
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM fact_types WHERE LOWER(label) = $1",
            normalized,
        )
        if row:
            return str(row["id"])

    # ── Step 2: Embedding similarity ──────────────────────────────────────
    try:
        query_vec = await embed_one(normalized, client)
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, label,
                       1 - (embedding <=> $1::vector) AS similarity
                FROM fact_types
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> $1::vector
                LIMIT 5
                """,
                str(query_vec),
            )

        for row in rows:
            if row["similarity"] >= FACT_TYPE_MERGE_THRESHOLD:
                logger.info(
                    f"Fact-type merge: '{proposed_label}' → '{row['label']}' "
                    f"(similarity={row['similarity']:.3f})"
                )
                return str(row["id"])

    except Exception as e:
        logger.warning(f"Fact-type embedding lookup failed for '{proposed_label}': {e} — falling back to exact match.")

    # ── Step 3: Register new type ─────────────────────────────────────────
    fact_type_id = await crud.get_or_create_fact_type(pool, normalized)
    logger.info(f"New fact_type registered: '{normalized}'")

    # Embed and store for future lookups
    try:
        embedding = await embed_one(normalized, client)
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE fact_types SET embedding = $1::vector WHERE id = $2",
                str(embedding),
                fact_type_id,
            )
    except Exception as e:
        logger.warning(f"Failed to embed fact_type '{normalized}': {e}")

    return fact_type_id
