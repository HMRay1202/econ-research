"""Optional, failure-isolated formula OCR for Docling-detected formula regions."""

from __future__ import annotations

import logging
import os
import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class FormulaRecognizer(Protocol):
    def recognize(self, image_path: Path) -> str: ...


@dataclass(frozen=True)
class FormulaCandidate:
    item_id: int
    text: str
    page_no: int
    bbox: object


@dataclass(frozen=True)
class FormulaEnrichmentResult:
    replacements: dict[int, str]
    detected: int
    recognized: int
    fallback: int
    status: str
    error: str | None = None


class PaddleFormulaRecognizer:
    """Lazy adapter for PaddleOCR 3's FormulaRecognition pipeline.

    PaddleOCR remains an optional dependency so ordinary text-only imports do not add a
    multi-gigabyte runtime.  Its output wrappers have changed across PaddleOCR 3 releases;
    extraction is deliberately tolerant of the documented ``rec_formula`` JSON field.
    """

    def __init__(
        self, model_name: str = "PP-FormulaNet_plus-L", cache_dir: Path | None = None
    ) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir
        self._pipeline: Any | None = None

    def set_cache_dir(self, cache_dir: Path) -> None:
        if self._pipeline is None:
            self.cache_dir = cache_dir

    def recognize(self, image_path: Path) -> str:
        if self._pipeline is None:
            if self.cache_dir is not None:
                # PaddleX otherwise writes under ~/.paddlex, which is both machine-global and
                # outside this application's managed runtime directory.
                os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(self.cache_dir))
            try:
                for module_name in ("paddle", "paddleocr", "ftfy"):
                    import_module(module_name)
                from paddleocr import FormulaRecognition
            except ImportError as exc:  # pragma: no cover - depends on optional runtime
                raise FormulaOcrUnavailableError(
                    f"PaddleOCR Formula dependency is missing ({exc.name}). Run: "
                    "python -m pip install -e '.[formula]'"
                ) from exc
            self._pipeline = FormulaRecognition(model_name=self.model_name)
        for result in self._pipeline.predict(str(image_path)):
            value = _find_formula_value(_as_mapping(result))
            if value:
                return value
        raise ValueError("PaddleOCR returned no formula text")


class FormulaOcrUnavailableError(RuntimeError):
    pass


class PdfFormulaCropper:
    """Render only one Docling formula bounding box, never a whole paper as OCR input."""

    def crop(self, pdf_path: Path, candidate: FormulaCandidate, output_path: Path) -> None:
        try:
            import pypdfium2 as pdfium
        except ImportError as exc:  # pragma: no cover - docling normally provides this
            message = "pypdfium2 is required to crop formula regions"
            raise FormulaOcrUnavailableError(message) from exc
        document = pdfium.PdfDocument(str(pdf_path))
        try:
            page = document[candidate.page_no - 1]
            image = page.render(scale=2.0).to_pil()
            page_width, page_height = page.get_size()
            left, top, right, bottom = _bbox_to_pixels(
                candidate.bbox, float(page_width), float(page_height), 2.0
            )
            # Small padding prevents clipped superscripts/subscripts at a detected boundary.
            padding = 8
            left = max(0, left - padding)
            top = max(0, top - padding)
            right = min(image.width, right + padding)
            bottom = min(image.height, bottom + padding)
            if right <= left or bottom <= top:
                raise ValueError("formula bounding box is empty")
            image.crop((left, top, right, bottom)).save(output_path)
        finally:
            document.close()


class FormulaEnricher:
    """Recognize only Docling-labelled formulas and preserve a safe original-text fallback."""

    def __init__(
        self,
        recognizer: FormulaRecognizer | None = None,
        cropper: PdfFormulaCropper | None = None,
        max_formulas: int = 80,
    ) -> None:
        self.recognizer = recognizer or PaddleFormulaRecognizer()
        self.cropper = cropper or PdfFormulaCropper()
        self.max_formulas = max_formulas

    def enrich(
        self,
        pdf_path: Path,
        items: list[object],
        on_progress: Callable[[int, int], None] | None = None,
    ) -> FormulaEnrichmentResult:
        candidates = formula_candidates(items)[: self.max_formulas]
        if not candidates:
            if on_progress:
                on_progress(0, 0)
            return FormulaEnrichmentResult({}, 0, 0, 0, "not_found")
        if isinstance(self.recognizer, PaddleFormulaRecognizer):
            self.recognizer.set_cache_dir(pdf_path.parent.parent / "models" / "paddlex")
        replacements: dict[int, str] = {}
        errors: list[str] = []
        unavailable = False
        with tempfile.TemporaryDirectory(prefix="econ-research-formula-") as temporary:
            directory = Path(temporary)
            for index, candidate in enumerate(candidates):
                if on_progress:
                    on_progress(index, len(candidates))
                image_path = directory / f"formula-{index}.png"
                try:
                    self.cropper.crop(pdf_path, candidate, image_path)
                    formula = normalize_formula_latex(self.recognizer.recognize(image_path))
                    replacements[candidate.item_id] = formula
                except FormulaOcrUnavailableError as exc:
                    unavailable = True
                    errors.append(str(exc))
                    logger.info("Formula OCR unavailable; retaining Docling text: %s", exc)
                    break
                except Exception as exc:
                    errors.append(f"page {candidate.page_no}: {type(exc).__name__}: {exc}")
                    logger.warning(
                        "Formula OCR failed on page %s; retaining Docling text: %s",
                        candidate.page_no,
                        exc,
                    )
                if on_progress:
                    on_progress(index + 1, len(candidates))
        recognized = len(replacements)
        fallback = len(candidates) - recognized
        status = "unavailable" if unavailable and not recognized else (
            "ready" if recognized == len(candidates) else "partial" if recognized else "fallback"
        )
        return FormulaEnrichmentResult(
            replacements,
            len(candidates),
            recognized,
            fallback,
            status,
            "; ".join(errors)[:1000] or None,
        )


