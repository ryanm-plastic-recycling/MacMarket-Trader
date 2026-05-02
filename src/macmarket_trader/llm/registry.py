"""LLM provider registry with safe defaults."""

from __future__ import annotations

from macmarket_trader.config import settings
from macmarket_trader.llm.base import LLMClient, LLMProviderUnavailable
from macmarket_trader.llm.mock_extractor import MockLLMClient
from macmarket_trader.llm.openai_provider import OpenAICompatibleLLMClient


def build_llm_client() -> LLMClient:
    provider = settings.llm_provider.strip().lower() or "mock"
    model = settings.llm_model.strip() or None
    if not settings.llm_enabled:
        return MockLLMClient(model=model)
    if provider == "mock":
        return MockLLMClient(model=model)
    if provider == "openai":
        try:
            return OpenAICompatibleLLMClient(
                api_key=settings.llm_api_key,
                model=model,
                timeout_seconds=settings.llm_timeout_seconds,
                max_output_tokens=settings.llm_max_output_tokens,
                temperature=settings.llm_temperature,
            )
        except LLMProviderUnavailable:
            return MockLLMClient(model=model)
    return MockLLMClient(model=model)
