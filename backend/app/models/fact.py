"""
Pydantic models for the core domain objects.
These are the shared schemas used across services, API, and DB layers.
"""

from __future__ import annotations
from enum import Enum
from typing import Optional, Any
from datetime import date
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ValueType(str, Enum):
    number = "number"
    date = "date"
    string = "string"
    enum = "enum"
    boolean = "boolean"


class RelationshipType(str, Enum):
    corroborates = "corroborates"
    contradicts = "contradicts"
    reconciled_by_context = "reconciled_by_context"
    unrelated = "unrelated"


class ReconciliationBasis(str, Enum):
    time_period = "time_period"
    scope = "scope"
    units = "units"
    rounding = "rounding"
    restatement = "restatement"
    none = "none"


class EvidenceConfidence(str, Enum):
    high = "high"    # verbatim quote validated as substring of raw page text
    low = "low"      # quote failed validation (model paraphrased or hallucinated)


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

class Evidence(BaseModel):
    verbatim_quote: str = Field(
        description="Exact text copied from the source document — not a paraphrase."
    )
    page_number: int = Field(description="1-indexed page number in the source PDF.")
    evidence_confidence: EvidenceConfidence = Field(
        default=EvidenceConfidence.high,
        description="'high' if quote was validated as a real substring of the raw page text, 'low' otherwise."
    )


# ---------------------------------------------------------------------------
# Fact (the universal envelope)
# ---------------------------------------------------------------------------

class TimeScope(BaseModel):
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    as_of_date: Optional[date] = None
    fiscal_year: Optional[str] = None   # e.g. "FY24", "2024-25"


class Fact(BaseModel):
    """
    Universal fact envelope — schema-light by design.
    Domain-specific structure is captured in qualifiers (free-form key-values),
    not in code-level subclasses. This allows new fact types to appear from
    documents without code changes.
    """
    entity: str = Field(description="The real-world entity this fact is about.")
    attribute: str = Field(description="What aspect of the entity this fact captures (e.g. 'revenue', 'registered_address').")
    value: str = Field(description="The fact's value, always as a string (use value_type to interpret).")
    value_type: ValueType = Field(description="How to interpret value (number / date / string / enum / boolean).")
    unit: Optional[str] = Field(default=None, description="Unit of the value, e.g. '₹ crore', 'USD million', 'km'.")
    time_scope: Optional[TimeScope] = Field(default=None)
    qualifiers: dict[str, Any] = Field(
        default_factory=dict,
        description="Free-form key-value pairs for anything that affects meaning: consolidation basis, revision status, etc."
    )
    fact_type: str = Field(
        description="Category label proposed by the extraction model, e.g. 'financial_metric', 'director_appointment'. Not a fixed enum."
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Extraction confidence 0–1.")
    evidence: list[Evidence] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# LLM extraction response schema
# ---------------------------------------------------------------------------

class QualifierItem(BaseModel):
    key: str = Field(description="Qualifier key, e.g. 'basis', 'scope', 'revision_status'")
    value: str = Field(description="Qualifier value, e.g. 'standalone', 'consolidated', 'restated'")


class ExtractedFact(BaseModel):
    """Schema fed to OpenAI Structured Outputs for per-page-batch extraction."""
    entity: str
    attribute: str
    value: str
    value_type: ValueType
    unit: Optional[str] = None
    period_start: Optional[str] = None   # ISO date string, parsed later
    period_end: Optional[str] = None
    as_of_date: Optional[str] = None
    fiscal_year: Optional[str] = None
    qualifiers: list[QualifierItem] = Field(
        default_factory=list,
        description="List of key-value qualifier pairs, e.g. [{'key': 'basis', 'value': 'standalone'}]"
    )
    fact_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    verbatim_quote: str = Field(
        description="Copy the EXACT words from the source text. Do NOT paraphrase. This will be machine-verified."
    )
    page_number: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict with qualifiers formatted as a key-value dictionary."""
        d = self.model_dump()
        d["qualifiers"] = {q.key: q.value for q in self.qualifiers}
        return d


class ExtractionResponse(BaseModel):
    """Wrapper for the full LLM response from one page-batch call."""
    facts: list[ExtractedFact]


# ---------------------------------------------------------------------------
# Reconciliation schema
# ---------------------------------------------------------------------------

class ReconciliationResult(BaseModel):
    """Schema fed to OpenAI Structured Outputs for the reconciliation call."""
    relationship: RelationshipType
    confidence: float = Field(ge=0.0, le=1.0)
    reconciliation_basis: ReconciliationBasis
    explanation: str = Field(
        description="One or two sentences a human can read and audit. Explain WHY this is the relationship, not just what it is."
    )
