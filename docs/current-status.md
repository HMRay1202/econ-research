# Current Status and Verification Baseline

Reviewed on 2026-09-02. This page owns implementation and verification status, not live process
monitoring or installation instructions; use the [runtime guide](runtime-guide.md) for operation.

## Implementation and publication

- Published implementation baseline: `c331715` — `feat: harden Windows GPU runtime and paper workflows`.
- Repository: `HMRay1202/econ-research`, branch `main`. That push was verified by matching the remote SHA.
- Package version remains `0.1.0`; no version tag or GitHub Release was created.
- The current documentation reorganization changes no business code. Its commit/push status must
  be checked in Git rather than inferred from this page.
- `58f8f1d` is the preceding baseline, not the current version. See the [publication archive](release-readiness.md).

The Phase 1 functional scope is delivered: import, original preservation, parsing/formula
enrichment, cards, lexical search, single-paper deep reads, progress, metadata maintenance,
archive/restore/purge and usage reporting. Functional completion is not full platform, crash-recovery
or OCR-quality validation.

## Verification matrix

| Area | Latest result | Limitation |
| --- | --- | --- |
| Windows / Python 3.11 offline suite | 107 passed; Ruff passed | Not a cross-platform CI result |
| Windows launchers and file handling | Native CMD/PowerShell and read-only cleanup checks passed | Mocked process controls do not prove all concurrent/crash scenarios safe |
| RTX 5070 Ti Laptop / CUDA 13 | Isolated Paddle GPU recognition verified | Not evidence for every NVIDIA device |
| macOS | Native Torch/MPS and CPU Paddle paths retained; policy tests passed | This update has not completed native Mac installation and full-flow validation |
| Windows CPU-only / CUDA 12.6 | Selection policy and tests exist | Clean-machine end-to-end validation remains outstanding |

The measured combination was Torch `2.9.1+cu130`, Paddle GPU `3.3.1`, PaddleOCR `3.7.0` and
PaddleX `3.7.2`. This is a tested-machine record, not a complete dependency lock file.

The offline suite reported one Starlette/httpx adapter deprecation warning, not a failure.
Historical results apply to the checked version; rerun relevant checks after changes following
[DEVELOPMENT](../DEVELOPMENT.md).

The documentation-only revision was rechecked on 2026-09-02: Ruff and all 107 offline tests
passed, as did English-text checks across 18 project documents, 90 local links/anchors,
five JSON examples against application models, and all 30 documented route/method pairs against
the generated OpenAPI schema. The test rerun required access to Windows' temporary test directory;
no research backend or real model call was started. These checks do not add native Mac coverage.

## Real workflow observations

A user-initiated synthetic PDF import completed in about 75 seconds with 15 chunks and 15 cards.
Of 16 detected formulas, 15 passed and one low-confidence page-5 formula fell back after three
crop strategies. The result was successful import with `formula_status=partial`, not perfect OCR.

An isolated cached-crop GPU smoke test took about 9.1 seconds initially and 0.55 seconds on repeat.
That is not a general performance benchmark. Real PDFs, request identifiers, account data and
runtime databases are not published in documentation or Git.

## Remaining work

Prioritize reliability and native validation before product expansion. Priorities and acceptance
criteria live only in [ROADMAP](../ROADMAP.md), avoiding competing plans in several documents.

This page intentionally excludes transient PIDs, paper counts and claims that the server is
currently running. Read processes, health and task records for live status; historical logs alone
are insufficient.
