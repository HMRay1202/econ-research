# Current Status and Handoff

## Snapshot

Phase 1 is complete. The repository provides a local-first economics-paper workspace with a
Typer CLI, FastAPI service, and a minimal loopback-only browser UI. On 2026-09-02, local `main`
and live remote `origin/main` both pointed to `58f8f1d`; the Windows/GPU, parser, recovery, frontend,
and documentation changes described below were still uncommitted. Do not confuse synchronized
commit history with a clean or published worktree. See [release-readiness.md](release-readiness.md)
and recheck Git status before publication.

The implementation is intentionally small. Do not introduce a second business-logic path: CLI
commands and HTTP handlers must call `ResearchService`, LLM calls must go through `ResearchLLM`,
and persistence must remain in `SQLiteRepository`.

## Delivered capabilities

- Windows purge recovers from read-only diagnostic directories/files with a managed-path-only
  retry; real locks still preserve the paper record and log the cause. macOS behavior is unchanged.
- Windows startup now offers restart/stop/logs/quit for an existing server, with a separate
  `stop-research.cmd` fallback for hidden processes. Foreground Python owns the console so Ctrl+C
  can shut down Uvicorn gracefully; fallback termination checks identity and active upload jobs.
- Import a PDF, preserve an immutable managed copy, parse it with Docling, create source chunks,
  generate Luna research cards, and index papers/cards/chunks in SQLite FTS5.
- Preserve Docling-detected tables in the ordered source chunks, so table headers and cell values
  are available to search, card prompts, deep reads, and the source-chunk viewer.
- Search one local library through CLI and documented `/api/*` routes.
- Produce on-demand Terra deep reads with stored report history and measured usage telemetry.
- Browse papers, cards, chunks, searches, managed files, deep reads, and usage in the local UI.
- Render deep reads and inspected source chunks as sanitized local Markdown with local KaTeX;
  source Markdown and API responses remain unchanged, while valid `[chunk N]` report references
  open the corresponding stored chunk.
- Reparse a ready paper with `research reparse PAPER_ID`. This refreshes generated Markdown,
  title-page metadata, chunks, and page/section provenance without calling an LLM; cards are
  reconnected by their prior chunk ordinal.
- For legacy PDFs whose font mapping damages a title, run a focused first-page OCR fallback.
  It updates recognized title, author, and year metadata without replacing the full body with OCR.
- Optionally recognize mathematical formulas through Docling formula regions plus PaddleOCR
  Formula. Formula OCR is crop-level rather than full-page OCR and retries failed validation with
  expanded/high-resolution crops. Unvalidated OCR is retained as a non-rendered fenced `latex`
  block (or a visible page marker when no text exists), so it remains available to search/chunks
  and LLM prompts without being treated as executable/renderable math. The UI's **重新解析公式**
  control reruns this local, non-billable parsing workflow.
- Queue single or batch uploads with persisted stage progress, detailed backend activity events,
  ten-second liveness heartbeats, elapsed time, and refresh-safe progress restoration. Parser
  callbacks report real milestones such as Docling parsing and per-formula PaddleOCR work rather
  than fabricating page-level completion values. Retain exact/likely duplicate information, retry
  billable card generation from stored chunks, and show generation/usage history.
- Support manual paper title/year overrides, soft archive/restore, and explicit permanent purge
  while keeping managed paths behind service-controlled file endpoints.

## Upload and generation recovery

After a backend restart, persisted `queued` and `running` upload tasks are marked `interrupted`
because their in-memory worker no longer exists. Running card-generation rows are marked `failed`;
papers with older completed cards remain usable with `card_status=ready`, while papers without
cards become retryable with `card_status=failed`.

## Local operation

Latest Windows verification (2026-09-02): 107 offline tests passed and `ruff check .` passed.
A user-initiated synthetic PDF import completed in about 75 seconds, producing 15 chunks and
15 cards. Of 16 detected formulas, 15 were recognized and one low-confidence page-5 formula fell
back after three crop attempts. The import succeeded with `formula_status=partial`; this is not
a claim of perfect OCR accuracy. No new billable call is required to reproduce the offline suite.
Native macOS, clean CPU-only, and CUDA 12.6 machine validation remain follow-up checks.

Windows setup now installs formula OCR libraries by default, including PaddleOCR's `doc-parser`
extras, and checks missing extras even in an existing editable installation. `--without-formula`
opts out. Both launchers use the shared hardware-aware `scripts/setup_runtime.py` installer.
Windows NVIDIA GPU profiles isolate Paddle in `<econ-research>/paddle-worker` (no Torch), while
the main Conda environment retains CUDA Torch. CPU Windows and macOS retain in-process CPU
Paddle; macOS Torch can use MPS. Setup checks imports and a tiny convolution, never an OCR model.
Missing model weights download only on actual recognition. Existing caches are reused directly.
Worker requests are serialized, reuse the model, time out after 300 seconds, and report their
actual device in backend logs; failures retain Docling's formula fallback.

On the RTX 5070 Ti Laptop GPU, the actual isolated PP-FormulaNet_plus-L test passed with Paddle
3.3.1/cu130 and Torch 2.9.1/cu130. One cached crop took about 9.1 seconds including worker/model
initialization and 0.55 seconds on repeat; this is a smoke test, not a general benchmark. The main
process did not import Paddle. No data migration, model replacement, or third-party DLL patching
was needed. macOS behavior is covered by policy tests, not a native macOS hardware test.

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
`conda run -n econ-research python scripts/setup_runtime.py --install`; it skips installation when
the editable import and runtime checks pass. Windows has an equivalent `start-research.cmd` launcher;
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

Formula OCR is enabled by default only when its optional dependencies are installed. Add the
hardware-appropriate runtime with
`conda run -n econ-research python scripts/setup_runtime.py --install` while the server is stopped.
The first use downloads model assets under ignored `data/models/`; it is not an OpenAI call. Set
`ECON_RESEARCH_PADDLE_FORMULA_OCR=false` to turn it off on an unsupported or resource-constrained
machine. On Windows, use the equivalent `start-research.cmd` launcher or run
`conda run -n econ-research research serve` from Anaconda Prompt and visit the printed
`127.0.0.1` URL.

On Apple Silicon, standard Docling/PyTorch stages may select MPS when the service is launched from
Terminal. PaddleOCR Formula is separately reported in the upload timeline and currently runs on
its supported Paddle device; the standard macOS PaddlePaddle runtime is CPU-only.

The experimental CodeFormula pipeline is platform-aware: it prefers CUDA when the installed
PyTorch build exposes it, uses Apple MPS on supported Macs, and otherwise uses CPU FP32. Shared
dependency files do not force a platform-specific CUDA or MPS package build.

## Data and Git boundaries

The repository deliberately excludes `.env`, API keys, PDFs, SQLite databases, parsed paper text,
generated reports, and other runtime data. Preserve original PDFs; never overwrite them with
parsed or generated output. Stage only source, tests, and documentation. Do not add real-paper
identifiers, model request IDs, or machine-specific paths to tracked documentation.

Database changes must be additive or explicitly migrated. Never delete a runtime database to make
a schema change work. Browser code may call only documented `/api/*` routes and must never access
SQLite, runtime directories, `.env`, or an API key directly.

## Parser quality and known limitation

Page provenance is now preserved for source chunks and inherited by cards when possible. Tables
are serialized as Markdown blocks in the same reading order as surrounding text and retain their
page range. A
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
