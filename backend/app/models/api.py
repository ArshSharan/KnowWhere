"""
API response schemas (separate from the domain models in models/fact.py).
These are what the API endpoints actually serialize and return.
"""

from __future__ import annotations
from typing import Any, Optional
from datetime import date, datetime
from pydantic import BaseModel


class EvidenceOut(BaseModel):
    verbatim_quote: str
    page_number: int
    evidence_confidence: str  # "high" | "low"


class FactOut(BaseModel):
    id: str
    entity: str
    attribute: str
    value: str
    value_type: str
    unit: Optional[str]
    fact_type: str
    confidence: float
    fiscal_year: Optional[str]
    period_start: Optional[str]
    period_end: Optional[str]
    as_of_date: Optional[str]
    qualifiers: dict[str, Any]
    evidence: EvidenceOut


class DocumentOut(BaseModel):
    id: str
    title: Optional[str]
    doc_type: Optional[str]
    status: str
    page_count: Optional[int]
    facts_count: int
    created_at: str
    updated_at: str


class DocumentWithFactsOut(DocumentOut):
    facts: list[FactOut]


class RelationshipOut(BaseModel):
    id: str
    fact_a_id: str
    fact_b_id: str
    fact_a_entity: Optional[str]
    fact_a_attribute: Optional[str]
    fact_b_entity: Optional[str]
    fact_b_attribute: Optional[str]
    relationship: str    # corroborates | contradicts | reconciled_by_context | unrelated
    basis: str           # time_period | scope | units | rounding | restatement | none
    explanation: str
    confidence: float
    created_at: str


class GlobalRelationshipOut(RelationshipOut):
    fact_a_value: Optional[str] = None
    fact_a_unit: Optional[str] = None
    fact_a_fiscal_year: Optional[str] = None
    fact_a_page: Optional[int] = None
    fact_a_quote: Optional[str] = None
    fact_a_doc_title: Optional[str] = None
    fact_a_doc_id: Optional[str] = None
    fact_b_value: Optional[str] = None
    fact_b_unit: Optional[str] = None
    fact_b_fiscal_year: Optional[str] = None
    fact_b_page: Optional[int] = None
    fact_b_quote: Optional[str] = None
    fact_b_doc_title: Optional[str] = None
    fact_b_doc_id: Optional[str] = None


class FactSearchResultOut(FactOut):
    similarity: float = 1.0
    document_title: Optional[str] = None


class UploadResponse(BaseModel):
    doc_id: str
    status: str
    duplicate: bool = False

