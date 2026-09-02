# Workflows

This document describes behavior, not UI instructions. See the [API contract](api-contracts.md)
for transport details and the [data model](data-model.md) for persisted states.

## Import and card generation

1. Validate the PDF and compute SHA-256. A ready exact match returns the existing paper; a
   processing match is rejected. A failed match can be retried under its existing identity.
2. Preserve a managed PDF and create/restart the paper in `processing`.
3. Run Docling and optional formula OCR. Save Markdown, chunks, formula attempts and the search
   index, then mark the parsed paper `ready`.
4. Check possible duplicates by DOI, normalized text and title. Hints do not merge papers.
5. Create a card-generation attempt and call `ResearchLLM`. Only a successful result replaces
   current cards. Provider/validation errors handled by this stage mark the generation failed
   and `card_status=failed` while retaining the parsed paper and any previous cards.

These are separate filesystem operations and database transactions, not one atomic import.
A parser or other unhandled ingest failure marks the paper failed and retains available evidence.
A handled card-generation failure can still leave the upload `succeeded` and paper `ready`:
inspect `card_status` and generation history instead of assuming upload success means cards exist.
Retry cards from the stored chunks without reparsing when the paper is ready.

The queue accepts uploads into `incoming/` and executes one at a time in the service process.
Events report stages and ten-second liveness heartbeats, not a measured percentage of remaining
work. Normal completion cleans up staging files; forced interruption may leave them behind.

## Formula handling

For detected crops, try standard, expanded, and high-resolution extraction until one result passes
structural/token checks. Persist attempt diagnostics and retain a failed crop when available.
A validation pass does not prove mathematical correctness or complete KaTeX compatibility.

The fallback order is validated LaTeX, unvalidated OCR in a fenced `latex` block, Docling source,
then a retained crop/page marker when available. Some unavailable-dependency cases cannot produce
a crop or an attempt record. The frontend supplies a code fallback for remaining rendering errors.
A `partial` formula result does not by itself fail document import.

## Reparse

Require a ready paper and read its managed PDF. Replace Markdown, chunks, formula attempts and
derived search entries. Preserve manual title/year overrides. Reconnect cards by prior chunk
ordinal when possible; changed reading order can change the meaning of a position.

Reparse does not call the LLM, rewrite the original PDF, update card text, or regenerate reports.
Review new source/provenance before requesting a separate billable generation.
Failures may leave partial filesystem changes; this is not a read-only diagnostic or a global transaction.

## Search and deep read

Search uses local FTS5 over papers, chunks and cards, returning ranked results with available
provenance. It is not semantic retrieval.

Deep read requires a ready paper and sends only that paper's stored source chunks, title, and
optional focus to the configured LLM. It saves a new database report and Markdown file; existing
reports remain history. No cross-paper context is added.

## Restart recovery

Each newly built service reconciles old queued/running uploads to `interrupted` because their
in-memory worker no longer exists. Running card generations become failed; papers previously
generating cards become `card_status=ready` when old cards exist, otherwise failed.

Recovery does not automatically replay parsing or billable requests. Confirm the prior outcome
before re-uploading or retrying. Do not construct a second service against an active database:
even maintenance CLI commands can invoke this initialization.

## Archive and permanent purge

Archive sets an archive timestamp and hides the paper from the default list; restore reverses it.
Neither operation removes files or history.

Purge validates managed targets, removes formula diagnostics first, then PDF/Markdown/report
files, and finally deletes the paper record and its cascading dependents. Windows read-only
access-denied gets a bounded attribute-clearing retry on eligible entries; it does not grant ACL
permissions or bypass sharing locks.

On cleanup failure, HTTP 409 preserves the paper record, but already removed files are not restored.
Retry tolerates missing files. Upload history can remain with null paper references; purge is not
a promise to erase every historical mention. Recovery of deleted research requires a prior
[backup](data-storage.md), not reinstalling dependencies.
