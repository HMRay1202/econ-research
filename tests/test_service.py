from pathlib import Path

import pytest

from econ_research.db.repository import SQLiteRepository
from econ_research.llm.telemetry import CardGenerationResult, DeepReadGenerationResult
from econ_research.models import LLMCallMetrics, ResearchCardDraft
from econ_research.service import ResearchService


class FailingLLM:
    def generate_cards(self, document):
        raise RuntimeError("simulated API outage")

    def deep_read(self, document, focus=None):
        raise AssertionError("not used")


def metrics(model: str = "gpt-5.6-luna") -> LLMCallMetrics:
    return LLMCallMetrics(
        provider_request_id="chatcmpl-test",
        model=model,
        reasoning_effort="low",
        input_tokens=100,
        output_tokens=20,
        total_tokens=120,
        input_price_per_million=0.2,
        cached_input_price_per_million=0.02,
        cache_write_price_per_million=0.25,
        output_price_per_million=1.2,
        estimated_cost_usd=0.000044,
        duration_ms=250,
        status="succeeded",
        started_at="2026-08-26T10:00:00+00:00",
        completed_at="2026-08-26T10:00:00.250000+00:00",
    )


class MeteredLLM:
    def generate_cards(self, document):
        card = ResearchCardDraft(
            type="identification",
            title="Parallel trends",
            content="Identification relies on parallel trends.",
            chunk_ordinal=0,
            claim_kind="author_claim",
        )
        return CardGenerationResult([card], metrics())

    def deep_read(self, document, focus=None):
        return DeepReadGenerationResult("# Metered report", metrics("gpt-5.6-terra"))


def test_offline_end_to_end_workflow(
    service: ResearchService, sample_pdf: Path, tmp_path: Path
) -> None:
    result = service.ingest(sample_pdf)

    assert result.paper.status == "ready"
    assert result.chunk_count == 2
    assert result.card_count == 1
    assert Path(result.paper.pdf_path).read_bytes() == sample_pdf.read_bytes()
    assert Path(result.paper.markdown_path or "").is_file()

    search_results = service.search("parallel trends")
    assert {item.entity_type for item in search_results} == {"chunk", "card"}
    assert all(item.paper_id == result.paper.id for item in search_results)

    deep_read = service.deep_read(result.paper.id, "identification")
    assert "parallel trends" in deep_read.report
    assert "identification" in deep_read.report
    assert (tmp_path / "data" / "generated" / f"deep-read-{deep_read.id}.md").is_file()


def test_duplicate_pdf_returns_existing_record(service: ResearchService, sample_pdf: Path) -> None:
    first = service.ingest(sample_pdf)
    second = service.ingest(sample_pdf)

    assert second.duplicate is True
    assert second.paper.id == first.paper.id
    assert len(service.list_papers()) == 1


def test_rejects_non_pdf(service: ResearchService, tmp_path: Path) -> None:
    bad = tmp_path / "notes.txt"
    bad.write_text("not a pdf", encoding="utf-8")

    with pytest.raises(ValueError, match=".pdf"):
        service.ingest(bad)


def test_rejects_fake_pdf_header(service: ResearchService, tmp_path: Path) -> None:
    bad = tmp_path / "bad.pdf"
    bad.write_text("not a pdf", encoding="utf-8")

    with pytest.raises(ValueError, match="valid PDF header"):
        service.ingest(bad)


def test_card_failure_preserves_parsed_paper_and_can_retry(
    service: ResearchService, sample_pdf: Path
) -> None:
    working_llm = service.llm
    service.llm = FailingLLM()

    imported = service.ingest(sample_pdf)

    failed = service.list_papers()[0]
    assert imported.paper.status == "ready"
    assert failed.card_status == "failed"
    assert Path(failed.pdf_path).read_bytes() == sample_pdf.read_bytes()
    assert service.repository.get_chunks(failed.id)

    service.llm = working_llm
    retried = service.regenerate_cards(failed.id)
    assert retried.status == "succeeded"
    assert service.get_paper(failed.id).card_status == "ready"
    assert len(service.list_papers()) == 1


