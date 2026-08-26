from econ_research.parsing.docling_parser import chunk_markdown


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

