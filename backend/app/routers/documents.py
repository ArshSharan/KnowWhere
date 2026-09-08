"""
Document and fact API endpoints.

POST /documents          — upload PDF, start background ingestion
GET  /documents          — list all documents
GET  /documents/{id}     — document status + metadata
GET  /documents/{id}/facts — all extracted facts with evidence
GET  /facts/{id}         — one fact in full
GET  /facts/{id}/relationships — relationship edges for one fact
GET  /facts/search       — semantic search + optional AI synthesis
"""

from __future__ import annotations
import json
import logging
from typing import Any, Optional

import asyncpg
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Query, Response
from openai import AsyncOpenAI
from pydantic import BaseModel

from app.config import get_settings
from app.db.connection import get_pool
from app.db import crud
from app.models.api import (
    DocumentOut,
    DocumentWithFactsOut,
    EvidenceOut,
    FactOut,
    FactSearchResultOut,
    GlobalRelationshipOut,
    RelationshipOut,
    UploadResponse,
)
from app.services.embedder import embed_texts
from app.services.ingestion_worker import compute_content_hash, ingest_document
from app.services import r2_client


class SynthesisResponse(BaseModel):
    answer: str
    model_used: str
    facts_used: int

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Helper: DB row → API model
# ---------------------------------------------------------------------------

def _row_to_fact_out(row: dict) -> FactOut:
    """Convert a facts DB row (with joined entity_name / fact_type_label) to FactOut."""
    qualifiers_raw = row.get("qualifiers") or {}
    if isinstance(qualifiers_raw, str):
        try:
            qualifiers = json.loads(qualifiers_raw)
        except Exception:
            qualifiers = {}
    else:
        qualifiers = qualifiers_raw

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
        qualifiers=qualifiers,
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

    # Store PDF file (R2 with local filesystem fallback)
    try:
        source_uri = await r2_client.store_pdf(doc_id, file.filename, pdf_bytes)
        async with pool.acquire() as conn:
            await conn.execute("UPDATE documents SET source_uri = $1 WHERE id = $2", source_uri, doc_id)
    except Exception as e:
        logger.warning(f"[{doc_id}] Failed to store PDF file: {e}")

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
# Fact endpoints (Static paths MUST precede parameterized {fact_id} paths)
# ---------------------------------------------------------------------------

@router.get("/facts/search", response_model=list[FactSearchResultOut], tags=["Facts"])
async def search_facts_endpoint(
    q: str = Query(..., min_length=1, description="Semantic search query across facts"),
    limit: int = Query(30, ge=1, le=100),
    pool: asyncpg.Pool = Depends(get_pool),
):
    """
    Semantic search over the Fact Knowledge Layer using vector embeddings + pgvector.
    Falls back gracefully to keyword search if embeddings fail.
    """
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    query_embedding = None
    try:
        embeddings = await embed_texts([q], client)
        if embeddings and embeddings[0]:
            query_embedding = embeddings[0]
    except Exception as e:
        logger.warning(f"Embedding generation failed for query '{q}': {e}")

    rows = await crud.search_facts(pool, query_embedding=query_embedding, query_text=q, limit=limit)

    results = []
    for r in rows:
        fact_out = _row_to_fact_out(r)
        results.append(
            FactSearchResultOut(
                **fact_out.model_dump(),
                similarity=float(r.get("similarity", 1.0)),
                document_title=r.get("document_title"),
            )
        )
    return results


SYNTHESIS_SYSTEM_PROMPT = """\
You are a precise financial-document analyst. You are given a user's question and a set of \
grounded facts extracted from real documents (each with a verbatim quote as evidence). \
Your job: answer the question in 2-4 clear, well-structured sentences using ONLY the provided facts. \
- State specific numbers, time periods and entity names exactly as given in the facts.
- If multiple facts cover the same metric for different periods, mention the trend.
- If the facts are insufficient to fully answer the question, say so briefly.
- Do NOT add information not present in the provided facts.
- Write in plain, professional English — no bullet points, no markdown.
"""

