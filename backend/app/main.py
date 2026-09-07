"""
KnowWhere FastAPI application.

Registers:
  - /health            (meta)
  - /documents         (upload, list, status, facts)
  - /facts/{id}        (single fact + relationships)
"""

import logging
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.connection import lifespan
from app.routers import documents

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
        "Every fact traces to a verbatim quote + page number. "
        "Related facts across documents are classified as corroborating, contradicting, "
        "or reconciled-by-context, with a human-readable explanation."
    ),
    version="0.2.0",
    lifespan=lifespan,
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

# Routers
app.include_router(documents.router)


@app.get("/health", tags=["Meta"])
async def health():
    """Basic health check — confirms the API is up and settings are loaded."""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "extraction_model": settings.extraction_model,
        "reconciliation_model": settings.reconciliation_model,
        "embedding_model": settings.embedding_model,
        "database_configured": bool(settings.database_url),
        "env": settings.env,
    }
