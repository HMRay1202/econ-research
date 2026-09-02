import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from econ_research.llm.prompts import CARD_SYSTEM_PROMPT, DEEP_READ_SYSTEM_PROMPT, render_document
from econ_research.parsing.formula_ocr import (
    FormulaEnricher,
    PaddleFormulaRecognizer,
    apply_formula_replacements,
    check_formula_dependencies,
    normalize_formula_latex,
    select_paddle_device,
    validate_formula_latex,
)


@pytest.fixture(autouse=True)
def use_fake_local_runtime(monkeypatch):
    # These tests exercise the in-process adapter regardless of the host's GPU setup.
    monkeypatch.setattr("econ_research.parsing.formula_ocr.worker_python", lambda: None)


def test_isolated_recognition_does_not_import_paddle_in_parent(monkeypatch, tmp_path):
    instances = []

    class FakeProcess:
        def __init__(self, python, model_name, cache_dir):
            instances.append((python, model_name, cache_dir))

        def predict(self, image):
            return [{"rec_formula": "x=2"}]

    monkeypatch.setattr("econ_research.parsing.formula_ocr.worker_python", lambda: tmp_path)
    monkeypatch.setattr("econ_research.parsing.formula_ocr.PaddleProcess", FakeProcess)

    def forbidden(*args):
        raise AssertionError("Paddle imports must stay in the worker")

    monkeypatch.setattr("econ_research.parsing.formula_ocr.import_module", forbidden)
    recognizer = PaddleFormulaRecognizer(cache_dir=tmp_path)
    assert instances == []
    assert recognizer.recognize(tmp_path / "a.png") == "x=2"
    assert recognizer.recognize(tmp_path / "b.png") == "x=2"
    assert len(instances) == 1


def test_paddle_model_is_created_only_on_first_recognition(tmp_path: Path, monkeypatch) -> None:
    calls = []

    class LazyModel:
        def __init__(self, **kwargs):
            calls.append(kwargs)

        def predict(self, image):
            return [{"rec_formula": "x=1"}]

    monkeypatch.setattr(
        "econ_research.parsing.formula_ocr.import_module",
        lambda name: SimpleNamespace(
            FormulaRecognition=LazyModel, require_extra=lambda *args, **kwargs: None
        ),
    )
    monkeypatch.setitem(sys.modules, "paddleocr", SimpleNamespace(FormulaRecognition=LazyModel))
    monkeypatch.setattr("econ_research.parsing.formula_ocr.select_paddle_device", lambda: "cpu")
    monkeypatch.delenv("PADDLE_PDX_CACHE_HOME", raising=False)
    # Ensure the test restores environment changes made by the lazy recognizer.
    monkeypatch.setenv("PADDLE_PDX_CACHE_HOME", str(tmp_path / "models"))
    recognizer = PaddleFormulaRecognizer()
    recognizer.set_cache_dir(tmp_path / "models")
    assert calls == []
    assert not (tmp_path / "models").exists()

    assert recognizer.recognize(tmp_path / "formula.png") == "x=1"
    assert recognizer.recognize(tmp_path / "another-formula.png") == "x=1"
    assert calls == [{"model_name": "PP-FormulaNet_plus-L", "device": "cpu"}]


@pytest.mark.parametrize(
    ("compiled", "count", "expected"),
    [(True, 1, "gpu:0"), (True, 0, "cpu"), (False, 0, "cpu")],
)
def test_paddle_device_selection_preserves_cpu_compatibility(compiled, count, expected) -> None:
    paddle = SimpleNamespace(
        is_compiled_with_cuda=lambda: compiled,
        device=SimpleNamespace(cuda=SimpleNamespace(device_count=lambda: count)),
    )
    assert select_paddle_device(paddle) == expected


def test_paddle_device_selection_handles_unavailable_driver() -> None:
    def driver_error():
        raise RuntimeError("driver unavailable")

    assert select_paddle_device(SimpleNamespace(is_compiled_with_cuda=driver_error)) == "cpu"


def test_formula_dependency_check_is_import_only_and_loads_torch_first(monkeypatch) -> None:
    imports = []
    extras = []

    def never_construct_model(*args, **kwargs):
        raise AssertionError("Setup must not create a model")

    def fake_import(name):
        imports.append(name)
        return SimpleNamespace(
            FormulaRecognition=never_construct_model,
            require_extra=lambda name, **kwargs: extras.append(name),
        )

    monkeypatch.setattr("econ_research.parsing.formula_ocr.import_module", fake_import)
    check_formula_dependencies()
    assert imports == ["torch", "paddle", "ftfy", "paddleocr", "paddlex.utils.deps"]
    assert extras == ["ocr"]


class FakeCropper:
    def __init__(self) -> None:
        self.calls = []

    def crop(self, pdf_path: Path, candidate, output_path: Path, *, scale=2.0, padding=8) -> None:
        self.calls.append((scale, padding))
        output_path.write_bytes(b"formula crop")


class FakeRecognizer:
    def recognize(self, image_path: Path) -> str:
        assert image_path.read_bytes() == b"formula crop"
        return r"Y_{it} = \alpha_i + \beta D_{it} + \varepsilon_{it}"


class BrokenRecognizer:
    def recognize(self, image_path: Path) -> str:
        raise ModuleNotFoundError("No module named 'ftfy'")


