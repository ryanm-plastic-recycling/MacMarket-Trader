"""Optional OpenAI-compatible LLM provider.

The provider is intentionally limited to structured explanation/extraction.
Its outputs are validated by Pydantic contracts before any caller can use
them, and RecommendationService never lets these outputs set trade levels,
sizing, approval, or order routing.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import ValidationError

from macmarket_trader.domain.schemas import (
    BetterElsewhereCandidate,
    LLMEventFields,
    LLMRecommendationExplanation,
    OpportunityCandidateSummary,
    OpportunityComparisonMemo,
    TradeRecommendation,
)
from macmarket_trader.llm.base import LLMClient, LLMProviderUnavailable, LLMValidationError, LLM_PROMPT_VERSION


class OpenAICompatibleLLMClient(LLMClient):
    provider_name = "openai"
    prompt_version = LLM_PROMPT_VERSION

    def __init__(
        self,
        *,
        api_key: str,
        model: str | None = None,
        timeout_seconds: float = 12.0,
        max_output_tokens: int = 1200,
        temperature: float = 0.2,
    ) -> None:
        if not api_key.strip():
            raise LLMProviderUnavailable("OPENAI_API_KEY is required for the openai provider.")
        self.api_key = api_key
        self.model = model or "gpt-4o-mini"
        self.timeout_seconds = timeout_seconds
        self.max_output_tokens = max_output_tokens
        self.temperature = temperature

    def summarize_event_text(self, *, symbol: str, text: str) -> str:
        payload = self._complete_json(
            task="summarize_event_text",
            user_payload={"symbol": symbol, "text": text},
        )
        summary = payload.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            raise LLMValidationError("summary missing or invalid")
        return summary.strip()

    def extract_event_fields(self, *, symbol: str, text: str) -> LLMEventFields:
        payload = self._complete_json(
            task="extract_event_fields",
            user_payload={"symbol": symbol, "text": text},
        )
        try:
            return LLMEventFields.model_validate(payload)
        except ValidationError as exc:
            raise LLMValidationError(str(exc)) from exc

    def explain_recommendation(self, *, recommendation: TradeRecommendation) -> LLMRecommendationExplanation:
        payload = self._complete_json(
            task="explain_recommendation",
            user_payload={
                "symbol": recommendation.symbol,
                "approved": recommendation.approved,
                "rejection_reason": recommendation.rejection_reason,
                "side": recommendation.side.value,
                "setup_type": recommendation.entry.setup_type.value,
                "regime": recommendation.regime_context.market_regime.value,
                "quality": recommendation.quality.model_dump(mode="json"),
                "deterministic_levels": {
                    "entry": recommendation.entry.model_dump(mode="json"),
                    "stop": recommendation.invalidation.model_dump(mode="json"),
                    "targets": recommendation.targets.model_dump(mode="json"),
                    "sizing": recommendation.sizing.model_dump(mode="json"),
                },
            },
        )
        try:
            return LLMRecommendationExplanation.model_validate(payload)
        except ValidationError as exc:
            raise LLMValidationError(str(exc)) from exc

    def generate_counter_thesis(self, *, recommendation: TradeRecommendation) -> list[str]:
        explanation = self.explain_recommendation(recommendation=recommendation)
        return explanation.counter_thesis

    def compare_candidates(
        self,
        *,
        candidates: list[OpportunityCandidateSummary],
        better_elsewhere: list[BetterElsewhereCandidate],
    ) -> OpportunityComparisonMemo:
        payload = self._complete_json(
            task="compare_candidates",
            user_payload={
                "candidates": [candidate.model_dump(mode="json") for candidate in candidates],
                "better_elsewhere": [candidate.model_dump(mode="json") for candidate in better_elsewhere],
                "guardrail": (
                    "Use only supplied candidate ids and symbols. Do not create candidates, "
                    "trade levels, approvals, sizing, or orders."
                ),
            },
        )
        try:
            return OpportunityComparisonMemo.model_validate(payload)
        except ValidationError as exc:
            raise LLMValidationError(str(exc)) from exc

    def generate_market_context_memo(self, *, candidates: list[OpportunityCandidateSummary]) -> str:
        payload = self._complete_json(
            task="generate_market_context_memo",
            user_payload={"candidates": [candidate.model_dump(mode="json") for candidate in candidates]},
        )
        memo = payload.get("market_desk_memo") or payload.get("memo")
        if not isinstance(memo, str) or not memo.strip():
            raise LLMValidationError("market context memo missing or invalid")
        return memo.strip()

    def generate_better_elsewhere_memo(
        self,
        *,
        candidates: list[OpportunityCandidateSummary],
        better_elsewhere: list[BetterElsewhereCandidate],
    ) -> str:
        payload = self._complete_json(
            task="generate_better_elsewhere_memo",
            user_payload={
                "selected_candidates": [candidate.model_dump(mode="json") for candidate in candidates],
                "better_elsewhere": [candidate.model_dump(mode="json") for candidate in better_elsewhere],
            },
        )
        memo = payload.get("memo") or payload.get("better_elsewhere_memo")
        if not isinstance(memo, str) or not memo.strip():
            raise LLMValidationError("better-elsewhere memo missing or invalid")
        return memo.strip()

    def _complete_json(self, *, task: str, user_payload: dict[str, Any]) -> dict[str, Any]:
        system = (
            "You explain and extract only. Do not choose trades, entries, stops, "
            "targets, sizing, approval status, or routing. Return compact JSON "
            "matching the requested schema and no additional keys."
        )
        request_payload = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "max_tokens": self.max_output_tokens,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "prompt_version": self.prompt_version,
                            "task": task,
                            "allowed_contracts": {
                                "extract_event_fields": [
                                    "source_type",
                                    "headline",
                                    "summary",
                                    "sentiment_score",
                                    "tags",
                                ],
                                "explain_recommendation": [
                                    "summary",
                                    "approval_explanation",
                                    "counter_thesis",
                                    "deterministic_engine_owns",
                                    "explanation_only",
                                ],
                                "summarize_event_text": ["summary"],
                                "compare_candidates": [
                                    "best_deterministic_candidate_id",
                                    "best_deterministic_symbol",
                                    "market_desk_memo",
                                    "comparison_rows",
                                    "counter_thesis_by_candidate",
                                    "better_elsewhere",
                                    "not_good_enough_warning",
                                    "missing_data",
                                    "deterministic_engine_owns",
                                    "explanation_only",
                                ],
                                "generate_market_context_memo": ["market_desk_memo"],
                                "generate_better_elsewhere_memo": ["memo"],
                            },
                            "payload": user_payload,
                        }
                    ),
                },
            ],
        }
        try:
            response = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=request_payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            decoded = json.loads(content)
        except Exception as exc:
            raise LLMProviderUnavailable(f"LLM provider request failed: {exc}") from exc
        if not isinstance(decoded, dict):
            raise LLMValidationError("provider returned non-object JSON")
        return decoded
