from pathlib import Path

from typer.testing import CliRunner

from econ_research import cli
from econ_research.service import ResearchService


def test_cli_ingest_search_and_deep_read(
    monkeypatch, service: ResearchService, sample_pdf: Path
) -> None:
    monkeypatch.setattr(cli, "build_service", lambda: service)
    runner = CliRunner()

    ingest = runner.invoke(cli.app, ["ingest", str(sample_pdf)])
    assert ingest.exit_code == 0, ingest.output
    paper_id = service.list_papers()[0].id

    search = runner.invoke(cli.app, ["search", "parallel trends"])
    assert search.exit_code == 0, search.output
    assert "identification" in search.output

    deep_read = runner.invoke(
        cli.app, ["deep-read", paper_id, "--focus", "identification"]
    )
    assert deep_read.exit_code == 0, deep_read.output
    assert "parallel trends" in deep_read.output
