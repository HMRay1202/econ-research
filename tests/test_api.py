from pathlib import Path
from time import sleep

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
    assert client.get("/api/ui-version").json()["version"] == "2026-08-27-formula-v2"
    with sample_pdf.open("rb") as handle:
        response = client.post(
            "/api/papers", files={"file": ("paper.pdf", handle, "application/pdf")}
        )
    assert response.status_code == 200
    paper_id = response.json()["paper"]["id"]
    updated = client.patch(f"/api/papers/{paper_id}", json={"title": "Reviewed title"})
    assert updated.status_code == 200
    assert updated.json()["title"] == "Reviewed title"
    assert updated.json()["title_source"] == "manual"
    updated_year = client.patch(f"/api/papers/{paper_id}", json={"year": 2024})
    assert updated_year.status_code == 200
    assert updated_year.json()["year"] == 2024
    assert updated_year.json()["year_source"] == "manual"

    assert client.get("/api/papers").status_code == 200
    assert client.get(f"/api/papers/{paper_id}").json()["status"] == "ready"
    reparse = client.post(f"/api/papers/{paper_id}/reparse")
    assert reparse.status_code == 200
    assert reparse.json()["paper"]["formula_status"] == "not_run"

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

    deep_read = client.post(f"/api/papers/{paper_id}/deep-read", json={"focus": "identification"})
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


def test_api_queued_upload_card_regeneration_and_archive(
    service: ResearchService, sample_pdf: Path
) -> None:
    client = TestClient(create_app(service))
    with sample_pdf.open("rb") as handle:
        response = client.post(
            "/api/uploads", files={"file": ("queued.pdf", handle, "application/pdf")}
        )
    assert response.status_code == 202
    job_id = response.json()["id"]
    job = response.json()
    for _ in range(40):
        job = client.get(f"/api/uploads/{job_id}").json()
        if job["status"] not in {"queued", "running"}:
            break
        sleep(0.01)
    assert job["status"] == "succeeded"
    paper_id = job["paper_id"]

    generation = client.post(f"/api/papers/{paper_id}/card-generations")
    assert generation.status_code == 200
    assert generation.json()["status"] == "succeeded"
    assert client.get(f"/api/papers/{paper_id}/card-generations").json()

    assert client.delete(f"/api/papers/{paper_id}").status_code == 200
    assert client.get("/api/papers").json() == []
    assert client.post(f"/api/papers/{paper_id}/restore").status_code == 200
    assert client.delete(f"/api/papers/{paper_id}/purge").status_code == 204
    assert client.get(f"/api/papers/{paper_id}").status_code == 404


def test_api_lists_persisted_active_uploads_for_page_refresh(
    service: ResearchService, sample_pdf: Path
) -> None:
    job = service.repository.create_ingest_job("refresh.pdf", str(sample_pdf))
    service.repository.update_ingest_job(
        job.id,
        status="running",
        stage="parsing",
        progress=30,
        message="正在读取并解析 PDF；首次运行可能准备本地模型。",
    )

    jobs = TestClient(create_app(service)).get("/api/uploads").json()

    assert len(jobs) == 1
    assert jobs[0]["id"] == job.id
    assert jobs[0]["message"].startswith("正在读取并解析 PDF")
    assert jobs[0]["updated_at"]


def test_frontend_restores_active_upload_jobs_after_refresh(service: ResearchService) -> None:
    script = TestClient(create_app(service)).get("/assets/app.js")

    assert script.status_code == 200
    assert "async function restoreUploadJobs()" in script.text
    assert 'api("/api/uploads")' in script.text
    assert "job.message" in script.text


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

    response = TestClient(create_app(service)).get(f"/api/papers/{paper.id}/files/original")

    assert response.status_code == 409
    assert "outside the managed data directory" in response.json()["detail"]
