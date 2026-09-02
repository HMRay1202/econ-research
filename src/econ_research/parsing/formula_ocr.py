"""Optional, failure-isolated formula OCR for Docling-detected formula regions."""

from __future__ import annotations

import logging
import os
import re
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from typing import Any, Protocol

from econ_research.models import FormulaAttempt, FormulaExtraction
from econ_research.parsing.paddle_process import PaddleProcess, check_worker, worker_python

logger = logging.getLogger(__name__)


def check_formula_dependencies() -> None:
    """Import libraries only, in a Windows-safe order; never construct/download a model."""
    python = worker_python()
    if python is not None:
        check_worker(python)
        return
    # Paddle and CUDA PyTorch ship overlapping native libraries on Windows. Loading
    # PyTorch first avoids Paddle's DLLs shadowing dependencies of torch/lib/shm.dll.
    for module_name in ("torch", "paddle", "ftfy"):
        import_module(module_name)
    _ = import_module("paddleocr").FormulaRecognition
    # A base paddleocr import can succeed even when formula preprocessing extras are absent.
    import_module("paddlex.utils.deps").require_extra("ocr", obj_name="Formula OCR")


def select_paddle_device(paddle_module=None) -> str:
    """Use Paddle's own CUDA capability, not PyTorch's; retain the macOS/CPU path."""
    if paddle_module is None:
        paddle_module = import_module("paddle")
    try:
        if paddle_module.is_compiled_with_cuda() and paddle_module.device.cuda.device_count() > 0:
            return "gpu:0"
    except Exception as exc:
        logger.warning("Paddle CUDA detection failed; using CPU: %s", exc)
    return "cpu"


class FormulaRecognizer(Protocol):
    def recognize(self, image_path: Path) -> str: ...


@dataclass(frozen=True)
class FormulaCandidate:
    item_id: int
    ordinal: int
    text: str
    page_no: int
    bbox: object


@dataclass(frozen=True)
class FormulaCropSpec:
    scale: float
    padding: int
    name: str


@dataclass(frozen=True)
class FormulaEnrichmentResult:
    replacements: dict[int, str]
    detected: int
    recognized: int
    fallback: int
    status: str
    error: str | None = None
    raw_fallbacks: dict[int, str] = field(default_factory=dict)
    failed_item_ids: frozenset[int] = frozenset()
    extractions: list[FormulaExtraction] = field(default_factory=list)


@dataclass(frozen=True)
class FormulaValidationResult:
    valid: bool
    normalized: str | None = None
    error_code: str | None = None
    error_message: str | None = None


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

    def close(self) -> None:
        if isinstance(self._pipeline, PaddleProcess):
            self._pipeline.close()
            self._pipeline = None

    def recognize(self, image_path: Path) -> str:
        if self._pipeline is None:
            python = worker_python()
            if python is not None:
                self._pipeline = PaddleProcess(
                    python, self.model_name,
                    self.cache_dir or Path("data/models/paddlex").resolve(),
                )
        if self._pipeline is None:
            if self.cache_dir is not None:
                # PaddleX otherwise writes under ~/.paddlex, which is both machine-global and
                # outside this application's managed runtime directory.
                os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(self.cache_dir))
            try:
                check_formula_dependencies()
                from paddleocr import FormulaRecognition
            except ImportError as exc:  # pragma: no cover - depends on optional runtime
                raise FormulaOcrUnavailableError(
                    f"PaddleOCR Formula dependency is missing ({exc.name}). Run: "
                    "python -m pip install -e '.[formula]'"
                ) from exc
            device = select_paddle_device()
            logger.info("Paddle formula recognition device: %s", device)
            self._pipeline = FormulaRecognition(model_name=self.model_name, device=device)
        for result in self._pipeline.predict(str(image_path)):
            value = _find_formula_value(_as_mapping(result))
            if value:
                return value
        raise ValueError("PaddleOCR returned no formula text")


class FormulaOcrUnavailableError(RuntimeError):
    pass


