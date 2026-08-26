from typing import Protocol

from econ_research.llm.telemetry import CardGenerationResult, DeepReadGenerationResult
from econ_research.models import ParsedDocument


class ResearchLLM(Protocol):
    def generate_cards(self, document: ParsedDocument) -> CardGenerationResult: ...

    def deep_read(
        self, document: ParsedDocument, focus: str | None = None
    ) -> DeepReadGenerationResult: ...
