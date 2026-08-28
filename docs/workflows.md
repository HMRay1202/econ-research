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
on the paper. Recognition is best-effort: failed validation is retried with expanded crops; if
all attempts fail, raw OCR is kept as a non-rendered fenced `latex` block (or a visible page
marker when no OCR text exists), so the source remains available to chunks and LLM prompts while
the model is told to treat it as unvalidated. Regenerate cards separately if corrected formulas
should be included in card prompts.

## Deep read

Load only the selected paper and its stored source chunks, ask the LLM for an economics-specific
analysis, save the derived report, and return it. Cross-paper context is not included.
