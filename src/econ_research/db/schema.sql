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

CREATE INDEX IF NOT EXISTS idx_chunks_paper ON chunks(paper_id, ordinal);
CREATE INDEX IF NOT EXISTS idx_cards_paper ON cards(paper_id);
CREATE INDEX IF NOT EXISTS idx_deep_reads_paper ON deep_reads(paper_id);

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

