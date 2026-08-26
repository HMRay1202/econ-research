# Architecture

```text
CLI ---------+
             +--> ResearchService --> Parser
FastAPI -----+                    --> LLM
                                  --> SQLiteRepository
```

`ResearchService` owns the three workflows. Interfaces only translate input/output and do not
duplicate research logic. `Parser` converts a PDF to `ParsedDocument`. `ResearchLLM` generates
cards and deep reads. `SQLiteRepository` persists and searches data.

The OpenAI adapter returns the domain result together with measured call metadata. The service
associates that metadata with the paper and the repository stores it in `llm_calls`; CLI and API
usage views read the same records. Price rates are copied into each call so historical estimates
remain stable when the active price table changes. Failed provider calls are recorded when an API
attempt was made, while local test doubles may omit telemetry.

The OpenAI implementation is isolated behind one small protocol, but Phase 1 does not build a
general multi-provider gateway. Provenance is represented by paper, chunk, page, and section
references where the parser can supply them.
