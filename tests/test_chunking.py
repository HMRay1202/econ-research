from types import SimpleNamespace

from econ_research.parsing.docling_parser import (
    DoclingTextBlock,
    _infer_authors,
    _infer_year,
    _looks_damaged,
    _replace_title_page_metadata,
    chunk_docling_blocks,
    chunk_markdown,
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


def test_title_page_metadata_replaces_recognizable_author_and_year() -> None:
    markdown = (
        "## Monetary Policy, Inflation, and the Business Cycle\n\n"
        "Jordi Gal CREI and UPF\n\nAugust 2007"
    )

    assert _replace_title_page_metadata(markdown, ["Jordi Galí"], 2007) == (
        "## Monetary Policy, Inflation, and the Business Cycle\n\nJordi Galí\n\n2007"
    )