def formula_candidates(items: list[object]) -> list[FormulaCandidate]:
    candidates: list[FormulaCandidate] = []
    for item in items:
        label = str(getattr(item, "label", "")).upper()
        if "FORMULA" not in label:
            continue
        text = str(getattr(item, "text", "")).strip()
        provenance = next(iter(getattr(item, "prov", []) or []), None)
        page_no = getattr(provenance, "page_no", None)
        bbox = getattr(provenance, "bbox", None)
        # A formula that lacks Docling text still has a page box and is represented in Markdown
        # as ``<!-- formula-not-decoded -->``.  It is exactly the case that needs image OCR.
        if not isinstance(page_no, int) or page_no < 1 or bbox is None:
            continue
        candidates.append(FormulaCandidate(id(item), text, page_no, bbox))
    return candidates


def normalize_formula_latex(value: str) -> str:
    formula = value.strip()
    if formula.startswith("$$") and formula.endswith("$$"):
        formula = formula[2:-2].strip()
    elif formula.startswith("$") and formula.endswith("$"):
        formula = formula[1:-1].strip()
    # Formula OCR occasionally places a punctuation mark immediately before a closing
    # subscript/superscript brace (for example ``x_{t+r,}``). This is not valid content and
    # differs from legitimate interior comma-separated indices such as ``x_{i,j}``.
    formula = re.sub(r",(?=})", "", formula)
    if not formula or len(formula) > 4_000:
        raise ValueError("formula is empty or exceeds the safety limit")
    if any(ord(character) < 32 and character not in "\n\t" for character in formula):
        raise ValueError("formula contains control characters")
    if re.search(r"\d{60,}", formula):
        raise ValueError("formula contains an implausibly long digit run")
    if not re.search(r"[A-Za-z0-9\\]", formula):
        raise ValueError("formula has no recognizable mathematical content")
    if formula.count("{") != formula.count("}"):
        raise ValueError("formula has unbalanced braces")
    return f"$$\n{formula}\n$$"


def apply_formula_replacements(
    markdown: str, items: list[object], replacements: dict[int, str]
) -> str:
    """Replace formula text, or its Docling placeholder, one occurrence at a time."""
    placeholder = "<!-- formula-not-decoded -->"
    for item in items:
        replacement = replacements.get(id(item))
        original = str(getattr(item, "text", "")).strip()
        if not replacement:
            continue
        if original and original in markdown:
            markdown = markdown.replace(original, replacement, 1)
        elif placeholder in markdown:
            markdown = markdown.replace(placeholder, replacement, 1)
    return markdown


def text_override(item: object, replacements: dict[int, str]) -> str | None:
    return replacements.get(id(item))


def _bbox_to_pixels(
    bbox: object, page_width: float, page_height: float, scale: float
) -> tuple[int, int, int, int]:
    left = float(bbox.l)
    right = float(bbox.r)
    first_y = float(bbox.t)
    second_y = float(bbox.b)
    x0, x1 = sorted((left, right))
    y0, y1 = sorted((first_y, second_y))
    # Docling PDF provenance uses bottom-left coordinates. Converting a full rendered page
    # avoids depending on renderer-specific crop-coordinate conventions.
    return (
        round(x0 * scale),
        round((page_height - y1) * scale),
        round(x1 * scale),
        round((page_height - y0) * scale),
    )


def _as_mapping(result: object) -> object:
    json_method = getattr(result, "json", None)
    if callable(json_method):
        return json_method()
    if isinstance(json_method, dict):
        return json_method
    return result


def _find_formula_value(value: object) -> str | None:
    if isinstance(value, dict):
        for key in ("rec_formula", "formula", "latex"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate
        for nested in value.values():
            found = _find_formula_value(nested)
            if found:
                return found
    if isinstance(value, list):
        for nested in value:
            found = _find_formula_value(nested)
            if found:
                return found
    return None
