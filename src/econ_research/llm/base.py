from typing import Protocol

from econ_research.models import ParsedDocument, ResearchCardDraft


class ResearchLLM(Protocol):
    def generate_cards(self, document: ParsedDocument) -> list[ResearchCardDraft]: ...

    def deep_read(self, document: ParsedDocument, focus: str | None = None) -> str: ...

