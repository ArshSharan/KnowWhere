"""
Reconciliation service — the core differentiating piece of the system.

Two responsibilities:
  1. generate_candidates(fact_id, pool): find facts that are plausibly about
     the same thing as fact_id, using pgvector kNN (same canonical entity +
     embedding similarity). This turns O(n²) comparison into O(n·k).

  2. reconcile_pair(fact_a, fact_b, client): call GPT (reconciliation_model)
     with both facts + both evidence quotes and ask it to classify the
     relationship as: corroborates | contradicts | reconciled_by_context | unrelated
     + a natural-language explanation.

The prompt is carefully designed to force the model to reason about:
  - time period differences
  - consolidation scope (standalone vs. consolidated)
  - unit differences (₹ crore vs. ₹ million)
  - rounding and restatement
before calling something a contradiction. This is the nuance the rubric rewards.
"""

from __future__ import annotations
import logging
from typing import Optional

import asyncpg
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.db import crud
from app.models.fact import ReconciliationResult
from app.services.embedder import fact_embedding_text

logger = logging.getLogger(__name__)

# Top-K nearest neighbours to fetch for candidate generation.
# Low enough to keep reconciliation LLM calls manageable,
# high enough to catch non-obvious matches.
CANDIDATE_K = 10

RECONCILIATION_SYSTEM_PROMPT = """\
You are a precise fact-reconciliation engine. You will be given two facts extracted from different documents.
Your job: determine how these two facts relate to each other.

CRITICAL REASONING STEPS — work through these before choosing a relationship:
1. Are they about the same real-world entity and attribute? If clearly not, choose "unrelated".
2. Do the time periods or fiscal years differ? If yes, this is likely "reconciled_by_context" with basis "time_period".
3. Do the consolidation scopes differ (standalone vs. consolidated, segment vs. group)? If yes, likely "reconciled_by_context" with basis "scope".
4. Do the units differ (₹ crore vs. ₹ million vs. ₹ lakh, %, absolute count)? If yes, reconcile by converting mentally — if after conversion they agree, use "reconciled_by_context" with basis "units"; if they still disagree, use "contradicts".
5. Is the difference within rounding tolerance (<2%)? If yes, "reconciled_by_context" basis "rounding".
6. Was one figure revised/restated? If yes, "reconciled_by_context" basis "restatement".
7. Only choose "contradicts" when you cannot explain the disagreement by any of the above.
8. Choose "corroborates" only when both facts clearly state the same thing for the same entity, attribute, time period, and scope.

Your explanation MUST:
  - Be 1–2 sentences a human analyst can audit.
  - State the specific reason (not just the label).
  - Mention the actual values, time periods, and scopes involved.
"""


