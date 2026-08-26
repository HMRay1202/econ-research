# Data Model

- `papers`: stable ID, SHA-256, source filename, stored PDF/Markdown paths, metadata, status.
- `chunks`: paper-owned normalized source passages with ordinal, section, and optional pages.
- `cards`: paper-owned structured knowledge with optional chunk/page/section provenance.
- `deep_reads`: derived paper-specific reports with an optional focus.
- `llm_calls`: per-call model, token, latency, status, request ID, and price-snapshot estimates.

FTS5 indexes paper metadata, chunks, and cards. Foreign keys use cascading deletion internally,
although Phase 1 exposes no delete workflow. Runtime records use UTC ISO-8601 timestamps.