class PdfFormulaCropper:
    """Render only one Docling formula bounding box, never a whole paper as OCR input."""

    def crop(
        self,
        pdf_path: Path,
        candidate: FormulaCandidate,
        output_path: Path,
        *,
        scale: float = 2.0,
        padding: int = 8,
    ) -> None:
        try:
            import pypdfium2 as pdfium
        except ImportError as exc:  # pragma: no cover - docling normally provides this
            message = "pypdfium2 is required to crop formula regions"
            raise FormulaOcrUnavailableError(message) from exc
        document = pdfium.PdfDocument(str(pdf_path))
        try:
            page = document[candidate.page_no - 1]
            image = page.render(scale=scale).to_pil()
            page_width, page_height = page.get_size()
            left, top, right, bottom = _bbox_to_pixels(
                candidate.bbox, float(page_width), float(page_height), scale
            )
            # Padding prevents clipped superscripts/subscripts and pieces of cases braces.
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
        self.crop_specs = (
            FormulaCropSpec(2.0, 8, "standard"),
            FormulaCropSpec(3.0, 16, "expanded"),
            FormulaCropSpec(4.0, 24, "high_resolution"),
        )

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
        raw_fallbacks: dict[int, str] = {}
        failed_item_ids: set[int] = set()
        extractions: list[FormulaExtraction] = []
        errors: list[str] = []
        unavailable = False
        diagnostics_dir = pdf_path.parent.parent / "diagnostics" / "formulas" / pdf_path.stem
        with tempfile.TemporaryDirectory(prefix="econ-research-formula-") as temporary:
            directory = Path(temporary)
            for index, candidate in enumerate(candidates):
                if on_progress:
                    on_progress(index, len(candidates))
                raw_formula = ""
                best_raw_formula = ""
                recognized = False
                attempts: list[FormulaAttempt] = []
                selected_crop: Path | None = None
                for attempt, spec in enumerate(self.crop_specs):
                    image_path = directory / f"formula-{index}-{attempt}.png"
                    try:
                        self.cropper.crop(
                            pdf_path,
                            candidate,
                            image_path,
                            scale=spec.scale,
                            padding=spec.padding,
                        )
                        raw_formula = self.recognizer.recognize(image_path).strip()
                        if raw_formula:
                            best_raw_formula = raw_formula
                        validation = validate_formula_latex(raw_formula)
                        attempts.append(
                            FormulaAttempt(
                                formula_ordinal=candidate.ordinal,
                                page_no=candidate.page_no,
                                crop_name=spec.name,
                                scale=spec.scale,
                                padding=spec.padding,
                                raw_output=raw_formula[:4000] or None,
                                normalized_output=validation.normalized,
                                validation_status="validated" if validation.valid else "rejected",
                                error_code=validation.error_code,
                                error_message=validation.error_message,
                            )
                        )
                        if not validation.valid:
                            raise ValueError(
                                validation.error_message or "formula validation failed"
                            )
                        replacements[candidate.item_id] = validation.normalized or ""
                        attempts[-1] = attempts[-1].model_copy(update={"selected": True})
                        selected_crop = image_path
                        recognized = True
                        break
                    except FormulaOcrUnavailableError as exc:
                        unavailable = True
                        errors.append(str(exc))
                        logger.info("Formula OCR unavailable; retaining Docling text: %s", exc)
                        break
                    except Exception as exc:
                        if not attempts or attempts[-1].crop_name != spec.name:
                            attempts.append(
                                FormulaAttempt(
                                    formula_ordinal=candidate.ordinal,
                                    page_no=candidate.page_no,
                                    crop_name=spec.name,
                                    scale=spec.scale,
                                    padding=spec.padding,
                                    raw_output=raw_formula[:4000] or None,
                                    normalized_output=None,
                                    validation_status="error",
                                    error_code=type(exc).__name__,
                                    error_message=str(exc)[:500],
                                )
                            )
                        errors.append(
                            f"page {candidate.page_no} ({spec.name}): "
                            f"{type(exc).__name__}: {exc}"
                        )
                        logger.warning(
                            "Formula OCR attempt failed on page %s (%s): %s",
                            candidate.page_no,
                            spec.name,
                            exc,
                        )
                if not recognized:
                    failed_item_ids.add(candidate.item_id)
                    if best_raw_formula:
                        raw_fallbacks[candidate.item_id] = best_raw_formula
                    selected_crop = image_path if image_path.is_file() else None
                crop_filename = _retain_diagnostic_crop(
                    selected_crop, diagnostics_dir, candidate.ordinal, recognized
                )
                if attempts and crop_filename:
                    attempts[-1] = attempts[-1].model_copy(update={"crop_filename": crop_filename})
                source_text = candidate.text or None
                extraction_status = (
                    "validated"
                    if recognized
                    else "unvalidated"
                    if best_raw_formula
                    else "source_fallback"
                    if source_text
                    else "image_fallback"
                )
                extractions.append(
                    FormulaExtraction(
                        ordinal=candidate.ordinal,
                        page_no=candidate.page_no,
                        status=extraction_status,
                        raw_ocr=best_raw_formula[:4000] or None,
                        source_text=source_text,
                        crop_filename=crop_filename,
                        attempts=attempts,
                    )
                )
                if unavailable:
                    for remaining in candidates[index + 1 :]:
                        failed_item_ids.add(remaining.item_id)
                        extractions.append(
                            FormulaExtraction(
                                ordinal=remaining.ordinal,
                                page_no=remaining.page_no,
                                status="source_fallback"
                                if remaining.text
                                else "image_fallback",
                                source_text=remaining.text or None,
                            )
                        )
                    break
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
            raw_fallbacks,
            frozenset(failed_item_ids),
            extractions,
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
        candidates.append(FormulaCandidate(id(item), len(candidates), text, page_no, bbox))
    return candidates