def _format_fact_for_prompt(fact: dict, label: str = "Fact A") -> str:
    lines = [
        f"=== {label} ===",
        f"Entity    : {fact.get('entity_name') or fact.get('entity', '')}",
        f"Attribute : {fact.get('attribute', '')}",
        f"Value     : {fact.get('value', '')} {fact.get('unit') or ''}",
        f"Fact type : {fact.get('fact_type_label') or fact.get('fact_type', '')}",
    ]
    # Time scope
    time_parts = []
    if fact.get("fiscal_year"): time_parts.append(f"FY={fact['fiscal_year']}")
    if fact.get("period_start"): time_parts.append(f"from={fact['period_start']}")
    if fact.get("period_end"): time_parts.append(f"to={fact['period_end']}")
    if fact.get("as_of_date"): time_parts.append(f"as_of={fact['as_of_date']}")
    if time_parts:
        lines.append(f"Time scope: {', '.join(time_parts)}")
    if fact.get("qualifiers"):
        lines.append(f"Qualifiers: {fact['qualifiers']}")
    lines.append(f"Evidence  : \"{fact.get('verbatim_quote', '')}\"")
    lines.append(f"Page      : {fact.get('page_number', '')}")
    lines.append(f"Source doc: {fact.get('document_id', '')}")
    return "\n".join(lines)


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10))
async def reconcile_pair(
    fact_a: dict,
    fact_b: dict,
    client: AsyncOpenAI,
) -> ReconciliationResult:
    """
    Call the reconciliation LLM on one pair of facts.
    Returns a structured ReconciliationResult.
    """
    settings = get_settings()

    prompt_a = _format_fact_for_prompt(fact_a, "Fact A")
    prompt_b = _format_fact_for_prompt(fact_b, "Fact B")

    user_content = (
        f"Classify the relationship between these two facts.\n\n"
        f"{prompt_a}\n\n{prompt_b}"
    )

    response = await client.beta.chat.completions.parse(
        model=settings.reconciliation_model,
        messages=[
            {"role": "system", "content": RECONCILIATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        response_format=ReconciliationResult,
    )

    result = response.choices[0].message.parsed
    logger.info(
        f"Reconciled [{fact_a.get('id','?')}] ↔ [{fact_b.get('id','?')}]: "
        f"{result.relationship} (confidence={result.confidence:.2f})"
    )
    return result


async def generate_candidates(
    pool: asyncpg.Pool,
    fact_id: str,
    entity_id: str,
    fact_embedding: list[float],
    k: int = CANDIDATE_K,
) -> list[dict]:
    """
    Find the top-K most similar facts for the same canonical entity.
    Uses pgvector cosine similarity on the fact embedding.
    Excludes the fact itself and facts from the same document.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT f.*,
                   e.canonical_name  AS entity_name,
                   ft.label          AS fact_type_label,
                   1 - (f.embedding <=> $1::vector) AS similarity
            FROM facts f
            JOIN entities   e  ON e.id  = f.entity_id
            JOIN fact_types ft ON ft.id = f.fact_type_id
            WHERE f.entity_id = $2
              AND f.id        != $3
              AND f.embedding IS NOT NULL
              AND (1 - (f.embedding <=> $1::vector)) >= 0.70
            ORDER BY f.embedding <=> $1::vector
            LIMIT $4
            """,
            str(fact_embedding),
            entity_id,
            fact_id,
            k,
        )
    from app.db.crud import _record_to_dict
    return [_record_to_dict(r) for r in rows]


async def reconcile_document_facts(
    pool: asyncpg.Pool,
    client: AsyncOpenAI,
    document_id: str,
    skip_same_document: bool = True,
) -> int:
    """
    Run reconciliation for all facts in a document against existing corpus facts.

    For each fact in the document:
      1. Check it has an embedding (skip if not).
      2. Find candidate facts (same entity, kNN by embedding).
      3. For each candidate pair not already reconciled: call reconcile_pair.
      4. Persist the result in fact_relationships.

    Returns the number of relationships created/updated.
    """
    relationship_count = 0

    async with pool.acquire() as conn:
        doc_facts = await conn.fetch(
            """
            SELECT f.*, e.canonical_name AS entity_name, ft.label AS fact_type_label
            FROM facts f
            JOIN entities   e  ON e.id  = f.entity_id
            JOIN fact_types ft ON ft.id = f.fact_type_id
            WHERE f.document_id = $1
              AND f.embedding IS NOT NULL
            """,
            document_id,
        )

    from app.db.crud import _record_to_dict
    doc_fact_dicts = [_record_to_dict(r) for r in doc_facts]

    for fact_a in doc_fact_dicts:
        fact_id_a = fact_a["id"]
        entity_id_a = fact_a["entity_id"]
        embedding_a = fact_a.get("embedding")

        if embedding_a is None:
            continue

        # Parse embedding from pgvector's string representation if needed
        if isinstance(embedding_a, str):
            embedding_a = [float(x) for x in embedding_a.strip("[]").split(",")]

        candidates = await generate_candidates(pool, fact_id_a, entity_id_a, embedding_a)

        for fact_b in candidates:
            # Skip same-document pairs if requested (cross-document only for demo)
            if skip_same_document and fact_b.get("document_id") == document_id:
                continue

            # Skip pairs already reconciled
            async with pool.acquire() as conn:
                existing = await conn.fetchval(
                    """
                    SELECT id FROM fact_relationships
                    WHERE (fact_a_id = $1 AND fact_b_id = $2)
                       OR (fact_a_id = $2 AND fact_b_id = $1)
                    """,
                    fact_id_a,
                    fact_b["id"],
                )
            if existing:
                continue

            try:
                result = await reconcile_pair(fact_a, fact_b, client)

                await crud.upsert_fact_relationship(
                    pool,
                    fact_a_id=fact_id_a,
                    fact_b_id=fact_b["id"],
                    relationship=result.relationship.value,
                    basis=result.reconciliation_basis.value,
                    explanation=result.explanation,
                    confidence=result.confidence,
                )
                relationship_count += 1

            except Exception as e:
                logger.warning(
                    f"Reconciliation failed for [{fact_id_a}] ↔ [{fact_b['id']}]: {e}"
                )
                continue

    logger.info(f"[{document_id}] Reconciliation complete: {relationship_count} relationships stored.")
    return relationship_count
