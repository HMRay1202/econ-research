# Project Charter

## Purpose

Build a local-first economics research workspace that turns papers into traceable, reusable
knowledge. Phase 1 began with the deliberately small goal of reliably ingesting one PDF,
generating searchable research cards, and deep-reading that paper later; it now also supports
batch imports and the local maintenance workflows listed below.

## Phase 1

Phase 1 contains Python, Docling, the OpenAI API, SQLite/FTS5, a shared application service,
a Typer CLI, a FastAPI API, and a local browser workspace. It supports ingestion and non-billable
reparse, lexical search, card generation and regeneration, deep reads, usage history, batch
uploads with progress, duplicate detection, manual paper metadata, and archive/restore/remove
controls.

Original PDFs are authoritative and never modified. Parsed Markdown and chunks remain close
to the source. Cards and deep reads are derived content and may be regenerated; they never
replace the source.

## Non-goals

Phase 1 does not include LangChain, LlamaIndex, RAGFlow, vector databases, PostgreSQL, Redis,
Celery, Docker orchestration, Zotero integration, knowledge graphs, multi-agent workflows,
multiple LLM providers, user accounts, a React frontend, or cloud deployment.

## Current Phase 1 status

The Phase 1 functional scope is complete and usable locally. Functional completion does not
mean every native platform, sleep/wake scenario, or formula extraction has been validated.
The dated verification baseline is maintained in [current status](docs/current-status.md), and
remaining work with acceptance criteria is maintained in [ROADMAP](ROADMAP.md).

Local-first means storage, parsing, and retrieval are local; configured card generation and deep
reads send source text to the model API. Research claims and uncertain formulas must remain
reviewable against the preserved PDF. Operational and privacy details belong in the
[runtime guide](docs/runtime-guide.md), not in this scope document.

## Completion criterion

A real PDF can be preserved, parsed, stored, compressed into cards, found by a known search
term, and deep-read through the installed local application.
