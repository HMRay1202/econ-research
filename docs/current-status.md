# Current Status and Handoff

## Snapshot

Phase 1 is complete. The repository provides a local-first economics-paper workspace with a
Typer CLI, FastAPI service, and a minimal loopback-only browser UI. The current branch is expected
to be `main` and synchronized with its configured GitHub remote; confirm with `git status --short
--branch` before starting work.

The implementation is intentionally small. Do not introduce a second business-logic path: CLI
commands and HTTP handlers must call `ResearchService`, LLM calls must go through `ResearchLLM`,
and persistence must remain in `SQLiteRepository`.

## Delivered capabilities

- Import a PDF, preserve an immutable managed copy, parse it with Docling, create source chunks,
  generate Luna research cards, and index papers/cards/chunks in SQLite FTS5.
- Search one local library through CLI and documented `/api/*` routes.
- Produce on-demand Terra deep reads with stored report history and measured usage telemetry.
- Browse papers, cards, chunks, searches, managed files, deep reads, and usage in the local UI.
- Reparse a ready paper with `research reparse PAPER_ID`. This refreshes generated Markdown,
  title-page metadata, chunks, and page/section provenance without calling an LLM; cards are
  reconnected by their prior chunk ordinal.
- For legacy PDFs whose font mapping damages a title, run a focused first-page OCR fallback.
  It updates recognized title, author, and year metadata without replacing the full body with OCR.
- Optionally recognize mathematical formulas through Docling formula regions plus PaddleOCR
  Formula. Formula OCR is crop-level rather than full-page OCR; a missing or failed recognizer
  preserves Docling text and records diagnostics on the paper. The UI's **重新解析公式** control
  reruns this local, non-billable parsing workflow.
- Queue single or batch uploads with persisted stage progress, detailed backend activity events,
  ten-second liveness heartbeats, elapsed time, and refresh-safe progress restoration. Parser
  callbacks report real milestones such as Docling parsing and per-formula PaddleOCR work rather
  than fabricating page-level completion values. Retain exact/likely duplicate information, retry
  billable card generation from stored chunks, and show generation/usage history.
- Support manual paper title/year overrides, soft archive/restore, and explicit permanent purge
  while keeping managed paths behind service-controlled file endpoints.

## Local operation

Use the existing Python 3.11 Conda environment, never Conda `base`:

```bash
conda run -n econ-research ruff check .
conda run -n econ-research pytest
conda run -n econ-research research serve
```

Open `http://127.0.0.1:8000/` after starting the server, or use `start-research.command` on
macOS. The launcher keeps its existing port and Conda checks, and also confirms that
`econ_research` imports from the current checkout's `src/econ_research`. If the project has moved
or the editable package is absent, it repairs that installation with
`conda run -n econ-research python -m pip install -e ".[dev,formula]"`; it skips this command when
the installed import is already correct. Windows has an equivalent `start-research.cmd` launcher;
it also reports PyTorch and Paddle CUDA availability. CPU-only operation is supported, while CUDA
requires matching NVIDIA drivers and GPU-enabled package builds. Before the Windows launcher
creates a missing Conda environment or downloads packages to repair an editable installation, it
asks for one confirmation. The normal non-billable maintenance command is:

```bash
conda run -n econ-research research reparse PAPER_ID
```

Ingestion and deep reads can call OpenAI and are billable. Before and after an authorized real
call, inspect `research usage --details`. Cards default to Luna/low reasoning; deep reads default
to Terra/medium reasoning. Actual token totals and cost estimates live only in the ignored local
SQLite database.

Formula OCR is enabled by default only when its optional dependencies are installed. Add them to
the existing environment with `conda run -n econ-research python -m pip install -e '.[formula]'`.
The first use downloads model assets under ignored `data/models/`; it is not an OpenAI call. Set
`ECON_RESEARCH_PADDLE_FORMULA_OCR=false` to turn it off on an unsupported or resource-constrained
machine. On Windows, use the equivalent `start-research.cmd` launcher or run
`conda run -n econ-research research serve` from Anaconda Prompt and visit the printed
`127.0.0.1` URL.

On Apple Silicon, standard Docling/PyTorch stages may select MPS when the service is launched from
Terminal. PaddleOCR Formula is separately reported in the upload timeline and currently runs on
its supported Paddle device; the standard macOS PaddlePaddle runtime is CPU-only.

## Data and Git boundaries

The repository deliberately excludes `.env`, API keys, PDFs, SQLite databases, parsed paper text,
generated reports, and other runtime data. Preserve original PDFs; never overwrite them with
parsed or generated output. Stage only source, tests, and documentation. Do not add real-paper
identifiers, model request IDs, or machine-specific paths to tracked documentation.

Database changes must be additive or explicitly migrated. Never delete a runtime database to make
a schema change work. Browser code may call only documented `/api/*` routes and must never access
SQLite, runtime directories, `.env`, or an API key directly.

## Parser quality and known limitation

Page provenance is now preserved for source chunks and inherited by cards when possible. A
focused OCR fallback repairs damaged title-page metadata in old PDFs lacking usable Unicode font
mappings. Formula regions can be selectively converted to LaTex by PaddleOCR Formula after
Docling layout detection. Dense body text continues to use Docling-native extraction because
full-page OCR can silently introduce different transcription errors. For quotations or numerical
claims, consult the original PDF.

Card text is intentionally unchanged by a reparse: users can review corrected Markdown before
choosing an explicit, billable card regeneration. The next parser improvement should be
confidence-gated and testable on representative PDFs; do not globally replace body text with OCR.
Keep both the source PDF and parser output available for comparison.

## Safe next increments

1. Card export/editing with a service method, additive API contract, and UI tests.
2. Cross-paper comparison tray using existing paper/card/chunk APIs.
3. Confidence-based normalization of known legacy-font defects, with source-page review.
4. Optional semantic search only after defining retrieval quality and privacy requirements.

Before changing browser-facing behavior, update `docs/api-contracts.md` and frontend tests. Read
`AGENTS.md`, `DEVELOPMENT.md`, `ARCHITECTURE.md`, and `docs/frontend.md` before implementation.
