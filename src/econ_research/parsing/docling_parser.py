from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from econ_research.models import ParsedChunk, ParsedDocument

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DoclingTextBlock:
    text: str
    is_heading: bool
    page_start: int | None
    page_end: int | None


@dataclass(frozen=True)
class TitlePageMetadata:
    title: str
    authors: list[str]
    year: int | None


class DoclingParser:
    """Docling adapter kept intentionally small for Phase 1."""

    def __init__(self) -> None:
        try:
            from docling.document_converter import DocumentConverter
        except ImportError as exc:  # pragma: no cover - depends on optional heavy runtime
            raise RuntimeError(
                "Docling is not installed. Install the project dependencies before ingestion."
            ) from exc
        self._converter = DocumentConverter()

    def parse(self, pdf_path: Path) -> ParsedDocument:
        result = self._converter.convert(str(pdf_path))
        markdown = result.document.export_to_markdown().strip()
        if not markdown:
            raise ValueError("Docling returned an empty document")
        title = _infer_title(markdown, pdf_path.stem)
        authors: list[str] = []
        year: int | None = None
        title_was_repaired = _looks_damaged(title)
        if title_was_repaired:
            metadata = self._ocr_title_page(pdf_path, title)
            title, authors, year = metadata.title, metadata.authors, metadata.year
            markdown = _replace_first_heading(markdown, title)
            markdown = _replace_title_page_metadata(markdown, authors, year)
        blocks = docling_text_blocks(result.document.texts)
        if title_was_repaired:
            blocks = _replace_first_block_heading(blocks, title)
        return ParsedDocument(
            title=title,
            authors=authors,
            year=year,
            markdown=markdown,
            chunks=chunk_docling_blocks(blocks) if blocks else chunk_markdown(markdown),
        )

    @staticmethod
    def _ocr_title_page(pdf_path: Path, fallback_title: str) -> TitlePageMetadata:
        """Use OCR only for a damaged title page; never replace full-document text blindly."""
        try:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import (
                OcrMode,
                PdfPipelineOptions,
                RapidOcrOptions,
            )
            from docling.document_converter import DocumentConverter, PdfFormatOption

            options = PdfPipelineOptions()
            options.ocr_options = RapidOcrOptions(
                mode=OcrMode.FULL_PAGE, lang=["english"], backend="torch"
            )
            converter = DocumentConverter(
                format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
            )
            document = converter.convert(str(pdf_path), page_range=(1, 1)).document
            ocr_title = _infer_title(document.export_to_markdown(), fallback_title)
            return TitlePageMetadata(
                title=ocr_title,
                authors=_infer_authors(document.texts, ocr_title),
                year=_infer_year(document.texts),
            )
        except Exception as exc:
            # OCR is a quality fallback, not a reason to reject a readable PDF.
            logger.warning("Title-page OCR fallback failed for %s: %s", pdf_path.name, exc)
            return TitlePageMetadata(title=fallback_title, authors=[], year=None)


