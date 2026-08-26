from __future__ import annotations

from types import SimpleNamespace

from econ_research import bootstrap
from econ_research.bootstrap import LazyOpenAIResearchLLM
from econ_research.config import Settings
from econ_research.llm.openai_client import CardsEnvelope, OpenAIResearchLLM
from econ_research.llm.telemetry import LLMCallError
from econ_research.models import ParsedChunk, ParsedDocument, ResearchCardDraft


def sample_document() -> ParsedDocument:
    return ParsedDocument(
        title="Test paper",
        markdown="# Test paper\n\nParallel trends.",
        chunks=[ParsedChunk(ordinal=0, text="Parallel trends.", section="Design")],
    )


def test_operation_models_and_reasoning_are_routed(monkeypatch) -> None:
    created: list[tuple[str, str]] = []
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    class CapturingClient:
        def __init__(self, api_key: str, model: str, reasoning_effort: str):
            assert api_key == "test-key"
            created.append((model, reasoning_effort))

        def generate_cards(self, document):
            return []

        def deep_read(self, document, focus=None):
            return "report"

    monkeypatch.setattr(bootstrap, "OpenAIResearchLLM", CapturingClient)
    settings = Settings(
        _env_file=None,
        OPENAI_DEFAULT_MODEL="gpt-5.6-terra",
        OPENAI_CARD_MODEL="gpt-5.6-luna",
        OPENAI_DEEP_READ_MODEL="gpt-5.6-terra",
        OPENAI_CARD_REASONING_EFFORT="low",
        OPENAI_DEEP_READ_REASONING_EFFORT="medium",
    )
    router = LazyOpenAIResearchLLM(settings)

    router.generate_cards(sample_document())
    router.deep_read(sample_document(), "identification")

    assert created == [("gpt-5.6-luna", "low"), ("gpt-5.6-terra", "medium")]


def test_blank_operation_models_fall_back_to_legacy_default_alias() -> None:
    settings = Settings(
        _env_file=None,
        OPENAI_MODEL="legacy-model",
        OPENAI_CARD_MODEL="",
        OPENAI_DEEP_READ_MODEL="",
    )

    assert settings.openai_default_model == "legacy-model"
    assert settings.effective_card_model == "legacy-model"
    assert settings.effective_deep_read_model == "legacy-model"


def test_openai_client_sends_reasoning_effort_to_both_operations() -> None:
    calls: list[dict[str, object]] = []
    card = ResearchCardDraft(
        type="identification",
        title="Parallel trends",
        content="The design relies on parallel trends.",
        chunk_ordinal=0,
        claim_kind="author_claim",
    )

    class FakeCompletions:
        def parse(self, **kwargs):
            calls.append(kwargs)
            message = SimpleNamespace(refusal=None, parsed=CardsEnvelope(cards=[card]))
            return fake_completion(message)

        def create(self, **kwargs):
            calls.append(kwargs)
            message = SimpleNamespace(content="# Deep read")
            return fake_completion(message)

    def fake_completion(message):
        usage = SimpleNamespace(
            prompt_tokens=1000,
            completion_tokens=200,
            total_tokens=1200,
            prompt_tokens_details=SimpleNamespace(
                cached_tokens=100, cache_write_tokens=50
            ),
            completion_tokens_details=SimpleNamespace(reasoning_tokens=30),
        )
        return SimpleNamespace(
            id="chatcmpl-test",
            model="gpt-5.6-terra",
            usage=usage,
            choices=[SimpleNamespace(message=message)],
        )

    completions = FakeCompletions()
    llm = object.__new__(OpenAIResearchLLM)
    llm._client = SimpleNamespace(
        beta=SimpleNamespace(chat=SimpleNamespace(completions=completions)),
        chat=SimpleNamespace(completions=completions),
    )
    llm._model = "gpt-5.6-terra"
    llm._reasoning_effort = "medium"

    cards = llm.generate_cards(sample_document())
    deep_read = llm.deep_read(sample_document())

    assert cards.value == [card]
    assert deep_read.value == "# Deep read"
    assert cards.metrics.provider_request_id == "chatcmpl-test"
    assert cards.metrics.input_tokens == 1000
    assert cards.metrics.cached_input_tokens == 100
    assert cards.metrics.cache_write_tokens == 50
    assert cards.metrics.output_tokens == 200
    assert cards.metrics.reasoning_tokens == 30
    assert cards.metrics.estimated_cost_usd == 0.004245
    assert [call["reasoning_effort"] for call in calls] == ["medium", "medium"]
    assert [call["model"] for call in calls] == ["gpt-5.6-terra", "gpt-5.6-terra"]


def test_openai_client_marks_failure_without_usage_as_unpriced() -> None:
    class FailingCompletions:
        def create(self, **kwargs):
            raise ConnectionError("network unavailable")

    llm = object.__new__(OpenAIResearchLLM)
    llm._client = SimpleNamespace(
        chat=SimpleNamespace(completions=FailingCompletions())
    )
    llm._model = "gpt-5.6-terra"
    llm._reasoning_effort = "medium"

    try:
        llm.deep_read(sample_document())
    except LLMCallError as exc:
        assert exc.metrics.status == "failed"
        assert exc.metrics.total_tokens == 0
        assert exc.metrics.estimated_cost_usd is None
        assert "network unavailable" in (exc.metrics.error or "")
    else:  # pragma: no cover
        raise AssertionError("Expected LLMCallError")
