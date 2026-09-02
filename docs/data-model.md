# Data Model

- `papers`: stable ID, SHA-256, source filename, managed PDF/Markdown paths, parser metadata,
  status, DOI, archive timestamp, and manually maintained title/year sources. Formula fields store
  the last parse's detected, recognized, fallback counts, status, and bounded diagnostic error.
- `chunks`: paper-owned normalized source passages and ordered Markdown table blocks with a stable
  ordinal, section, and optional page range. Reparse replaces these derived records and reconnects
  cards where possible.
- `cards`: paper-owned structured knowledge with optional chunk/page/section provenance. A
  successful regeneration replaces the current card set; prior generation attempts remain tracked.
- `card_generations`: status, timestamps, generated-card count, and error for every card
  generation attempt, including initial import and explicit regeneration or retry requests.
- `ingest_jobs`: local queued upload task, stage, progress, source filename, optional resulting
  paper/duplicate reference, timestamps, and error.
- `ingest_job_events`: persisted stage messages and liveness heartbeats for upload progress.
- `paper_sources`: associated source filenames, managed PDF paths, and source identity metadata.
- `formula_attempts`: bounded per-formula OCR output, crop strategy, validation result, selected
  attempt, and an optional managed crop filename for failed or low-confidence extraction. This
  preserves evidence without treating unvalidated text as executable mathematics.
- `deep_reads`: derived paper-specific reports with an optional focus.
- `llm_calls`: per-call operation, model, token totals, latency, status, request ID, and
  price-snapshot estimates.

FTS5 indexes paper metadata, chunks, and cards. Exact duplicate detection uses the preserved
source SHA-256; likely duplicates may be identified through DOI or normalized parsed text but are
never merged automatically. Foreign keys cascade only for an explicit permanent purge. Normal
library removal is a soft archive that retains managed files and history and can be restored.
Runtime records use UTC ISO-8601 timestamps; PDFs, parsed Markdown, databases, reports, upload
staging files, and model assets are ignored runtime data rather than version-controlled content.

The pending version adds `formula_attempts` and its index with `CREATE ... IF NOT EXISTS`; it does
not migrate paper/model directories or rewrite old stored paths. Existing papers acquire detailed
attempt records only after a new parse. On service startup, orphaned upload/card-generation state
is reconciled through the repository. No runtime database should be deleted to apply this update.
