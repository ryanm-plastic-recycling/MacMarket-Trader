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


OPENAI_RESPONSES_ENDPOINT = "https://api.openai.com/v1/responses"
_LAST_OPENAI_PROVIDER_ERROR: dict[str, object] | None = None


def get_last_openai_provider_error() -> dict[str, object] | None:
    """Return the latest sanitized OpenAI failure, if any."""

    return dict(_LAST_OPENAI_PROVIDER_ERROR) if _LAST_OPENAI_PROVIDER_ERROR else None


def _redact(value: object, *, api_key: str | None = None) -> str:
    text = str(value or "").replace("\n", " ").replace("\r", " ").strip()
    if api_key and api_key.strip():
        text = text.replace(api_key.strip(), "[redacted]")
    if "Authorization" in text:
        text = text.split("Authorization", 1)[0].strip()
    return text[:700]


def _schema_for_task(task: str) -> dict[str, Any]:
    string_array = {"type": "array", "items": {"type": "string"}}
    nullable_string = {"anyOf": [{"type": "string"}, {"type": "null"}]}
    nullable_number = {"anyOf": [{"type": "number"}, {"type": "null"}]}
    if task == "summarize_event_text":
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
        }
    if task == "extract_event_fields":
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "source_type": {"type": "string", "enum": ["news", "macro", "corporate"]},
                "headline": {"type": "string"},
                "summary": {"type": "string"},
                "sentiment_score": {"type": "number"},
                "tags": string_array,
            },
            "required": ["source_type", "headline", "summary", "sentiment_score", "tags"],
        }
    if task == "explain_recommendation":
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "summary": {"type": "string"},
                "approval_explanation": {"type": "string"},
                "counter_thesis": string_array,
                "deterministic_engine_owns": string_array,
                "explanation_only": {"type": "boolean"},
            },
            "required": [
                "summary",
                "approval_explanation",
                "counter_thesis",
                "deterministic_engine_owns",
                "explanation_only",
            ],
        }
    if task == "compare_candidates":
        better_elsewhere = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "recommendation_id": nullable_string,
                "symbol": {"type": "string"},
                "rank": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
                "deterministic_score": nullable_number,
                "expected_rr": nullable_number,
                "confidence": nullable_number,
                "reason": {"type": "string"},
                "source": {"type": "string", "enum": ["deterministic_scan", "research_only_unverified"]},
                "verified_by_scan": {"type": "boolean"},
            },
            "required": [
                "recommendation_id",
                "symbol",
                "rank",
                "deterministic_score",
                "expected_rr",
                "confidence",
                "reason",
                "source",
                "verified_by_scan",
            ],
        }
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "best_deterministic_candidate_id": nullable_string,
                "best_deterministic_symbol": nullable_string,
                "market_desk_memo": {"type": "string"},
                "comparison_rows": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "candidate_id": {"type": "string"},
                            "symbol": {"type": "string"},
                            "rank": nullable_number,
                            "score": nullable_number,
                            "expected_rr": nullable_number,
                            "confidence": nullable_number,
                            "desk_read": {"type": "string"},
                        },
                        "required": [
                            "candidate_id",
                            "symbol",
                            "rank",
                            "score",
                            "expected_rr",
                            "confidence",
                            "desk_read",
                        ],
                    },
                },
                "counter_thesis_by_candidate": {
                    "type": "object",
                    "additionalProperties": string_array,
                },
                "better_elsewhere": {"type": "array", "items": better_elsewhere},
                "not_good_enough_warning": nullable_string,
                "missing_data": string_array,
                "deterministic_engine_owns": string_array,
                "explanation_only": {"type": "boolean"},
            },
            "required": [
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
        }
    if task == "generate_market_context_memo":
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {"market_desk_memo": {"type": "string"}},
            "required": ["market_desk_memo"],
        }
    if task == "generate_better_elsewhere_memo":
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {"memo": {"type": "string"}},
            "required": ["memo"],
        }
    return _schema_for_task("summarize_event_text")


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

    @property
    def endpoint(self) -> str:
        return OPENAI_RESPONSES_ENDPOINT

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
        global _LAST_OPENAI_PROVIDER_ERROR
        system = (
            "You explain and extract only. Do not choose trades, entries, stops, "
            "targets, sizing, approval status, or routing. Return compact JSON "
            "matching the requested schema and no additional keys."
        )
        user_content = json.dumps(
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
        )
        request_payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": system}]},
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_content}],
                },
            ],
            "max_output_tokens": self.max_output_tokens,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": f"macmarket_{task}",
                    "schema": _schema_for_task(task),
                    "strict": False,
                }
            },
        }
        if self.model.startswith("gpt-5"):
            request_payload["reasoning"] = {"effort": "none"}
        else:
            request_payload["temperature"] = self.temperature
        try:
            response = httpx.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=request_payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
            content = self._extract_output_text(body)
            decoded = json.loads(content)
            _LAST_OPENAI_PROVIDER_ERROR = None
        except httpx.HTTPStatusError as exc:
            error = self._capture_http_error(exc)
            raise LLMProviderUnavailable(self._format_provider_error(error)) from exc
        except (httpx.RequestError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            error = {
                "endpoint": self.endpoint,
                "model": self.model,
                "status_code": None,
                "error_type": type(exc).__name__,
                "error_code": None,
                "message": _redact(exc, api_key=self.api_key),
                "request_id": None,
            }
            _LAST_OPENAI_PROVIDER_ERROR = error
            raise LLMProviderUnavailable(self._format_provider_error(error)) from exc
        if not isinstance(decoded, dict):
            raise LLMValidationError("provider returned non-object JSON")
        return decoded

    def _capture_http_error(self, exc: httpx.HTTPStatusError) -> dict[str, object]:
        global _LAST_OPENAI_PROVIDER_ERROR
        response = exc.response
        request_id = (
            response.headers.get("x-request-id")
            or response.headers.get("request-id")
            or response.headers.get("openai-request-id")
        )
        error_payload: dict[str, Any] = {}
        try:
            parsed = response.json()
            if isinstance(parsed, dict):
                maybe_error = parsed.get("error")
                error_payload = maybe_error if isinstance(maybe_error, dict) else parsed
        except ValueError:
            error_payload = {"message": response.text}
        error = {
            "endpoint": self.endpoint,
            "model": self.model,
            "status_code": response.status_code,
            "error_type": _redact(error_payload.get("type"), api_key=self.api_key),
            "error_code": _redact(error_payload.get("code"), api_key=self.api_key),
            "message": _redact(error_payload.get("message") or response.text, api_key=self.api_key),
            "request_id": _redact(request_id, api_key=self.api_key),
        }
        _LAST_OPENAI_PROVIDER_ERROR = error
        return error

    @staticmethod
    def _format_provider_error(error: dict[str, object]) -> str:
        parts = [
            f"endpoint={error.get('endpoint')}",
            f"model={error.get('model')}",
            f"status={error.get('status_code')}",
            f"type={error.get('error_type')}",
            f"code={error.get('error_code')}",
            f"request_id={error.get('request_id')}",
            f"message={error.get('message')}",
        ]
        return "OpenAI provider request failed: " + "; ".join(parts)

    @staticmethod
    def _extract_output_text(body: dict[str, Any]) -> str:
        output_text = body.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text
        for item in body.get("output", []):
            if not isinstance(item, dict):
                continue
            for content in item.get("content", []):
                if isinstance(content, dict):
                    text = content.get("text")
                    if content.get("type") in {"output_text", "text"} and isinstance(text, str):
                        return text
        raise KeyError("OpenAI response did not include output text")
