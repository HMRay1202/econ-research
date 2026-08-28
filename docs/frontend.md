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
├── app.js       # API client, local view state, and DOM rendering
└── vendor/       # fixed-version Marked, DOMPurify, KaTeX, fonts, and license notices
```

`api.py` serves `index.html` at `/` and mounts the directory at `/assets`. `pyproject.toml`
includes these files as package data, so the installed `research serve` command works outside an
editable checkout as well.

## Current product surface

- Single or batch PDF upload with browser transfer progress and persisted local task-stage output.
- Card-generation retry: a parsed paper remains available if the billable Luna call fails.
- Paper list and paper detail metadata.
- Card browsing, type filtering, text filtering, and source-chunk inspection.
- Cross-paper FTS5 search.
- Safe original-PDF and parsed-Markdown access.
- On-demand Terra deep reads with an explicit cost confirmation.
- Deep-read history, report display, and Markdown download.
- Global and per-paper token, latency, estimated-cost, and status-history views.
- Soft remove and restore for papers; the library toggle reveals removed entries without exposing
  managed file paths or permanently deleting research materials.
- A selected paper can be renamed or have its year edited through **修改标题** and **修改年份**.
  Each change is marked as manual, updates library search, and remains in place if the source PDF
  is reparsed.
- **重新解析公式** retries the non-billable parser pipeline from the preserved original PDF; users
  explicitly regenerate cards afterward if the revised text should become LLM input.

Most dynamic strings are assigned through `textContent`. Deep-read reports and source chunks are
the deliberate exception: the shared `renderMarkdown` helper first parses local Markdown with
Marked, removes raw HTML, sanitizes the resulting document with DOMPurify, then renders LaTeX
delimiters with local KaTeX. It allows only document-oriented Markdown elements and safe
`http`, `https`, and `mailto` links; scripts, event attributes, forms, iframes, SVG, images, and
embedded media are not rendered. Do not bypass this helper with `innerHTML`.

The web package includes fixed-version third-party assets under `web/vendor/`, so rendering does
not require a CDN, Node build, or network connection. KaTeX uses `throwOnError: false` and
`trust: false`: malformed parser/OCR LaTeX remains visible instead of breaking a report, and
untrusted formula commands cannot opt into privileged output. Before Markdown parsing, the helper
temporarily preserves `\\[...\\]` and `\\(...\\)` delimiters because ordinary Markdown would otherwise
treat their backslashes as escapes before KaTeX sees them.

### Markdown and mathematics rendering

Rendering is presentation-only and applies only to a displayed deep-read report and to the source
chunk dialog. Card titles/content and other UI strings continue to use `textContent`. The renderer
accepts GitHub-flavored Markdown and recognizes `$...$`, `$$...$$`, `\\(...\\)`, and `\\[...\\]` LaTeX
delimiters. Display equations can scroll horizontally on narrow screens rather than changing the
stored source text.

After sanitization and before mathematics rendering, a report reference in the form `[chunk N]`
becomes a button only when chunk `N` belongs to the paper currently loaded in the browser. Selecting
it opens that stored source chunk. References inside links, inline code, or code blocks remain plain
text. This is a client-side convenience only; it neither changes deep-read Markdown nor adds a
route or persistence contract.

The asset versions and license notices are recorded in `web/vendor/THIRD_PARTY_NOTICES.md`. Keep
these assets local and versioned together; do not replace them with a CDN URL or introduce a Node
build solely for Markdown rendering.

Upload jobs are server-side records. On page load, the client requests `GET /api/uploads` and
resumes polling queued or running jobs, so refreshing during parsing restores the visible backend
stage message instead of creating a replacement placeholder.

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

- Parser output prefers a credible PDF metadata title before layout extraction, preserves
  source-chunk page ranges, and uses a title-page OCR fallback when legacy PDF font mappings
  damage the title. With optional `.[formula]`, Docling formula boxes are cropped and passed to
  PaddleOCR Formula. Invalid, failed, or unavailable recognition keeps Docling text and records a
  formula error; the older `ECON_RESEARCH_FORMULA_ENRICHMENT=true` CodeFormula path remains
  experimental and opt-in. Dense body text remains Docling-native because full-page OCR can
  introduce new transcription errors; consult the original PDF for quotations.
- Cards cannot yet be edited, approved, or exported as a collection. Generation attempts are
  retained as history; the current card set is replaced only after a successful generation.
- Global cards can be filtered by paper, type, and claim kind, but tag normalization is deferred.
- Search is lexical FTS5 rather than semantic search.
- Deep reads and source chunks render safe Markdown and local KaTeX. Unvalidated formula OCR is
  displayed as fenced `latex` source code and intentionally excluded from KaTeX rendering; for a
  quotation or uncertain formula, consult the original PDF.
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
