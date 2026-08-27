from __future__ import annotations

import hashlib
import logging
import re
import shutil
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

from econ_research.db.repository import SQLiteRepository
from econ_research.llm.base import ResearchLLM
from econ_research.llm.telemetry import LLMCallError, LLMResult
from econ_research.models import (
    CardGeneration,
    CardType,
    ClaimKind,
    DeepReadResult,
    DeepReadSummary,
    IngestJob,
    IngestResult,
    Paper,
    ParsedChunk,
    ParsedDocument,
    ReparseResult,
    ResearchCard,
    SourceChunk,
    UsageReport,
)
from econ_research.parsing.base import Parser

logger = logging.getLogger(__name__)


class PaperNotFoundError(LookupError):
    pass


class DuplicateInProgressError(RuntimeError):
    pass


class DeepReadNotFoundError(LookupError):
    pass


def _stage_message(stage: str) -> str:
    return {
        "parsing": "正在读取并解析 PDF；首次运行可能准备本地模型。",
        "generating_cards": "正在生成研究卡片。",
        "saving": "正在保存解析结果和索引。",
    }.get(stage, f"正在执行：{stage}。")


class ResearchService:
    def __init__(
        self,
        repository: SQLiteRepository,
        parser: Parser,
        llm: ResearchLLM,
        originals_dir: Path,
        parsed_dir: Path,
        generated_dir: Path,
    ):
        self.repository = repository
        self.parser = parser
        self.llm = llm
        self.originals_dir = originals_dir
        self.parsed_dir = parsed_dir
        self.generated_dir = generated_dir
        self.incoming_dir = originals_dir.parent / "incoming"
        for directory in (originals_dir, parsed_dir, generated_dir, self.incoming_dir):
            directory.mkdir(parents=True, exist_ok=True)
        self.repository.initialize()
        self.repository.interrupt_running_jobs()
        self.repository.recover_orphaned_processing_papers()
        self._jobs = ThreadPoolExecutor(max_workers=1, thread_name_prefix="econ-research-ingest")

    def ingest(
        self, source: Path | str, on_stage: Callable[[str, int], None] | None = None
    ) -> IngestResult:
        source_path = Path(source).expanduser().resolve()
        self._validate_pdf(source_path)
        sha256 = _sha256(source_path)
        existing = self.repository.find_by_sha256(sha256)
        if existing:
            if existing.status == "ready":
                return IngestResult(
                    paper=existing,
                    chunk_count=len(self.repository.get_chunks(existing.id)),
                    card_count=self.repository.count_cards(existing.id),
                    duplicate=True,
                )
            if existing.status == "processing":
                raise DuplicateInProgressError(
                    f"This PDF is already being processed ({existing.id})."
                )
            paper_id = existing.id
            pdf_path = Path(existing.pdf_path)
        else:
            paper_id = str(uuid4())
            pdf_path = self.originals_dir / f"{paper_id}.pdf"
        markdown_path = self.parsed_dir / f"{paper_id}.md"
        if source_path != pdf_path.resolve():
            shutil.copy2(source_path, pdf_path)
        if existing:
            self.repository.restart_failed_paper(paper_id, source_path.name, str(pdf_path))
        else:
            self.repository.create_processing_paper(
                paper_id, sha256, source_path.name, str(pdf_path)
            )
        try:
            if on_stage:
                on_stage("parsing", 30)
            document = self.parser.parse(pdf_path)
            markdown_path.write_text(document.markdown, encoding="utf-8")
            chunk_count, _ = self.repository.finalize_ingest(
                paper_id, str(markdown_path), document, []
            )
            possible_duplicate = self.repository.find_possible_duplicate(
                doi=_extract_doi(document.markdown),
                normalized_text_sha256=_normalized_text_sha256(document.markdown),
                title=document.title,
            )
            self.repository.update_document_identity(
                paper_id,
                doi=_extract_doi(document.markdown),
                normalized_text_sha256=_normalized_text_sha256(document.markdown),
            )
            if on_stage:
                on_stage("generating_cards", 75)
            self.regenerate_cards(paper_id)
            card_count = self.repository.count_cards(paper_id)
            if on_stage:
                on_stage("saving", 95)
        except Exception as exc:
            self.repository.mark_failed(paper_id, f"{type(exc).__name__}: {exc}")
            raise
        completed = self.repository.get_paper(paper_id)
        assert completed is not None
        return IngestResult(
            paper=completed,
            chunk_count=chunk_count,
            card_count=card_count,
            possible_duplicate_of=(possible_duplicate.id if possible_duplicate else None),
        )

    def queue_upload(self, source: Path | str) -> IngestJob:
        """Persist an uploaded file, then process it in the local single-worker queue."""
        source_path = Path(source).resolve()
        upload_path = self.incoming_dir / f"{uuid4()}-{source_path.name}"
        shutil.copy2(source_path, upload_path)
        job = self.repository.create_ingest_job(source_path.name, str(upload_path))
        self._report_ingest_job(
            job.id, stage="queued", progress=0, message="已保存上传文件，正在等待导入队列。"
        )
        self._jobs.submit(self._run_ingest_job, job.id, upload_path)
        return job

    def _run_ingest_job(self, job_id: str, upload_path: Path) -> None:
        self._report_ingest_job(
            job_id,
            status="running",
            stage="validating",
            progress=5,
            message="正在验证 PDF 文件。",
        )
        try:
            result = self.ingest(
                upload_path,
                on_stage=lambda stage, progress: self._report_ingest_job(
                    job_id, stage=stage, progress=progress, message=_stage_message(stage)
                ),
            )
            self._report_ingest_job(
                job_id,
                status="succeeded",
                stage="completed",
                progress=100,
                paper_id=result.paper.id,
                duplicate_of=result.paper.id if result.duplicate else result.possible_duplicate_of,
                message="导入完成，论文现已显示在资料库中。",
                complete=True,
            )
        except Exception as exc:
            self._report_ingest_job(
                job_id,
                status="failed",
                stage="failed",
                progress=100,
                message="导入失败；请查看下方错误信息后重试。",
                error=f"{type(exc).__name__}: {exc}"[:2000],
                complete=True,
            )
        finally:
            upload_path.unlink(missing_ok=True)

    def get_ingest_job(self, job_id: str) -> IngestJob:
        job = self.repository.get_ingest_job(job_id)
        if not job:
            raise PaperNotFoundError(f"Upload task not found: {job_id}")
        return job

    def list_ingest_jobs(self, *, active_only: bool = True) -> list[IngestJob]:
        return self.repository.list_ingest_jobs(active_only=active_only)

    def _report_ingest_job(
        self,
        job_id: str,
        *,
        status: str | None = None,
        stage: str | None = None,
        progress: int | None = None,
        message: str | None = None,
        paper_id: str | None = None,
        duplicate_of: str | None = None,
        error: str | None = None,
        complete: bool = False,
    ) -> None:
        self.repository.update_ingest_job(
            job_id,
            status=status,
            stage=stage,
            progress=progress,
            message=message,
            paper_id=paper_id,
            duplicate_of=duplicate_of,
            error=error,
            complete=complete,
        )
        if message:
            logger.info("Upload %s [%s]: %s", job_id, stage or "update", message)
            print(f"[Econ Research] upload {job_id}: {message}", flush=True)

    def regenerate_cards(self, paper_id: str) -> CardGeneration:
        paper = self.get_paper(paper_id)
        if paper.status != "ready":
            raise PaperNotFoundError(f"Ready paper not found: {paper_id}")
        chunks = self.repository.get_chunks(paper_id)
        document = ParsedDocument(
            title=paper.title or paper.source_filename,
            authors=paper.authors,
            year=paper.year,
            markdown="\n\n".join(str(chunk["text"]) for chunk in chunks),
            chunks=[
                ParsedChunk(
                    **{
                        key: chunk[key]
                        for key in ("ordinal", "text", "section", "page_start", "page_end")
                    }
                )
                for chunk in chunks
            ],
        )
        generation = self.repository.create_card_generation(paper_id)
        try:
            generated = self.llm.generate_cards(document)
            if isinstance(generated, LLMResult):
                self.repository.save_llm_call(paper_id, "generate_cards", generated.metrics)
                cards = generated.value
            else:
                cards = generated
            count = self.repository.replace_cards(paper_id, generation.id, cards)
            self.repository.finish_card_generation(generation.id, card_count=count)
        except LLMCallError as exc:
            self.repository.save_llm_call(paper_id, "generate_cards", exc.metrics)
            self.repository.finish_card_generation(generation.id, error=str(exc))
        except Exception as exc:
            self.repository.finish_card_generation(
                generation.id, error=f"{type(exc).__name__}: {exc}"
            )
        return self.repository.list_card_generations(paper_id)[0]

    def list_card_generations(self, paper_id: str) -> list[CardGeneration]:
        self.get_paper(paper_id)
        return self.repository.list_card_generations(paper_id)

    def archive_paper(self, paper_id: str, archived: bool = True) -> Paper:
        self.get_paper(paper_id)
        self.repository.set_archived(paper_id, archived)
        return self.get_paper(paper_id)

    def update_paper_metadata(
        self,
        paper_id: str,
        *,
        title: str | None = None,
        update_title: bool = False,
        year: int | None = None,
        update_year: bool = False,
    ) -> Paper:
        if not update_title and not update_year:
            raise ValueError("provide a title or year to update")
        if update_title:
            if title is None:
                raise ValueError("title must contain 1 to 300 characters")
            title = " ".join(title.split())
            if not 1 <= len(title) <= 300:
                raise ValueError("title must contain 1 to 300 characters")
        if update_year and year is not None and not 1000 <= year <= 2100:
            raise ValueError("year must be between 1000 and 2100")
        paper = self.repository.update_paper_metadata(
            paper_id,
            title=title,
            update_title=update_title,
            year=year,
            update_year=update_year,
        )
        if not paper:
            raise PaperNotFoundError(f"Paper not found: {paper_id}")
        return paper

    def update_paper_title(self, paper_id: str, title: str) -> Paper:
        """Compatibility wrapper for callers that update only the title."""
        return self.update_paper_metadata(paper_id, title=title, update_title=True)

    def permanently_delete_paper(self, paper_id: str) -> None:
        """Irreversibly remove one paper and only its files inside managed directories."""
        paper = self.get_paper(paper_id)
        source_paths, deep_read_ids = self.repository.paper_deletion_paths(paper_id)
        managed_paths = [
            self._managed_file_if_present(path, self.originals_dir) for path in source_paths
        ]
        if paper.markdown_path:
            managed_paths.append(
                self._managed_file_if_present(paper.markdown_path, self.parsed_dir)
            )
        managed_paths.extend(
            self._managed_file_if_present(
                str(self.generated_dir / f"deep-read-{deep_read_id}.md"), self.generated_dir
            )
            for deep_read_id in deep_read_ids
        )
        self.repository.delete_paper(paper_id)
        for path in managed_paths:
            if path is not None:
                path.unlink()

    def search(self, query: str, limit: int = 20):
        return self.repository.search(query, limit)

    def reparse(self, paper_id: str) -> ReparseResult:
        """Refresh derived text and provenance without any LLM call or card regeneration."""
        paper = self.get_paper(paper_id)
        if paper.status != "ready":
            raise PaperNotFoundError(f"Ready paper not found: {paper_id}")
        pdf_path = self._managed_file(paper.pdf_path, self.originals_dir)
        document = self.parser.parse(pdf_path)
        markdown_path = self.parsed_dir / f"{paper_id}.md"
        markdown_path.write_text(document.markdown, encoding="utf-8")
        reconnected = self.repository.refresh_parsed_document(
            paper_id, str(markdown_path), document
        )
        refreshed = self.get_paper(paper_id)
        return ReparseResult(
            paper=refreshed,
            chunk_count=len(document.chunks),
            reconnected_card_count=reconnected,
        )

    def deep_read(self, paper_id: str, focus: str | None = None) -> DeepReadResult:
        paper = self.repository.get_paper(paper_id)
        if not paper or paper.status != "ready":
            raise PaperNotFoundError(f"Ready paper not found: {paper_id}")
        chunks = self.repository.get_chunks(paper_id)
        document = ParsedDocument(
            title=paper.title or paper.source_filename,
            authors=paper.authors,
            year=paper.year,
            markdown="\n\n".join(str(chunk["text"]) for chunk in chunks),
            chunks=[
                ParsedChunk(
                    ordinal=int(chunk["ordinal"]),
                    text=str(chunk["text"]),
                    section=str(chunk["section"]) if chunk["section"] is not None else None,
                    page_start=chunk["page_start"],
                    page_end=chunk["page_end"],
                )
                for chunk in chunks
            ],
        )
        try:
            generated_report = self.llm.deep_read(document, focus)
        except LLMCallError as exc:
            self.repository.save_llm_call(paper_id, "deep_read", exc.metrics)
            raise
        if isinstance(generated_report, LLMResult):
            self.repository.save_llm_call(paper_id, "deep_read", generated_report.metrics)
            report = generated_report.value
        else:  # Test doubles and custom local backends may omit telemetry.
            report = generated_report
        result = self.repository.save_deep_read(paper_id, focus, report)
        report_path = self.generated_dir / f"deep-read-{result.id}.md"
        report_path.write_text(report, encoding="utf-8")
        return result

    def get_paper(self, paper_id: str) -> Paper:
        paper = self.repository.get_paper(paper_id)
        if not paper:
            raise PaperNotFoundError(f"Paper not found: {paper_id}")
        return paper

    def list_papers(self, *, include_archived: bool = False) -> list[Paper]:
        return self.repository.list_papers(include_archived=include_archived)

    def list_cards(
        self,
        *,
        paper_id: str | None = None,
        card_type: CardType | None = None,
        claim_kind: ClaimKind | None = None,
        limit: int = 200,
    ) -> list[ResearchCard]:
        if paper_id:
            self.get_paper(paper_id)
        return self.repository.list_cards(
            paper_id=paper_id,
            card_type=card_type,
            claim_kind=claim_kind,
            limit=limit,
        )

    def list_chunks(self, paper_id: str) -> list[SourceChunk]:
        self.get_paper(paper_id)
        return self.repository.list_source_chunks(paper_id)

    def list_deep_reads(self, paper_id: str) -> list[DeepReadSummary]:
        self.get_paper(paper_id)
        return self.repository.list_deep_reads(paper_id)

    def get_deep_read(self, deep_read_id: str) -> DeepReadResult:
        result = self.repository.get_deep_read(deep_read_id)
        if not result:
            raise DeepReadNotFoundError(f"Deep read not found: {deep_read_id}")
        return result

    def original_pdf_path(self, paper_id: str) -> Path:
        paper = self.get_paper(paper_id)
        return self._managed_file(paper.pdf_path, self.originals_dir)

    def parsed_markdown_path(self, paper_id: str) -> Path:
        paper = self.get_paper(paper_id)
        if not paper.markdown_path:
            raise FileNotFoundError(f"Parsed document not available: {paper_id}")
        return self._managed_file(paper.markdown_path, self.parsed_dir)

    def deep_read_path(self, deep_read_id: str) -> Path:
        self.get_deep_read(deep_read_id)
        return self._managed_file(
            str(self.generated_dir / f"deep-read-{deep_read_id}.md"), self.generated_dir
        )

    def usage(
        self,
        *,
        paper_id: str | None = None,
        operation: str | None = None,
        since: str | None = None,
        include_calls: bool = False,
    ) -> UsageReport:
        if operation not in (None, "generate_cards", "deep_read"):
            raise ValueError("operation must be generate_cards or deep_read")
        return self.repository.usage_report(
            paper_id=paper_id,
            operation=operation,
            since=since,
            include_calls=include_calls,
        )

    @staticmethod
    def _validate_pdf(path: Path) -> None:
        if not path.is_file():
            raise FileNotFoundError(f"PDF not found: {path}")
        if path.suffix.lower() != ".pdf":
            raise ValueError("Input must have a .pdf extension")
        with path.open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                raise ValueError("Input does not have a valid PDF header")

    @staticmethod
    def _managed_file(raw_path: str, root: Path) -> Path:
        candidate = Path(raw_path).resolve()
        managed_root = root.resolve()
        if not candidate.is_relative_to(managed_root):
            raise ValueError("Stored file path is outside the managed data directory")
        if not candidate.is_file():
            raise FileNotFoundError(f"Stored file not found: {candidate.name}")
        return candidate

    @staticmethod
    def _managed_file_if_present(raw_path: str, root: Path) -> Path | None:
        candidate = Path(raw_path).resolve()
        managed_root = root.resolve()
        if not candidate.is_relative_to(managed_root):
            raise ValueError("Stored file path is outside the managed data directory")
        return candidate if candidate.is_file() else None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalized_text_sha256(markdown: str) -> str:
    normalized = re.sub(r"\s+", " ", markdown).strip().casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _extract_doi(markdown: str) -> str | None:
    match = re.search(r"\b10\.\d{4,9}/[-._;()/:a-z0-9]+", markdown, flags=re.IGNORECASE)
    return match.group(0).rstrip(".,;:)").lower() if match else None
