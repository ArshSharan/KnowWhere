"""
Typed CRUD helpers for all database operations.

All functions take an asyncpg.Pool (or Connection) as first argument.
Row dicts are returned as plain Python dicts — no ORM layer, just typed helpers.

Phase 1 coverage: documents, entities (simple string match), fact_types, facts.
Phase 2 will extend: entity embedding lookup, fact_types embedding lookup, reconciliation.
"""

from __future__ import annotations
import hashlib
import json
import logging
from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

import asyncpg

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _record_to_dict(record: asyncpg.Record) -> dict:
    """Convert an asyncpg Record to a plain dict with string UUIDs."""
    d = dict(record)
    for k, v in d.items():
        if isinstance(v, UUID):
            d[k] = str(v)
    return d


def _parse_date(value: Optional[str]) -> Optional[date]:
    """Parse an ISO date string from the LLM into a Python date. Returns None on failure."""
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

async def create_document(
    pool: asyncpg.Pool,
    *,
    title: Optional[str],
    content_hash: str,
    source_uri: str = "",
) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO documents (title, content_hash, source_uri, status)
            VALUES ($1, $2, $3, 'pending')
            RETURNING *
            """,
            title, content_hash, source_uri,
        )
    return _record_to_dict(row)


async def get_document(pool: asyncpg.Pool, doc_id: str) -> Optional[dict]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM documents WHERE id = $1",
            UUID(doc_id),
        )
    return _record_to_dict(row) if row else None


async def get_document_by_hash(pool: asyncpg.Pool, content_hash: str) -> Optional[dict]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM documents WHERE content_hash = $1",
            content_hash,
        )
    return _record_to_dict(row) if row else None


async def update_document_status(
    pool: asyncpg.Pool,
    doc_id: str,
    status: str,
    *,
    page_count: Optional[int] = None,
    facts_count: Optional[int] = None,
    error_message: Optional[str] = None,
    doc_type: Optional[str] = None,
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE documents
            SET status        = $2,
                page_count    = COALESCE($3, page_count),
                facts_count   = COALESCE($4, facts_count),
                error_message = COALESCE($5, error_message),
                doc_type      = COALESCE($6, doc_type),
                updated_at    = NOW()
            WHERE id = $1
            """,
            UUID(doc_id), status, page_count, facts_count, error_message, doc_type,
        )


