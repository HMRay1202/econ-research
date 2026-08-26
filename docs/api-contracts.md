# Local API Contracts

The browser UI and external local clients share these FastAPI routes. Interactive schemas and
validation details are available at `/docs`. All IDs are opaque strings; clients must not derive
filesystem paths from them.

## Existing workflow routes

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/health` | Local service health |
| `POST` | `/api/papers` | Upload and ingest one PDF |
| `GET` | `/api/papers` | List papers |
| `GET` | `/api/papers/{paper_id}` | Get one paper |
| `GET` | `/api/search?q=...` | Search papers, cards, and chunks |
| `POST` | `/api/papers/{paper_id}/deep-read` | Run a billable Terra deep read |
| `GET` | `/api/usage` | Aggregate or detailed LLM usage |
| `GET` | `/api/papers/{paper_id}/usage` | Paper-scoped LLM usage |

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
- LLM/provider failures from ingestion or deep read remain workflow errors (`500`) and are
  recorded in telemetry when an API attempt occurred.
