"""LLM interfaces.

LLM logic is strictly limited to summarization/classification/entity
extraction/explanation. Trade decisioning remains deterministic in
setup/risk/portfolio engines.
"""

from abc import ABC, abstractmethod

from macmarket_trader.domain.schemas import (
    CorporateEvent,
    LLMEventFields,
    LLMRecommendationExplanation,
    MacroEvent,
    NewsEvent,
    BetterElsewhereCandidate,
    OpportunityCandidateSummary,
    OpportunityComparisonMemo,
    TradeRecommendation,
)


LLM_PROMPT_VERSION = "llm-explanation-v1"


class LLMProviderUnavailable(RuntimeError):
    """Raised when a configured LLM provider cannot be used safely."""


class LLMValidationError(ValueError):
    """Raised when provider output fails the allowed structured contract."""


class EventExtractor(ABC):
    """Extracts structured events from unstructured text."""

    @abstractmethod
    def extract(self, symbol: str, text: str) -> NewsEvent | MacroEvent | CorporateEvent:
        """Return structured event payload from text."""


class LLMClient(ABC):
    """Provider-agnostic client for explanation/extraction only."""

    provider_name: str
    model: str | None
    prompt_version: str = LLM_PROMPT_VERSION

    @abstractmethod
    def summarize_event_text(self, *, symbol: str, text: str) -> str:
        """Summarize event text without producing trade levels or sizing."""

    @abstractmethod
    def extract_event_fields(self, *, symbol: str, text: str) -> LLMEventFields:
        """Extract only the event fields allowed by LLMEventFields."""

    @abstractmethod
    def explain_recommendation(self, *, recommendation: TradeRecommendation) -> LLMRecommendationExplanation:
        """Explain a deterministic recommendation without altering it."""

    @abstractmethod
    def generate_counter_thesis(self, *, recommendation: TradeRecommendation) -> list[str]:
        """List failure modes/counter-thesis bullets for operator review."""

    @abstractmethod
    def compare_candidates(
        self,
        *,
        candidates: list[OpportunityCandidateSummary],
        better_elsewhere: list[BetterElsewhereCandidate],
    ) -> OpportunityComparisonMemo:
        """Compare backend-supplied deterministic candidates without changing trade fields."""

    @abstractmethod
    def generate_market_context_memo(self, *, candidates: list[OpportunityCandidateSummary]) -> str:
        """Generate a market/news context memo from backend-supplied structured data only."""

    @abstractmethod
    def generate_better_elsewhere_memo(
        self,
        *,
        candidates: list[OpportunityCandidateSummary],
        better_elsewhere: list[BetterElsewhereCandidate],
    ) -> str:
        """Explain deterministic better-elsewhere candidates without inventing new symbols."""
