# LLM Output Schema

Cards use the following types: `research-question`, `contribution`, `data`, `identification`,
`assumption`, `econometric-specification`, `result`, `robustness`, `heterogeneity`, `mechanism`,
`limitation`, `external-validity`, and `method`.

The structured LLM output for each card contains `type`, `title`, `content`, optional
`chunk_ordinal`, page range and section, `tags`, plus `claim_kind`: `author_claim`, `evidence`,
`interpretation`, or `critical_assessment`. Prompts require explicit uncertainty, forbid turning
correlation into causation, and ask for source-linked claims. Output is validated before
persistence. When a card is stored, `chunk_ordinal` is resolved to the corresponding `chunk_id`;
the public card API returns both fields when provenance is available.

Card generation consumes the currently stored source chunks. A parser reparse does not alter
existing card content; an explicit regeneration creates a tracked, billable generation attempt.
Only a successful attempt replaces the current cards, while failed attempts remain in generation
history and leave the previous parsed paper available.
