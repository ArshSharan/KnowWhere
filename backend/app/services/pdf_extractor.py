"""
PDF text and table extraction service.

Uses PyMuPDF (fitz) as the primary text extractor (fast, page-accurate, gives
character offsets) and pdfplumber for tables (handles merged cells and
structured cell grids better than fitz's text).

Returns per-page dicts with:
  - text: raw page text (used for quote validation)
  - tables: list of cell grids (list[list[str]]) extracted by pdfplumber
  - page_number: 1-indexed
  - has_text_layer: False if the page appears to be scanned/image-only
"""

from __future__ import annotations
import io
import logging
from dataclasses import dataclass, field
from typing import Optional

import fitz  # PyMuPDF
import pdfplumber

logger = logging.getLogger(__name__)


@dataclass
class PageContent:
    page_number: int          # 1-indexed
    text: str                 # raw extracted text
    tables: list[list[list[str]]] = field(default_factory=list)  # list of tables; each table is list[rows] of list[cells]
    has_text_layer: bool = True


def extract_pages(pdf_bytes: bytes) -> list[PageContent]:
    """
    Extract all pages from a PDF given its raw bytes.
    Returns a list of PageContent, one per page, 1-indexed.
    """
    pages: list[PageContent] = []

    # Open with pdfplumber for table extraction (we keep it open across all pages)
    plumber_doc = pdfplumber.open(io.BytesIO(pdf_bytes))

    # Open with fitz for raw text (faster and more accurate for plain text)
    fitz_doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    try:
        for page_idx in range(len(fitz_doc)):
            page_number = page_idx + 1

            # --- Text extraction via fitz ---
            fitz_page = fitz_doc[page_idx]
            raw_text = fitz_page.get_text("text")  # plain text, preserves layout

            # Heuristic: if the page has very little extractable text but non-zero image area,
            # it's likely a scanned/image page.
            has_text_layer = len(raw_text.strip()) > 50

            # --- Table extraction via pdfplumber ---
            tables: list[list[list[str]]] = []
            try:
                plumber_page = plumber_doc.pages[page_idx]
                extracted_tables = plumber_page.extract_tables()
                if extracted_tables:
                    for tbl in extracted_tables:
                        # Normalize None cells to empty string
                        clean_table = [
                            [str(cell) if cell is not None else "" for cell in row]
                            for row in tbl
                        ]
                        tables.append(clean_table)
            except Exception as e:
                logger.warning(f"pdfplumber table extraction failed on page {page_number}: {e}")

            pages.append(PageContent(
                page_number=page_number,
                text=raw_text,
                tables=tables,
                has_text_layer=has_text_layer,
            ))

    finally:
        plumber_doc.close()
        fitz_doc.close()

    logger.info(f"Extracted {len(pages)} pages, {sum(1 for p in pages if not p.has_text_layer)} image-only pages.")
    return pages


def pages_to_batches(pages: list[PageContent], batch_size: int = 8) -> list[list[PageContent]]:
    """
    Split pages into batches of `batch_size` for parallel LLM extraction.
    Keeps page order within each batch.
    """
    return [pages[i:i + batch_size] for i in range(0, len(pages), batch_size)]


def format_pages_for_prompt(batch: list[PageContent]) -> str:
    """
    Format a batch of pages into a single prompt-friendly string.
    Tables are inlined as pipe-delimited rows after the page text.
    Page boundaries are clearly marked so the model knows which page a quote comes from.
    """
    parts: list[str] = []
    for page in batch:
        parts.append(f"=== PAGE {page.page_number} ===")
        if page.text.strip():
            parts.append(page.text.strip())
        if page.tables:
            for t_idx, table in enumerate(page.tables):
                parts.append(f"\n[TABLE {t_idx + 1} on page {page.page_number}]")
                for row in table:
                    parts.append(" | ".join(row))
        parts.append("")  # blank line between pages

    return "\n".join(parts)


def get_page_text(pages: list[PageContent], page_number: int) -> Optional[str]:
    """Helper: retrieve raw text for a specific 1-indexed page number."""
    for p in pages:
        if p.page_number == page_number:
            return p.text
    return None