def test_archive_hides_and_restores_paper(service: ResearchService, sample_pdf: Path) -> None:
    paper = service.ingest(sample_pdf).paper

    service.archive_paper(paper.id)
    assert service.list_papers() == []
    assert service.list_papers(include_archived=True)[0].archived_at is not None

    restored = service.archive_paper(paper.id, archived=False)
    assert restored.archived_at is None
    assert service.list_papers()[0].id == paper.id


def test_permanent_delete_removes_paper_and_managed_files(
    service: ResearchService, sample_pdf: Path
) -> None:
    paper = service.ingest(sample_pdf).paper
    report = service.deep_read(paper.id)
    pdf_path = Path(paper.pdf_path)
    markdown_path = Path(paper.markdown_path or "")
    report_path = service.generated_dir / f"deep-read-{report.id}.md"

    service.permanently_delete_paper(paper.id)

    with pytest.raises(Exception, match="Paper not found"):
        service.get_paper(paper.id)
    assert not pdf_path.exists()
    assert not markdown_path.exists()
    assert not report_path.exists()


def test_initialize_migrates_existing_database_additively(tmp_path: Path) -> None:
    repository = SQLiteRepository(tmp_path / "legacy.db")
    with repository.connect() as connection:
        connection.execute(
            """CREATE TABLE papers (
                   id TEXT PRIMARY KEY, sha256 TEXT NOT NULL UNIQUE, source_filename TEXT NOT NULL,
                   pdf_path TEXT NOT NULL, markdown_path TEXT, title TEXT,
                   authors_json TEXT NOT NULL,
                   year INTEGER, status TEXT NOT NULL, error TEXT, created_at TEXT NOT NULL,
                   updated_at TEXT NOT NULL)"""
        )

    repository.initialize()
    with repository.connect() as connection:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(papers)")}
    assert {"card_status", "doi", "normalized_text_sha256", "archived_at"} <= columns


def test_usage_tracks_metered_calls(service: ResearchService, sample_pdf: Path) -> None:
    service.llm = MeteredLLM()
    result = service.ingest(sample_pdf)
    service.deep_read(result.paper.id)

    report = service.usage(paper_id=result.paper.id, include_calls=True)

    assert report.summary.call_count == 2
    assert report.summary.input_tokens == 200
    assert report.summary.output_tokens == 40
    assert report.summary.estimated_cost_usd == 0.000088
    assert report.calls is not None
    assert {call.operation for call in report.calls} == {"generate_cards", "deep_read"}


def test_reparse_refreshes_provenance_without_calling_llm(
    service: ResearchService, sample_pdf: Path
) -> None:
    imported = service.ingest(sample_pdf)
    with service.repository.connect() as connection:
        connection.execute("UPDATE cards SET page_start = NULL, page_end = NULL, section = NULL")

    refreshed = service.reparse(imported.paper.id)
    cards = service.list_cards(paper_id=imported.paper.id)

    assert refreshed.chunk_count == 2
    assert refreshed.reconnected_card_count == 1
    assert len(cards) == 1
    assert cards[0].chunk_id is not None
    assert cards[0].page_start == 4
    assert cards[0].page_end == 4
    assert cards[0].section == "Research Design"
    assert service.search("parallel trends")


def test_manual_title_is_preserved_by_reparse(service: ResearchService, sample_pdf: Path) -> None:
    imported = service.ingest(sample_pdf)
    changed = service.update_paper_title(imported.paper.id, "Corrected paper title")

    assert changed.title == "Corrected paper title"
    assert changed.title_source == "manual"

    service.reparse(imported.paper.id)
    refreshed = service.get_paper(imported.paper.id)
    assert refreshed.title == "Corrected paper title"
    assert refreshed.title_source == "manual"


def test_manual_year_is_preserved_by_reparse(service: ResearchService, sample_pdf: Path) -> None:
    imported = service.ingest(sample_pdf)
    changed = service.update_paper_metadata(
        imported.paper.id, year=2020, update_year=True
    )

    assert changed.year == 2020
    assert changed.year_source == "manual"

    service.reparse(imported.paper.id)
    refreshed = service.get_paper(imported.paper.id)
    assert refreshed.year == 2020
    assert refreshed.year_source == "manual"