def normalize_formula_latex(value: str) -> str:
    """Compatibility wrapper for callers that expect invalid input to raise ValueError."""
    result = validate_formula_latex(value)
    if not result.valid:
        raise ValueError(result.error_message or "formula validation failed")
    assert result.normalized is not None
    return result.normalized


def validate_formula_latex(value: str) -> FormulaValidationResult:
    """Conservatively normalize OCR output without accepting unrenderable LaTeX."""
    formula = value.strip()
    if formula.startswith("$$") and formula.endswith("$$"):
        formula = formula[2:-2].strip()
    elif formula.startswith("$") and formula.endswith("$"):
        formula = formula[1:-1].strip()
    formula = re.sub(r"\\eqno\s*\(([^()]*)\)", r"\\tag{\1}", formula)
    formula = formula.replace(r"\upgamma", r"\gamma")
    formula = re.sub(r"\\operatorname\*\{m\s+a\s+x\}", r"\\max", formula)
    formula = re.sub(r"\\operatorname\*\{l\s+i\s+m\}", r"\\lim", formula)
    formula = re.sub(r"\\mathrm\{w\s+h\s+e\s+r\s+e\}", r"\\mathrm{where}", formula)
    formula = re.sub(r"\\mathrm\{a\s+n\s+d\}", r"\\mathrm{and}", formula)
    # Formula OCR occasionally places a punctuation mark immediately before a closing
    # subscript/superscript brace (for example ``x_{t+r,}``). This is not valid content and
    # differs from legitimate interior comma-separated indices such as ``x_{i,j}``.
    formula = re.sub(r",(?=})", "", formula)
    if not formula or len(formula) > 4_000:
        return FormulaValidationResult(
            False, error_code="length", error_message="formula is empty or exceeds the safety limit"
        )
    if any(ord(character) < 32 and character not in "\n\t" for character in formula):
        return FormulaValidationResult(
            False,
            error_code="control_characters",
            error_message="formula contains control characters",
        )
    if re.search(r"\d{60,}", formula):
        return FormulaValidationResult(
            False,
            error_code="digit_run",
            error_message="formula contains an implausibly long digit run",
        )
    if not re.search(r"[A-Za-z0-9\\]", formula):
        return FormulaValidationResult(
            False,
            error_code="no_content",
            error_message="formula has no recognizable mathematical content",
        )
    if "$" in formula:
        return FormulaValidationResult(
            False,
            error_code="nested_delimiter",
            error_message="formula contains a nested math delimiter",
        )
    error = _validate_formula_structure(formula)
    if error:
        return FormulaValidationResult(False, error_code="structure", error_message=error)
    if _looks_low_confidence(formula):
        return FormulaValidationResult(
            False,
            error_code="low_confidence",
            error_message="formula contains repeated or split OCR tokens",
        )
    return FormulaValidationResult(True, normalized=f"$$\n{formula}\n$$")


