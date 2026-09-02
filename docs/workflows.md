# Workflows

## Ingest

Validate the PDF, hash it, reject or return an existing successful import, preserve a private
copy, parse to Markdown/chunks (including ordered Markdown representations of detected tables),
generate cards, and commit all database records in a single workflow. Failures mark the paper as
failed with a diagnostic message.

## Search

Query the FTS5 index and return ranked paper, card, and source-passage results. Every result
includes its paper ID and provenance where applicable.

## Reparse

Load the managed original PDF for a ready paper and run the current parser again. Replace only
the generated Markdown and ordered chunk records, including detected tables, then reconnect cards
to their replacement chunks and fill missing section/page provenance. This workflow never calls the LLM and never
modifies the source PDF, cards' generated text, or deep-read reports. When configured, it also
retries PaddleOCR Formula for each Docling-detected formula region and stores formula diagnostics
on the paper. Recognition is best-effort: only OCR passing structural and supported-command
heuristics becomes renderable LaTeX; this is not a complete KaTeX or mathematical correctness
proof. The browser supplies a safe fallback for remaining rendering errors. Failed or
low-confidence validation is retried with expanded crops; if all
attempts fail, raw OCR is kept as a non-rendered fenced `latex` block, then Docling text, then a
retained crop and visible page marker. Every detected formula therefore retains an output for chunks
and LLM prompts while the model is told to treat it as unvalidated. Regenerate cards separately if corrected formulas
should be included in card prompts.

## Deep read

Load only the selected paper and its stored source chunks, ask the LLM for an economics-specific
analysis, save the derived report, and return it. Cross-paper context is not included.

## Upload interruption recovery

The upload queue uses one in-process worker and persisted task records. A process restart must
reconcile every task that was `queued` or `running`; retaining an old queued record without
resubmitting it creates a task that the browser can display but no worker can advance. Recovery
marks such work interrupted for an explicit retry. It also closes running card generations as
failed while preserving any older completed cards. Interrupted staging files are not treated as
completed papers.

## Permanent purge

Permanent purge removes managed diagnostics and files before deleting the database record. If a
cloud-sync or operating-system lock prevents file removal, the paper remains visible and the purge
can be retried instead of failing after its database record has already disappeared.
Windows access-denied errors on read-only managed entries receive one attribute-clearing retry;
symlinks/junctions, unrelated permission failures, and file-sharing locks are not bypassed. The
database record is retained on failure, but files already removed by that attempt are not restored.
Retry tolerates missing files. Normal archive/restore does not perform this destructive workflow.
