PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS papers (
    id TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL UNIQUE,
    source_filename TEXT NOT NULL,
    pdf_path TEXT NOT NULL,
    markdown_path TEXT,
    title TEXT,
    title_source TEXT NOT NULL DEFAULT 'parser',
    authors_json TEXT NOT NULL DEFAULT '[]',
    year INTEGER,
    year_source TEXT NOT NULL DEFAULT 'parser',
    formula_detected INTEGER NOT NULL DEFAULT 0,
    formula_recognized INTEGER NOT NULL DEFAULT 0,
    formula_fallback INTEGER NOT NULL DEFAULT 0,
    formula_status TEXT NOT NULL DEFAULT 'not_run',
    formula_error TEXT,
    status TEXT NOT NULL CHECK (status IN ('processing', 'ready', 'failed')),
    card_status TEXT NOT NULL DEFAULT 'pending',
    doi TEXT,
    normalized_text_sha256 TEXT,
    archived_at TEXT,
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
    generation_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS paper_sources (
    id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    sha256 TEXT NOT NULL UNIQUE,
    source_filename TEXT NOT NULL,
    pdf_path TEXT NOT NULL,
    normalized_text_sha256 TEXT,
    doi TEXT,
    created_at TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS ingest_jobs (
    id TEXT PRIMARY KEY,
    source_filename TEXT NOT NULL,
    upload_path TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'interrupted')),
    stage TEXT NOT NULL,
    progress INTEGER NOT NULL DEFAULT 0,
    paper_id TEXT REFERENCES papers(id) ON DELETE SET NULL,
    duplicate_of TEXT REFERENCES papers(id) ON DELETE SET NULL,
    message TEXT NOT NULL DEFAULT '',
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS card_generations (
    id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
    card_count INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
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
CREATE INDEX IF NOT EXISTS idx_paper_sources_paper ON paper_sources(paper_id, created_at);
CREATE INDEX IF NOT EXISTS idx_ingest_jobs_created ON ingest_jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_card_generations_paper ON card_generations(paper_id, created_at);

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
