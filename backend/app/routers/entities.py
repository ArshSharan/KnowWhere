"""
Entity and reconciliation API endpoints.

GET  /entities                — list all canonical entities
GET  /entities/{id}           — entity + all facts across all documents
GET  /entities/{id}/aliases   — surface forms merged into this entity

POST /documents/{id}/reconcile — manually trigger reconciliation for a document
                                 (useful after uploading multiple docs)
"""

from __future__ import annotations
import logging
from typing import Any, Optional

import asyncpg
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from app.db.connection import get_pool
from app.db import crud
from app.models.api import EvidenceOut, FactOut, RelationshipOut
from app.routers.documents import _row_to_fact_out

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class AliasOut(BaseModel):
    entity_id: str
    canonical_name: str
    aliases: list[str]


class EntityOut(BaseModel):
    id: str
    canonical_name: str
    aliases: list[str]
    facts: list[FactOut]


class ReconcileResponse(BaseModel):
    doc_id: str
    status: str
    message: str


# ---------------------------------------------------------------------------
# Entity endpoints
# ---------------------------------------------------------------------------

@router.get("/entities", tags=["Entities"])
async def list_entities(pool: asyncpg.Pool = Depends(get_pool)):
    """List all canonical entities with alias counts."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT e.id, e.canonical_name, e.aliases,
                   COUNT(f.id) AS fact_count
            FROM entities e
            LEFT JOIN facts f ON f.entity_id = e.id
            GROUP BY e.id, e.canonical_name, e.aliases
            ORDER BY fact_count DESC
            """
        )
    return [
        {
            "id": str(r["id"]),
            "canonical_name": r["canonical_name"],
            "alias_count": len(r["aliases"] or []),
            "fact_count": r["fact_count"],
        }
        for r in rows
    ]


@router.get("/entities/{entity_id}", response_model=EntityOut, tags=["Entities"])
async def get_entity(entity_id: str, pool: asyncpg.Pool = Depends(get_pool)):
    """
    Get a canonical entity with all facts referencing it across all documents.
    This is where cross-document fact comparison is most visible.
    """
    async with pool.acquire() as conn:
        entity_row = await conn.fetchrow(
            "SELECT * FROM entities WHERE id = $1",
            entity_id,
        )
    if not entity_row:
        raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found.")

    async with pool.acquire() as conn:
        fact_rows = await conn.fetch(
            """
            SELECT f.*, e.canonical_name AS entity_name, ft.label AS fact_type_label
            FROM facts f
            JOIN entities   e  ON e.id  = f.entity_id
            JOIN fact_types ft ON ft.id = f.fact_type_id
            WHERE f.entity_id = $1
            ORDER BY f.page_number
            """,
            entity_id,
        )

    from app.db.crud import _record_to_dict
    facts = [_row_to_fact_out(_record_to_dict(r)) for r in fact_rows]

    return EntityOut(
        id=str(entity_row["id"]),
        canonical_name=entity_row["canonical_name"],
        aliases=list(entity_row["aliases"] or []),
        facts=facts,
    )


@router.get("/entities/{entity_id}/aliases", response_model=AliasOut, tags=["Entities"])
async def get_entity_aliases(entity_id: str, pool: asyncpg.Pool = Depends(get_pool)):
    """
    Show how entity resolution merged different surface forms into this canonical entity.
    Useful for demonstrating the entity canonicalization logic.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, canonical_name, aliases FROM entities WHERE id = $1",
            entity_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found.")
    return AliasOut(
        entity_id=str(row["id"]),
        canonical_name=row["canonical_name"],
        aliases=list(row["aliases"] or []),
    )


# ---------------------------------------------------------------------------
# Reconciliation trigger
# ---------------------------------------------------------------------------

@router.post("/documents/{doc_id}/reconcile", response_model=ReconcileResponse, tags=["Documents"])
async def trigger_reconciliation(
    doc_id: str,
    background_tasks: BackgroundTasks,
    pool: asyncpg.Pool = Depends(get_pool),
):
    """
    Manually trigger cross-document reconciliation for a document.

    Useful when:
    - A second document is uploaded after the first (to reconcile new-vs-existing facts)
    - You want to re-run reconciliation with updated logic

    Returns immediately; runs in the background. Poll /documents/{id} for status.
    """
    doc = await crud.get_document(pool, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found.")

    if doc["status"] not in ("done", "failed"):
        raise HTTPException(
            status_code=400,
            detail=f"Document must be fully ingested before reconciliation. Current status: {doc['status']}"
        )

    async def _run_reconciliation():
        from openai import AsyncOpenAI
        from app.config import get_settings
        from app.services.reconciler import reconcile_document_facts

        settings = get_settings()
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        await crud.update_document_status(pool, doc_id, "reconciling")
        try:
            rel_count = await reconcile_document_facts(pool, client, doc_id)
            await crud.update_document_status(pool, doc_id, "done")
            logger.info(f"[{doc_id}] Manual reconciliation: {rel_count} relationships.")
        except Exception as e:
            logger.error(f"[{doc_id}] Manual reconciliation failed: {e}")
            await crud.update_document_status(pool, doc_id, "done", error_message=str(e))

    background_tasks.add_task(_run_reconciliation)

    return ReconcileResponse(
        doc_id=doc_id,
        status="reconciling",
        message="Reconciliation started in background. Poll /documents/{id} for status.",
    )
