"""
LLM-based structured fact extraction service.

Sends page-batch text to OpenAI using Structured Outputs (JSON schema strict mode)
to get back a list of ExtractedFact objects.

Model choice (per TRD §2.1):
  - Primary: gpt-5.6-luna (cheap, fast, good at structured extraction)
  - Escalation: gpt-5.6-sol if luna returns 0 facts from a page-batch that has
    dense numeric content (heuristic: >N numeric tokens but 0 facts → retry)

The prompt is designed to:
  1. Return exact verbatim quotes (machine-verified downstream).
  2. Work on ANY document type — no document-specific rules or hardcoded fields.
  3. Use the universal Fact envelope (entity / attribute / value / fact_type / qualifiers).
"""

from __future__ import annotations
import json
import logging
from typing import Optional

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.models.fact import ExtractionResponse, ExtractedFact
from app.services.pdf_extractor import PageContent, format_pages_for_prompt

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = """\
You are a precise information extraction engine. Your job is to extract structured facts from document text.

RULES — follow these exactly:
1. Extract ONLY facts that are explicitly stated in the text. Never infer or hallucinate.
2. For `verbatim_quote`: copy the EXACT words from the source text. Do NOT paraphrase, summarize, or rephrase. The quote will be machine-verified against the original document — any paraphrase will be flagged as a failure.
3. For `entity`: use the most complete name given in the document (e.g. "Delhivery Limited", not just "the Company").
4. For `fact_type`: use a short snake_case label like "financial_metric", "director_appointment", "registered_address", "macro_indicator", "operational_metric". You may invent new types — do not limit yourself to these examples.
5. For `qualifiers`: capture anything that affects the meaning of the value — consolidation basis (standalone/consolidated), revision status (provisional/revised/final), geographic scope, etc. Use free-form key-value pairs.
6. For financial numbers: always capture the unit (₹ crore, USD million, %, etc.) and the time scope (period_start, period_end, or fiscal_year).
7. If a page has no extractable facts (e.g. table of contents, blank page), return an empty facts list.
8. `confidence` should reflect how certain you are the extraction is correct (0.0–1.0). Use lower confidence for ambiguous phrasing or unclear scope.

IMPORTANT: Extract from BOTH narrative text AND tables. For tables, treat each data cell with its row/column headers as a separate fact.
"""


def _has_dense_numerics(batch: list[PageContent], threshold: int = 20) -> bool:
    """Heuristic: does this batch have many numeric tokens? Used to decide escalation."""
    import re
    combined = " ".join(p.text for p in batch)
    return len(re.findall(r"\b\d[\d,\.]*\b", combined)) > threshold


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
async def extract_facts_from_batch(
    batch: list[PageContent],
    client: AsyncOpenAI,
    model: Optional[str] = None,
    escalation_model: Optional[str] = None,
) -> list[ExtractedFact]:
    """
    Extract facts from a batch of pages using OpenAI Structured Outputs.

    Args:
        batch: list of PageContent objects for this batch
        client: AsyncOpenAI client
        model: model ID to use (defaults to settings.extraction_model)
        escalation_model: model ID to escalate to if primary returns 0 facts
                          (defaults to settings.reconciliation_model)

    Returns:
        List of ExtractedFact objects (may be empty if no facts found)
    """
    settings = get_settings()
    model = model or settings.extraction_model
    escalation_model = escalation_model or settings.reconciliation_model

    page_text = format_pages_for_prompt(batch)
    page_range = f"{batch[0].page_number}–{batch[-1].page_number}" if len(batch) > 1 else str(batch[0].page_number)

    logger.info(f"Extracting facts from pages {page_range} using {model}")

    response = await client.beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Extract all facts from the following document pages. "
                    f"Return a JSON object with a 'facts' array.\n\n{page_text}"
                ),
            },
        ],
        response_format=ExtractionResponse,
        temperature=0,  # deterministic extraction
    )

    result = response.choices[0].message.parsed
    facts = result.facts if result else []

    # Escalation heuristic: if primary model returned 0 facts but page has
    # dense numeric content, retry with the stronger model
    if len(facts) == 0 and _has_dense_numerics(batch) and model != escalation_model:
        logger.warning(
            f"Pages {page_range}: {model} returned 0 facts despite dense numeric content. "
            f"Escalating to {escalation_model}."
        )
        return await extract_facts_from_batch(
            batch, client,
            model=escalation_model,
            escalation_model=escalation_model,  # no further escalation
        )

    logger.info(f"Pages {page_range}: extracted {len(facts)} facts")
    return facts


async def extract_all_facts(
    pages: list[PageContent],
    client: AsyncOpenAI,
    batch_size: int = 8,
) -> list[ExtractedFact]:
    """
    Extract facts from all pages of a document, processing in batches.
    Batches are processed sequentially to avoid rate limits; can be made
    concurrent later if needed.

    Image-only pages (has_text_layer=False) are skipped for now —
    vision-based extraction is a future extension.
    """
    import asyncio
    from app.services.pdf_extractor import pages_to_batches

    # Filter to pages with text; log skipped image pages
    text_pages = [p for p in pages if p.has_text_layer]
    skipped = len(pages) - len(text_pages)
    if skipped > 0:
        logger.info(f"Skipping {skipped} image-only pages (no text layer detected).")

    batches = pages_to_batches(text_pages, batch_size=batch_size)
    all_facts: list[ExtractedFact] = []

    for batch in batches:
        batch_facts = await extract_facts_from_batch(batch, client)
        all_facts.extend(batch_facts)

    logger.info(f"Total facts extracted from document: {len(all_facts)}")
    return all_facts
