"""LLM extraction interface.

LLM logic is strictly limited to summarization/classification/entity extraction/explanation.
Trade decisioning remains deterministic in setup/risk/portfolio engines.
"""

from abc import ABC, abstractmethod

from macmarket_trader.domain.schemas import CorporateEvent, MacroEvent, NewsEvent


class EventExtractor(ABC):
    """Extracts structured events from unstructured text."""

    @abstractmethod
    def extract(self, symbol: str, text: str) -> NewsEvent | MacroEvent | CorporateEvent:
        """Return structured event payload from text."""
