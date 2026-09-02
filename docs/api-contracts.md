# Local API Contracts

The browser and local clients share these FastAPI routes. Interactive schemas are available at
`/docs`; `src/econ_research/api.py` and its Pydantic response models are authoritative.
IDs are opaque. Clients must not derive filesystem paths from IDs or access runtime files directly.
This is a local application API, not an authenticated public deployment interface.

## Route reference

Unless noted otherwise, successful operations return HTTP `200` with JSON.

| Method | Route | Response or purpose |
| --- | --- | --- |
| `GET` | `/health` | `{"status":"ok"}`; liveness only, not a database/model/GPU readiness check |
| `GET` | `/api/ui-version` | Launcher compatibility marker; not a Git commit or package version |
| `POST` | `/api/papers` | Synchronous PDF ingest; `IngestResult` |
| `POST` | `/api/uploads` | Queue a PDF; `202` with `IngestJob` |
| `GET` | `/api/uploads` | Recent upload jobs; `active_only=true` by default |
| `GET` | `/api/uploads/{job_id}` | One `IngestJob` |
| `GET` | `/api/uploads/{job_id}/events` | Recent `IngestJobEvent` timeline |
| `GET` | `/api/papers` | Papers; `include_archived=false` by default |
| `GET` | `/api/papers/{paper_id}` | One `Paper` |
| `PATCH` | `/api/papers/{paper_id}` | Update manual metadata; `Paper` |
| `POST` | `/api/papers/{paper_id}/reparse` | Local reparse; `ReparseResult` |
| `POST` | `/api/papers/{paper_id}/card-generations` | Billable regeneration; `CardGeneration` |
| `GET` | `/api/papers/{paper_id}/card-generations` | Generation history |
| `GET` | `/api/papers/{paper_id}/cards` | One paper's cards |
| `GET` | `/api/cards` | Cards across papers |
| `GET` | `/api/papers/{paper_id}/chunks` | Ordered `SourceChunk` records |
| `GET` | `/api/papers/{paper_id}/formula-attempts` | `FormulaAttempt` diagnostics |
| `GET` | `/api/papers/{paper_id}/formulas/{formula_ordinal}/crop` | Retained failed-formula PNG |
| `GET` | `/api/search` | Search results; required `q`, optional `limit` |
| `POST` | `/api/papers/{paper_id}/deep-read` | Billable report; `DeepReadResult` |
| `GET` | `/api/papers/{paper_id}/deep-reads` | `DeepReadSummary` history |
| `GET` | `/api/deep-reads/{deep_read_id}` | Stored `DeepReadResult` |
| `GET` | `/api/deep-reads/{deep_read_id}/download` | Markdown attachment |
| `GET` | `/api/usage` | `UsageReport` |
| `GET` | `/api/papers/{paper_id}/usage` | Paper-scoped `UsageReport` |
| `DELETE` | `/api/papers/{paper_id}` | Soft archive; `Paper` |
| `POST` | `/api/papers/{paper_id}/restore` | Restore archive; `Paper` |
| `DELETE` | `/api/papers/{paper_id}/purge` | Permanent removal; `204` with no body |
| `GET` | `/api/papers/{paper_id}/files/original` | Original PDF |
| `GET` | `/api/papers/{paper_id}/files/parsed` | Parsed Markdown attachment |

## Paper metadata and provenance

`PATCH` accepts either or both fields, for example `{"title":"Revised title","year":2020}`.
Titles are normalized to 1–300 characters; years must be 1000–2100 or `null` to clear the year.
Omitted fields remain unchanged. Each supplied field records a manual source and survives reparse.

A `Paper` separates parse `status` from `card_status`. A ready paper can have failed cards;
an upload can succeed while card generation fails. Formula counts/status report the last parse,
not a guarantee of mathematical correctness. See [workflow state transitions](workflows.md).

Legacy `pdf_path` and `markdown_path` fields remain in the paper response for compatibility.
Browser clients must treat them as opaque metadata and use the managed file endpoints.