@router.get("/facts/synthesize", response_model=SynthesisResponse, tags=["Facts"])
async def synthesize_answer(
    q: str = Query(..., min_length=1, description="Question to answer from the knowledge base"),
    limit: int = Query(12, ge=1, le=30, description="Number of top facts to use as context"),
    pool: asyncpg.Pool = Depends(get_pool),
):
    """
    RAG-style synthesis: retrieve the top-K relevant facts for the query,
    then ask Luna (gpt-5.6-luna) to produce a grounded natural-language answer.
    If Luna returns something too short (<40 chars), escalates to Sol automatically.
    """
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    # Retrieve top facts via semantic search
    query_embedding = None
    try:
        embeddings = await embed_texts([q], client)
        if embeddings and embeddings[0]:
            query_embedding = embeddings[0]
    except Exception as e:
        logger.warning(f"Embedding failed for synthesis query '{q}': {e}")

    rows = await crud.search_facts(pool, query_embedding=query_embedding, query_text=q, limit=limit)
    if not rows:
        return SynthesisResponse(
            answer="No relevant facts were found in the knowledge base for this query. "
                   "Try uploading more documents or rephrasing your question.",
            model_used="none",
            facts_used=0,
        )

    # Build context block
    context_lines = []
    for i, r in enumerate(rows, 1):
        entity = r.get("entity_name") or r.get("entity", "")
        attr   = r.get("attribute", "")
        value  = r.get("value", "")
        unit   = r.get("unit") or ""
        fy     = r.get("fiscal_year") or ""
        quote  = r.get("verbatim_quote") or ""
        doc    = r.get("document_title") or "unknown document"
        page   = r.get("page_number") or ""
        context_lines.append(
            f"[Fact {i}] {entity} — {attr}: {value} {unit} {('(' + fy + ')') if fy else ''}\n"
            f"  Evidence: \"{quote}\" (p.{page}, {doc})"
        )

    context = "\n\n".join(context_lines)
    user_message = f"Question: {q}\n\nGrounded facts from the knowledge base:\n\n{context}"

    # Try Luna first (cheaper, faster)
    primary_model = settings.extraction_model
    fallback_model = settings.reconciliation_model
    model_used = primary_model

    try:
        resp = await client.chat.completions.create(
            model=primary_model,
            messages=[
                {"role": "system", "content": SYNTHESIS_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_completion_tokens=400,
        )
        answer = resp.choices[0].message.content.strip()

        # Escalate if answer is suspiciously short or evasive
        if len(answer) < 40 and primary_model != fallback_model:
            logger.info(f"Luna answer too short ({len(answer)} chars) — escalating to {fallback_model}.")
            resp2 = await client.chat.completions.create(
                model=fallback_model,
                messages=[
                    {"role": "system", "content": SYNTHESIS_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                max_completion_tokens=400,
            )
            answer = resp2.choices[0].message.content.strip()
            model_used = fallback_model

    except Exception as e:
        logger.error(f"Synthesis LLM call failed: {e}")
        answer = "Could not generate a synthesized answer at this time. The raw facts are shown below."
        model_used = "error"

    return SynthesisResponse(answer=answer, model_used=model_used, facts_used=len(rows))


@router.get("/relationships", response_model=list[GlobalRelationshipOut], tags=["Facts"])
async def list_all_relationships_endpoint(
    relationship: Optional[str] = Query(None, description="Filter: corroborates | contradicts | reconciled_by_context"),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    pool: asyncpg.Pool = Depends(get_pool),
):
    """
    Global feed of cross-document reconciliation edges with human-readable explanations.
    Powers the Reconciliation Hub and showcases the 4 required cases.
    """
    rows = await crud.list_all_relationships(pool, relationship=relationship, limit=limit, offset=offset)
    return [
        GlobalRelationshipOut(
            id=r["id"],
            fact_a_id=r["fact_a_id"],
            fact_b_id=r["fact_b_id"],
            fact_a_entity=r.get("fact_a_entity"),
            fact_a_attribute=r.get("fact_a_attribute"),
            fact_a_value=r.get("fact_a_value"),
            fact_a_unit=r.get("fact_a_unit"),
            fact_a_fiscal_year=r.get("fact_a_fiscal_year"),
            fact_a_page=r.get("fact_a_page"),
            fact_a_quote=r.get("fact_a_quote"),
            fact_a_doc_title=r.get("fact_a_doc_title"),
            fact_a_doc_id=r.get("fact_a_doc_id"),
            fact_b_entity=r.get("fact_b_entity"),
            fact_b_attribute=r.get("fact_b_attribute"),
            fact_b_value=r.get("fact_b_value"),
            fact_b_unit=r.get("fact_b_unit"),
            fact_b_fiscal_year=r.get("fact_b_fiscal_year"),
            fact_b_page=r.get("fact_b_page"),
            fact_b_quote=r.get("fact_b_quote"),
            fact_b_doc_title=r.get("fact_b_doc_title"),
            fact_b_doc_id=r.get("fact_b_doc_id"),
            relationship=r["relationship"],
            basis=r["basis"],
            explanation=r["explanation"],
            confidence=r["confidence"],
            created_at=str(r.get("created_at", "")),
        )
        for r in rows
    ]


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


@router.get("/documents/{doc_id}/file", tags=["Documents"])
async def get_document_file(doc_id: str, pool: asyncpg.Pool = Depends(get_pool)):
    """Stream source PDF bytes for viewing in UI / evidence verification."""
    doc = await crud.get_document(pool, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found.")

    pdf_bytes = r2_client.get_pdf_bytes(doc_id, doc.get("source_uri") or "")
    if not pdf_bytes:
        raise HTTPException(status_code=404, detail="PDF content not found.")

    filename = doc.get("title") or f"{doc_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


