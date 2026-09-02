# Data Model

`SQLiteRepository` owns SQL and schema initialization. Definitions are in
`src/econ_research/db/schema.sql`; public representations are in `models.py`.
File placement and backup belong in [data storage](data-storage.md).

## Entities and relationships

| Entity | Contents and relationship |
| --- | --- |
| `papers` | Stable ID, unique source hash, managed paths, metadata overrides, parse/card/formula status, archive timestamp |
| `chunks` | Paper-owned text/table blocks; unique `(paper_id, ordinal)`, optional section and page range |
| `cards` | Current paper-owned cards; optional `chunk_id`, source metadata, generation ID |
| `paper_sources` | Paper-owned source identities and managed PDF paths |
| `formula_attempts` | Paper-owned crop strategy, OCR output, validation, selection and optional retained crop filename |
| `card_generations` | Paper-owned generation status, timestamps, count and error; not a full archive of every old card set |
| `deep_reads` | Paper-owned report text, focus and creation time |
| `llm_calls` | Paper-owned operation, measured usage, status, request ID and price snapshot |
| `ingest_jobs` | Upload state and staging path; optional paper and duplicate references |
| `ingest_job_events` | Job-owned progress messages and liveness events |
| `search_index` | FTS5 entries for papers, chunks and cards; maintained explicitly by repository methods |

Paper deletion cascades to chunks, cards, sources, formula attempts, card generations, deep reads
and calls. Cards' chunk references use `ON DELETE SET NULL`, then reparse reconnects where possible.
Upload paper/duplicate references also use `SET NULL`: their tasks and events can survive a paper
purge. Events cascade when their owning job is deleted. The FTS index is not an automatic FK cascade.

## Independent state fields

| Record/field | Current values and meaning |
| --- | --- |
| `Paper.status` | `processing`, `ready`, `failed`: document workflow outcome |
| `Paper.card_status` | `pending`, `generating`, `ready`, `failed`: current card-generation state |
| `Paper.archived_at` | Nullable timestamp, independent of parse and card status |
| `IngestJob.status` | `queued`, `running`, `succeeded`, `failed`, `interrupted` |
| `CardGeneration.status` | `running`, `succeeded`, `failed` |
| Formula attempt validation | `validated`, `rejected`, `error`; public field is currently a string, not a closed enum |

A ready paper may have failed cards. A succeeded upload may therefore need a card retry.
A generation failure does not erase earlier cards. Startup recovery closes orphaned generations
and reconciles the paper's card status based on retained cards. See [workflows](workflows.md).

Paper formula fields report detected/recognized/fallback counts, status and a bounded diagnostic.
Detailed attempts describe one parse, not an append-only history: reparse replaces them.
Crop ordinals are zero-based, page numbers one-based. Candidate metadata without a recognizer
attempt is not necessarily represented by a persisted attempt row.

## Updates and provenance

Reparse replaces derived chunks/search records, refreshes formula attempts and reconnects current
cards by ordinal; it preserves manual title/year overrides and card text. Ordinals are positions,
not permanent semantic identities. A successful card regeneration replaces current cards, while
generation metadata remains history.

Exact duplicate detection uses the source hash. DOI/text/title checks can produce a possible
duplicate hint, but do not merge records. Archive is reversible hiding; permanent purge follows
the separate managed-file workflow.

Timestamps are generated as UTC ISO-8601 strings. Runtime database/files remain private and ignored
by Git. Database records may contain legacy relative or absolute file paths; configuration changes
do not automatically rewrite them.

## Schema evolution

Initialization uses additive table/index creation and repository-managed additive column checks.
The implementation update `c331715` introduced `formula_attempts` and its index; it did not migrate
paper/model directories or backfill OCR attempts for old papers. Those appear on a later parse.

Incompatible changes need an explicit migration and backup plan. Never delete a user's database
to apply an update. Filesystem changes and SQLite transactions do not share atomic rollback.
