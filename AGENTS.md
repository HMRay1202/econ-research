# Repository Instructions

- Work from the repository root: `/Users/minrui/Documents/Rutgers/Paper_Research`.
- Keep Phase 1 small and follow `PROJECT_CHARTER.md`.
- CLI and HTTP handlers must call the shared `ResearchService`.
- The local web client must call documented `/api/*` routes. Never access SQLite, `.env`, runtime
  paths, or an OpenAI key from browser code, and never mount the entire `data/` directory.
- Keep public API changes additive. Update `docs/api-contracts.md` and frontend tests when a
  browser-facing contract changes.
- Preserve original PDFs; generated summaries never replace source material.
- Keep LLM calls behind `ResearchLLM` and persistence behind the repository boundary.
- Use the existing Conda environment `econ-research` with Python 3.11. Do not install into
  Conda `base` or the macOS system Python.
- Prefer environment-independent commands such as `conda run -n econ-research research ...`,
  `conda run -n econ-research ruff check .`, and `conda run -n econ-research pytest`.
- If the environment is absent, create it with `conda env create -f environment.yml`, activate
  it, then run `python -m pip install -e ".[dev]"`.
- Add or update tests for behavior changes, and run relevant checks.
- Update documentation when commands, configuration, architecture, or schemas change.
- Never commit API keys, `.env`, PDFs, databases, parsed paper text, or generated reports.
- Treat real LLM tests as networked and billable. Use offline test doubles by default, and
  inspect `research usage --details` after an authorized real call.
- Database schema changes must be additive or explicitly migrated; never delete a user's
  runtime database to make a new schema work.
- Do not add deferred infrastructure without an explicit requirement.
