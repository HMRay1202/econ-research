from types import SimpleNamespace

import pytest

from econ_research.parsing.docling_parser import (
    DoclingTextBlock,
    _clean_metadata_title,
    _default_pipeline_options,
    _formula_pipeline_options,
    _infer_authors,
    _infer_year,
    _looks_damaged,
    _prefer_pdf_metadata_title,
    _replace_title_page_metadata,
    _select_formula_accelerator,
    chunk_docling_blocks,
    chunk_markdown,
    docling_content_blocks,
)


def test_chunk_markdown_preserves_sections_and_ordinals() -> None:
    chunks = chunk_markdown(
        "# Title\n\nIntro text.\n\n## Identification\n\nParallel trends assumption.",
        max_chars=100,
    )

    assert [chunk.ordinal for chunk in chunks] == list(range(len(chunks)))
    assert chunks[-1].section == "Identification"
    assert "Parallel trends" in chunks[-1].text


def test_chunk_markdown_splits_large_paragraphs() -> None:
    chunks = chunk_markdown("# Results\n\n" + "effect " * 100, max_chars=80)

    assert len(chunks) > 1
    assert all(len(chunk.text) <= 80 for chunk in chunks)


def test_chunk_docling_blocks_preserves_section_and_page_ranges() -> None:
    chunks = chunk_docling_blocks(
        [
            DoclingTextBlock("Introduction", True, 1, 1),
            DoclingTextBlock("First page text.", False, 1, 1),
            DoclingTextBlock("Second page text.", False, 2, 2),
            DoclingTextBlock("Results", True, 3, 3),
            DoclingTextBlock("Final finding.", False, 3, 3),
        ],
        max_chars=40,
    )

    assert [(chunk.section, chunk.page_start, chunk.page_end) for chunk in chunks] == [
        ("Introduction", 1, 2),
        ("Results", 3, 3),
    ]
    assert [chunk.ordinal for chunk in chunks] == [0, 1]


def test_docling_content_blocks_include_tables_in_reading_order() -> None:
    class Table:
        label = "TABLE"
        prov = [SimpleNamespace(page_no=6)]

        @staticmethod
        def export_to_markdown(*, doc) -> str:
            assert doc is document
            return "| Year | Estimate |\n|---|---:|\n| 2020 | 1.1291 |"

    document = SimpleNamespace(
        texts=[],
        iterate_items=lambda: iter(
            [
                (SimpleNamespace(label="SECTION_HEADER", text="Results", prov=[]), 0),
                (SimpleNamespace(label="TEXT", text="The estimates follow.", prov=[]), 0),
                (Table(), 0),
                (
                    SimpleNamespace(
                        label="TEXT", text="Source: author calculations.", prov=[]
                    ),
                    0,
                ),
            ]
        ),
    )

    blocks = docling_content_blocks(document)

    assert [block.text for block in blocks] == [
        "Results",
        "The estimates follow.",
        "| Year | Estimate |\n|---|---:|\n| 2020 | 1.1291 |",
        "Source: author calculations.",
    ]
    assert blocks[2].is_table is True
    assert (blocks[2].page_start, blocks[2].page_end) == (6, 6)


def test_table_block_stays_intact_when_chunking() -> None:
    table = "| Year | Estimate |\n|---|---:|\n| 2020 | 1.1291 |"
    chunks = chunk_docling_blocks(
        [
            DoclingTextBlock("Results", True, 6, 6),
            DoclingTextBlock(table, False, 6, 6, is_table=True),
        ],
        max_chars=20,
    )

    assert chunks[-1].text == table
    assert chunks[-1].page_start == 6
    assert chunks[-1].page_end == 6


def test_failed_formula_enters_ordered_blocks_as_non_rendered_code() -> None:
    formula = SimpleNamespace(
        label="FORMULA",
        text="",
        prov=[SimpleNamespace(page_no=4)],
    )
    document = SimpleNamespace(iterate_items=lambda: iter([(formula, 0)]))
    blocks = docling_content_blocks(
        document,
        raw_formula_fallbacks={id(formula): r"\\frac{x{"},
        failed_formula_ids={id(formula)},
    )
    assert len(blocks) == 1
    assert "```latex" in blocks[0].text
    assert r"\\frac{x{" in blocks[0].text
    assert chunk_docling_blocks(blocks)[0].text == blocks[0].text


def test_title_page_metadata_helpers_are_conservative() -> None:
    items = [
        SimpleNamespace(text="Monetary Policy, Inflation, and the Business Cycle"),
        SimpleNamespace(text="Chapter 1 Introduction"),
        SimpleNamespace(text="Jordi Galí CREI and UPF"),
        SimpleNamespace(text="August 2007"),
    ]

    assert _looks_damaged("In  ation")
    assert not _looks_damaged("Inflation")
    assert _infer_authors(items, items[0].text) == ["Jordi Galí"]
    assert _infer_year(items) == 2007


def test_pdf_metadata_title_is_preferred_over_out_of_order_body_text() -> None:
    title = "Time series decomposition as a method of measuring capital markets convergence"
    assert _prefer_pdf_metadata_title(title, "czasowych składających", "fallback") == title
    assert _prefer_pdf_metadata_title(None, "# Parsed title", "fallback") == "Parsed title"
    assert _clean_metadata_title("  Untitled  ") is None


def test_formula_enrichment_is_enabled_for_pdf_parsing(monkeypatch) -> None:
    monkeypatch.setattr(
        "econ_research.parsing.docling_parser._select_formula_accelerator",
        lambda: ("cuda", "float16"),
    )
    options = _formula_pipeline_options()
    assert options.do_formula_enrichment is True
    assert options.accelerator_options.device == "cuda"
    assert options.document_timeout == 180
    assert options.code_formula_options.engine_options.device == "cuda"
    assert options.code_formula_options.engine_options.load_in_8bit is False
    assert options.code_formula_options.model_spec.max_new_tokens == 512


@pytest.mark.parametrize(
    ("cuda_available", "mps_available", "expected_device", "expected_dtype"),
    [
        (True, False, "cuda", "float16"),
        (False, True, "mps", "float16"),
        (False, False, "cpu", "float32"),
    ],
)
def test_formula_accelerator_is_cross_platform(
    cuda_available, mps_available, expected_device, expected_dtype
) -> None:
    fake_torch = SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: cuda_available),
        backends=SimpleNamespace(
            mps=SimpleNamespace(is_available=lambda: mps_available),
        ),
    )

    device, dtype = _select_formula_accelerator(fake_torch)

    assert device == expected_device
    assert dtype == expected_dtype


def test_default_pdf_pipeline_uses_detected_accelerator_with_cpu_fallback() -> None:
    options = _default_pipeline_options()

    assert options.accelerator_options.device == "auto"


def test_title_page_metadata_replaces_recognizable_author_and_year() -> None:
    markdown = (
        "## Monetary Policy, Inflation, and the Business Cycle\n\n"
        "Jordi Gal CREI and UPF\n\nAugust 2007"
    )

    assert _replace_title_page_metadata(markdown, ["Jordi Galí"], 2007) == (
        "## Monetary Policy, Inflation, and the Business Cycle\n\nJordi Galí\n\n2007"
    )
