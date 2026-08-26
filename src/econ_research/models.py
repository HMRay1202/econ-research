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
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    status: str
    error: str | None = None
    created_at: str
    updated_at: str


class IngestResult(BaseModel):
    paper: Paper
    chunk_count: int
    card_count: int
    duplicate: bool = False


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

