"""
KnowWhere FastAPI application.

Phase 0: health endpoint only.
Phase 1 will add: POST /documents, GET /documents/{id}, GET /documents/{id}/facts
"""

import logging
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings

# Configure logging
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="KnowWhere — Fact Knowledge Layer",
    description=(
        "A generalizable PDF → grounded facts pipeline. "
        "Every fact traces to a verbatim quote + page number in its source document. "
        "Related facts across documents are classified as corroborating, contradicting, "
        "or reconciled-by-context, with a human-readable explanation."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tightened in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Meta"])
async def health():
    """Basic health check — confirms the API is up and settings loaded."""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "extraction_model": settings.extraction_model,
        "reconciliation_model": settings.reconciliation_model,
        "embedding_model": settings.embedding_model,
        "env": settings.env,
    }