def _infer_title(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        candidate = re.sub(r"^#+\s*", "", line).strip()
        if candidate and len(candidate) <= 300:
            return candidate
    return fallback


def _replace_first_heading(markdown: str, title: str) -> str:
    lines = markdown.splitlines()
    for index, line in enumerate(lines):
        if re.match(r"^#+\s+", line):
            prefix = line[: len(line) - len(line.lstrip("#"))]
            lines[index] = f"{prefix} {title}"
            return "\n".join(lines)
    return markdown


def _replace_title_page_metadata(markdown: str, authors: list[str], year: int | None) -> str:
    """Synchronize only recognizable title-page metadata returned by focused OCR."""
    if not authors and year is None:
        return markdown
    lines = markdown.splitlines()
    heading_index = next(
        (index for index, line in enumerate(lines) if re.match(r"^#+\s+", line)), None
    )
    if heading_index is None:
        return markdown
    for index in range(heading_index + 1, min(heading_index + 16, len(lines))):
        candidate = lines[index].strip()
        if (
            authors
            and candidate
            and candidate.casefold().startswith(authors[0].split()[0].casefold())
        ):
            lines[index] = ", ".join(authors)
        elif year is not None and re.fullmatch(
            r"(?:January|February|March|April|May|June|July|August|September|October|November|December)?\s*(?:19|20)\d{2}",
            candidate,
        ):
            lines[index] = str(year)
    return "\n".join(lines)


def _looks_damaged(text: str) -> bool:
    return bool(
        re.search(r"[\x00-\x1f\x7f-\x9f]", text)
        or re.search(r"[A-Za-z]\s{2,}[a-z]", text)
        or re.search(r"[A-Za-z]/[A-Za-z]", text)
    )


def _infer_authors(items: list[object], title: str) -> list[str]:
    affiliation_markers = (
        "bank",
        "centre",
        "center",
        "college",
        "crei",
        "department",
        "ecb",
        "imf",
        "institute",
        "nber",
        "school",
        "university",
        "upf",
    )
    marker_pattern = re.compile(
        rf"\s+(?=(?:{'|'.join(affiliation_markers)})\b)", flags=re.IGNORECASE
    )
    for item in items[:12]:
        text = re.sub(r"\s+", " ", str(getattr(item, "text", ""))).strip()
        if not text or text == title or re.search(r"\bchapter\b|\b(19|20)\d{2}\b", text, re.I):
            continue
        candidate = marker_pattern.split(text, maxsplit=1)[0].strip(" ,;")
        words = candidate.split()
        if 2 <= len(words) <= 6 and all(any(char.isalpha() for char in word) for word in words):
            return [candidate]
    return []


def _infer_year(items: list[object]) -> int | None:
    for item in items[:12]:
        match = re.search(r"\b((?:19|20)\d{2})\b", str(getattr(item, "text", "")))
        if match:
            return int(match.group(1))
    return None


def docling_text_blocks(items: list[object]) -> list[DoclingTextBlock]:
    blocks: list[DoclingTextBlock] = []
    for item in items:
        text = str(getattr(item, "text", "")).strip()
        if not text:
            continue
        page_numbers = [
            int(provenance.page_no)
            for provenance in getattr(item, "prov", [])
            if getattr(provenance, "page_no", None) is not None
        ]
        blocks.append(
            DoclingTextBlock(
                text=text,
                is_heading=type(item).__name__ == "SectionHeaderItem",
                page_start=min(page_numbers) if page_numbers else None,
                page_end=max(page_numbers) if page_numbers else None,
            )
        )
    return blocks


def _replace_first_block_heading(
    blocks: list[DoclingTextBlock], title: str
) -> list[DoclingTextBlock]:
    for index, block in enumerate(blocks):
        if block.is_heading:
            replacement = DoclingTextBlock(title, True, block.page_start, block.page_end)
            return [*blocks[:index], replacement, *blocks[index + 1 :]]
    return blocks


def chunk_docling_blocks(
    blocks: list[DoclingTextBlock], max_chars: int = 6000
) -> list[ParsedChunk]:
    """Chunk Docling items while retaining their section and inclusive page range."""
    chunks: list[ParsedChunk] = []
    section: str | None = None
    current: list[DoclingTextBlock] = []
    current_length = 0

    def flush() -> None:
        nonlocal current, current_length
        if not current:
            return
        pages = [
            page
            for block in current
            for page in (block.page_start, block.page_end)
            if page is not None
        ]
        chunks.append(
            ParsedChunk(
                ordinal=len(chunks),
                text="\n\n".join(block.text for block in current),
                section=section,
                page_start=min(pages) if pages else None,
                page_end=max(pages) if pages else None,
            )
        )
        current = []
        current_length = 0

    for block in blocks:
        if block.is_heading:
            flush()
            section = block.text
            continue
        if current and current_length + len(block.text) + 2 > max_chars:
            flush()
        if len(block.text) > max_chars:
            remainder = block.text
            while len(remainder) > max_chars:
                split_at = remainder.rfind(" ", 0, max_chars)
                split_at = split_at if split_at > max_chars // 2 else max_chars
                current.append(
                    DoclingTextBlock(
                        remainder[:split_at].strip(),
                        False,
                        block.page_start,
                        block.page_end,
                    )
                )
                flush()
                remainder = remainder[split_at:].strip()
            if remainder:
                current.append(
                    DoclingTextBlock(remainder, False, block.page_start, block.page_end)
                )
                current_length = len(remainder)
            continue
        current.append(block)
        current_length += len(block.text) + 2
    flush()

    if not chunks:
        raise ValueError("Parsed document contains no usable text blocks")
    return chunks


def chunk_markdown(markdown: str, max_chars: int = 6000) -> list[ParsedChunk]:
    """Split on headings and then size, retaining stable ordinals and section labels."""
    blocks: list[tuple[str | None, str]] = []
    section: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            text = "\n".join(buffer).strip()
            if text:
                blocks.append((section, text))
            buffer.clear()

    for line in markdown.splitlines():
        heading = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if heading:
            flush()
            section = heading.group(1).strip()
        buffer.append(line)
    flush()

    chunks: list[ParsedChunk] = []
    for block_section, block in blocks:
        paragraphs = re.split(r"\n\s*\n", block)
        current = ""
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            if len(current) + len(paragraph) + 2 <= max_chars:
                current = f"{current}\n\n{paragraph}".strip()
                continue
            if current:
                chunks.append(
                    ParsedChunk(ordinal=len(chunks), text=current, section=block_section)
                )
                current = ""
            while len(paragraph) > max_chars:
                split_at = paragraph.rfind(" ", 0, max_chars)
                split_at = split_at if split_at > max_chars // 2 else max_chars
                chunks.append(
                    ParsedChunk(
                        ordinal=len(chunks),
                        text=paragraph[:split_at].strip(),
                        section=block_section,
                    )
                )
                paragraph = paragraph[split_at:].strip()
            current = paragraph
        if current:
            chunks.append(ParsedChunk(ordinal=len(chunks), text=current, section=block_section))

    if not chunks:
        raise ValueError("Parsed Markdown contains no usable text")
    return chunks
