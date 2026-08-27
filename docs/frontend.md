# Local Web Frontend

## Purpose and boundaries

The local frontend is a thin client for the existing FastAPI application. It is deliberately
implemented with plain HTML, CSS, and JavaScript so it adds no Node build, frontend framework,
authentication, cloud deployment, or parallel business-logic layer. The browser must use
documented `/api/*` endpoints; it must never read SQLite, runtime paths, `.env`, or an API key.

Start it with:

```bash
conda run -n econ-research research serve
```

Open `http://127.0.0.1:8000/`. Keep the default loopback host for private local use. The API
console remains available at `http://127.0.0.1:8000/docs`.

## Source layout

```text
src/econ_research/web/
├── index.html   # stable page regions and accessible controls
├── styles.css   # responsive presentation; no generated CSS
└── app.js       # API client, local view state, and DOM rendering
```

`api.py` serves `index.html` at `/` and mounts the directory at `/assets`. `pyproject.toml`
includes these files as package data, so the installed `research serve` command works outside an
editable checkout as well.

## Current product surface

- PDF upload. Ingest automatically invokes Luna card generation and can incur cost.
- Paper list and paper detail metadata.
- Card browsing, type filtering, text filtering, and source-chunk inspection.
- Cross-paper FTS5 search.
- Safe original-PDF and parsed-Markdown access.
- On-demand Terra deep reads with an explicit cost confirmation.
- Deep-read history, report display, and Markdown download.
- Global and per-paper token, latency, and estimated-cost views.

Dynamic strings are assigned through `textContent`; do not render model or PDF-derived content
with `innerHTML`. The UI uses same-origin requests, so CORS is neither needed nor enabled.

## Extension rules

1. Add persistence reads or writes to `SQLiteRepository` first.
2. Expose the use case through `ResearchService`.
3. Define public Pydantic response models in `models.py`.
4. Add or extend an `/api/*` route and document it in `api-contracts.md`.
5. Consume only that API from `web/app.js`.
6. Add API/service tests before changing the visual surface.

Do not import repository code into `api.py` or duplicate query logic in JavaScript. Preserve
existing response fields when adding features. A future React/Vue/Svelte client can replace the
contents of `web/` without changing the service and repository layers as long as the API contracts
remain compatible.

## Known limitations and good next changes

- Parser output now preserves source-chunk page ranges and uses a title-page OCR fallback when
  legacy PDF font mappings damage the title. Dense body text remains Docling-native because
  full-page OCR can introduce new transcription errors; users should consult the original PDF
  for verbatim quotations.
- Cards cannot yet be edited, approved, versioned, or exported as a collection.
- Global cards can be filtered by paper, type, and claim kind, but tag normalization is deferred.
- Search is lexical FTS5 rather than semantic search.
- Deep-read Markdown is displayed as safe plain text rather than rendered HTML.
- The UI has no user accounts because it is intended for loopback-only use.

Good independent additions are card export, a cross-paper comparison tray, targeted body-text
normalization with confidence checks, and optional semantic search. Keep each behind a service method and additive API so
parallel work does not couple to the current frontend implementation.

## Verification

```bash
conda run -n econ-research ruff check .
conda run -n econ-research pytest
conda run -n econ-research research serve
```

Verify `/`, `/assets/app.js`, `/health`, `/api/papers`, and one paper's cards without invoking an
LLM. A real deep-read UI test is billable and should run only when explicitly authorized.
