# Architecture

```text
CLI ------------+
                +--> ResearchService --> Parser
FastAPI API ----+                    --> LLM
                |                    --> SQLiteRepository
Local web UI ---+ (only through /api/*)
```

`ResearchService` owns the four workflows. Interfaces only translate input/output and do not
duplicate research logic. `Parser` converts a PDF to `ParsedDocument`. `ResearchLLM` generates
cards and deep reads. `SQLiteRepository` persists and searches data.

The OpenAI adapter returns the domain result together with measured call metadata. The service
associates that metadata with the paper and the repository stores it in `llm_calls`; CLI and API
usage views read the same records. Price rates are copied into each call so historical estimates
remain stable when the active price table changes. Failed provider calls are recorded when an API
attempt was made, while local test doubles may omit telemetry.

The OpenAI implementation is isolated behind one small protocol, but Phase 1 does not build a
general multi-provider gateway. Provenance is represented by paper, chunk, page, and section
references where the parser can supply them. Reparsing replaces only generated Markdown/chunks,
reconnects cards by stable chunk ordinal, and does not invoke `ResearchLLM`.

The local web UI is a replaceable static client packaged with the Python application. It owns no
business logic or persistence. Managed file endpoints accept opaque record IDs, resolve paths in
the service, and refuse paths outside configured runtime directories; `data/` is never mounted as
a public static directory. See `docs/frontend.md` and `docs/api-contracts.md` for extension rules.
