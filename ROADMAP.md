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
- [x] Validate the Windows CUDA 13 runtime with isolated Paddle GPU, model-free hardware-aware
  setup, foreground server controls, and safe read-only-file deletion.
- [x] Reconcile orphaned queued/running uploads and card generations after a service restart.
- [x] Persist formula attempts and failed crops; render card content through the shared safe
  Markdown/math renderer and replace KaTeX errors with an unvalidated-source fallback.

## Next candidates

1. Improve parser observability and confidence-gated normalization for difficult PDF text and
   formulas, using representative local fixtures rather than replacing body text with full-page
   OCR.
2. Extend native validation beyond the tested Windows CUDA 13 machine to macOS, clean CPU-only
   installation, and CUDA 12.6 hardware. Repeat `conda run -n econ-research pytest` and verify
   model-free setup, first-use downloads, and start/stop behavior on each platform.
3. Add card editing, approval, and export through additive service/API contracts.
4. Add a cross-paper comparison tray, followed by optional semantic search only after defining
   quality, privacy, and local-model requirements.
5. Evaluate Zotero integration only when its desired import/synchronization behavior is specified.

## Open issues to investigate

1. **Upload selection cannot be accumulated.** Multiple PDFs can currently be queued only when
   they are selected together in one file-picker operation. Selecting files again replaces the
   browser selection instead of appending them to a visible pending queue.
2. **Batch queues lack per-document detail.** The multi-document upload view does not provide a
   clear expandable status, stage, event timeline, error, or resulting paper link for each queued
   document.
3. **Sleep/wake stability is not yet established.** A native `docling-parse`/QPDF heap-corruption
   crash has been observed after wake, but current evidence does not prove that sleep caused it.
   Investigate both deeper system sleep during an active import and the independent native-parser
   failure mode, including whether the service survives and marks/retries interrupted work safely.
4. **Refreshing during import can restore an inconsistent web view.** After a page refresh, an
   unfinished import may be displayed using incomplete or incorrectly decoded intermediate data,
   including garbled text. Investigate refresh-time task restoration, the boundary between upload
   status and paper visibility, and ensure parsed content/cards are shown only after their
   corresponding stage has completed successfully.
5. **Interruption recovery needs broader lifecycle testing.** Startup now marks queued/running
   uploads interrupted and closes orphaned card generations. It does not replay billable work.
   Verify the end-user retry flow and incoming-file retention after native crashes, sleep/wake,
   and forced termination; these are separate from the fixed stale-active-state bug.
6. **Formula validation remains heuristic.** Common malformed delimiters/tokens are normalized
   or rejected, and the frontend now replaces KaTeX errors with a safe source-code fallback.
   Broader browser-level rendering tests and semantic formula checks are still needed; structural
   validation alone cannot prove mathematical correctness.
7. **Formula-heavy card quality still needs source review.** Card content now shares the sanitized
   Markdown/KaTeX path. That presentation fix does not repair degraded source prose or an LLM's
   altered symbols. Compare stored chunks, card output, and the original PDF when assessing quality.
8. **Expanded-crop retries still fail on some detected formulas.** In the current test paper,
   24 formula regions are detected but only 22 are recognized; both remaining page-13 formulas
   fail with unbalanced braces at the standard, expanded, and high-resolution attempts. Changing
   only crop scale and padding is therefore insufficient for these cases. Preserve the raw
   fallback, capture and compare each attempt's crop/OCR output, and investigate adaptive region
   correction, image preprocessing, alternate recognition, or explicitly bounded repair before
   treating additional retries as useful. The UI should also summarize repeated attempt errors
   without filling the paper header with near-identical diagnostics.
   A later synthetic Windows smoke test recognized 15 of 16 formulas, with one page-5
   low-confidence fallback after three attempts; it demonstrates successful partial handling,
   not resolution of the harder recognition cases above.

Knowledge graphs, multiple LLM providers, cloud deployment, and orchestration infrastructure
remain deferred until a concrete research workflow justifies their additional complexity.
