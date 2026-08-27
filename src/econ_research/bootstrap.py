from __future__ import annotations

from econ_research.config import Settings, get_settings
from econ_research.db.repository import SQLiteRepository
from econ_research.llm.openai_client import OpenAIResearchLLM
from econ_research.parsing.docling_parser import DoclingParser
from econ_research.service import ResearchService


class LazyDoclingParser:
    def __init__(
        self, *, formula_enrichment: bool = False, paddle_formula_ocr: bool = True
    ) -> None:
        self.formula_enrichment = formula_enrichment
        self.paddle_formula_ocr = paddle_formula_ocr

    def parse(self, pdf_path):
        return DoclingParser(
            formula_enrichment=self.formula_enrichment,
            paddle_formula_ocr=self.paddle_formula_ocr,
        ).parse(pdf_path)


class LazyOpenAIResearchLLM:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _client(self, model: str, reasoning_effort: str) -> OpenAIResearchLLM:
        if not self.settings.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Copy .env.example to .env and add a local key."
            )
        return OpenAIResearchLLM(
            self.settings.openai_api_key,
            model,
            reasoning_effort=reasoning_effort,
        )

    def generate_cards(self, document):
        return self._client(
            self.settings.effective_card_model,
            self.settings.openai_card_reasoning_effort,
        ).generate_cards(document)

    def deep_read(self, document, focus=None):
        return self._client(
            self.settings.effective_deep_read_model,
            self.settings.openai_deep_read_reasoning_effort,
        ).deep_read(document, focus)


def build_service(settings: Settings | None = None) -> ResearchService:
    settings = settings or get_settings()
    settings.ensure_directories()
    return ResearchService(
        repository=SQLiteRepository(settings.db_path),
        parser=LazyDoclingParser(
            formula_enrichment=settings.formula_enrichment,
            paddle_formula_ocr=settings.paddle_formula_ocr,
        ),
        llm=LazyOpenAIResearchLLM(settings),
        originals_dir=settings.originals_dir,
        parsed_dir=settings.parsed_dir,
        generated_dir=settings.generated_dir,
    )
