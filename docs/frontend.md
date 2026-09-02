# Local Web Frontend

## Boundary and source layout

The browser is a thin plain-HTML/CSS/JavaScript client. It calls documented `/api/*` routes and
does not own persistence or research logic. It must not read SQLite, environment secrets or
arbitrary runtime paths. See [API contracts](api-contracts.md) before changing requests.

`web/index.html` supplies page regions; `app.js` owns client state and rendering; `styles.css`
owns presentation. Fixed-version Marked, DOMPurify, KaTeX, fonts and license notices live under
`web/vendor/`. FastAPI serves `/` and mounts only those assets at `/assets`, not `data/`.
Assets are package data; no Node build or rendering CDN is required.

Startup instructions belong in the [README](../README.md) and [runtime guide](runtime-guide.md).

## User interactions

- Single/batch upload, task-stage progress and restoration of active tasks on refresh.
- Paper listing, card filtering, source-chunk inspection and local search.
- Original PDF and parsed Markdown access through managed file routes.
- Separate card-generation retry and non-billable reparse.
- Manual title/year overrides preserved during reparse.
- Archive/restore and explicitly confirmed permanent deletion.
- Billable deep-read requests, report history/download and usage views.

On purge failure, keep the selected paper and show the service error. Do not hide it optimistically
before the DELETE request succeeds. Archive and purge must remain visibly different operations.

Upload completion and card-generation success are distinct; a ready parsed paper can need a card
retry. Restore persisted jobs via `GET /api/uploads` rather than creating fake paper placeholders.
State semantics live in [workflows](workflows.md), not in a second client-side implementation.

## Safe rendering

Ordinary strings, including card titles, use `textContent`. Card content, source chunks and
deep-read reports use one shared `renderMarkdown` path:

1. Preserve math delimiters needed across Markdown parsing.
2. Parse with local Marked, remove raw HTML and sanitize with DOMPurify.
3. Render math with local KaTeX using `trust: false` and `throwOnError: false`.
4. Replace remaining KaTeX error nodes with text-only unvalidated LaTeX and a source-PDF reminder.

Allow only document-oriented elements and safe HTTP/HTTPS/mailto links. Scripts, event handlers,
forms, iframes, SVG, images and embedded media are not rendered. Do not bypass the helper with
unsanitized `innerHTML`.

Recognize `$...$`, `$$...$$`, `\(...\)` and `\[...\]`. Fenced/inline code stays non-rendered.
Wide display equations can scroll rather than alter stored source. Unvalidated OCR is evidence,
not executable mathematics, and should remain code rather than forced KaTeX output.

A `[chunk N]` reference becomes a source button only for a known chunk in the current paper.
References inside links or code remain text. This presentation feature does not alter report
Markdown or add a persistence contract.

## Testing and extension

Add service/API tests before extending the visual surface. Cover failure states, nullable
provenance, additive fields, retained selection on failed deletion, and the shared rendering path.
Source-level assertions are useful but do not replace native browser regression checks with
malformed formulas, Markdown and untrusted HTML.

Keep third-party assets and [license notices](../src/econ_research/web/vendor/THIRD_PARTY_NOTICES.md)
versioned together. Do not add a frontend framework or build pipeline without an explicit need.

Open UX and rendering work belongs in [ROADMAP](../ROADMAP.md); platform verification belongs in
[current status](current-status.md). A real deep-read test is networked and billable, unlike
read-only checks of existing reports.
