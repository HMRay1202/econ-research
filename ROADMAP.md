# Roadmap

- [x] Define Phase 1 scope and boundaries.
- [x] Initialize project files and SQLite/FTS5 persistence.
- [x] Implement Docling parsing and source preservation.
- [x] Implement OpenAI research cards and deep reads.
- [x] Expose ingest, search, and deep-read through CLI and FastAPI.
- [x] Pass offline automated tests.
- [x] Pass a real PDF/OpenAI end-to-end test.
- [x] Add a minimal local browser workspace and stable read/file APIs.
- [x] Preserve parser page provenance and provide a non-billable reparse workflow for existing
  papers.
- [x] Add batch upload, task progress, exact/likely duplicate detection, card-generation retry,
  manual title/year editing, archive/restore, permanent removal, and usage-history views.
- [x] Add optional crop-level PaddleOCR Formula enrichment with diagnostics and a safe Docling
  fallback.

## Next candidates

1. Improve parser observability and confidence-gated normalization for difficult PDF text and
   formulas, using representative local fixtures rather than replacing body text with full-page
   OCR.
2. Add a Windows-friendly launcher or setup check; the application already runs through
   `conda run -n econ-research research serve` on Windows, while the current double-click launcher
   is macOS-only.
3. Add card editing, approval, and export through additive service/API contracts.
4. Add a cross-paper comparison tray, followed by optional semantic search only after defining
   quality, privacy, and local-model requirements.
5. Evaluate Zotero integration only when its desired import/synchronization behavior is specified.

Knowledge graphs, multiple LLM providers, cloud deployment, and orchestration infrastructure
remain deferred until a concrete research workflow justifies their additional complexity.
