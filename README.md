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
- Reparse preserved PDFs locally, including optional crop-level formula OCR, without an LLM call.
- Queue single or batch uploads with persisted progress, exact/likely duplicate detection, and
  card-generation retry.
- Maintain paper title/year metadata, archive or restore papers, and permanently purge a paper
  only through the managed service workflow.

Phase 1 is complete and usable locally. Its full scope and deferred work are defined in
[PROJECT_CHARTER.md](PROJECT_CHARTER.md) and [ROADMAP.md](ROADMAP.md).

## Setup

```bash
conda env create -f environment.yml
conda activate econ-research
python scripts/setup_runtime.py --install
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
project move, or when libraries are missing, it offers to run
`conda run -n econ-research python scripts/setup_runtime.py --install` to repair the editable
installation and platform runtimes. A missing Conda environment can also be created after
confirmation. Successful checks do not reinstall dependencies. Keep the
terminal window open while using the app; close it or press Control-C to stop the server.

On Windows, double-click `start-research.cmd`, or run it from **Anaconda Prompt**. It performs the
same port, Conda, and editable-install checks as the macOS launcher, then opens the loopback-only
workspace. Installation and server output are streamed live so a long dependency operation does
not look stalled. It also prints whether PyTorch and an installed PaddlePaddle can see CUDA. A CPU
result is valid: the application keeps its CPU fallback and formula OCR remains optional. If the
Conda environment is missing, or the editable installation must be repaired, it asks for
confirmation before downloading or installing any Conda/Python packages. By default it installs
core, development, and formula OCR libraries, and repairs missing formula libraries even when the
editable project is already installed. Checks import libraries and perform a tiny convolution;
they never instantiate an OCR model or download model weights. Use `start-research.cmd --setup-only`
to prepare libraries
without starting the server, or `--without-formula` for an explicit minimal installation.
`--with-formula` remains a compatibility alias. If a server is already running, checks still run,
but package repair requires stopping that server first. Conda itself must already be installed.
When the server is already running, the Windows launcher offers **R** (stop and restart in this
window), **S** (stop), **L** (read-only logs), or **Q** (leave it running). A new foreground server
runs directly in this console: **Ctrl+C** requests a graceful Uvicorn shutdown. For an old hidden
server, double-click `stop-research.cmd` (or use `start-research.cmd --stop` without expensive GPU
checks). Stopping an existing process requires typing `STOP`, verifies the port owner against this
environment and checkout's editable package, and refuses while upload jobs are active. This
fallback terminates the process, so finish reparse/card/deep-read requests first; prefer Ctrl+C
in the original terminal whenever available. It never kills all Python processes or a process tree.
The optional log viewer watches `data/server-windows.stdout.log` and `data/server-windows.stderr.log`;
Ctrl+C there closes only the viewer. A foreground server logs in its original terminal, not those
old redirected files. `--setup-only` still exits after validation.

Permanent deletion handles Windows read-only files and diagnostic directories with a bounded
retry inside managed paths, without following symlinks/junctions or changing ACLs. Other file
locks still return 409 and preserve the database record; the backend logs the underlying error.
The Windows-only retry does not change macOS deletion behavior.

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
Install the hardware-appropriate libraries with
`conda run -n econ-research python scripts/setup_runtime.py --install` while the service is stopped.
The manual `.[formula]` extra is the CPU Paddle alternative, not the managed Windows GPU setup;
do not add it to a configured GPU installation. See the runtime profiles below.
`ECON_RESEARCH_PADDLE_FORMULA_OCR=false` disables this
step. The older `ECON_RESEARCH_FORMULA_ENRICHMENT=true` CodeFormula path remains experimental and
is off by default because its accuracy and latency vary by PDF. Use **重新解析公式** to retry the
non-billable local parse from a preserved original PDF, then explicitly regenerate cards if the
updated formulas should be included in LLM input.

The first actual formula recognition downloads missing model assets to ignored
`data/models/paddlex/official_models/`; existing cached models are reused. Installing libraries,
running setup checks, or simply opening the web app does not download models. If installation,
model loading, or one formula crop fails, the paper remains available with Docling text and formula
diagnostics in its detail view; formula recognition never turns a successful document parse into a
failed upload.

Both launchers use `scripts/setup_runtime.py` for model-free checks and `--install` for repair.
`scripts/runtime_policy.py` detects the operating system, NVIDIA driver, and compute capability:

| Host | Installed runtime |
| --- | --- |
| Windows x64, supported NVIDIA GPU and driver 580+ | Torch CUDA 13 in `econ-research`; Paddle GPU CUDA 13 in its dedicated worker |
| Windows x64, supported pre-Blackwell GPU and driver 560.76+ | Torch/Paddle CUDA 12.6, with Paddle isolated |
| Windows without a supported GPU/driver | CPU Torch and CPU Paddle |
| macOS | Native Torch (MPS when available) and CPU Paddle; no CUDA worker |

The supported CUDA profiles require compute capability 7.5 or newer; CUDA 12.6 is not selected
for Blackwell. Unsupported/undetected hardware prints a CPU fallback reason. Existing compatible
installations are checked rather than reinstalled. macOS native wheels are resolved for that
machine; platform-policy tests run on Windows, but macOS installation needs native verification.

Windows CUDA Paddle runs in a persistent local subprocess using an isolated venv at
`<econ-research>/paddle-worker`, created by the main Conda Python. The worker has no Torch
installation, does not read the database, reuses the project's existing model cache, and returns
formula results over stdin/stdout. Its diagnostics appear in the backend log. Requests time out
after 300 seconds; worker failure retains the existing Docling fallback. The model is reused
within one document; completing/failing that document closes its worker to release GPU memory.
Normal shutdown also closes workers; forced process termination cannot guarantee cleanup.
Selection requires a model-free GPU convolution check.
`ECON_RESEARCH_PADDLE_PYTHON` can explicitly select a dedicated worker interpreter.

This avoids the verified cuDNN DLL conflict between Windows Torch 2.9.1/cu130 (cuDNN 9.12) and
Paddle 3.3.1/cu130 (cuDNN 9.13), without modifying third-party DLLs. The legacy `formula-gpu`
extra is not the Windows managed installation path: do not install it into the main environment.
CPU `paddlepaddle` and `paddlepaddle-gpu` must never coexist in the same environment. Stop the
service before package repair; the installer refuses to repair while port 8000's health endpoint
is running. Model weights still download only on first actual recognition.

GPU use is optional. For Windows GPU acceleration, install an NVIDIA driver and CUDA-enabled
PyTorch/PaddlePaddle builds that match the machine; verify the launcher's CUDA diagnostics before
expecting acceleration. Standard Docling PDF parsing explicitly uses automatic device selection, so
it can use supported CUDA or Apple MPS devices and otherwise falls back to CPU. The experimental
CodeFormula path selects CUDA first, then Apple MPS, and finally CPU; FP16 is limited to CUDA/MPS
while CPU uses FP32. Platform-specific accelerator packages are intentionally not forced by the
shared environment file, so one checkout remains usable on macOS and Windows.

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
The pending publication scope and dated verification record are in
[docs/release-readiness.md](docs/release-readiness.md).
