"""Market data provider interfaces."""

from abc import ABC, abstractmethod

from macmarket_trader.domain.schemas import Bar, TechnicalContext


class MarketDataProvider(ABC):
    """Abstract provider for bars and derived technical context."""

    @abstractmethod
    def build_technical_context(self, bars: list[Bar]) -> TechnicalContext:
        """Return deterministic context values derived from recent bars."""
