from __future__ import annotations

import json
from pathlib import Path

import typer

from econ_research.bootstrap import build_service

app = typer.Typer(
    name="research",
    no_args_is_help=True,
    help="Turn economics papers into searchable, traceable research knowledge.",
)


@app.command()
def ingest(pdf: Path) -> None:
    """Preserve, parse, compress, and index one PDF."""
    try:
        result = build_service().ingest(pdf)
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(result.model_dump_json(indent=2))


@app.command()
def reparse(paper_id: str) -> None:
    """Refresh parsed text and page provenance without calling an LLM."""
    try:
        result = build_service().reparse(paper_id)
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(result.model_dump_json(indent=2))


@app.command("search")
def search_command(
    query: str,
    limit: int = typer.Option(20, min=1, max=100, help="Maximum result count."),
) -> None:
    """Search papers, research cards, and source passages."""
    try:
        results = build_service().search(query, limit)
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps([item.model_dump() for item in results], indent=2, ensure_ascii=False))


@app.command("deep-read")
def deep_read_command(
    paper_id: str,
    focus: str | None = typer.Option(None, help="Optional analytical focus."),
) -> None:
    """Generate a source-grounded deep read of one stored paper."""
    try:
        result = build_service().deep_read(paper_id, focus)
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(result.report)


@app.command("usage")
def usage_command(
    paper_id: str | None = typer.Option(None, help="Limit results to one paper ID."),
    operation: str | None = typer.Option(
        None, help="Limit results to generate_cards or deep_read."
    ),
    since: str | None = typer.Option(
        None, help="Only include calls started at or after this ISO-8601 timestamp."
    ),
    details: bool = typer.Option(False, help="Include every matching call record."),
) -> None:
    """Show measured LLM token, estimated cost, and latency totals."""
    try:
        report = build_service().usage(
            paper_id=paper_id,
            operation=operation,
            since=since,
            include_calls=details,
        )
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(report.model_dump_json(indent=2))


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind host."),
    port: int = typer.Option(8000, min=1, max=65535, help="Bind port."),
    reload: bool = typer.Option(False, help="Reload when source files change."),
) -> None:
    """Run the local FastAPI server."""
    import uvicorn

    uvicorn.run("econ_research.api:app", host=host, port=port, reload=reload)


if __name__ == "__main__":  # pragma: no cover
    app()
