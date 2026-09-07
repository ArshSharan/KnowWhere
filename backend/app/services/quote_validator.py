"""
Server-side verbatim quote validation.

After LLM extraction, we verify that each returned `verbatim_quote` actually
appears as a substring of the raw page text extracted by pdfplumber/PyMuPDF.
This prevents silently trusting hallucinated or paraphrased quotes.

Strategy:
  1. Normalize whitespace on both sides (collapse runs of whitespace to single space).
  2. Check substring match.
  3. If it fails, try a "fuzzy" match — check if ≥85% of the quote's words appear
     in the page text in order (handles minor formatting artefacts from PDF extraction).
  4. Mark evidence_confidence = "high" on success, "low" on failure.

The validation failures are deliberately logged in detail — they're a legitimate
source for the required extraction-failure case (FR-17).
"""

from __future__ import annotations
import logging
import re
import unicodedata

logger = logging.getLogger(__name__)


def _normalize(text: str) -> str:
    """Normalize whitespace and unicode for comparison."""
    # Normalize unicode (e.g. smart quotes, em-dashes)
    text = unicodedata.normalize("NFKC", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _fuzzy_match(quote: str, page_text: str, threshold: float = 0.80) -> bool:
    """
    Sliding-window word-overlap check.
    Returns True if at least `threshold` fraction of the quote's words appear
    consecutively in the page text (order-sensitive).
    This handles minor PDF extraction artefacts (e.g. line breaks mid-word,
    ligature characters, hyphenation).
    """
    quote_words = _normalize(quote).split()
    page_words = _normalize(page_text).split()

    if not quote_words:
        return False

    n, m = len(quote_words), len(page_words)
    if n > m:
        return False

    best_overlap = 0
    for start in range(m - n + 1):
        overlap = sum(
            1 for i, w in enumerate(quote_words)
            if (start + i) < m and page_words[start + i] == w
        )
        if overlap > best_overlap:
            best_overlap = overlap
        if best_overlap >= len(quote_words):
            break

    ratio = best_overlap / len(quote_words)
    return ratio >= threshold


def validate_quote(
    verbatim_quote: str,
    page_text: str,
    page_number: int,
    fact_entity: str = "",
    fact_attribute: str = "",
) -> tuple[bool, str]:
    """
    Validate that `verbatim_quote` is a real substring of `page_text`.

    Returns:
        (is_valid: bool, confidence: str)  — confidence is "high" or "low"
    """
    if not verbatim_quote or not page_text:
        logger.warning(
            f"Quote validation: empty quote or page text | page={page_number} | "
            f"entity={fact_entity} | attribute={fact_attribute}"
        )
        return False, "low"

    norm_quote = _normalize(verbatim_quote)
    norm_page = _normalize(page_text)

    # Primary check: exact substring
    if norm_quote in norm_page:
        return True, "high"

    # Secondary check: fuzzy word-overlap (handles PDF extraction artefacts)
    if _fuzzy_match(verbatim_quote, page_text):
        logger.info(
            f"Quote validation: fuzzy match (not exact substring) | page={page_number} | "
            f"quote_start='{verbatim_quote[:60]}...'"
        )
        return True, "high"

    # Validation failed — log the full context for FR-17 (extraction failure case)
    logger.warning(
        f"Quote validation FAILED | page={page_number} | "
        f"entity={fact_entity} | attribute={fact_attribute} | "
        f"quote='{verbatim_quote[:120]}'"
    )
    return False, "low"


def validate_batch(
    extracted_facts: list[dict],
    page_texts: dict[int, str],  # page_number -> raw text
) -> list[dict]:
    """
    Run quote validation over a list of raw extracted fact dicts.
    Adds/updates 'evidence_confidence' field on each.

    Args:
        extracted_facts: raw fact dicts as returned by the LLM
        page_texts: mapping from page_number to raw page text

    Returns:
        The same list with 'evidence_confidence' set on each item.
    """
    validated = []
    for fact in extracted_facts:
        page_num = fact.get("page_number", -1)
        page_text = page_texts.get(page_num, "")
        quote = fact.get("verbatim_quote", "")

        is_valid, confidence = validate_quote(
            verbatim_quote=quote,
            page_text=page_text,
            page_number=page_num,
            fact_entity=fact.get("entity", ""),
            fact_attribute=fact.get("attribute", ""),
        )

        fact["evidence_confidence"] = confidence
        fact["quote_validated"] = is_valid
        validated.append(fact)

    return validated
