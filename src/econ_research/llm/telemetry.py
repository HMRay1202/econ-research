from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Generic, TypeVar

from econ_research.models import LLMCallMetrics, ResearchCardDraft

T = TypeVar("T")


@dataclass(frozen=True)
class ModelPrice:
    input_per_million: float
    cached_input_per_million: float
    cache_write_per_million: float
    output_per_million: float


# OpenAI public pricing snapshot, captured 2026-08-26. Each call stores these rates.
MODEL_PRICES: dict[str, ModelPrice] = {
    "gpt-5.6-luna": ModelPrice(0.20, 0.02, 0.25, 1.20),
    "gpt-5.6-terra": ModelPrice(2.00, 0.20, 2.50, 12.00),
    "gpt-5.6-sol": ModelPrice(4.00, 0.40, 5.00, 20.00),
}


@dataclass(frozen=True)
class TimedCall:
    started_at: str
    started_counter: float

    @classmethod
    def start(cls) -> TimedCall:
        return cls(datetime.now(UTC).isoformat(), perf_counter())

    def finish(self) -> tuple[str, int]:
        completed_at = datetime.now(UTC).isoformat()
        duration_ms = max(0, round((perf_counter() - self.started_counter) * 1000))
        return completed_at, duration_ms


class LLMCallError(RuntimeError):
    def __init__(self, message: str, metrics: LLMCallMetrics):
        super().__init__(message)
        self.metrics = metrics


class LLMResult(Generic[T]):
    def __init__(self, value: T, metrics: LLMCallMetrics):
        self.value = value
        self.metrics = metrics


CardGenerationResult = LLMResult[list[ResearchCardDraft]]
DeepReadGenerationResult = LLMResult[str]


def build_metrics(
    *,
    completion: object | None,
    model: str,
    reasoning_effort: str,
    timer: TimedCall,
    error: Exception | None = None,
) -> LLMCallMetrics:
    usage = getattr(completion, "usage", None)
    prompt_details = getattr(usage, "prompt_tokens_details", None)
    completion_details = getattr(usage, "completion_tokens_details", None)
    input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    cached_tokens = int(getattr(prompt_details, "cached_tokens", 0) or 0)
    cache_write_tokens = int(getattr(prompt_details, "cache_write_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    reasoning_tokens = int(getattr(completion_details, "reasoning_tokens", 0) or 0)
    total_tokens = int(getattr(usage, "total_tokens", input_tokens + output_tokens) or 0)
    actual_model = str(getattr(completion, "model", None) or model)
    price = MODEL_PRICES.get(actual_model) or MODEL_PRICES.get(model)
    estimated_cost = None
    if price is not None and usage is not None:
        standard_input = max(0, input_tokens - cached_tokens - cache_write_tokens)
        estimated_cost = (
            standard_input * price.input_per_million
            + cached_tokens * price.cached_input_per_million
            + cache_write_tokens * price.cache_write_per_million
            + output_tokens * price.output_per_million
        ) / 1_000_000
    completed_at, duration_ms = timer.finish()
    request_id = getattr(completion, "_request_id", None) or getattr(completion, "id", None)
    return LLMCallMetrics(
        provider_request_id=str(request_id) if request_id else None,
        model=actual_model,
        reasoning_effort=reasoning_effort,
        input_tokens=input_tokens,
        cached_input_tokens=cached_tokens,
        cache_write_tokens=cache_write_tokens,
        output_tokens=output_tokens,
        reasoning_tokens=reasoning_tokens,
        total_tokens=total_tokens,
        input_price_per_million=price.input_per_million if price else None,
        cached_input_price_per_million=price.cached_input_per_million if price else None,
        cache_write_price_per_million=price.cache_write_per_million if price else None,
        output_price_per_million=price.output_per_million if price else None,
        estimated_cost_usd=estimated_cost,
        duration_ms=duration_ms,
        status="failed" if error else "succeeded",
        error=f"{type(error).__name__}: {error}"[:2000] if error else None,
        started_at=timer.started_at,
        completed_at=completed_at,
    )
