# Project Charter

## Purpose

Build a local-first economics research workspace that turns papers into traceable, reusable
knowledge. The immediate goal is deliberately smaller: reliably ingest one PDF, generate
searchable research cards, and deep-read that paper later.

## Phase 1

Phase 1 contains Python, Docling, the OpenAI API, SQLite/FTS5, a shared application service,
a Typer CLI, and a minimal FastAPI API. It supports `ingest`, `search`, and `deep-read`.

Original PDFs are authoritative and never modified. Parsed Markdown and chunks remain close
to the source. Cards and deep reads are derived content and may be regenerated; they never
replace the source.

## Non-goals

Phase 1 does not include LangChain, LlamaIndex, RAGFlow, vector databases, PostgreSQL, Redis,
Celery, Docker orchestration, Zotero integration, knowledge graphs, multi-agent workflows,
multiple LLM providers, user accounts, a React frontend, or cloud deployment.

## Completion criterion

A real PDF can be preserved, parsed, stored, compressed into cards, found by a known search
term, and deep-read through the installed local application.

