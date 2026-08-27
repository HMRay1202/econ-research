from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles

from econ_research.bootstrap import build_service
from econ_research.models import (
    CardGeneration,
    CardType,
    ClaimKind,
    DeepReadResult,
    DeepReadSummary,
    IngestJob,
    IngestResult,
    Paper,
    ReparseResult,
    ResearchCard,
    SearchResult,
    SourceChunk,
    UsageReport,
)
from econ_research.service import (
    DeepReadNotFoundError,
    PaperNotFoundError,
    ResearchService,
)

MAX_UPLOAD_BYTES = 100 * 1024 * 1024
WEB_DIR = Path(__file__).with_name("web")
WEB_UI_VERSION = "2026-08-27-formula-v2"


class DeepReadRequest(BaseModel):
    focus: str | None = None


class PaperTitleUpdate(BaseModel):
    title: str | None = None
    year: int | None = None


def create_app(service: ResearchService | None = None) -> FastAPI:
    application = FastAPI(title="Econ Research API", version="0.1.0")
    application.state.research_service = service
    application.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")

    def get_service(request: Request) -> ResearchService:
        current = request.app.state.research_service
        if current is None:
            current = build_service()
            request.app.state.research_service = current
        return current

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/api/ui-version")
    def ui_version() -> dict[str, str]:
        """Lets the launcher distinguish this workspace from an older running process."""
        return {"version": WEB_UI_VERSION}

    @application.get("/", include_in_schema=False)
    def web_app() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html", media_type="text/html")

    @application.post("/api/papers", response_model=IngestResult)
    async def ingest_paper(request: Request, file: Annotated[UploadFile, File()]) -> IngestResult:
        original_name = Path(file.filename or "upload.pdf").name
        if not original_name.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF uploads are accepted")
        try:
            with tempfile.TemporaryDirectory(prefix="econ-research-upload-") as tmp:
                upload_path = Path(tmp) / original_name
                total = 0
                with upload_path.open("wb") as destination:
                    while chunk := await file.read(1024 * 1024):
                        total += len(chunk)
                        if total > MAX_UPLOAD_BYTES:
                            raise HTTPException(status_code=413, detail="PDF exceeds 100 MiB limit")
                        destination.write(chunk)
                return await run_in_threadpool(get_service(request).ingest, upload_path)
        except HTTPException:
            raise
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        finally:
            await file.close()

    @application.get("/api/papers", response_model=list[Paper])
    def list_papers(request: Request, include_archived: bool = False) -> list[Paper]:
        return get_service(request).list_papers(include_archived=include_archived)

    @application.post("/api/uploads", response_model=IngestJob, status_code=202)
    async def queue_upload(request: Request, file: Annotated[UploadFile, File()]) -> IngestJob:
        """Queue an upload so parsing and card generation cannot hold one browser request open."""
        original_name = Path(file.filename or "upload.pdf").name
        if not original_name.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF uploads are accepted")
        try:
            with tempfile.TemporaryDirectory(prefix="econ-research-upload-") as tmp:
                upload_path = Path(tmp) / original_name
                total = 0
                with upload_path.open("wb") as destination:
                    while chunk := await file.read(1024 * 1024):
                        total += len(chunk)
                        if total > MAX_UPLOAD_BYTES:
                            raise HTTPException(status_code=413, detail="PDF exceeds 100 MiB limit")
                        destination.write(chunk)
                return await run_in_threadpool(get_service(request).queue_upload, upload_path)
        finally:
            await file.close()

    @application.get("/api/uploads/{job_id}", response_model=IngestJob)
    def get_upload(request: Request, job_id: str) -> IngestJob:
        try:
            return get_service(request).get_ingest_job(job_id)
        except PaperNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.get("/api/cards", response_model=list[ResearchCard])
    def list_cards(
        request: Request,
        paper_id: str | None = None,
        card_type: Annotated[CardType | None, Query(alias="type")] = None,
        claim_kind: ClaimKind | None = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 200,
    ) -> list[ResearchCard]:
        try:
            return get_service(request).list_cards(
                paper_id=paper_id,
                card_type=card_type,
                claim_kind=claim_kind,
                limit=limit,
            )
        except PaperNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.get("/api/papers/{paper_id}", response_model=Paper)
    def get_paper(request: Request, paper_id: str) -> Paper:
        try:
            return get_service(request).get_paper(paper_id)
        except PaperNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.patch("/api/papers/{paper_id}", response_model=Paper)
    def update_paper_metadata(
        request: Request, paper_id: str, body: PaperTitleUpdate
    ) -> Paper:
        try:
            return get_service(request).update_paper_metadata(
                paper_id,
                title=body.title,
                update_title="title" in body.model_fields_set,
                year=body.year,
                update_year="year" in body.model_fields_set,
            )
        except PaperNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @application.get("/api/papers/{paper_id}/cards", response_model=list[ResearchCard])
    def paper_cards(
        request: Request,
        paper_id: str,
        card_type: Annotated[CardType | None, Query(alias="type")] = None,
        claim_kind: ClaimKind | None = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 200,
    ) -> list[ResearchCard]:
        try:
            return get_service(request).list_cards(
                paper_id=paper_id,
                card_type=card_type,
                claim_kind=claim_kind,
                limit=limit,
            )
        except PaperNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.post("/api/papers/{paper_id}/reparse", response_model=ReparseResult)
    async def reparse_paper(request: Request, paper_id: str) -> ReparseResult:
        """Refresh derived text and formula OCR from the preserved PDF without an LLM call."""
        try:
            return await run_in_threadpool(get_service(request).reparse, paper_id)
        except PaperNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.post("/api/papers/{paper_id}/card-generations", response_model=CardGeneration)
    async def regenerate_cards(request: Request, paper_id: str) -> CardGeneration:
        try:
            return await run_in_threadpool(get_service(request).regenerate_cards, paper_id)
        except PaperNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.get("/api/papers/{paper_id}/card-generations", response_model=list[CardGeneration])
    def card_generations(request: Request, paper_id: str) -> list[CardGeneration]:
        try:
            return get_service(request).list_card_generations(paper_id)
        except PaperNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.delete("/api/papers/{paper_id}", response_model=Paper)
    def archive_paper(request: Request, paper_id: str) -> Paper:
        try:
            return get_service(request).archive_paper(paper_id)
        except PaperNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.post("/api/papers/{paper_id}/restore", response_model=Paper)
    def restore_paper(request: Request, paper_id: str) -> Paper:
        try:
            return get_service(request).archive_paper(paper_id, archived=False)
        except PaperNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.delete("/api/papers/{paper_id}/purge", status_code=204)
    def purge_paper(request: Request, paper_id: str) -> None:
        try:
            get_service(request).permanently_delete_paper(paper_id)
        except PaperNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @application.get("/api/papers/{paper_id}/chunks", response_model=list[SourceChunk])
    def paper_chunks(request: Request, paper_id: str) -> list[SourceChunk]:
        try:
            return get_service(request).list_chunks(paper_id)
        except PaperNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.get("/api/papers/{paper_id}/deep-reads", response_model=list[DeepReadSummary])
    def paper_deep_reads(request: Request, paper_id: str) -> list[DeepReadSummary]:
        try:
            return get_service(request).list_deep_reads(paper_id)
        except PaperNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.get("/api/deep-reads/{deep_read_id}", response_model=DeepReadResult)
    def get_deep_read(request: Request, deep_read_id: str) -> DeepReadResult:
        try:
            return get_service(request).get_deep_read(deep_read_id)
        except DeepReadNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.get("/api/papers/{paper_id}/files/original")
    def original_pdf(request: Request, paper_id: str) -> FileResponse:
        try:
            service = get_service(request)
            paper = service.get_paper(paper_id)
            path = service.original_pdf_path(paper_id)
            return FileResponse(path, media_type="application/pdf", filename=paper.source_filename)
        except (PaperNotFoundError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @application.get("/api/papers/{paper_id}/files/parsed")
    def parsed_markdown(request: Request, paper_id: str) -> FileResponse:
        try:
            service = get_service(request)
            paper = service.get_paper(paper_id)
            path = service.parsed_markdown_path(paper_id)
            filename = f"{Path(paper.source_filename).stem}-parsed.md"
            return FileResponse(path, media_type="text/markdown", filename=filename)
        except (PaperNotFoundError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @application.get("/api/deep-reads/{deep_read_id}/download")
    def download_deep_read(request: Request, deep_read_id: str) -> FileResponse:
        try:
            path = get_service(request).deep_read_path(deep_read_id)
            return FileResponse(
                path,
                media_type="text/markdown",
                filename=f"deep-read-{deep_read_id}.md",
            )
        except (DeepReadNotFoundError, FileNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @application.get("/api/search", response_model=list[SearchResult])
    def search(
        request: Request,
        q: str = Query(min_length=1),
        limit: int = Query(default=20, ge=1, le=100),
    ) -> list[SearchResult]:
        return get_service(request).search(q, limit)

    @application.get("/api/usage", response_model=UsageReport)
    def usage(
        request: Request,
        paper_id: str | None = None,
        operation: str | None = None,
        since: str | None = None,
        include_calls: bool = False,
    ) -> UsageReport:
        try:
            return get_service(request).usage(
                paper_id=paper_id,
                operation=operation,
                since=since,
                include_calls=include_calls,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.get("/api/papers/{paper_id}/usage", response_model=UsageReport)
    def paper_usage(
        request: Request,
        paper_id: str,
        operation: str | None = None,
        since: str | None = None,
        include_calls: bool = False,
    ) -> UsageReport:
        try:
            get_service(request).get_paper(paper_id)
            return get_service(request).usage(
                paper_id=paper_id,
                operation=operation,
                since=since,
                include_calls=include_calls,
            )
        except PaperNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @application.post("/api/papers/{paper_id}/deep-read", response_model=DeepReadResult)
    async def deep_read(request: Request, paper_id: str, body: DeepReadRequest) -> DeepReadResult:
        try:
            return await run_in_threadpool(get_service(request).deep_read, paper_id, body.focus)
        except PaperNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return application


app = create_app()
