#!/usr/bin/env python3
"""
Phase 0 Proof-of-Concept: Single-page-range extraction + quote validation.

This script validates the core riskiest bet BEFORE any infrastructure is built:
  PDF pages → LLM structured extraction → verbatim quote validated against raw page text

Usage:
    python scripts/poc_single_page.py --pdf path/to/file.pdf --pages 1-5

Output:
    Pretty-printed JSON with each extracted fact, including:
      - verbatim_quote
      - page_number
      - evidence_confidence (high/low)
      - quote_validated (bool)
    Summary statistics at the end.

Requires:
    - OPENAI_API_KEY in .env (or environment)
    - pip install -r requirements.txt
"""

import argparse
import asyncio
import io
import json
import os
import sys
from pathlib import Path

# Force UTF-8 output on Windows (handles ₹, ₨, em-dashes, etc.)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Make sure we can import from app/
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from openai import AsyncOpenAI

from app.config import get_settings
from app.services.pdf_extractor import extract_pages, get_page_text
from app.services.llm_extractor import extract_facts_from_batch
from app.services.quote_validator import validate_batch


def parse_page_range(page_str: str) -> tuple[int, int]:
    """Parse '3-7' or '5' into (start, end) inclusive, 1-indexed."""
    if "-" in page_str:
        parts = page_str.split("-")
        return int(parts[0]), int(parts[1])
    n = int(page_str)
    return n, n


async def main(pdf_path: str, pages_arg: str, batch_size: int) -> None:
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    # --- 1. Load PDF and extract pages ---
    print(f"\n{'='*60}")
    print(f"PDF: {pdf_path}")
    print(f"Pages requested: {pages_arg}")
    print(f"Extraction model: {settings.extraction_model}")
    print(f"{'='*60}\n")

    pdf_bytes = Path(pdf_path).read_bytes()
    all_pages = extract_pages(pdf_bytes)

    print(f"✓ PDF loaded: {len(all_pages)} total pages")

    # Filter to requested range
    start_page, end_page = parse_page_range(pages_arg)
    pages_to_process = [p for p in all_pages if start_page <= p.page_number <= end_page]

    if not pages_to_process:
        print(f"✗ No pages found in range {pages_arg}. PDF has {len(all_pages)} pages.")
        return

    print(f"✓ Processing pages {start_page}–{end_page} ({len(pages_to_process)} pages)\n")

    # Show what text was extracted (first 300 chars of page 1)
    first_page = pages_to_process[0]
    print(f"--- Raw text preview (page {first_page.page_number}, first 300 chars) ---")
    print(first_page.text[:300])
    if first_page.tables:
        print(f"  [+ {len(first_page.tables)} table(s) detected on this page]")
    print()

    # --- 2. LLM extraction ---
    # Process in one batch (pages_to_process is small for PoC)
    # If more than batch_size pages, chunk it
    from app.services.pdf_extractor import pages_to_batches
    batches = pages_to_batches(pages_to_process, batch_size=batch_size)

    all_extracted = []
    for i, batch in enumerate(batches):
        page_range = f"{batch[0].page_number}–{batch[-1].page_number}"
        print(f"⏳ Calling LLM for pages {page_range} (batch {i+1}/{len(batches)})...")
        facts = await extract_facts_from_batch(batch, client)
        all_extracted.extend([f.model_dump() for f in facts])
        print(f"  → {len(facts)} facts extracted")

    print(f"\n✓ Total facts before validation: {len(all_extracted)}")

    if not all_extracted:
        print("\n⚠  No facts extracted. Try different pages or check the PDF has a text layer.")
        return

    # --- 3. Quote validation ---
    page_texts = {p.page_number: p.text for p in pages_to_process}
    validated_facts = validate_batch(all_extracted, page_texts)

    # --- 4. Print results ---
    print(f"\n{'='*60}")
    print("EXTRACTED FACTS (with quote validation)")
    print(f"{'='*60}\n")

    for i, fact in enumerate(validated_facts, 1):
        confidence_icon = "✓" if fact.get("quote_validated") else "✗"
        confidence_label = fact.get("evidence_confidence", "unknown")

        print(f"[{i}] {confidence_icon} evidence={confidence_label.upper()}")
        print(f"    entity    : {fact.get('entity', '')}")
        print(f"    attribute : {fact.get('attribute', '')}")
        print(f"    value     : {fact.get('value', '')} {fact.get('unit') or ''}")
        print(f"    fact_type : {fact.get('fact_type', '')}")
        print(f"    page      : {fact.get('page_number', '')}")
        print(f"    confidence: {fact.get('confidence', '')}")

        # Time scope
        time_parts = []
        if fact.get("fiscal_year"): time_parts.append(f"FY={fact['fiscal_year']}")
        if fact.get("period_start"): time_parts.append(f"from={fact['period_start']}")
        if fact.get("period_end"): time_parts.append(f"to={fact['period_end']}")
        if time_parts:
            print(f"    time_scope: {', '.join(time_parts)}")

        if fact.get("qualifiers"):
            print(f"    qualifiers: {json.dumps(fact['qualifiers'])}")

        quote = fact.get("verbatim_quote", "")
        print(f"    quote     : \"{quote[:120]}{'...' if len(quote) > 120 else ''}\"")
        print()

    # --- 5. Summary ---
    total = len(validated_facts)
    high_conf = sum(1 for f in validated_facts if f.get("evidence_confidence") == "high")
    low_conf = total - high_conf

    print(f"{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"  Facts extracted : {total}")
    print(f"  Quote validated : {high_conf} ✓  ({100*high_conf//total if total else 0}%)")
    print(f"  Quote failed    : {low_conf} ✗  ({100*low_conf//total if total else 0}%)")
    print()

    if low_conf > 0:
        print("⚠  Failed quotes logged above are the FR-17 extraction-failure cases.")
        print("   These are expected and intentional — we catch them rather than trust them.")
    else:
        print("✓ All quotes validated against raw page text. Core bet confirmed.")

    # Optionally write full JSON to stdout for piping
    print(f"\n{'='*60}")
    print("FULL JSON OUTPUT")
    print(f"{'='*60}")
    print(json.dumps(validated_facts, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Phase 0 PoC: extract facts from PDF pages and validate quotes."
    )
    parser.add_argument("--pdf", required=True, help="Path to PDF file")
    parser.add_argument(
        "--pages",
        default="1-5",
        help="Page range to process, e.g. '1-5' or '3'. Default: 1-5"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=8,
        help="Pages per LLM batch. Default: 8"
    )

    args = parser.parse_args()

    if not Path(args.pdf).exists():
        print(f"Error: PDF not found at '{args.pdf}'")
        sys.exit(1)

    asyncio.run(main(args.pdf, args.pages, args.batch_size))
