# Local API Contracts

The browser UI and external local clients share these FastAPI routes. Interactive schemas and
validation details are available at `/docs`. All IDs are opaque strings; clients must not derive
filesystem paths from them.

## Existing workflow routes

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/health` | Local service health |
| `POST` | `/api/papers` | Upload and ingest one PDF |
| `POST` | `/api/uploads` | Queue one PDF upload and return a task record |
| `GET` | `/api/uploads/{job_id}` | Read upload, parse, and card-generation progress |
| `GET` | `/api/papers` | List papers |
| `GET` | `/api/papers/{paper_id}` | Get one paper |
| `PATCH` | `/api/papers/{paper_id}` | Set a manually maintained paper title |
| `POST` | `/api/papers/{paper_id}/reparse` | Reparse preserved PDF and retry local formula OCR without an LLM call |
| `GET` | `/api/search?q=...` | Search papers, cards, and chunks |
| `POST` | `/api/papers/{paper_id}/deep-read` | Run a billable Terra deep read |
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
`queued` or `running`.

```json
{
  "id": "opaque-job-id",
  "source_filename": "paper.pdf",
  "status": "running",
  "stage": "parsing",
  "progress": 25,
  "paper_id": null,
  "duplicate_of": null,
  "error": null
}
```

Exact SHA-256 matches return the existing paper. Different PDF files are also compared by DOI and
normalized parsed text; a possible match is returned in `duplicate_of` but is never merged or
overwritten automatically. Interrupted local jobs are marked `interrupted` so an exact re-upload
does not remain permanently blocked.

`POST /api/papers/{paper_id}/card-generations` runs a new billable Luna generation from existing
source chunks. `GET /api/papers/{paper_id}/card-generations` returns the generation history. A
card failure leaves the parsed paper available and sets `Paper.card_status` to `failed`.

`POST /api/papers/{paper_id}/reparse` refreshes Markdown, source chunks, page provenance, and
formula OCR from the managed original PDF. It does not call an LLM or regenerate cards. The
additive `formula_detected`, `formula_recognized`, `formula_fallback`, `formula_status`, and
`formula_error` paper fields report the last parse's formula handling; a failed or unavailable
formula recognizer keeps the original Docling text and never fails the complete paper import.

## Deep-read history routes

| Method | Route | Response |
|---|---|---|
| `GET` | `/api/papers/{paper_id}/deep-reads` | Lightweight history with 240-character previews |
| `GET` | `/api/deep-reads/{deep_read_id}` | Complete stored report |
| `GET` | `/api/deep-reads/{deep_read_id}/download` | Markdown attachment |

The `POST` route creates a new report; the `GET` routes never call an LLM.

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
- Invalid enum filters or limits return FastAPI validation errors (`422`).
- LLM/provider failures from synchronous ingestion or deep read remain workflow errors (`500`) and
  are recorded in telemetry when an API attempt occurred. Queued upload failures are reported on
  their task record instead of holding one browser request open.
