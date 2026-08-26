from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from uuid import uuid4

from econ_research.db.repository import SQLiteRepository
from econ_research.llm.base import ResearchLLM
from econ_research.models import DeepReadResult, IngestResult, Paper, ParsedChunk, ParsedDocument
from econ_research.parsing.base import Parser


class PaperNotFoundError(LookupError):
    pass


class DuplicateInProgressError(RuntimeError):
    pass


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
        for directory in (originals_dir, parsed_dir, generated_dir):
            directory.mkdir(parents=True, exist_ok=True)
        self.repository.initialize()

    def ingest(self, source: Path | str) -> IngestResult:
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
            document = self.parser.parse(pdf_path)
            markdown_path.write_text(document.markdown, encoding="utf-8")
            cards = self.llm.generate_cards(document)
            valid_ordinals = {chunk.ordinal for chunk in document.chunks}
            invalid_ordinals = {
                card.chunk_ordinal
                for card in cards
                if card.chunk_ordinal is not None and card.chunk_ordinal not in valid_ordinals
            }
            if invalid_ordinals:
                raise ValueError(
                    f"LLM cards reference unknown source chunks: {sorted(invalid_ordinals)}"
                )
            chunk_count, card_count = self.repository.finalize_ingest(
                paper_id, str(markdown_path), document, cards
            )
        except Exception as exc:
            self.repository.mark_failed(paper_id, f"{type(exc).__name__}: {exc}")
            raise
        completed = self.repository.get_paper(paper_id)
        assert completed is not None
        return IngestResult(paper=completed, chunk_count=chunk_count, card_count=card_count)

    def search(self, query: str, limit: int = 20):
        return self.repository.search(query, limit)

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
        report = self.llm.deep_read(document, focus)
        result = self.repository.save_deep_read(paper_id, focus, report)
        report_path = self.generated_dir / f"deep-read-{result.id}.md"
        report_path.write_text(report, encoding="utf-8")
        return result

    def get_paper(self, paper_id: str) -> Paper:
        paper = self.repository.get_paper(paper_id)
        if not paper:
            raise PaperNotFoundError(f"Paper not found: {paper_id}")
        return paper

    def list_papers(self) -> list[Paper]:
        return self.repository.list_papers()

    @staticmethod
    def _validate_pdf(path: Path) -> None:
        if not path.is_file():
            raise FileNotFoundError(f"PDF not found: {path}")
        if path.suffix.lower() != ".pdf":
            raise ValueError("Input must have a .pdf extension")
        with path.open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                raise ValueError("Input does not have a valid PDF header")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