async def list_documents(pool: asyncpg.Pool) -> list[dict]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM documents ORDER BY created_at DESC"
        )
    return [_record_to_dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Entities — Phase 1: simple case-insensitive string match
# Phase 2 will add embedding-based similarity lookup
# ---------------------------------------------------------------------------

async def get_or_create_entity(pool: asyncpg.Pool, canonical_name: str) -> str:
    """
    Look up an entity by canonical_name (case-insensitive).
    Creates a new entity if none found. Returns entity_id as str.
    Phase 1: string match only. Phase 2 adds embedding similarity.
    """
    normalized = canonical_name.strip()
    async with pool.acquire() as conn:
        # Try exact match first (case-insensitive)
        row = await conn.fetchrow(
            "SELECT id FROM entities WHERE LOWER(canonical_name) = LOWER($1)",
            normalized,
        )
        if row:
            return str(row["id"])

        # Create new entity
        row = await conn.fetchrow(
            "INSERT INTO entities (canonical_name) VALUES ($1) RETURNING id",
            normalized,
        )
        logger.info(f"New entity created: '{normalized}'")
        return str(row["id"])


async def add_entity_alias(pool: asyncpg.Pool, entity_id: str, alias: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE entities
            SET aliases = array_append(aliases, $2)
            WHERE id = $1 AND NOT ($2 = ANY(aliases))
            """,
            UUID(entity_id), alias,
        )


# ---------------------------------------------------------------------------
# Fact types — Phase 1: simple string match
# Phase 2 will add embedding-based registry with auto-registration
# ---------------------------------------------------------------------------

async def get_or_create_fact_type(pool: asyncpg.Pool, label: str) -> str:
    """
    Look up a fact_type by label (case-insensitive).
    Creates a new type if none found. Returns fact_type_id as str.
    """
    normalized = label.strip().lower()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM fact_types WHERE LOWER(label) = $1",
            normalized,
        )
        if row:
            return str(row["id"])

        row = await conn.fetchrow(
            "INSERT INTO fact_types (label) VALUES ($1) RETURNING id",
            normalized,
        )
        logger.info(f"New fact_type registered: '{normalized}'")
        return str(row["id"])


# ---------------------------------------------------------------------------
# Facts
# ---------------------------------------------------------------------------

async def create_fact(
    pool: asyncpg.Pool,
    *,
    document_id: str,
    entity_id: str,
    fact_type_id: str,
    fact_data: dict,
) -> str:
    """Insert a fact row and return its UUID as str."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO facts (
                document_id, entity_id, fact_type_id,
                attribute, value, value_type, unit,
                period_start, period_end, as_of_date, fiscal_year,
                qualifiers, verbatim_quote, page_number,
                evidence_confidence, confidence
            ) VALUES (
                $1, $2, $3,
                $4, $5, $6, $7,
                $8, $9, $10, $11,
                $12::jsonb, $13, $14,
                $15, $16
            )
            RETURNING id
            """,
            UUID(document_id), UUID(entity_id), UUID(fact_type_id),
            fact_data.get("attribute", ""),
            str(fact_data.get("value", "")),
            fact_data.get("value_type", "string"),
            fact_data.get("unit"),
            _parse_date(fact_data.get("period_start")),
            _parse_date(fact_data.get("period_end")),
            _parse_date(fact_data.get("as_of_date")),
            fact_data.get("fiscal_year"),
            json.dumps(fact_data.get("qualifiers") or {}),
            fact_data.get("verbatim_quote", ""),
            fact_data.get("page_number", 0),
            fact_data.get("evidence_confidence", "high"),
            float(fact_data.get("confidence", 1.0)),
        )
    return str(row["id"])


async def get_facts_by_document(pool: asyncpg.Pool, document_id: str) -> list[dict]:
    """Return all facts for a document, joined with entity and fact_type labels."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                f.*,
                e.canonical_name  AS entity_name,
                ft.label          AS fact_type_label
            FROM facts f
            JOIN entities   e  ON e.id  = f.entity_id
            JOIN fact_types ft ON ft.id = f.fact_type_id
            WHERE f.document_id = $1
            ORDER BY f.page_number, f.created_at
            """,
            UUID(document_id),
        )
    return [_record_to_dict(r) for r in rows]


async def get_fact(pool: asyncpg.Pool, fact_id: str) -> Optional[dict]:
    """Return one fact with entity and fact_type labels."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                f.*,
                e.canonical_name  AS entity_name,
                ft.label          AS fact_type_label
            FROM facts f
            JOIN entities   e  ON e.id  = f.entity_id
            JOIN fact_types ft ON ft.id = f.fact_type_id
            WHERE f.id = $1
            """,
            UUID(fact_id),
        )
    return _record_to_dict(row) if row else None


async def get_fact_relationships(pool: asyncpg.Pool, fact_id: str) -> list[dict]:
    """Return all relationship edges for a fact (in either direction)."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT fr.*,
                   fa.attribute AS fact_a_attribute,
                   ea.canonical_name AS fact_a_entity,
                   fb.attribute AS fact_b_attribute,
                   eb.canonical_name AS fact_b_entity
            FROM fact_relationships fr
            JOIN facts fa ON fa.id = fr.fact_a_id
            JOIN facts fb ON fb.id = fr.fact_b_id
            JOIN entities ea ON ea.id = fa.entity_id
            JOIN entities eb ON eb.id = fb.entity_id
            WHERE fr.fact_a_id = $1 OR fr.fact_b_id = $1
            ORDER BY fr.confidence DESC
            """,
            UUID(fact_id),
        )
    return [_record_to_dict(r) for r in rows]


async def upsert_fact_relationship(
    pool: asyncpg.Pool,
    *,
    fact_a_id: str,
    fact_b_id: str,
    relationship: str,
    basis: str,
    explanation: str,
    confidence: float,
) -> str:
    """Insert or update a fact relationship. Returns relationship_id."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO fact_relationships
                (fact_a_id, fact_b_id, relationship, basis, explanation, confidence)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (fact_a_id, fact_b_id)
            DO UPDATE SET
                relationship = EXCLUDED.relationship,
                basis        = EXCLUDED.basis,
                explanation  = EXCLUDED.explanation,
                confidence   = EXCLUDED.confidence
            RETURNING id
            """,
            UUID(fact_a_id), UUID(fact_b_id), relationship, basis, explanation, confidence,
        )
    return str(row["id"])


async def list_all_relationships(
    pool: asyncpg.Pool,
    relationship: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
    include_unrelated: bool = False,
) -> list[dict]:
    """
    Return meaningful relationship edges across all documents, joined with full metadata
    for both Fact A and Fact B, plus source documents.

    By default, excludes 'unrelated' pairs — they are a reconciliation detail
    (necessary to cache negative results) but are not useful in the UI feed.
    Pass include_unrelated=True or relationship='unrelated' to include them.
    """
    query = """
        SELECT 
            fr.*,
            fa.attribute AS fact_a_attribute,
            fa.value AS fact_a_value,
            fa.unit AS fact_a_unit,
            fa.fiscal_year AS fact_a_fiscal_year,
            fa.page_number AS fact_a_page,
            fa.verbatim_quote AS fact_a_quote,
            ea.canonical_name AS fact_a_entity,
            da.title AS fact_a_doc_title,
            da.id::text AS fact_a_doc_id,
            fb.attribute AS fact_b_attribute,
            fb.value AS fact_b_value,
            fb.unit AS fact_b_unit,
            fb.fiscal_year AS fact_b_fiscal_year,
            fb.page_number AS fact_b_page,
            fb.verbatim_quote AS fact_b_quote,
            eb.canonical_name AS fact_b_entity,
            db.title AS fact_b_doc_title,
            db.id::text AS fact_b_doc_id
        FROM fact_relationships fr
        JOIN facts fa ON fa.id = fr.fact_a_id
        JOIN facts fb ON fb.id = fr.fact_b_id
        JOIN entities ea ON ea.id = fa.entity_id
        JOIN entities eb ON eb.id = fb.entity_id
        JOIN documents da ON da.id = fa.document_id
        JOIN documents db ON db.id = fb.document_id
    """
    args: list[Any] = []
    where_clauses = []

    if relationship:
        where_clauses.append(f"fr.relationship = ${len(args)+1}")
        args.append(relationship)
    elif not include_unrelated:
        # Default: hide unrelated pairs — they are accurate but not useful in the feed
        where_clauses.append("fr.relationship != 'unrelated'")

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    query += f" ORDER BY fr.confidence DESC, fr.created_at DESC LIMIT ${len(args)+1} OFFSET ${len(args)+2}"
    args.extend([limit, offset])

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *args)
    return [_record_to_dict(r) for r in rows]


async def search_facts(
    pool: asyncpg.Pool,
    query_embedding: Optional[list[float]] = None,
    query_text: Optional[str] = None,
    limit: int = 30,
) -> list[dict]:
    """
    Semantic search over facts using vector similarity (<=> cosine distance).
    Falls back to ILIKE text search if embedding is not provided.
    """
    async with pool.acquire() as conn:
        if query_embedding:
            rows = await conn.fetch(
                """
                SELECT 
                    f.*,
                    e.canonical_name AS entity_name,
                    ft.label AS fact_type_label,
                    d.title AS document_title,
                    1 - (f.embedding <=> $1::vector) AS similarity
                FROM facts f
                JOIN entities e ON e.id = f.entity_id
                JOIN fact_types ft ON ft.id = f.fact_type_id
                JOIN documents d ON d.id = f.document_id
                WHERE f.embedding IS NOT NULL
                ORDER BY f.embedding <=> $1::vector ASC
                LIMIT $2
                """,
                str(query_embedding),
                limit,
            )
            return [_record_to_dict(r) for r in rows]

        pattern = f"%{query_text or ''}%"
        rows = await conn.fetch(
            """
            SELECT 
                f.*,
                e.canonical_name AS entity_name,
                ft.label AS fact_type_label,
                d.title AS document_title,
                1.0 AS similarity
            FROM facts f
            JOIN entities e ON e.id = f.entity_id
            JOIN fact_types ft ON ft.id = f.fact_type_id
            JOIN documents d ON d.id = f.document_id
            WHERE f.attribute ILIKE $1 
               OR f.value ILIKE $1 
               OR f.verbatim_quote ILIKE $1
               OR e.canonical_name ILIKE $1
            ORDER BY f.created_at DESC
            LIMIT $2
            """,
            pattern,
            limit,
        )
        return [_record_to_dict(r) for r in rows]

