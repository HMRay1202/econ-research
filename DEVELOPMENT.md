# Development

Use Python 3.11 in the `econ-research` Conda environment. Install the project in editable mode
with its `dev` extra. SQLite must support FTS5; the test suite verifies this.

Configuration is loaded from environment variables and an optional local `.env`. Runtime
directories are created on demand. Never commit `.env`, databases, PDFs, parsed paper text, or
generated reports.

Run checks with:

```bash
ruff check .
pytest
```

An offline end-to-end test uses test doubles for parsing and the LLM. A real end-to-end run
requires a PDF and `OPENAI_API_KEY`:

```bash
research ingest /absolute/path/to/sample.pdf
research search "a term known to occur in the paper"
research deep-read PAPER_ID
```

The first real Docling conversion may download model assets and therefore take longer than
later ingestions. Keep downloaded models and runtime paper data outside version control.
