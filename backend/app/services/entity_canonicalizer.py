"""
Entity canonicalization service.

Merges surface-form entity strings (e.g. "Delhivery Limited", "Delhivery",
"the Company") into a single canonical entity record in the DB.

Phase 1 used a simple case-insensitive string match (still the fallback).
Phase 2 adds an embedding-similarity pass so near-synonymous names
(e.g. "Delhivery Ltd." vs "Delhivery Limited") are merged automatically.

Merge logic (two passes, cheapest first):
  1. Deterministic normalization: strip legal suffixes (Limited, Ltd., Inc., Corp., Co.),
     collapse whitespace, lowercase — and try exact DB match.
  2. Embedding similarity: embed the normalized name, query the entities vector index,
     and merge if cosine similarity > ENTITY_MERGE_THRESHOLD.
  3. If no match: register as a new canonical entity.
"""

from __future__ import annotations
import logging
import re
from typing import Optional

import asyncpg
from openai import AsyncOpenAI

from app.db import crud
from app.services.embedder import embed_one

logger = logging.getLogger(__name__)

# Cosine similarity threshold for entity merging (0.92 is deliberately tight —
# we'd rather create a duplicate entity than silently merge unrelated ones).
ENTITY_MERGE_THRESHOLD = 0.92

# Legal suffixes to strip for normalization
_LEGAL_SUFFIXES = re.compile(
    r"\b(limited|ltd\.?|incorporated|inc\.?|corporation|corp\.?|"
    r"private|pvt\.?|llp|llc|plc)\b\.?",
    re.IGNORECASE,
)

_WHITESPACE = re.compile(r"\s+")
_TRAILING_PUNCT = re.compile(r"[\s.\-,]+$")


def normalize_entity_name(name: str) -> str:
    """
    Deterministic normalization: strip legal suffixes, collapse whitespace, lowercase.
    e.g. "Delhivery Limited" -> "delhivery"
         "Delhivery Ltd."    -> "delhivery"
         "  Delhivery  "     -> "delhivery"
    """
    name = _LEGAL_SUFFIXES.sub("", name)
    name = _WHITESPACE.sub(" ", name).strip()
    name = _TRAILING_PUNCT.sub("", name)
    return name.lower()


async def resolve_entity(
    pool: asyncpg.Pool,
    client: AsyncOpenAI,
    raw_name: str,
) -> str:
    """
    Resolve a raw entity name string to a canonical entity_id.

    Steps:
      1. Normalize raw_name.
      2. Try exact DB match on canonical_name or aliases.
      3. Embed + pgvector cosine search for near-duplicate detection.
      4. Create new entity if no match found.

    Returns entity_id as str.
    """
    raw_name = raw_name.strip()
    normalized = normalize_entity_name(raw_name)

    # ── Step 1: Exact match (canonical_name, case-insensitive) ────────────
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, canonical_name FROM entities
            WHERE LOWER(canonical_name) = $1
               OR $2 = ANY(aliases)
            LIMIT 1
            """,
            normalized,
            raw_name,  # also check against stored alias surface forms
        )
        if row:
            # Store the surface form as an alias if it's new
            entity_id = str(row["id"])
            if raw_name.lower() != row["canonical_name"].lower():
                await crud.add_entity_alias(pool, entity_id, raw_name)
            return entity_id

    # ── Step 2: Embedding similarity search ───────────────────────────────
    try:
        query_vec = await embed_one(normalized, client)
        async with pool.acquire() as conn:
            # Requires pgvector HNSW index (enabled once embeddings are populated)
            rows = await conn.fetch(
                """
                SELECT id, canonical_name,
                       1 - (embedding <=> $1::vector) AS similarity
                FROM entities
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> $1::vector
                LIMIT 5
                """,
                str(query_vec),  # pgvector accepts text representation of float[]
            )

        for row in rows:
            if row["similarity"] >= ENTITY_MERGE_THRESHOLD:
                entity_id = str(row["id"])
                logger.info(
                    f"Entity merge: '{raw_name}' → '{row['canonical_name']}' "
                    f"(similarity={row['similarity']:.3f})"
                )
                await crud.add_entity_alias(pool, entity_id, raw_name)
                return entity_id

    except Exception as e:
        logger.warning(f"Entity embedding lookup failed for '{raw_name}': {e} — falling back to string match.")

    # ── Step 3: Create new canonical entity ───────────────────────────────
    entity_id = await crud.get_or_create_entity(pool, raw_name)

    # Embed and store the new entity's embedding for future lookups
    try:
        embedding = await embed_one(normalized, client)
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE entities SET embedding = $1::vector WHERE id = $2",
                str(embedding),
                entity_id,
            )
    except Exception as e:
        logger.warning(f"Failed to embed new entity '{raw_name}': {e}")

    return entity_id
