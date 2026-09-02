# Roadmap

The Phase 1 functional scope is delivered; remaining validation and quality work is not implied
complete. Shipped changes belong in [CHANGELOG](CHANGELOG.md), current evidence in
[verification status](docs/current-status.md), and product boundaries in the [charter](PROJECT_CHARTER.md).

Priorities below are an ordering for planning, not authorization to implement or a release promise.
P1 covers reliability and data trust, P2 covers usability/quality, and P3 covers optional expansion.

## Reliability and verification

| Priority | Work | Acceptance criteria |
| --- | --- | --- |
| P1 | Audit Docling article-structure extraction and reliability | Trace the current version, models, configuration and project post-processing from PDF layout/text through reading order, heading/section detection, Markdown and source chunks; document the signals and rules used, compare representative economics papers with manually reviewed structure, and assess omissions, misordering, section boundaries, tables/formulas and page provenance; deliver an evidence-backed keep/change recommendation with prioritized fixes and offline regression cases where needed |
| P1 | Native macOS, clean Windows CPU-only, CUDA 12.6 | On each target: install/check without downloading OCR weights, exercise first-use models, parse a fixture, verify expected device/fallback, run tests and stop cleanly |
| P1 | Native parser and sleep/wake stability | Reproduce or isolate the observed docling-parse/QPDF heap-corruption failure; separate correlation from cause; document survival/recovery and preserve originals |
| P1 | Interrupted tasks and lifecycle cleanup | Queued/running work leaves no permanently active orphan; users can retry without automatic billable replay; audit incoming files and worker cleanup after crash/forced stop |
| P1 | Refresh during import | Refresh at each major stage without duplicate work, garbled placeholders, or presenting unfinished cards as complete |

Startup recovery already marks orphaned uploads interrupted and closes unfinished card generations.
That fix does not establish arbitrary sleep/wake or process-crash safety. Do not reopen a fixed
stale-state bug merely because broader lifecycle tests remain incomplete.

## Parsing and user experience

| Priority | Work | Acceptance criteria |
| --- | --- | --- |
| P2 | Accumulate upload selections | Reopening the picker appends to a visible pending list; users can remove items and understand duplicates before submission |
| P2 | Per-document batch detail | Each queued item exposes its stage, events, error and resulting paper link without losing other items |
| P2 | Formula validation and browser rendering | Representative malformed delimiters/tokens render safely or show code fallback, without raw KaTeX errors; verify in a browser, not only source assertions |
| P2 | Difficult OCR and degraded card prose | Preserve every candidate's evidence; compare source, attempts and cards; confidence-gate any correction and never silently replace uncertain mathematics |

Historical observations motivating the last item include two page-13 formulas failing all three
crop strategies in a 24-region document, and one low-confidence fallback in a later 16-region
synthetic smoke test. These are separate fixtures, not contradictory results or a general accuracy
benchmark. Scale/padding retries alone have not resolved all cases. Avoid repetitive errors
overwhelming the paper header; preserve detailed evidence separately.

Body text remains primarily Docling-native. Any legacy-font correction should be targeted,
confidence-gated and checked against the PDF rather than replacing all text with full-page OCR.

## Optional product increments

| Priority | Candidate | Definition needed before implementation |
| --- | --- | --- |
| P3 | Card editing, approval and export | Provenance/history semantics, export format, additive service/API and UI tests |
| P3 | Cross-paper comparison | Explicit paper selection and traceable comparison output |
| P3 | Semantic search | Retrieval quality, privacy, local-model footprint and fallback requirements |
| P3 | Zotero integration | Import versus synchronization, conflict resolution and ownership of originals |

Knowledge graphs, cloud hosting, multi-user authentication, multiple-provider routing and
orchestration infrastructure remain outside the current scope. Add them only for an explicit
research workflow, not as prerequisites for the work above.
