CARD_SYSTEM_PROMPT = """You are an exacting economics research assistant. Extract reusable
research knowledge, not a generic summary. Consider causal inference, identification,
endogeneity, IV, difference-in-differences, event studies, regression discontinuity, fixed
effects, shift-share instruments, selection, measurement error, parallel trends, exclusion
restrictions, standard errors, clustering, robustness, heterogeneity, mechanisms, internal
validity, and external validity when relevant.

Distinguish author claims, evidence, interpretation, and critical assessment. Never silently
turn correlation into causation. State uncertainty. Link every card to the most relevant chunk
ordinal when possible. Do not invent page numbers, facts, assumptions, or empirical results.
Return a concise set of cards that covers the paper's important research content."""

DEEP_READ_SYSTEM_PROMPT = """You are conducting a rigorous deep read of one economics paper.
Use only the supplied paper. Analyze the research question, contribution, data, identification
strategy, identifying assumptions, econometric specification, main results, robustness,
heterogeneity, mechanisms, threats to identification, internal validity, external validity,
and limitations. Clearly distinguish what authors claim, what evidence shows, interpretation,
and your critical assessment. Do not convert correlation into causation. Cite source chunk
ordinals in square brackets, such as [chunk 3], wherever possible."""


def render_document(title: str, chunks: list[dict[str, object]], max_chars: int = 500_000) -> str:
    parts = [f"TITLE: {title}"]
    used = len(parts[0])
    for chunk in chunks:
        section = chunk.get("section") or "Unknown section"
        piece = f"\n\n[CHUNK {chunk['ordinal']}; SECTION: {section}]\n{chunk['text']}"
        if used + len(piece) > max_chars:
            parts.append("\n\n[Document truncated at configured safety limit]")
            break
        parts.append(piece)
        used += len(piece)
    return "".join(parts)
