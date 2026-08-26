# Repository Instructions

- Keep Phase 1 small and follow `PROJECT_CHARTER.md`.
- CLI and HTTP handlers must call the shared `ResearchService`.
- Preserve original PDFs; generated summaries never replace source material.
- Keep LLM calls behind `ResearchLLM` and persistence behind the repository boundary.
- Add or update tests for behavior changes, and run relevant checks.
- Update documentation when commands, configuration, architecture, or schemas change.
- Never commit API keys, `.env`, PDFs, databases, parsed paper text, or generated reports.
- Do not add deferred infrastructure without an explicit requirement.

