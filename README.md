# Econ Research

A small, local-first system that converts economics papers into traceable research cards,
searchable source passages, and paper-specific deep-reading reports.

## Phase 1 capabilities

- Preserve an immutable local copy of each PDF.
- Parse PDFs to normalized Markdown with Docling.
- Generate economics-specific research cards with the OpenAI API.
- Store papers, chunks, cards, and deep reads in SQLite.
- Record per-call LLM token usage, latency, status, and price-snapshot cost estimates.
- Search papers, cards, and source passages with SQLite FTS5.
- Use the same application service from Typer CLI and FastAPI.

## Setup

```bash
conda env create -f environment.yml
conda activate econ-research
python -m pip install -e ".[dev]"
cp .env.example .env
```

Add `OPENAI_API_KEY` to the local `.env`. The file is ignored by Git.

The default model routing balances cost and research quality:

- `gpt-5.6-luna` with low reasoning generates structured research cards.
- `gpt-5.6-terra` with medium reasoning generates deep-reading reports.
- `gpt-5.6-terra` is the fallback when an operation-specific model is blank.

Override `OPENAI_DEFAULT_MODEL`, `OPENAI_CARD_MODEL`, `OPENAI_DEEP_READ_MODEL`, and their
reasoning-effort settings in `.env` when needed. The legacy `OPENAI_MODEL` variable remains a
fallback alias for `OPENAI_DEFAULT_MODEL`.

## Usage

```bash
research ingest /path/to/paper.pdf
research reparse PAPER_ID
research search "parallel trends"
research deep-read PAPER_ID
research deep-read PAPER_ID --focus identification
research usage
research usage --paper-id PAPER_ID --details
research serve
```

After `research serve`, open `http://127.0.0.1:8000/` for the local research workspace. It can
queue single or batch PDF uploads with persisted backend activity, elapsed-time heartbeats, and
refresh-safe progress recovery; detect exact and likely duplicates; retry card generation without
reparsing; archive papers; browse cards and source chunks; search the library; access managed
files; request deep reads; and inspect per-paper and global usage history. The API documentation
remains available at
`http://127.0.0.1:8000/docs`.

Do not open `src/econ_research/web/index.html` directly with a `file:///` URL: it is a static
client and needs the local `/api/*` service. The launcher detects an older service already using
port 8000 and asks you to stop it before opening a potentially stale interface.

On macOS, you can instead double-click `start-research.command` in Finder. It locates the existing
`econ-research` Conda environment, verifies that its editable `econ_research` import points to this
project's `src/econ_research`, starts the loopback-only server, and opens the workspace. After a
project move, or when the package is not installed, it automatically runs
`conda run -n econ-research python -m pip install -e ".[dev,formula]"` once to repair the editable
installation; when the import already points here, it does not reinstall dependencies. Keep the
terminal window open while using the app; close it or press Control-C to stop the server.

On Windows, double-click `start-research.cmd`, or run it from **Anaconda Prompt**. It performs the
same port, Conda, and editable-install checks as the macOS launcher, then opens the loopback-only
workspace. It also prints whether PyTorch and PaddlePaddle can see CUDA. A CPU result is valid: the
application keeps its CPU fallback and formula OCR remains optional. If the Conda environment is
missing, or the editable installation must be repaired, it asks for confirmation before downloading
or installing any Conda/Python packages.

If you prefer to start manually, use Anaconda Prompt (or another shell in which Conda is available)
and open the displayed loopback address in a browser:

```powershell
conda run -n econ-research research serve
```

`start-research.command` and `start-research.cmd` are macOS and Windows convenience launchers,
respectively, not cross-platform requirements. The web application, its SQLite data, and the
optional formula parser use project-relative runtime paths and do not depend on a browser
integration.

`research reparse PAPER_ID` regenerates the stored Markdown and source chunks from the preserved
original PDF. It is useful after parser improvements: it refreshes paper metadata and page
provenance, reconnects existing cards by chunk ordinal, and does not call an LLM or regenerate
cards. Review the refreshed text before relying on it for quotations.

Formula recognition uses a safe two-stage path. Docling identifies formula regions while the
optional PaddleOCR Formula module converts only those cropped regions to LaTeX. Failed formulas,
or a missing PaddleOCR installation, retain Docling's original text and never fail an upload.
Install it with `python -m pip install -e '.[formula]'`; this installs PaddleOCR, PaddlePaddle,
and its formula-text cleanup dependency. `ECON_RESEARCH_PADDLE_FORMULA_OCR=false` disables this
step. The older `ECON_RESEARCH_FORMULA_ENRICHMENT=true` CodeFormula path remains experimental and
is off by default because its accuracy and latency vary by PDF. Use **重新解析公式** to retry the
non-billable local parse from a preserved original PDF, then explicitly regenerate cards if the
updated formulas should be included in LLM input.

The first PaddleOCR Formula run downloads model assets to ignored `data/models/`. If installation,
model loading, or one formula crop fails, the paper remains available with Docling text and formula
diagnostics in its detail view; formula recognition never turns a successful document parse into a
failed upload.

GPU use is optional. For Windows GPU acceleration, install an NVIDIA driver and CUDA-enabled
PyTorch/PaddlePaddle builds that match the machine; verify the launcher's CUDA diagnostics before
expecting acceleration. Standard Docling PDF parsing explicitly uses automatic device selection, so
it requests CUDA when CUDA PyTorch is available and otherwise falls back to CPU. The current
experimental CodeFormula path is configured for Apple MPS, so do not enable
`ECON_RESEARCH_FORMULA_ENRICHMENT=true` on Windows expecting CUDA support.

## Data and privacy

Runtime data defaults to `data/`. PDFs, parsed paper text, databases, generated reports,
credentials, and `.env` files are excluded from Git. Do not force-add them. The application
continues to work without Codex after installation.

## Development

```bash
conda run -n econ-research ruff check .
conda run -n econ-research pytest
```

See [DEVELOPMENT.md](DEVELOPMENT.md), [ARCHITECTURE.md](ARCHITECTURE.md), and
[PROJECT_CHARTER.md](PROJECT_CHARTER.md). Frontend maintainers should also read
[docs/frontend.md](docs/frontend.md) and [docs/api-contracts.md](docs/api-contracts.md).
