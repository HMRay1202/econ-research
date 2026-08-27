from pathlib import Path
from types import SimpleNamespace

import pytest

from econ_research.parsing.formula_ocr import (
    FormulaEnricher,
    apply_formula_replacements,
    normalize_formula_latex,
)


class FakeCropper:
    def crop(self, pdf_path: Path, candidate, output_path: Path) -> None:
        output_path.write_bytes(b"formula crop")


class FakeRecognizer:
    def recognize(self, image_path: Path) -> str:
        assert image_path.read_bytes() == b"formula crop"
        return r"Y_{it} = \alpha_i + \beta D_{it} + \varepsilon_{it}"


class BrokenRecognizer:
    def recognize(self, image_path: Path) -> str:
        raise ModuleNotFoundError("No module named 'ftfy'")


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


def test_formula_enricher_records_per_formula_failure_reason(tmp_path: Path) -> None:
    result = FormulaEnricher(BrokenRecognizer(), FakeCropper()).enrich(
        tmp_path / "paper.pdf", [_formula_item("")]
    )

    assert result.status == "fallback"
    assert result.error == "page 2: ModuleNotFoundError: No module named 'ftfy'"
