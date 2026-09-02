# Change Record

Implementation changes and verified publication outcomes. A Git commit is not a package version;
without a tag, do not describe a push as a formal versioned Release.

## Documentation reorganization — check Git for publication status

- Make the README a concise English entry point and add runtime, storage/backup and navigation guides.
- Distinguish local processing from LLM network calls, and installed environments from installer caches.
- Separate current status from publication history; clarify workflow, relation and API/LLM contracts.
- No business-code or dependency changes, server startup or data migration.

## 2026-09-02 — Windows GPU runtime and paper workflows

Commit [c331715](https://github.com/HMRay1202/econ-research/commit/c331715b049ec5f6a8546eff448d105b563e66ea)
was pushed to `origin/main` and the remote SHA verified. Package version remained `0.1.0`;
no tag or GitHub Release was created.

- Hardware-aware setup, isolated Windows Torch/Paddle GPU processes and first-use model downloads.
- Foreground server control and a fallback stop entry point; Windows read-only deletion retries.
- Formula validation, attempt records and failed crops; safe Markdown/math rendering for cards.
- Recovery of upload and card-generation state after backend interruption.
- 41 changed files; verification and outstanding native coverage are in [current status](docs/current-status.md).

The preceding baseline and publication safety checks are archived in [publication audit](docs/release-readiness.md).
