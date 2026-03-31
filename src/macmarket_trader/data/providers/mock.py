"""Mock deterministic providers for local research/testing."""

from __future__ import annotations

from datetime import datetime
from statistics import mean

from macmarket_trader.data.providers.base import (
    AuthProvider,
    EmailMessage,
    EmailProvider,
    MacroCalendarProvider,
    MarketDataProvider,
    NewsProvider,
)
from macmarket_trader.domain.schemas import Bar, TechnicalContext


class MockMarketDataProvider(MarketDataProvider):
    def build_technical_context(self, bars: list[Bar]) -> TechnicalContext:
        if len(bars) < 2:
            msg = "At least two bars are required to build technical context"
            raise ValueError(msg)

        prior = bars[-2]
        window = bars[-20:]
        tr_values = [bar.high - bar.low for bar in bars[-14:]] or [bars[-1].high - bars[-1].low]
        atr14 = mean(tr_values)
        event_day = bars[-1]
        return TechnicalContext(
            prior_day_high=prior.high,
            prior_day_low=prior.low,
            recent_20d_high=max(bar.high for bar in window),
            recent_20d_low=min(bar.low for bar in window),
            atr14=max(atr14, 0.01),
            event_day_range=event_day.high - event_day.low,
            rel_volume=event_day.rel_volume,
        )


class MockNewsProvider(NewsProvider):
    def fetch_latest(self, symbol: str, since: datetime | None = None) -> list[dict[str, object]]:
        return [{"symbol": symbol, "headline": "Mock headline", "since": since.isoformat() if since else None}]


class MockMacroCalendarProvider(MacroCalendarProvider):
    def upcoming_events(self, from_ts: datetime, to_ts: datetime) -> list[dict[str, object]]:
        return [{"event": "FOMC", "from": from_ts.isoformat(), "to": to_ts.isoformat()}]


class ConsoleEmailProvider(EmailProvider):
    def send(self, message: EmailMessage) -> str:
        print(f"[console-email] to={message.to_email} template={message.template_name} subject={message.subject}")
        return "console-local"


class MockAuthProvider(AuthProvider):
    def verify_token(self, token: str) -> dict[str, object]:
        if token == "admin-token":
            return {"sub": "clerk_admin", "email": "admin@example.com", "name": "Admin", "role": "admin", "mfa": True}
        if token == "user-token":
            return {"sub": "clerk_user", "email": "user@example.com", "name": "User", "role": "user", "mfa": False}
        raise ValueError("Invalid auth token")
