from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from econ_research.db.repository import SQLiteRepository
from econ_research.models import ParsedChunk, ParsedDocument, ResearchCardDraft
from econ_research.service import ResearchService


class FakeParser:
    def parse(
        self,
        pdf_path: Path,
        on_progress: Callable[[str, int, str], None] | None = None,
    ) -> ParsedDocument:
        assert pdf_path.read_bytes().startswith(b"%PDF-")
        if on_progress:
            on_progress("parsing", 45, "测试解析器正在读取 PDF。")
        markdown = """# Employment Effects of a Policy

## Research Design

The paper uses difference-in-differences. Parallel trends is the key identifying assumption.

## Results

The estimates report an employment effect with standard errors clustered by state.

| Year | Estimate |
|---|---:|
| 2020 | 1.1291 |
"""
        return ParsedDocument(
            title="Employment Effects of a Policy",
            authors=["A. Economist"],
            year=2025,
            markdown=markdown,
            chunks=[
                ParsedChunk(
                    ordinal=0,
                    section="Research Design",
                    text=(
                        "The paper uses difference-in-differences. Parallel trends is the key "
                        "identifying assumption."
                    ),
                    page_start=4,
                    page_end=4,
                ),
                ParsedChunk(
                    ordinal=1,
                    section="Results",
                    text=(
                        "The estimates report an employment effect with standard errors "
                        "clustered by state.\n\n| Year | Estimate |\n|---|---:|\n| 2020 | 1.1291 |"
                    ),
                    page_start=8,
                    page_end=8,
                ),
            ],
        )


class FakeLLM:
    def generate_cards(self, document: ParsedDocument) -> list[ResearchCardDraft]:
        assert "Parallel trends" in document.markdown
        return [
            ResearchCardDraft(
                type="identification",
                title="Difference-in-differences design",
                content="Identification relies on a parallel trends assumption.",
                chunk_ordinal=0,
                page_start=4,
                page_end=4,
                section="Research Design",
                tags=["difference-in-differences", "parallel trends"],
                claim_kind="author_claim",
            )
        ]

    def deep_read(self, document: ParsedDocument, focus: str | None = None) -> str:
        return (
            "# Deep Read\n\nThe design relies on parallel trends [chunk 0].\n\n"
            f"Focus: {focus or 'general'}"
        )


@pytest.fixture
def service(tmp_path: Path) -> ResearchService:
    data = tmp_path / "data"
    return ResearchService(
        repository=SQLiteRepository(data / "research.db"),
        parser=FakeParser(),
        llm=FakeLLM(),
        originals_dir=data / "originals",
        parsed_dir=data / "parsed",
        generated_dir=data / "generated",
    )


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "sample.pdf"
    path.write_bytes(b"%PDF-1.4\nsynthetic offline test fixture\n%%EOF\n")
    return path
