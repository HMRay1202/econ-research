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

The OpenAI implementation is isolated behind one small protocol, but Phase 1 does not build a
general multi-provider gateway. Provenance is represented by paper, chunk, page, and section
references where the parser can supply them.

