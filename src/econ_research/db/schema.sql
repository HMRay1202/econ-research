PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS papers (
    id TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL UNIQUE,
    source_filename TEXT NOT NULL,
    pdf_path TEXT NOT NULL,
    markdown_path TEXT,
    title TEXT,
    authors_json TEXT NOT NULL DEFAULT '[]',
    year INTEGER,
    status TEXT NOT NULL CHECK (status IN ('processing', 'ready', 'failed')),
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    text TEXT NOT NULL,
    section TEXT,
    page_start INTEGER,
    page_end INTEGER,
    UNIQUE (paper_id, ordinal)
);

CREATE TABLE IF NOT EXISTS cards (
    id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    chunk_id TEXT REFERENCES chunks(id) ON DELETE SET NULL,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    section TEXT,
    page_start INTEGER,
    page_end INTEGER,
    tags_json TEXT NOT NULL DEFAULT '[]',
    claim_kind TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS deep_reads (
    id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    focus TEXT,
    report TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS llm_calls (
    id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    operation TEXT NOT NULL CHECK (operation IN ('generate_cards', 'deep_read')),
    provider_request_id TEXT,
    model TEXT NOT NULL,
    reasoning_effort TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    cached_input_tokens INTEGER NOT NULL DEFAULT 0,
    cache_write_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    reasoning_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    input_price_per_million REAL,
    cached_input_price_per_million REAL,
    cache_write_price_per_million REAL,
    output_price_per_million REAL,
    estimated_cost_usd REAL,
    duration_ms INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('succeeded', 'failed')),
    error TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunks_paper ON chunks(paper_id, ordinal);
CREATE INDEX IF NOT EXISTS idx_cards_paper ON cards(paper_id);
CREATE INDEX IF NOT EXISTS idx_deep_reads_paper ON deep_reads(paper_id);
CREATE INDEX IF NOT EXISTS idx_llm_calls_paper ON llm_calls(paper_id, started_at);
CREATE INDEX IF NOT EXISTS idx_llm_calls_operation ON llm_calls(operation, started_at);

CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
    entity_type UNINDEXED,
    entity_id UNINDEXED,
    paper_id UNINDEXED,
    title,
    content,
    section UNINDEXED,
    page_start UNINDEXED,
    page_end UNINDEXED,
    tokenize = 'unicode61 remove_diacritics 2'
);
