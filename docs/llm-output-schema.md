# LLM Output Schema

Cards use the following types: `research-question`, `contribution`, `data`, `identification`,
`assumption`, `econometric-specification`, `result`, `robustness`, `heterogeneity`, `mechanism`,
`limitation`, `external-validity`, and `method`.

Each card contains `type`, `title`, `content`, optional `chunk_id`, page range and section,
`tags`, plus `claim_kind`: `author_claim`, `evidence`, `interpretation`, or
`critical_assessment`. Prompts require explicit uncertainty, forbid turning correlation into
causation, and ask for source-linked claims. Output is validated before persistence.