def _validate_formula_structure(formula: str) -> str | None:
    braces: list[int] = []
    environments: list[str] = []
    left_right = 0
    for match in re.finditer(
        r"\\(?:begin|end)\{([^{}]+)\}|\\(?:left|right)\b|(?<!\\)[{}]", formula
    ):
        token = match.group(0)
        if token == "{":
            braces.append(match.start())
        elif token == "}":
            if not braces:
                return "formula has an unexpected closing brace"
            braces.pop()
        elif token.startswith(r"\begin"):
            environments.append(match.group(1) or "")
        elif token.startswith(r"\end"):
            if not environments or environments.pop() != (match.group(1) or ""):
                return "formula has an unbalanced LaTeX environment"
        elif token == r"\left":
            left_right += 1
        elif token == r"\right":
            left_right -= 1
            if left_right < 0:
                return "formula has an unmatched \\right delimiter"
    if braces:
        return "formula has unbalanced braces"
    if environments:
        return "formula has an unbalanced LaTeX environment"
    if left_right:
        return "formula has an unmatched \\left delimiter"
    return None


def _looks_low_confidence(formula: str) -> bool:
    repeated_ones = formula.count(r"\left(1\right)")
    if repeated_ones >= 3:
        return True
    return bool(re.search(r"\\(?:operatorname\*|mathrm)\{(?:[A-Za-z]\s+){3,}[A-Za-z]\}", formula))


def _retain_diagnostic_crop(
    crop: Path | None, directory: Path, ordinal: int, validated: bool
) -> str | None:
    """Keep only non-validated evidence; normal successful crops remain temporary."""
    if validated or crop is None or not crop.is_file():
        return None
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"formula-{ordinal}.png"
    shutil.copy2(crop, target)
    return target.name


def apply_formula_replacements(
    markdown: str,
    items: list[object],
    replacements: dict[int, str],
    raw_fallbacks: dict[int, str] | None = None,
    failed_item_ids: frozenset[int] | set[int] | None = None,
) -> str:
    """Replace formulas while retaining invalid OCR as non-rendered source code."""
    placeholder = "<!-- formula-not-decoded -->"
    raw_fallbacks = raw_fallbacks or {}
    failed_item_ids = failed_item_ids or set()
    for item in items:
        item_id = id(item)
        replacement = replacements.get(item_id)
        original = str(getattr(item, "text", "")).strip()
        if not replacement and item_id in failed_item_ids:
            page_no = _item_page(item)
            raw = raw_fallbacks.get(item_id) or original
            replacement = (
                unvalidated_formula_block(raw, page_no)
                if raw
                else unavailable_formula_marker(page_no)
            )
        if not replacement:
            continue
        if original and original in markdown:
            markdown = markdown.replace(original, replacement, 1)
        elif placeholder in markdown:
            markdown = markdown.replace(placeholder, replacement, 1)
    return markdown


def text_override(
    item: object,
    replacements: dict[int, str],
    raw_fallbacks: dict[int, str] | None = None,
    failed_item_ids: frozenset[int] | set[int] | None = None,
) -> str | None:
    item_id = id(item)
    replacement = replacements.get(item_id)
    if replacement:
        return replacement
    if failed_item_ids and item_id in failed_item_ids:
        page_no = _item_page(item)
        raw = (raw_fallbacks or {}).get(item_id) or str(getattr(item, "text", "")).strip()
        return (
            unvalidated_formula_block(raw, page_no)
            if raw
            else unavailable_formula_marker(page_no)
        )
    return None


def unvalidated_formula_block(value: str, page_no: int | None) -> str:
    """Keep raw formula OCR visible as code so Markdown math rendering cannot reinterpret it."""
    cleaned = "".join(
        character for character in value if ord(character) >= 32 or character in "\n\t"
    )
    longest_fence = max(
        (len(match.group(0)) for match in re.finditer(r"`+", cleaned)), default=0
    )
    fence = "`" * max(3, longest_fence + 1)
    page = str(page_no) if page_no is not None else "unknown"
    return (
        f"> Formula OCR is incomplete or unvalidated. Verify against the original PDF, "
        f"page {page}.\n\n"
        f"{fence}latex\n{cleaned[:4000]}\n{fence}"
    )


def unavailable_formula_marker(page_no: int | None) -> str:
    page = str(page_no) if page_no is not None else "unknown"
    return (
        f"[Formula unavailable on page {page}: no reliable text was extracted. "
        "Consult the original PDF.]"
    )


def _item_page(item: object) -> int | None:
    provenance = next(iter(getattr(item, "prov", []) or []), None)
    page_no = getattr(provenance, "page_no", None)
    return page_no if isinstance(page_no, int) and page_no >= 1 else None


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
