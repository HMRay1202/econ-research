# Architecture

## Ownership and trust boundaries

~~~text
Browser -- HTTP /api/* --> FastAPI --+
                                   +--> ResearchService --> Parser
Typer CLI -------------------------+                    --> ResearchLLM
                                                        --> SQLiteRepository
~~~

The browser does not call the service directly, read SQLite, load environment secrets, or browse
runtime directories. FastAPI and Typer translate inputs/outputs; all research workflows belong to
`ResearchService`. The service owns an in-process, single-worker upload queue; there is no external
queue, database server, or second application backend.

The static client is packaged under `web/` with local rendering assets. Only that static directory
is mounted. File endpoints resolve opaque record IDs through the service and validate managed paths.
Some legacy `Paper` response fields contain stored paths; clients must not use them as file access
instructions. This is a loopback-only application, not a multi-user authorization system.

## Parsing and formula isolation

`Parser` produces a `ParsedDocument` with ordered chunks, page/section provenance, Markdown,
and formula diagnostics. Docling supplies native text/layout and ordered table blocks. The
standard formula path sends only detected crops to PaddleOCR; it does not replace all body text
with full-page OCR.

Only structurally accepted formula output becomes renderable LaTeX. When validation fails, the
pipeline prefers unvalidated OCR in a fenced code block, then retained Docling source, then a
crop/page marker when available. Missing dependencies preserve usable source rather than forcing
the entire parse to fail. Validation is heuristic, not a proof of mathematical correctness.

On Windows CUDA profiles, `paddle_process.py` starts `paddle_worker.py` through an isolated venv
without Torch. The worker reads crop/model requests over stdin and returns marked JSON responses
over stdout; stderr supplies diagnostics. It has no database or LLM access. Requests are serialized,
reuse a model during one parse, and time out after 300 seconds. Parse completion/failure closes the
worker; forced termination may bypass cleanup.

CPU Windows and macOS use the in-process Paddle path. The launcher policy selects libraries
before serving; device policy and package details live only in the [runtime guide](docs/runtime-guide.md).

## LLM and persistence

`ResearchLLM` receives source chunks through the service. The OpenAI adapter returns a domain result
and measured metadata, persisted as `llm_calls` with a price snapshot. Default model configuration
and network disclosure are in the runtime guide; response shapes are in
[LLM output](docs/llm-output-schema.md).

`SQLiteRepository` owns SQLite/FTS5 and all SQL. Filesystem writes and database transactions are
separate: ingest can retain a PDF or parsed content after a later stage fails. Startup recovery
marks orphaned uploads interrupted and unfinished card generations failed, without replaying calls.
Do not build another service against a live database solely for diagnostics.

Reparse replaces derived Markdown/chunks and formula attempt records, reconnects cards by ordinal
when possible, and never rewrites card text or calls an LLM. Ordinal reconnection is not a guarantee
that reordered source passages still have identical meaning; users should review changed provenance.

Permanent purge validates managed targets, removes diagnostics/files, then deletes the paper record
and associated records. File cleanup is not rolled back on failure. Windows read-only retry does
not grant ACL permissions or bypass sharing locks. Upload history can survive with null paper links.

Details belong in [workflows](docs/workflows.md), [data model](docs/data-model.md),
and [API contracts](docs/api-contracts.md). Scope remains governed by the [charter](PROJECT_CHARTER.md).
