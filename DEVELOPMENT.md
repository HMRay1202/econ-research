# Development

Use Python 3.11 in the `econ-research` Conda environment. Do not modify Conda `base` or the
macOS system Python. Confirm or create the environment with:

```bash
conda env list
conda env create -f environment.yml  # only when econ-research is absent
conda activate econ-research
python -m pip install -e ".[dev]"
python --version
```

For the supported platform-aware runtime setup, use the shared installer from the repository
root. Stop the service before installing or repairing packages:

```bash
conda run --no-capture-output -n econ-research python scripts/setup_runtime.py --install
conda run --no-capture-output -n econ-research python scripts/setup_runtime.py
```

The first command installs libraries; the second verifies imports and tiny device operations
without installing packages or loading OCR models. `--without-formula` skips optional formula
libraries during setup, but does not uninstall them or disable an existing OCR configuration.
Use `ECON_RESEARCH_PADDLE_FORMULA_OCR=false` to disable recognition at runtime.

On supported Windows NVIDIA systems, Torch stays in `econ-research` and Paddle GPU runs in an
isolated `<econ-research>/paddle-worker` venv with no Torch. This avoids conflicting cuDNN DLLs.
CPU Windows and macOS use CPU Paddle in the main environment; macOS Torch can use native MPS.
Do not install the legacy `.[formula-gpu]` extra into the main Windows environment, or install
CPU and GPU Paddle together. See the runtime profile table in [README.md](README.md).

The first formula parse downloads PaddleOCR model assets into the ignored `data/models/` runtime
directory. On a machine where the optional dependency is unavailable, imports still succeed and
Docling's extracted formula text is retained; the paper records the unavailable/failed formula
status instead of failing the complete import. Set `ECON_RESEARCH_PADDLE_FORMULA_OCR=false` to
disable the optional step deliberately.

On macOS, `start-research.command` is a convenience launcher. Before starting the server, it
checks that `econ_research` imports from this checkout's `src/econ_research`. If a project move
left the editable installation pointing elsewhere, or the package is missing, the launcher repairs
it through `scripts/setup_runtime.py --install` after confirmation; a correct local installation
is left untouched. `start-research.cmd` provides the Windows double-click launcher. Both install
formula libraries by default, support `--without-formula`, and support `--setup-only` without
starting a new server. The macOS launcher returns immediately when it finds an existing compatible
service; stop that service before using setup-only for a fresh check. Windows streams installation
progress and GPU diagnostics, then runs the environment's Python directly in the console so
Ctrl+C reaches Uvicorn. For an existing Windows server, choose restart, stop, read-only logs, or
quit. `stop-research.cmd` is the confirmed, identity-checked termination fallback for a hidden
server; it refuses active uploads, but users must also finish reparse/card/deep-read work first.
Use Anaconda Prompt and the platform-neutral server command when a launcher is not wanted:

```powershell
conda run -n econ-research research serve
```

The 2026-09-02 Windows verification passed 107 offline tests and Ruff, including native CMD and
PowerShell checks, real read-only-directory cleanup, and mocked process-control safety checks.
An RTX 5070 Ti Laptop GPU also passed isolated Paddle GPU inference and a real PDF import.
Native macOS, clean CPU-only installation, and CUDA 12.6 hardware validation remain outstanding;
policy tests on Windows are not substitutes for those runs. The experimental
`ECON_RESEARCH_FORMULA_ENRICHMENT` path selects CUDA, then MPS, then CPU FP32 and remains off by
default; it is separate from the standard Paddle formula path.

For agents and non-interactive shells, `conda run -n econ-research COMMAND` is the canonical
form because it does not depend on shell activation. SQLite must support FTS5; the test suite
verifies this.

Configuration is loaded from environment variables and an optional local `.env`. Runtime
directories are created on demand. Never commit `.env`, databases, PDFs, parsed paper text, or
generated reports.

LLM routing is explicit: card generation defaults to `gpt-5.6-luna` with low reasoning, while
deep reads default to `gpt-5.6-terra` with medium reasoning. `OPENAI_DEFAULT_MODEL` is the
fallback for an operation-specific blank model; `OPENAI_MODEL` is accepted for compatibility.

Every real OpenAI call stores returned token counts, latency, status, request identifier, and a
price snapshot in SQLite. Costs are estimates based on the configured model price table; unknown
models remain explicitly unpriced. Reasoning tokens are reported separately but are already part
of output tokens and are not billed twice. Inspect totals or individual calls with:

```bash
research usage
research usage --details
research usage --paper-id PAPER_ID --operation deep_read
```

Run checks with:

```bash
conda run -n econ-research ruff check .
conda run -n econ-research pytest
```

An offline end-to-end test uses test doubles for parsing and the LLM. A real end-to-end run
requires a PDF and `OPENAI_API_KEY`:

```bash
research ingest /absolute/path/to/sample.pdf
research reparse PAPER_ID
research search "a term known to occur in the paper"
research deep-read PAPER_ID
```

The first real Docling conversion may download model assets and therefore take longer than
later ingestions. Keep downloaded models and runtime paper data outside version control.
Reparsing is local and non-billable: it uses the preserved PDF, refreshes parsed Markdown and
chunk provenance, and reconnects existing cards without calling the LLM.
It also retries formula OCR. It does not rewrite existing card text, so regenerate cards only
after reviewing the revised source text; that regeneration is an LLM call and may be billable.
For parser diagnosis, inspect `formula_status` and `formula_error` in the paper response or web
detail view before changing dependencies or disabling formula OCR.
Schema initialization is additive (`CREATE ... IF NOT EXISTS`) so an existing Phase 1 database
gains new tables without discarding papers. Future incompatible changes require an explicit
migration rather than database deletion.

For the pending GitHub publication scope, verification evidence, and privacy checks, see
[docs/release-readiness.md](docs/release-readiness.md). Do not treat a passing local suite as a
cross-platform CI result or as evidence that a commit has already been pushed.