Card lists accept `type`, `claim_kind` and `limit` (default 200, range 1–500).
The cross-paper route additionally accepts `paper_id`. A persisted card looks like:

~~~json
{
  "id": "opaque-card-id",
  "paper_id": "opaque-paper-id",
  "chunk_id": "opaque-chunk-id",
  "chunk_ordinal": 6,
  "type": "identification",
  "title": "Why a correlation may not be causal",
  "content": "Review the source passage before interpreting the association.",
  "section": "Identification",
  "page_start": null,
  "page_end": null,
  "tags": ["endogeneity"],
  "claim_kind": "author_claim",
  "created_at": "2026-09-02T12:00:00+00:00"
}
~~~

`chunk_ordinal` maps to `ordinal` in the chunk response. Ordinals are zero-based; page numbers
are one-based when known and nullable otherwise. Draft card types, claim kinds and constraints
are defined in [LLM output contracts](llm-output-schema.md); persisted cards add IDs and timestamps.

## Uploads and progress

Both upload routes accept one multipart `file` field, require a `.pdf` filename and limit the
stream to 100 MiB. Synchronous ingest waits for processing and returns `paper`, `chunk_count`,
`card_count`, `duplicate` and `possible_duplicate_of`.

The queued route returns after transfer/staging, not after parsing. Poll while `status` is
`queued` or `running`; terminal values are `succeeded`, `failed` and `interrupted`.
The single-worker queue persists progress. Job listing returns up to 50 recent jobs, newest
first; set `active_only=false` to include terminal jobs.

~~~json
{
  "id": "opaque-job-id",
  "source_filename": "paper.pdf",
  "status": "running",
  "stage": "parsing",
  "progress": 25,
  "paper_id": null,
  "duplicate_of": null,
  "message": "Parsing the PDF; first use may prepare local models.",
  "error": null,
  "created_at": "2026-09-02T12:00:00+00:00",
  "updated_at": "2026-09-02T12:00:10+00:00",
  "started_at": "2026-09-02T12:00:01+00:00",
  "completed_at": null
}
~~~

Messages here are illustrative English text. Actual messages may be localized: display them,
but do not parse their wording as machine state. `stage` is a descriptive string, separate from
the status enum. Progress is bounded to 0–100 but is not a measured percentage of remaining work.
Long opaque calls emit a ten-second liveness heartbeat.

The event endpoint returns the most recent 50 events, arranged oldest-to-newest within that
window; it is not the complete upload log.

~~~json
{
  "id": 42,
  "job_id": "opaque-job-id",
  "stage": "formula_ocr",
  "progress": 65,
  "message": "Recognizing formula 3 of 8.",
  "created_at": "2026-09-02T12:01:10+00:00"
}
~~~

An exact hash match to an already-ready paper reuses it. A failed exact match can be retried;
an already-processing match is rejected. Different PDFs may produce a DOI/text duplicate hint,
but are not automatically merged. The synchronous hint field is `possible_duplicate_of`;
the upload job uses `duplicate_of`. Startup recovery marks unfinished jobs interrupted; it
does not replay them automatically. See [workflows](workflows.md) before interpreting recovery.

## Reparse and card generation

Reparse updates derived Markdown, chunks, provenance and formula diagnostics from the preserved
PDF without an LLM call. Its response contains `paper`, `chunk_count` and `reconnected_card_count`.
Existing card text remains unchanged; ordinal-based reconnection does not prove that a passage
kept the same meaning. Reparse is a mutation, not a read-only diagnostic or an atomic filesystem/
database transaction.

Card generation waits for a new model attempt using current chunks. The response contains
`id`, `paper_id`, `status`, `card_count`, `error`, `created_at` and `completed_at`.
Generation states are `running`, `succeeded` and `failed`. Handled provider/validation failures
return HTTP `200` with `status="failed"`: clients must inspect the body. They leave the parsed
paper available and preserve previous cards. A successful generation replaces the current set.
History is returned newest-first.

