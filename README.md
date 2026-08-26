# Econ Research

A small, local-first system that converts economics papers into traceable research cards,
searchable source passages, and paper-specific deep-reading reports.

## Phase 1 capabilities

- Preserve an immutable local copy of each PDF.
- Parse PDFs to normalized Markdown with Docling.
- Generate economics-specific research cards with the OpenAI API.
- Store papers, chunks, cards, and deep reads in SQLite.
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

## Usage

```bash
research ingest /path/to/paper.pdf
research search "parallel trends"
research deep-read PAPER_ID
research deep-read PAPER_ID --focus identification
research serve
```

The API documentation is available at `http://127.0.0.1:8000/docs` while the server runs.

## Data and privacy

Runtime data defaults to `data/`. PDFs, parsed paper text, databases, generated reports,
credentials, and `.env` files are excluded from Git. Do not force-add them. The application
continues to work without Codex after installation.

## Development

```bash
ruff check .
pytest
```

See [DEVELOPMENT.md](DEVELOPMENT.md), [ARCHITECTURE.md](ARCHITECTURE.md), and
[PROJECT_CHARTER.md](PROJECT_CHARTER.md).

