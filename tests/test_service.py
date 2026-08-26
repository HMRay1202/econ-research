from pathlib import Path

import pytest

from econ_research.service import ResearchService


class FailingLLM:
    def generate_cards(self, document):
        raise RuntimeError("simulated API outage")

    def deep_read(self, document, focus=None):
        raise AssertionError("not used")


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


def test_duplicate_pdf_returns_existing_record(
    service: ResearchService, sample_pdf: Path
) -> None:
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


def test_failed_import_preserves_pdf_and_can_retry(
    service: ResearchService, sample_pdf: Path
) -> None:
    working_llm = service.llm
    service.llm = FailingLLM()

    with pytest.raises(RuntimeError, match="simulated API outage"):
        service.ingest(sample_pdf)

    failed = service.list_papers()[0]
    assert failed.status == "failed"
    assert Path(failed.pdf_path).read_bytes() == sample_pdf.read_bytes()

    service.llm = working_llm
    retried = service.ingest(sample_pdf)
    assert retried.paper.id == failed.id
    assert retried.paper.status == "ready"
    assert len(service.list_papers()) == 1
