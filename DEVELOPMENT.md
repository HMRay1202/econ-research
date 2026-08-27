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

Formula-aware parsing is optional because PaddlePaddle is a platform-specific dependency. Install
it into the same environment when testing or using formula recognition:

```bash
conda run -n econ-research python -m pip install -e '.[formula]'
```

The first formula parse downloads PaddleOCR model assets into the ignored `data/models/` runtime
directory. On a machine where the optional dependency is unavailable, imports still succeed and
Docling's extracted formula text is retained; the paper records the unavailable/failed formula
status instead of failing the complete import. Set `ECON_RESEARCH_PADDLE_FORMULA_OCR=false` to
disable the optional step deliberately.

On macOS, `start-research.command` is a convenience launcher. On Windows, use Anaconda Prompt and
the platform-neutral server command instead:

```powershell
conda run -n econ-research research serve
```

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
