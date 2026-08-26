from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from econ_research.bootstrap import build_service
from econ_research.models import DeepReadResult, IngestResult, Paper, SearchResult
from econ_research.service import PaperNotFoundError, ResearchService

MAX_UPLOAD_BYTES = 100 * 1024 * 1024


class DeepReadRequest(BaseModel):
    focus: str | None = None


def create_app(service: ResearchService | None = None) -> FastAPI:
    application = FastAPI(title="Econ Research API", version="0.1.0")
    application.state.research_service = service

    def get_service(request: Request) -> ResearchService:
        current = request.app.state.research_service
        if current is None:
            current = build_service()
            request.app.state.research_service = current
        return current

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.post("/api/papers", response_model=IngestResult)
    async def ingest_paper(
        request: Request, file: Annotated[UploadFile, File()]
    ) -> IngestResult:
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
    def list_papers(request: Request) -> list[Paper]:
        return get_service(request).list_papers()

    @application.get("/api/papers/{paper_id}", response_model=Paper)
    def get_paper(request: Request, paper_id: str) -> Paper:
        try:
            return get_service(request).get_paper(paper_id)
        except PaperNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.get("/api/search", response_model=list[SearchResult])
    def search(
        request: Request,
        q: str = Query(min_length=1),
        limit: int = Query(default=20, ge=1, le=100),
    ) -> list[SearchResult]:
        return get_service(request).search(q, limit)

    @application.post("/api/papers/{paper_id}/deep-read", response_model=DeepReadResult)
    async def deep_read(
        request: Request, paper_id: str, body: DeepReadRequest
    ) -> DeepReadResult:
        try:
            return await run_in_threadpool(
                get_service(request).deep_read, paper_id, body.focus
            )
        except PaperNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return application


app = create_app()
