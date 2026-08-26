from __future__ import annotations

from pydantic import BaseModel, Field

from econ_research.llm.prompts import (
    CARD_SYSTEM_PROMPT,
    DEEP_READ_SYSTEM_PROMPT,
    render_document,
)
from econ_research.models import ParsedDocument, ResearchCardDraft


class CardsEnvelope(BaseModel):
    cards: list[ResearchCardDraft] = Field(min_length=1)


class OpenAIResearchLLM:
    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for LLM operations")
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self._model = model

    def generate_cards(self, document: ParsedDocument) -> list[ResearchCardDraft]:
        source = render_document(
            document.title, [chunk.model_dump() for chunk in document.chunks]
        )
        completion = self._client.beta.chat.completions.parse(
            model=self._model,
            messages=[
                {"role": "system", "content": CARD_SYSTEM_PROMPT},
                {"role": "user", "content": source},
            ],
            response_format=CardsEnvelope,
        )
        message = completion.choices[0].message
        if message.refusal:
            raise RuntimeError(f"The model refused card generation: {message.refusal}")
        if message.parsed is None:
            raise RuntimeError("The model returned no structured card output")
        return message.parsed.cards

    def deep_read(self, document: ParsedDocument, focus: str | None = None) -> str:
        source = render_document(
            document.title, [chunk.model_dump() for chunk in document.chunks]
        )
        focus_instruction = (
            f"\n\nGive additional attention to this requested focus: {focus}" if focus else ""
        )
        completion = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": DEEP_READ_SYSTEM_PROMPT},
                {"role": "user", "content": source + focus_instruction},
            ],
        )
        report = completion.choices[0].message.content
        if not report:
            raise RuntimeError("The model returned an empty deep-read report")
        return report
