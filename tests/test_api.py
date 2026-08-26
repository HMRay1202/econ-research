from pathlib import Path

from fastapi.testclient import TestClient

from econ_research.api import create_app
from econ_research.service import ResearchService


def test_api_uses_shared_service(service: ResearchService, sample_pdf: Path) -> None:
    client = TestClient(create_app(service))

    assert client.get("/health").json() == {"status": "ok"}
    with sample_pdf.open("rb") as handle:
        response = client.post(
            "/api/papers", files={"file": ("paper.pdf", handle, "application/pdf")}
        )
    assert response.status_code == 200
    paper_id = response.json()["paper"]["id"]

    assert client.get("/api/papers").status_code == 200
    assert client.get(f"/api/papers/{paper_id}").json()["status"] == "ready"

    search = client.get("/api/search", params={"q": "parallel trends"})
    assert search.status_code == 200
    assert len(search.json()) == 2

    deep_read = client.post(
        f"/api/papers/{paper_id}/deep-read", json={"focus": "identification"}
    )
    assert deep_read.status_code == 200
    assert deep_read.json()["paper_id"] == paper_id

    usage = client.get(f"/api/papers/{paper_id}/usage", params={"include_calls": True})
    assert usage.status_code == 200
    assert usage.json()["summary"]["call_count"] == 0


def test_api_rejects_non_pdf_upload(service: ResearchService) -> None:
    client = TestClient(create_app(service))
    response = client.post(
        "/api/papers", files={"file": ("notes.txt", b"private notes", "text/plain")}
    )
    assert response.status_code == 400
