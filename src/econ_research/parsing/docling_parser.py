from __future__ import annotations

import re
from pathlib import Path

from econ_research.models import ParsedChunk, ParsedDocument


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
        return ParsedDocument(
            title=title,
            markdown=markdown,
            chunks=chunk_markdown(markdown),
        )


def _infer_title(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        candidate = re.sub(r"^#+\s*", "", line).strip()
        if candidate and len(candidate) <= 300:
            return candidate
    return fallback


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

