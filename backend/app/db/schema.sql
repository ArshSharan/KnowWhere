-- ============================================================
-- KnowWhere — Database Schema
-- Run this in the Supabase SQL Editor (Dashboard → SQL Editor)
-- ============================================================

-- 1. Extensions
CREATE EXTENSION IF NOT EXISTS vector;          -- pgvector (needed for Phase 2 embeddings)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";     -- for uuid generation fallback

-- ============================================================
-- 2. Core tables
-- ============================================================

CREATE TABLE IF NOT EXISTS documents (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT,
    doc_type        TEXT,                        -- inferred by LLM, not hard-coded
    publisher       TEXT,
    as_of_date      DATE,
    source_uri      TEXT,                        -- Cloudflare R2 object key (Phase 3)
    content_hash    TEXT        UNIQUE NOT NULL, -- SHA-256 of PDF bytes; idempotency key
    status          TEXT        NOT NULL DEFAULT 'pending',
                                                 -- pending | processing | done | failed
                                                 -- may contain progress like "extracting: 12/48"
    page_count      INTEGER,
    facts_count     INTEGER     DEFAULT 0,
    error_message   TEXT,                        -- set on failure
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS entities (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name  TEXT        NOT NULL UNIQUE,
    aliases         TEXT[]      NOT NULL DEFAULT '{}',
    embedding       vector(1536),                -- populated in Phase 2
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fact_types (
    id                        UUID  PRIMARY KEY DEFAULT gen_random_uuid(),
    label                     TEXT  NOT NULL UNIQUE,
    description               TEXT,
    embedding                 vector(1536),      -- populated in Phase 2
    example_qualifiers_schema JSONB DEFAULT '{}',
    created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS facts (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id         UUID        NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    entity_id           UUID        NOT NULL REFERENCES entities(id),
    fact_type_id        UUID        NOT NULL REFERENCES fact_types(id),
    attribute           TEXT        NOT NULL,
    value               TEXT        NOT NULL,
    value_type          TEXT        NOT NULL,   -- number|date|string|enum|boolean
    unit                TEXT,
    period_start        DATE,
    period_end          DATE,
    as_of_date          DATE,
    fiscal_year         TEXT,                   -- e.g. "FY24", "2024-25"
    qualifiers          JSONB       DEFAULT '{}',
    verbatim_quote      TEXT        NOT NULL,
    page_number         INTEGER     NOT NULL,
    evidence_confidence TEXT        NOT NULL DEFAULT 'high', -- high|low
    confidence          FLOAT       NOT NULL DEFAULT 1.0,
    embedding           vector(1536),            -- populated in Phase 2
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fact_relationships (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    fact_a_id    UUID        NOT NULL REFERENCES facts(id) ON DELETE CASCADE,
    fact_b_id    UUID        NOT NULL REFERENCES facts(id) ON DELETE CASCADE,
    relationship TEXT        NOT NULL,  -- corroborates|contradicts|reconciled_by_context|unrelated
    basis        TEXT        NOT NULL DEFAULT 'none',
                                        -- time_period|scope|units|rounding|restatement|none
    explanation  TEXT        NOT NULL,
    confidence   FLOAT       NOT NULL DEFAULT 1.0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(fact_a_id, fact_b_id)
);

-- ============================================================
-- 3. Indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_facts_document_id    ON facts(document_id);
CREATE INDEX IF NOT EXISTS idx_facts_entity_id      ON facts(entity_id);
CREATE INDEX IF NOT EXISTS idx_facts_fact_type_id   ON facts(fact_type_id);
CREATE INDEX IF NOT EXISTS idx_documents_hash       ON documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_fr_fact_a            ON fact_relationships(fact_a_id);
CREATE INDEX IF NOT EXISTS idx_fr_fact_b            ON fact_relationships(fact_b_id);

-- HNSW vector indexes (uncomment after Phase 2 embeddings are populated):
-- CREATE INDEX idx_facts_embedding    ON facts    USING hnsw (embedding vector_cosine_ops);
-- CREATE INDEX idx_entities_embedding ON entities USING hnsw (embedding vector_cosine_ops);
-- CREATE INDEX idx_ft_embedding       ON fact_types USING hnsw (embedding vector_cosine_ops);