class InvalidThenValidRecognizer:
    def __init__(self) -> None:
        self.calls = 0

    def recognize(self, image_path: Path) -> str:
        self.calls += 1
        return r"x_{i" if self.calls == 1 else r"x_{i}"


class AlwaysInvalidRecognizer:
    def recognize(self, image_path: Path) -> str:
        return r"\frac{x{"


def _formula_item(text: str = "Yit = ..."):
    return SimpleNamespace(
        label="FORMULA",
        text=text,
        prov=[SimpleNamespace(page_no=2, bbox=SimpleNamespace(l=10, t=30, r=90, b=10))],
    )


def test_formula_enricher_replaces_only_docling_detected_formula(tmp_path: Path) -> None:
    formula = _formula_item()
    result = FormulaEnricher(FakeRecognizer(), FakeCropper()).enrich(
        tmp_path / "paper.pdf", [SimpleNamespace(label="TEXT", text="Body"), formula]
    )

    assert result.detected == 1
    assert result.recognized == 1
    assert result.fallback == 0
    assert result.status == "ready"
    markdown = apply_formula_replacements(
        "Before\n\nYit = ...\n\nAfter", [formula], result.replacements
    )
    assert "$$\nY_{it}" in markdown


def test_formula_enricher_accepts_empty_docling_formula_and_replaces_placeholder(
    tmp_path: Path,
) -> None:
    formula = _formula_item("")
    result = FormulaEnricher(FakeRecognizer(), FakeCropper()).enrich(
        tmp_path / "paper.pdf", [formula]
    )

    assert result.detected == 1
    assert result.recognized == 1
    markdown = apply_formula_replacements(
        "Before\n\n<!-- formula-not-decoded -->\n\nAfter", [formula], result.replacements
    )
    assert "formula-not-decoded" not in markdown
    assert "$$\nY_{it}" in markdown


def test_formula_validation_rejects_corrupt_output() -> None:
    with pytest.raises(ValueError, match="digit run"):
        normalize_formula_latex("1" * 60)
    with pytest.raises(ValueError, match="unbalanced braces"):
        normalize_formula_latex(r"x_{i")
    assert "x_{t+r}" in normalize_formula_latex(r"x_{t+r,}")
    assert "x_{i,j}" in normalize_formula_latex(r"x_{i,j}")


def test_formula_validation_normalizes_known_katex_compatibility_defects() -> None:
    normalized = normalize_formula_latex(r"D=\sum_{1}^{n}d_n\eqno(3)")
    assert r"\tag{3}" in normalized
    assert r"\eqno" not in normalized
    assert r"\gamma_s" in normalize_formula_latex(r"\upgamma_s")


def test_formula_validation_rejects_nested_delimiters_and_low_confidence_cases() -> None:
    nested = validate_formula_latex(r"(3)$x=y$")
    assert nested.valid is False
    assert nested.error_code == "nested_delimiter"
    repeated = validate_formula_latex(
        r"x=\left(\left(1\right),\left(1\right),\left(1\right)\right)"
    )
    assert repeated.valid is False
    assert repeated.error_code == "low_confidence"


def test_formula_enricher_records_per_formula_failure_reason(tmp_path: Path) -> None:
    formula = _formula_item("")
    result = FormulaEnricher(BrokenRecognizer(), FakeCropper()).enrich(
        tmp_path / "paper.pdf", [formula]
    )

    assert result.status == "fallback"
    assert result.error and "ModuleNotFoundError" in result.error
    assert result.failed_item_ids
    markdown = apply_formula_replacements(
        "<!-- formula-not-decoded -->",
        [formula],
        result.replacements,
        result.raw_fallbacks,
        result.failed_item_ids,
    )
    assert "Formula unavailable on page 2" in markdown


def test_formula_enricher_retries_with_expanded_crops(tmp_path: Path) -> None:
    cropper = FakeCropper()
    result = FormulaEnricher(InvalidThenValidRecognizer(), cropper).enrich(
        tmp_path / "paper.pdf", [_formula_item()]
    )
    assert result.recognized == 1
    assert cropper.calls[:2] == [(2.0, 8), (3.0, 16)]


def test_invalid_formula_is_retained_as_non_rendered_latex_code(tmp_path: Path) -> None:
    formula = _formula_item("")
    result = FormulaEnricher(AlwaysInvalidRecognizer(), FakeCropper()).enrich(
        tmp_path / "paper.pdf", [formula]
    )
    markdown = apply_formula_replacements(
        "<!-- formula-not-decoded -->",
        [formula],
        result.replacements,
        result.raw_fallbacks,
        result.failed_item_ids,
    )
    assert result.recognized == 0
    assert result.raw_fallbacks[id(formula)] == r"\frac{x{"
    assert "```latex" in markdown
    assert r"\frac{x{" in markdown
    extraction = result.extractions[0]
    assert extraction.status == "unvalidated"
    assert extraction.crop_filename
    crop = tmp_path.parent / "diagnostics" / "formulas" / "paper" / extraction.crop_filename
    assert crop.read_bytes() == b"formula crop"


def test_llm_document_keeps_unvalidated_formula_and_prompts_uncertainty() -> None:
    block = "```latex\nx_{i\n```"
    rendered = render_document("Paper", [{"ordinal": 1, "section": "Results", "text": block}])
    assert block in rendered
    assert "unvalidated OCR" in CARD_SYSTEM_PROMPT
    assert "unvalidated OCR" in DEEP_READ_SYSTEM_PROMPT
