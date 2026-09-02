# Local API Contracts

The browser UI and external local clients share these FastAPI routes. Interactive schemas and
validation details are available at `/docs`. All IDs are opaque strings; clients must not derive
filesystem paths from them.

## Existing workflow routes

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/health` | Local service health |
| `GET` | `/api/ui-version` | Version marker used by local launchers to distinguish this UI from an older running service |
| `POST` | `/api/papers` | Upload and ingest one PDF |
| `POST` | `/api/uploads` | Queue one PDF upload and return a task record |
| `GET` | `/api/uploads` | List persisted active upload tasks for page-refresh recovery |
| `GET` | `/api/uploads/{job_id}` | Read upload, parse, and card-generation progress |
| `GET` | `/api/uploads/{job_id}/events` | Read the persisted backend activity timeline for one upload |
| `GET` | `/api/papers` | List papers |
| `GET` | `/api/papers/{paper_id}` | Get one paper |
| `PATCH` | `/api/papers/{paper_id}` | Set manually maintained paper title and/or year |
| `POST` | `/api/papers/{paper_id}/reparse` | Reparse preserved PDF and retry local formula OCR without an LLM call |
| `POST` | `/api/papers/{paper_id}/card-generations` | Billably regenerate cards from current chunks |
| `GET` | `/api/papers/{paper_id}/card-generations` | List card-generation history |
| `GET` | `/api/papers/{paper_id}/cards` | List one paper's cards |
| `GET` | `/api/cards` | List cards across papers |
| `GET` | `/api/papers/{paper_id}/chunks` | List ordered source chunks |
| `GET` | `/api/papers/{paper_id}/formula-attempts` | List bounded formula-OCR diagnostics |
| `GET` | `/api/papers/{paper_id}/formulas/{formula_ordinal}/crop` | Read a preserved failed-formula crop |
| `GET` | `/api/search?q=...` | Search papers, cards, and chunks |
| `POST` | `/api/papers/{paper_id}/deep-read` | Run a billable Terra deep read |
| `GET` | `/api/papers/{paper_id}/deep-reads` | List deep-read history |
| `GET` | `/api/deep-reads/{deep_read_id}` | Get one stored deep read |
| `GET` | `/api/deep-reads/{deep_read_id}/download` | Download one deep read as Markdown |
| `GET` | `/api/usage` | Aggregate or detailed LLM usage |
| `GET` | `/api/papers/{paper_id}/usage` | Paper-scoped LLM usage |
| `DELETE` | `/api/papers/{paper_id}` | Soft-archive a paper while retaining managed files and history |
| `POST` | `/api/papers/{paper_id}/restore` | Restore an archived paper |
| `DELETE` | `/api/papers/{paper_id}/purge` | Permanently remove a paper and its managed files/history |

`PATCH /api/papers/{paper_id}` accepts either or both of `{ "title": "...", "year": 2020 }`.
Titles are normalized to 1–300 characters; years are limited to 1000–2100 and may be `null` to
clear a previously inferred year. Each field records an independent manual source and is preserved
when the paper is reparsed.

## Card and provenance routes

`GET /api/cards` lists cards across papers. Optional filters are `paper_id`, `type`,
`claim_kind`, and `limit` (1–500).

`GET /api/papers/{paper_id}/cards` returns the same card representation scoped to one paper and
accepts `type`, `claim_kind`, and `limit`.

```json
{
  "id": "opaque-card-id",
  "paper_id": "opaque-paper-id",
  "chunk_id": "opaque-chunk-id",
  "chunk_ordinal": 6,
  "type": "identification",
  "title": "Why simple monetary correlations are not causal",
  "content": "...",
  "section": "2.1.2 Evidence of Monetary Policy Non-Neutralities",
  "page_start": null,
  "page_end": null,
  "tags": ["endogeneity", "causal-inference"],
  "claim_kind": "author_claim",
  "created_at": "2026-08-26T21:04:06.082247+00:00"
}
```

`GET /api/papers/{paper_id}/chunks` returns ordered source chunks. `chunk_ordinal` on a card maps
to `ordinal` in this response. Page fields remain nullable.

## Upload tasks and card regeneration

`POST /api/uploads` accepts the same multipart `file` field as the legacy synchronous ingest
route, but returns `202` after browser transfer. The local single-worker queue validates,
deduplicates, parses, and generates cards; poll `GET /api/uploads/{job_id}` while status is
`queued` or `running`. `GET /api/uploads` returns persisted active tasks by default, so a browser
refresh can restore progress display. `message` is the latest human-readable backend update and
`updated_at` records when it was written. Concrete parser steps are persisted as events; during a
long-running opaque model call, the service emits a ten-second liveness heartbeat instead of
inventing a page-level percentage.

```json
{
  "id": "opaque-job-id",
  "source_filename": "paper.pdf",
  "status": "running",
  "stage": "parsing",
  "progress": 25,
  "paper_id": null,
  "duplicate_of": null,
  "message": "正在读取并解析 PDF；首次运行可能准备本地模型。",
  "updated_at": "2026-08-27T12:00:00+00:00",
  "error": null
}
```

`GET /api/uploads/{job_id}/events` returns the oldest-to-newest persisted events (up to 50). Each
event has the additive representation below, allowing the browser to restore a detailed activity
timeline after refresh.

```json
{
  "id": 42,
  "job_id": "opaque-job-id",
  "stage": "formula_ocr",
  "progress": 65,
  "message": "正在使用 PaddleOCR 识别公式：3/8。",
  "created_at": "2026-08-27T12:01:10+00:00"
}
```

Exact SHA-256 matches return the existing paper. Different PDF files are also compared by DOI and
normalized parsed text; a possible match is returned in `duplicate_of` but is never merged or
overwritten automatically. Interrupted local jobs are marked `interrupted` so an exact re-upload
does not remain permanently blocked.

`POST /api/papers/{paper_id}/card-generations` runs a new billable Luna generation from existing
source chunks. `GET /api/papers/{paper_id}/card-generations` returns the generation history. A
card failure leaves the parsed paper available and sets `Paper.card_status` to `failed`; a later
successful run replaces its current card set.

`POST /api/papers/{paper_id}/reparse` refreshes Markdown, source chunks, page provenance, and
formula OCR from the managed original PDF. It does not call an LLM or regenerate cards. The
additive `formula_detected`, `formula_recognized`, `formula_fallback`, `formula_status`, and
`formula_error` paper fields report the last parse's formula handling; a failed or unavailable
formula recognizer keeps the original Docling text and never fails the complete paper import.

Every detected formula preserves one of: validated LaTeX, unvalidated raw OCR, Docling source
text, or a retained crop/page marker. `GET /api/papers/{paper_id}/formula-attempts` returns bounded
attempt output, crop strategy, validation status, and selection information. The crop route accepts
only opaque paper identity plus a formula ordinal; it never accepts a filesystem path and returns
`404` if no crop was retained.

## Deep-read history routes

| Method | Route | Response |
|---|---|---|
| `GET` | `/api/papers/{paper_id}/deep-reads` | Lightweight history with 240-character previews |
| `GET` | `/api/deep-reads/{deep_read_id}` | Complete stored report |
| `GET` | `/api/deep-reads/{deep_read_id}/download` | Markdown attachment |

The `POST` route creates a new report; the `GET` routes never call an LLM. The local web client
renders report Markdown and source chunks with packaged sanitizer and KaTeX assets; these routes
continue to return the original Markdown string, so rendering does not change the API
representation.

## Managed file routes

| Method | Route | Content |
|---|---|---|
| `GET` | `/api/papers/{paper_id}/files/original` | Original PDF |
| `GET` | `/api/papers/{paper_id}/files/parsed` | Parsed Markdown attachment |

The service resolves the stored record, verifies that its file remains inside the configured
managed directory, and verifies that it exists. There is intentionally no arbitrary file-path
parameter and no static mount for `data/`.

## Compatibility and errors

- Additive response fields are allowed; avoid removing or renaming existing fields.
- Missing paper, report, or managed file returns `404`.
- A stored path outside its managed directory returns `409`.
- A file lock or permission error during permanent purge returns `409` with retry guidance. The
  paper record is retained until all managed-file cleanup succeeds; retries tolerate files already
  removed by an earlier partial cleanup.
  On Windows, read-only managed entries are retried after clearing only that attribute; unrelated
  access errors remain failures. Detailed filesystem errors are logged only on the backend.
- Invalid enum filters or limits return FastAPI validation errors (`422`).
- LLM/provider failures from synchronous ingestion or deep read remain workflow errors (`500`) and
  are recorded in telemetry when an API attempt occurred. Queued upload failures are reported on
  their task record instead of holding one browser request open.
