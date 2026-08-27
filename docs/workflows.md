# Workflows

## Ingest

Validate the PDF, hash it, reject or return an existing successful import, preserve a private
copy, parse to Markdown/chunks, generate cards, and commit all database records in a single
workflow. Failures mark the paper as failed with a diagnostic message.

## Search

Query the FTS5 index and return ranked paper, card, and source-passage results. Every result
includes its paper ID and provenance where applicable.

## Reparse

Load the managed original PDF for a ready paper and run the current parser again. Replace only
the generated Markdown and chunk records, then reconnect cards to their same-ordinal replacement
chunks and fill missing section/page provenance. This workflow never calls the LLM and never
modifies the source PDF, cards' generated text, or deep-read reports. When configured, it also
retries PaddleOCR Formula for each Docling-detected formula region and stores formula diagnostics
on the paper. Recognition is best-effort: a bad, unavailable, or timed-out formula crop falls
back to the original Docling text while the rest of the paper remains usable. Regenerate cards
separately if corrected formulas should be included in card prompts.

## Deep read

Load only the selected paper and its stored source chunks, ask the LLM for an economics-specific
analysis, save the derived report, and return it. Cross-paper context is not included.
