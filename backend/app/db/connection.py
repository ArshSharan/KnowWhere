"""
Database connection management using asyncpg.

The pool is created on app startup via the lifespan context manager
and stored on app.state.pool. Endpoints get the pool via the
get_pool() FastAPI dependency.

If DATABASE_URL is not set, the pool is None and endpoints that require
the DB will return 503 with a clear message — so the app starts up even
in a dev environment without Supabase configured yet.
"""

from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncpg
from fastapi import FastAPI, HTTPException, Request

from app.config import get_settings

logger = logging.getLogger(__name__)


def _asyncpg_url(database_url: str) -> str:
    """
    Convert a SQLAlchemy-style URL to a raw asyncpg URL.
    Strips the '+asyncpg' dialect suffix if present.
    e.g. postgresql+asyncpg://user:pass@host/db -> postgresql://user:pass@host/db
    """
    return database_url.replace("postgresql+asyncpg://", "postgresql://")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: create DB pool on startup, close on shutdown."""
    settings = get_settings()

    if settings.database_url:
        try:
            url = _asyncpg_url(settings.database_url)
            app.state.pool = await asyncpg.create_pool(
                url,
                min_size=2,
                max_size=10,
                command_timeout=60,
                ssl="require",   # Supabase requires SSL
            )
            logger.info("Database pool created successfully.")
        except Exception as e:
            logger.error(f"Failed to create database pool: {e}")
            app.state.pool = None
    else:
        logger.warning("DATABASE_URL not set — running without database (some endpoints will return 503).")
        app.state.pool = None

    yield  # app runs here

    if getattr(app.state, "pool", None):
        await app.state.pool.close()
        logger.info("Database pool closed.")


async def get_pool(request: Request) -> asyncpg.Pool:
    """
    FastAPI dependency: inject the asyncpg pool.
    Raises 503 if the database is not configured.
    """
    pool: asyncpg.Pool | None = getattr(request.app.state, "pool", None)
    if pool is None:
        raise HTTPException(
            status_code=503,
            detail="Database not configured. Set DATABASE_URL in .env and restart.",
        )
    return pool
