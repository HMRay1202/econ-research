from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CARD_TYPES = (
    "research-question",
    "contribution",
    "data",
    "identification",
    "assumption",
    "econometric-specification",
    "result",
    "robustness",
    "heterogeneity",
    "mechanism",
    "limitation",
    "external-validity",
    "method",
)

CardType = Literal[
    "research-question",
    "contribution",
    "data",
    "identification",
    "assumption",
    "econometric-specification",
    "result",
    "robustness",
    "heterogeneity",
    "mechanism",
    "limitation",
    "external-validity",
    "method",
]
ClaimKind = Literal["author_claim", "evidence", "interpretation", "critical_assessment"]


class ParsedChunk(BaseModel):
    ordinal: int = Field(ge=0)
    text: str = Field(min_length=1)
    section: str | None = None
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)


class ParsedDocument(BaseModel):
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    markdown: str = Field(min_length=1)
    chunks: list[ParsedChunk] = Field(min_length=1)
    formula_detected: int = Field(default=0, ge=0)
    formula_recognized: int = Field(default=0, ge=0)
    formula_fallback: int = Field(default=0, ge=0)
    formula_status: str = "not_run"
    formula_error: str | None = None


class ResearchCardDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: CardType
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    chunk_ordinal: int | None = Field(default=None, ge=0)
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    section: str | None = None
    tags: list[str] = Field(default_factory=list)
    claim_kind: ClaimKind


class Paper(BaseModel):
    id: str
    sha256: str
    source_filename: str
    pdf_path: str
    markdown_path: str | None = None
    title: str | None = None
    title_source: str = "parser"
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    year_source: str = "parser"
    formula_detected: int = Field(default=0, ge=0)
    formula_recognized: int = Field(default=0, ge=0)
    formula_fallback: int = Field(default=0, ge=0)
    formula_status: str = "not_run"
    formula_error: str | None = None
    status: str
    card_status: str = "pending"
    doi: str | None = None
    archived_at: str | None = None
    error: str | None = None
    created_at: str
    updated_at: str


class IngestResult(BaseModel):
    paper: Paper
    chunk_count: int
    card_count: int
    duplicate: bool = False
    possible_duplicate_of: str | None = None


class IngestJob(BaseModel):
    id: str
    source_filename: str
    status: Literal["queued", "running", "succeeded", "failed", "interrupted"]
    stage: str
    progress: int = Field(ge=0, le=100)
    paper_id: str | None = None
    duplicate_of: str | None = None
    error: str | None = None
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None


class CardGeneration(BaseModel):
    id: str
    paper_id: str
    status: Literal["running", "succeeded", "failed"]
    card_count: int = 0
    error: str | None = None
    created_at: str
    completed_at: str | None = None


class ReparseResult(BaseModel):
    paper: Paper
    chunk_count: int
    reconnected_card_count: int


class SearchResult(BaseModel):
    entity_type: Literal["paper", "chunk", "card"]
    entity_id: str
    paper_id: str
    title: str | None = None
    snippet: str
    rank: float
    section: str | None = None
    page_start: int | None = None
    page_end: int | None = None


class DeepReadResult(BaseModel):
    id: str
    paper_id: str
    focus: str | None = None
    report: str
    created_at: str


class DeepReadSummary(BaseModel):
    id: str
    paper_id: str
    focus: str | None = None
    preview: str
    created_at: str


class SourceChunk(BaseModel):
    id: str
    paper_id: str
    ordinal: int = Field(ge=0)
    text: str
    section: str | None = None
    page_start: int | None = None
    page_end: int | None = None


class ResearchCard(BaseModel):
    id: str
    paper_id: str
    chunk_id: str | None = None
    chunk_ordinal: int | None = None
    type: CardType
    title: str
    content: str
    section: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    tags: list[str] = Field(default_factory=list)
    claim_kind: ClaimKind
    created_at: str


class LLMCallMetrics(BaseModel):
    provider_request_id: str | None = None
    model: str
    reasoning_effort: str
    input_tokens: int = Field(default=0, ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    cache_write_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    input_price_per_million: float | None = None
    cached_input_price_per_million: float | None = None
    cache_write_price_per_million: float | None = None
    output_price_per_million: float | None = None
    estimated_cost_usd: float | None = None
    duration_ms: int = Field(ge=0)
    status: Literal["succeeded", "failed"]
    error: str | None = None
    started_at: str
    completed_at: str


class LLMCall(LLMCallMetrics):
    id: str
    paper_id: str
    operation: Literal["generate_cards", "deep_read"]


class UsageSummary(BaseModel):
    call_count: int = 0
    succeeded_count: int = 0
    failed_count: int = 0
    unpriced_count: int = 0
    input_tokens: int = 0
    cached_input_tokens: int = 0
    cache_write_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0
    total_duration_ms: int = 0
    average_duration_ms: float = 0
    estimated_cost_usd: float = 0


class UsageReport(BaseModel):
    summary: UsageSummary
    calls: list[LLMCall] | None = None
