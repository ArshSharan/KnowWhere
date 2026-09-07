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
    Convert a SQLAlchemy-style or Supabase URL to a sanitized asyncpg URL.
    - Strips dialect suffix '+asyncpg'
    - Strips outer quotes and bracket notation
    - URL-encodes special characters in passwords
    """
    import re
    from urllib.parse import quote_plus, unquote

    url = database_url.strip().strip('"').strip("'")
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    url = re.sub(r'\[([^\]]+)\]', r'\1', url)

    m = re.match(
        r'^(?P<scheme>[^:]+)://(?P<user>[^:]+):(?P<password>.+)@(?P<host>[^:/]+)(:(?P<port>\d+))?/(?P<dbname>.+)$',
        url
    )
    if m:
        d = m.groupdict()
        user = d['user']
        password = quote_plus(unquote(d['password']))
        host = d['host']
        port = d['port'] or "5432"
        dbname = d['dbname']
        return f"{d['scheme']}://{user}:{password}@{host}:{port}/{dbname}"

    return url


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
                ssl="require",          # Supabase requires SSL
                statement_cache_size=0, # Required for PgBouncer / Supabase Pooler compatibility
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
