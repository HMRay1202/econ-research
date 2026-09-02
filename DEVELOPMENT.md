# Development

This guide is for contributors. For installation choices and GPU troubleshooting, use the
[runtime guide](docs/runtime-guide.md); for local data, use [storage and backup](docs/data-storage.md).

## Prepare an environment

Work from the current repository root on every platform, using the Conda environment
`econ-research` with Python 3.11. Never install into Conda `base` or system Python.

~~~text
conda env list
conda env create -f environment.yml
~~~

Run the second command only if the environment is absent. Choose one setup path:

- Offline/unit-test development without formula runtime management:
  `conda run -n econ-research python -m pip install -e ".[dev]"`.
- Full application development with hardware-aware libraries:
  `conda run --no-capture-output -n econ-research python scripts/setup_runtime.py --install`.

Both install development dependencies. Stop the service before changing installed packages.
The shared setup script selects platform libraries; do not manually combine CPU/GPU Paddle or
install the legacy `.[formula-gpu]` extra into the main Windows environment.

## Run checks

~~~text
conda run -n econ-research ruff check .
conda run -n econ-research pytest
conda run -n econ-research python -m pip check
~~~

Tests use temporary fixtures and parser/LLM doubles by default. Native Windows tests exercise CMD,
PowerShell and file attributes; passing platform-policy tests does not prove native macOS or GPU
installation success. The dated results belong in [current status](docs/current-status.md), not
in each installation document.

Do not run a real ingest, deep read, or card regeneration merely to test documentation. Real
model calls require explicit authorization and a configured key. Inspect usage before/after an
authorized call; for an active backend use its usage API/UI rather than building another service
against the same database. CLI commands that construct `ResearchService` also run startup recovery.

## Run and debug

Use the platform launcher for interactive work or, from the repository root:

~~~text
conda run --no-capture-output -n econ-research research serve
~~~

Do not start a second instance against the same database. Read the actual foreground output, not
an old redirected log. Stop the service before editing an executing CMD launcher, updating the
checkout, repairing dependencies, or copying a database backup.

To debug OCR, inspect paper formula counts/status and the attempt endpoint before changing
packages. A `partial` result is not a server failure. Use local synthetic fixtures rather than
committing real PDFs, extracted text, credentials, request IDs, or database snapshots.

A reparse is non-billable but mutates derived text and provenance; it is not a read-only diagnostic.
Existing cards keep their text. Regeneration is a separate, potentially billable operation.

## Change discipline

1. Keep CLI and HTTP adapters behind `ResearchService`, persistence behind `SQLiteRepository`,
   and provider calls behind `ResearchLLM`.
2. Update [workflows](docs/workflows.md) when behavior changes and
   [data model](docs/data-model.md) when persistence changes.
3. Keep browser-facing changes additive; update [API contracts](docs/api-contracts.md) and tests.
4. Use the shared sanitized renderer for Markdown; follow [frontend rules](docs/frontend.md).
5. Add offline regression tests. Record native validation gaps honestly.
6. Update the owning document from the [documentation index](docs/index.md), linking rather than
   copying hardware profiles, setup commands, or roadmap entries everywhere.

Schema changes must be additive or explicitly migrated. Never delete runtime data to make tests
or a new schema work. Git ignores runtime data but is not a substitute for reviewing staged files.

## Commit and publish

Review `git status --short --branch` and the actual diff, including untracked files.
Stage only intended source, tests, and documentation. Check `git diff --cached --check` and
scan for secrets, runtime data, binaries, and unexpected deletions before committing.

A local commit is not a push. Push only when requested, without force; verify the remote SHA,
then update the [change record](CHANGELOG.md) and [current status](docs/current-status.md).
The old [publication audit](docs/release-readiness.md) is historical evidence, not a new release instruction.
