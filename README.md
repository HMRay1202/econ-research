# Econ Research

A local-first workspace for economics papers. Preserve original PDFs, turn them into searchable
source passages and research cards, and generate paper-specific deep reads with traceable sources.

**Local-first does not mean fully offline.** Parsing, formula OCR and search run locally.
Card generation and deep reads send paper titles, source chunks and instructions to the configured
OpenAI API and may incur charges.

[Quick start](#quick-start) · [Running the app](docs/runtime-guide.md) ·
[Data and backups](docs/data-storage.md) · [All documentation](docs/index.md)

## What you can do

- Import individual or batches of PDFs, track progress and identify duplicates.
- Extract text, tables and page provenance with Docling; optionally recognize formulas with PaddleOCR.
- Generate research cards, search papers and passages, and request single-paper deep reads.
- Edit paper titles/years, reparse a document, and retry card generation separately.
- Archive, restore or explicitly permanently delete papers, and inspect LLM usage.

The original PDF remains authoritative. Generated claims and uncertain formulas require source
review; a successful import does not guarantee perfect extraction.

## Project status

The Phase 1 functional scope is complete; platform and reliability validation remain ongoing.

| Area | Status |
| --- | --- |
| Windows with NVIDIA CUDA 13 | Local GPU inference and real import verified |
| macOS, Windows CPU-only, CUDA 12.6 | Corresponding paths exist; this update still needs native end-to-end validation on those targets |
| Automated checks | Latest baseline: 107 offline tests passed; see [verification status](docs/current-status.md) |
| Card editing/export, cross-paper comparison, semantic search | Not implemented; see [roadmap](ROADMAP.md) |

The package version is `0.1.0`. Published implementation changes are recorded in
[CHANGELOG](CHANGELOG.md); a Git commit, package version and test result are different things.

## Quick start

Install Conda (Miniconda or Anaconda) first. Clone the repository, or download and extract its code
from GitHub, then work from the repository root:

~~~text
git clone https://github.com/HMRay1202/econ-research.git
cd econ-research
~~~

All relative paths below assume this directory. Do not open `src/econ_research/web/index.html` directly.

### Windows

Open PowerShell in the project directory and create your local configuration without overwriting
an existing file:

~~~powershell
if (-not (Test-Path -LiteralPath .env)) { Copy-Item -LiteralPath .env.example -Destination .env }
notepad .env
~~~

Set your `OPENAI_API_KEY`, save, and double-click `start-research.cmd` or run:

~~~powershell
.\start-research.cmd
~~~

The launcher checks the `econ-research` environment and offers to install missing libraries for
your hardware. Choose Y when approving downloads and keep the window open. Missing model weights
download only when actual parsing or recognition first needs them.

### macOS

From Terminal in the repository root:

~~~bash
test -e .env || cp .env.example .env
open -e .env
~~~

Set `OPENAI_API_KEY`, save, and double-click `start-research.command` or run:

~~~bash
./start-research.command
~~~

If an extracted copy lacks execute permission, run `chmod +x start-research.command` first.
macOS does not install CUDA: Torch can use MPS when available; Paddle uses CPU.

### After startup

Open <http://127.0.0.1:8000/>. You can start the UI and read existing data without a key, but a new
import attempts card generation; it is not a dedicated key-free offline-import mode.

## Everyday workflow

1. Upload a PDF and wait for parsing and card generation; batch items run through the queue.
2. Read cards and follow their source passages back to the PDF.
3. Reparse when extraction needs improvement: this is local and leaves existing card text unchanged.
4. After reviewing the new source, explicitly regenerate cards or request a deep read if needed.
5. Stop the app with **Ctrl+C in the actual server terminal**.

On Windows, an existing server offers R to restart, S to stop, L for read-only logs, or Q to quit.
If its terminal is unavailable, `stop-research.cmd` requests STOP confirmation and terminates the
verified process. Finish all tasks first. Closing the read-only viewer does not stop the server.

## Data, space and costs

- Research records and files default to `data/`; configuration lives in `.env`. Neither is pushed to Git.
- Models and Python environments account for most storage; pip download caches are separate from installed libraries.
- A GitHub clone is not a research backup and does not restore local papers or their database.
- See [runtime configuration and costs](docs/runtime-guide.md) and [storage and backup](docs/data-storage.md).

## For contributors

Start with [DEVELOPMENT](DEVELOPMENT.md) and [ARCHITECTURE](ARCHITECTURE.md).
The [project charter](PROJECT_CHARTER.md) defines scope; the [documentation index](docs/index.md)
routes you to contracts, workflows, current status and release history.
