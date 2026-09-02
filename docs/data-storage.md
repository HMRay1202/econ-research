# Data, Storage and Backup

Code, research data, environments, models and installer caches are different assets.
Paths below describe default configuration, not a requirement to copy a particular user's directory.

## Locations

| Content | Default location | In Git? | Purpose |
| --- | --- | --- | --- |
| Source, docs, tests, web assets | Repository root, `src/`, `docs/`, `tests/` | Yes | Recoverable from the repository |
| Configuration and credentials | Repository-root `.env` | No | Keep private; do not include in logs/screenshots |
| SQLite database | `data/research.db` | No | Papers, cards, jobs, usage, search index and other records |
| Original PDFs | `data/originals/` | No | Authoritative source material |
| Parsed Markdown | `data/parsed/` | No | Regenerable, but a later parse can differ |
| Deep-read reports | `data/generated/`; report text also in SQLite | No | Regeneration may cost money and produce different text |
| Formula diagnostic crops | `data/diagnostics/formulas/` | No | Failed/low-confidence recognition evidence |
| Upload staging | `data/incoming/` | No | Temporary inputs; interruption can leave files behind |
| Paddle formula models | `data/models/paddlex/official_models/` | No | First-use weights; current model is PP-FormulaNet_plus-L |
| Docling model cache | Normally user-directory `.cache/huggingface/` | No | Outside project data; potentially shared |
| Main Python environment | Conda installation's `envs/econ-research/` | No | Installed runtime libraries |
| Windows GPU worker | Main environment's `paddle-worker/` | No | Isolated Paddle GPU libraries |
| pip download cache | Query with `python -m pip cache dir` | No | Downloaded installation packages, not installed libraries |
| Conda package cache | Configured package cache, commonly `pkgs/` | No | May be shared across environments |

`.git/` is code history, not a research backup. Logs may contain filenames, paths or request
information and should remain private. Dependency cache environment variables can override the
locations above; inspect the actual local configuration when diagnosing storage.

## Moving folders or machines

`ECON_RESEARCH_DATA_DIR` and `ECON_RESEARCH_DB_PATH` are independent. Changing one does not
automatically move the other. Relative paths depend on the process working directory: launch
from the repository root consistently.

Paths already stored in SQLite are not rewritten when configuration changes. Moving drives,
folders or operating systems may require an explicit path migration. There is no complete
one-click data migration tool; do not delete the database to solve a path mismatch.

A fresh Git clone restores code, not papers, models, libraries or keys. Reinstalling dependencies
and downloading models can rebuild the runtime, but continuing research history also requires
the database, corresponding files and path validation.

## Interpreting disk usage

One Windows CUDA 13 machine was measured on 2026-09-02. These are reference sizes, not minimum
requirements or a promise about another installation:

| Category | Reference size |
| --- | --- |
| Main environment excluding worker | 3.84 GiB |
| Paddle worker | 3.15 GiB |
| Project directory including Paddle weights and a small library | 0.71 GiB |
| Hugging Face model cache | 0.49 GiB |
| Subtotal above | 8.19 GiB |
| Additional pip + Conda installer caches | 6.25 GiB |

Figures sum logical file sizes, not actual allocated disk space. OneDrive placeholders, hard links
and shared caches affect physical accounting. Paddle weights contributed about 701 MiB inside the
project, while Git-tracked content was about 1 MiB. Dependency versions, hardware and paper count
will change these figures.

## Cache cleanup boundaries

- pip caches contain downloaded installers. Clearing them does not uninstall libraries or delete
  research/model files; a later installation may download packages again.
- Model caches are different: removing them can force another download and break offline parsing.
- Do not manually delete pieces of `site-packages`, the worker or Conda environments to clear caches.
- Incoming files and diagnostic crops are not generic download caches. Check task state and
  evidence needs before removing them.
- This guide does not run cleanup. Shared caches and Conda hard-link relationships need separate review.

## Backup and restore

1. Finish uploads, reparse, card and deep-read requests. Stop the app and any other database writers.
2. Back up SQLite together with originals, parsed files, reports and diagnostics; copying the whole
   data directory while stopped is simplest. Include a separately configured database location.
   If SQLite WAL/companion files exist, do not take only the main database file.
3. Back up `.env` privately and record the code version. Do not commit credential-bearing backups.
4. Store a backup independently. Cloud synchronization propagates deletion and is not a sole
   backup strategy; do not let two machines write the same synchronized database.
5. Restore into an isolated location. Check configuration, stored paths and paper/file associations,
   then validate with one instance. Read existing records before initiating paid regeneration.

Models/install caches are optional backup material that can save downloading time; they cannot
replace the database and originals. Cross-platform restore still requires path checks and a
separate migration plan.

## Deletion is not cache cleanup

Archive hides a paper and can be reversed. Purge removes managed files before deleting associated
records. Filesystem and database changes are not one transaction: failed deletion does not restore
files already removed. Upload history may remain with null paper references.

See [data model](data-model.md) and [workflows](workflows.md). Reinstalling libraries cannot recover
research data that was deleted without a backup.
