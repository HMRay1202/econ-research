from pathlib import Path

from fastapi.testclient import TestClient

from econ_research.api import create_app
from econ_research.service import ResearchService


def test_api_uses_shared_service(service: ResearchService, sample_pdf: Path) -> None:
    client = TestClient(create_app(service))

    home = client.get("/")
    assert home.status_code == 200
    assert "Econ Research" in home.text
    assert client.get("/assets/app.js").status_code == 200
    assert client.get("/assets/styles.css").status_code == 200
    assert client.get("/health").json() == {"status": "ok"}
    with sample_pdf.open("rb") as handle:
        response = client.post(
            "/api/papers", files={"file": ("paper.pdf", handle, "application/pdf")}
        )
    assert response.status_code == 200
    paper_id = response.json()["paper"]["id"]

    assert client.get("/api/papers").status_code == 200
    assert client.get(f"/api/papers/{paper_id}").json()["status"] == "ready"

    cards = client.get(f"/api/papers/{paper_id}/cards")
    assert cards.status_code == 200
    assert len(cards.json()) == 1
    assert cards.json()[0]["type"] == "identification"
    assert cards.json()[0]["chunk_ordinal"] == 0
    assert len(client.get("/api/cards", params={"type": "identification"}).json()) == 1

    chunks = client.get(f"/api/papers/{paper_id}/chunks")
    assert chunks.status_code == 200
    assert len(chunks.json()) == 2

    original = client.get(f"/api/papers/{paper_id}/files/original")
    assert original.status_code == 200
    assert original.content.startswith(b"%PDF-")
    parsed = client.get(f"/api/papers/{paper_id}/files/parsed")
    assert parsed.status_code == 200
    assert "Parallel trends" in parsed.text

    search = client.get("/api/search", params={"q": "parallel trends"})
    assert search.status_code == 200
    assert len(search.json()) == 2

    deep_read = client.post(
        f"/api/papers/{paper_id}/deep-read", json={"focus": "identification"}
    )
    assert deep_read.status_code == 200
    assert deep_read.json()["paper_id"] == paper_id
    deep_read_id = deep_read.json()["id"]

    history = client.get(f"/api/papers/{paper_id}/deep-reads")
    assert history.status_code == 200
    assert history.json()[0]["id"] == deep_read_id
    assert client.get(f"/api/deep-reads/{deep_read_id}").status_code == 200
    download = client.get(f"/api/deep-reads/{deep_read_id}/download")
    assert download.status_code == 200
    assert "parallel trends" in download.text

    usage = client.get(f"/api/papers/{paper_id}/usage", params={"include_calls": True})
    assert usage.status_code == 200
    assert usage.json()["summary"]["call_count"] == 0


def test_api_rejects_non_pdf_upload(service: ResearchService) -> None:
    client = TestClient(create_app(service))
    response = client.post(
        "/api/papers", files={"file": ("notes.txt", b"private notes", "text/plain")}
    )
    assert response.status_code == 400


def test_read_api_returns_not_found(service: ResearchService) -> None:
    client = TestClient(create_app(service))

    assert client.get("/api/papers/missing/cards").status_code == 404
    assert client.get("/api/papers/missing/files/original").status_code == 404
    assert client.get("/api/deep-reads/missing").status_code == 404
    assert client.get("/api/deep-reads/missing/download").status_code == 404


def test_file_api_rejects_path_outside_managed_directory(
    service: ResearchService, sample_pdf: Path
) -> None:
    paper = service.ingest(sample_pdf).paper
    with service.repository.connect() as connection:
        connection.execute(
            "UPDATE papers SET pdf_path = ? WHERE id = ?", (str(sample_pdf), paper.id)
        )

    response = TestClient(create_app(service)).get(
        f"/api/papers/{paper.id}/files/original"
    )

    assert response.status_code == 409
    assert "outside the managed data directory" in response.json()["detail"]