## Formula diagnostics and crops

`FormulaAttempt` describes an attempted crop strategy, bounded output, validation and selection:

~~~json
{
  "formula_ordinal": 0,
  "page_no": 3,
  "crop_name": "standard",
  "scale": 2.0,
  "padding": 8,
  "raw_output": "y = x",
  "normalized_output": "y = x",
  "validation_status": "validated",
  "error_code": null,
  "error_message": null,
  "selected": true,
  "crop_filename": null
}
~~~

`formula_ordinal` is zero-based, `page_no` is one-based, `scale` is positive and `padding`
is nonnegative. Current status strings include `validated`, `rejected` and `error`; the field
is not a closed enum. Raw attempt output is truncated to 4,000 characters; exception messages
are bounded to 500. Normalized output and error fields can be null. Attempt rows are grouped
by formula ordinal; clients must not assume chronological ordering within one formula.

A missing/unavailable recognizer may produce no attempt rows. Failed validation can retain raw
OCR, then Docling text, then a crop/page marker as fallback; `partial` is not an import failure.
The crop endpoint returns only a retained crop, not every attempted crop. A nullable
`crop_filename` is diagnostic metadata, not a client-accessible filesystem path.
Reparse replaces the current diagnostics rather than appending a permanent attempt history.

## Deep reads, search and usage

Deep-read creation accepts a JSON body such as `{"focus":"Assess the identification strategy"}`
or `{}`. It returns `id`, `paper_id`, `focus`, `report` and `created_at`.
The history list uses previews of up to 240 characters; the detail/download routes retrieve
stored Markdown. GET routes never generate a new LLM report. Safe rendering is a
[frontend responsibility](frontend.md), not a change to the stored response format.

Search requires nonempty `q` and accepts `limit` (default 20, range 1–100). Results identify a
paper, chunk or card with `entity_type`, `entity_id`, `paper_id`, `title`, `snippet`, `rank`
and optional section/page provenance. Search is lexical, not semantic retrieval.

Usage accepts `operation`, `since` and `include_calls` (default false); the global route also
accepts `paper_id`. The report contains `summary` and nullable `calls`. Summary fields include
call counts, unpriced counts, tokens, duration and estimated USD cost. Estimates are stored
application telemetry, not an authoritative provider invoice; reading usage makes no model call.
See [runtime and cost boundaries](runtime-guide.md).

## Managed files and deletion

File handlers resolve a stored record, restrict it to the configured managed directory and check
existence. There is no arbitrary file-path parameter or static mount for `data/`.

Archive retains files/history; restore reverses that visibility change. Permanent purge removes
managed files before deleting the paper and paper-owned database records. Upload jobs/events
survive with paper references cleared. A cleanup failure retains the paper record, but files
already removed are not rolled back. Retry tolerates missing files. On Windows, narrowly scoped
read-only attribute handling does not bypass unrelated permission failures.
See [storage and backup](data-storage.md) before permanent removal.

## Compatibility and errors

Clients must tolerate additive fields. Read status fields as well as HTTP status.

| Status | Meaning |
| --- | --- |
| `400` | Non-PDF filename; synchronous ingest validation failure; invalid usage filters |
| `413` | Upload exceeds 100 MiB |
| `422` | Invalid request schema, enum/limit or metadata update |
| `404` | Missing requested record/file; a workflow requiring a ready paper can also reject an unready paper this way |
| `409` | Managed-file path restriction or purge cleanup conflict; file cleanup errors include retry guidance |
| `500` | Unhandled workflow failures, including deep-read provider errors |

The `409` mapping belongs to managed-file/crop/download and purge handlers; it is not a promise
that every filesystem failure in every workflow is converted to `409`.
Queued processing errors are reported on the job after the initial `202`.
Handled card-generation failures use the failed generation response, including during ingest;
they do not necessarily produce an HTTP error or a failed upload. Detailed purge filesystem
errors are logged on the backend.
