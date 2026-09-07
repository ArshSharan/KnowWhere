"""
Document and fact API endpoints.

POST /documents          — upload PDF, start background ingestion
GET  /documents          — list all documents
GET  /documents/{id}     — document status + metadata
GET  /documents/{id}/facts — all extracted facts with evidence
GET  /facts/{id}         — one fact in full
GET  /facts/{id}/relationships — relationship edges for one fact
"""

from __future__ import annotations
import logging
from typing import Any, Optional

import asyncpg
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File

from app.db.connection import get_pool
from app.db import crud
from app.models.api import (
    DocumentOut,
    DocumentWithFactsOut,
    EvidenceOut,
    FactOut,
    RelationshipOut,
    UploadResponse,
)
from app.services.ingestion_worker import compute_content_hash, ingest_document

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Helper: DB row → API model
# ---------------------------------------------------------------------------

def _row_to_fact_out(row: dict) -> FactOut:
    """Convert a facts DB row (with joined entity_name / fact_type_label) to FactOut."""
    return FactOut(
        id=row["id"],
        entity=row.get("entity_name") or row.get("entity", ""),
        attribute=row["attribute"],
        value=row["value"],
        value_type=row["value_type"],
        unit=row.get("unit"),
        fact_type=row.get("fact_type_label") or row.get("fact_type", ""),
        confidence=row.get("confidence", 1.0),
        fiscal_year=row.get("fiscal_year"),
        period_start=str(row["period_start"]) if row.get("period_start") else None,
        period_end=str(row["period_end"]) if row.get("period_end") else None,
        as_of_date=str(row["as_of_date"]) if row.get("as_of_date") else None,
        qualifiers=row.get("qualifiers") or {},
        evidence=EvidenceOut(
            verbatim_quote=row.get("verbatim_quote", ""),
            page_number=row.get("page_number", 0),
            evidence_confidence=row.get("evidence_confidence", "high"),
        ),
    )


def _row_to_doc_out(row: dict) -> DocumentOut:
    return DocumentOut(
        id=row["id"],
        title=row.get("title"),
        doc_type=row.get("doc_type"),
        status=row.get("status", "pending"),
        page_count=row.get("page_count"),
        facts_count=row.get("facts_count") or 0,
        created_at=str(row.get("created_at", "")),
        updated_at=str(row.get("updated_at", "")),
    )


# ---------------------------------------------------------------------------
# Document endpoints
# ---------------------------------------------------------------------------

@router.post("/documents", response_model=UploadResponse, status_code=202, tags=["Documents"])
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF file to ingest"),
    pool: asyncpg.Pool = Depends(get_pool),
):
    """
    Upload a PDF and start asynchronous fact extraction.

    Returns immediately with a `doc_id` and `status: "processing"`.
    Poll `GET /documents/{doc_id}` until status is `"done"` or `"failed"`.

    Re-uploading the same file (same bytes) is a no-op — returns the existing
    document with `duplicate: true`.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    pdf_bytes = await file.read()
    if len(pdf_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    content_hash = compute_content_hash(pdf_bytes)

    # Idempotency check
    existing = await crud.get_document_by_hash(pool, content_hash)
    if existing:
        logger.info(f"Duplicate upload detected for hash {content_hash[:12]}… returning existing doc.")
        return UploadResponse(
            doc_id=existing["id"],
            status=existing["status"],
            duplicate=True,
        )

    # Create document record
    doc = await crud.create_document(
        pool,
        title=file.filename,
        content_hash=content_hash,
    )
    doc_id = doc["id"]

    # Start background ingestion (non-blocking)
    background_tasks.add_task(ingest_document, doc_id, pdf_bytes, pool)
    logger.info(f"Document {doc_id} queued for ingestion (file={file.filename}).")

    return UploadResponse(doc_id=doc_id, status="processing")


@router.get("/documents", response_model=list[DocumentOut], tags=["Documents"])
async def list_documents(pool: asyncpg.Pool = Depends(get_pool)):
    """List all ingested documents with their current status."""
    rows = await crud.list_documents(pool)
    return [_row_to_doc_out(r) for r in rows]


@router.get("/documents/{doc_id}", response_model=DocumentOut, tags=["Documents"])
async def get_document(doc_id: str, pool: asyncpg.Pool = Depends(get_pool)):
    """
    Get document status and metadata.
    Poll this endpoint until `status` is `"done"` or `"failed"`.
    The `status` field may contain progress strings like `"extracting: 12/48"`.
    """
    doc = await crud.get_document(pool, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found.")
    return _row_to_doc_out(doc)


@router.get("/documents/{doc_id}/facts", response_model=DocumentWithFactsOut, tags=["Documents"])
async def get_document_facts(doc_id: str, pool: asyncpg.Pool = Depends(get_pool)):
    """
    Get all extracted facts for a document, each with its evidence quote and page number.
    The document must have `status: "done"` for facts to be present.
    """
    doc = await crud.get_document(pool, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found.")

    fact_rows = await crud.get_facts_by_document(pool, doc_id)
    facts = [_row_to_fact_out(r) for r in fact_rows]

    return DocumentWithFactsOut(
        **_row_to_doc_out(doc).model_dump(),
        facts=facts,
    )


# ---------------------------------------------------------------------------
# Fact endpoints
# ---------------------------------------------------------------------------

@router.get("/facts/{fact_id}", response_model=FactOut, tags=["Facts"])
async def get_fact(fact_id: str, pool: asyncpg.Pool = Depends(get_pool)):
    """Get a single fact with full evidence."""
    row = await crud.get_fact(pool, fact_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Fact {fact_id} not found.")
    return _row_to_fact_out(row)


@router.get("/facts/{fact_id}/relationships", response_model=list[RelationshipOut], tags=["Facts"])
async def get_fact_relationships(fact_id: str, pool: asyncpg.Pool = Depends(get_pool)):
    """
    Get all corroborate/contradict/reconcile edges for a fact.
    This is the key endpoint for the demo — it shows the reasoning behind each relationship.
    Populated after Phase 2 (reconciliation) runs.
    """
    rows = await crud.get_fact_relationships(pool, fact_id)
    return [
        RelationshipOut(
            id=r["id"],
            fact_a_id=r["fact_a_id"],
            fact_b_id=r["fact_b_id"],
            fact_a_entity=r.get("fact_a_entity"),
            fact_a_attribute=r.get("fact_a_attribute"),
            fact_b_entity=r.get("fact_b_entity"),
            fact_b_attribute=r.get("fact_b_attribute"),
            relationship=r["relationship"],
            basis=r["basis"],
            explanation=r["explanation"],
            confidence=r["confidence"],
            created_at=str(r.get("created_at", "")),
        )
        for r in rows
    ]
