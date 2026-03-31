"""Provider interfaces kept vendor-agnostic and mockable."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from macmarket_trader.domain.schemas import Bar, TechnicalContext


@dataclass
class EmailMessage:
    to_email: str
    subject: str
    body: str
    template_name: str


class MarketDataProvider(ABC):
    @abstractmethod
    def build_technical_context(self, bars: list[Bar]) -> TechnicalContext:
        """Return deterministic context values derived from recent bars."""


class NewsProvider(ABC):
    @abstractmethod
    def fetch_latest(self, symbol: str, since: datetime | None = None) -> list[dict[str, object]]:
        """Fetch latest company news."""


class MacroCalendarProvider(ABC):
    @abstractmethod
    def upcoming_events(self, from_ts: datetime, to_ts: datetime) -> list[dict[str, object]]:
        """Fetch macro calendar entries for a range."""


class BrokerProvider(ABC):
    @abstractmethod
    def place_paper_order(self, symbol: str, side: str, shares: int, limit_price: float) -> dict[str, object]:
        """Place a paper-only order request."""


class EmailProvider(ABC):
    @abstractmethod
    def send(self, message: EmailMessage) -> str:
        """Send transactional email and return provider message id."""


class AuthProvider(ABC):
    @abstractmethod
    def verify_token(self, token: str) -> dict[str, object]:
        """Verify upstream auth token/JWT and return claims."""
