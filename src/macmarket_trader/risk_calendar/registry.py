"""Risk-calendar service construction."""

from __future__ import annotations

from macmarket_trader.config import settings
from macmarket_trader.risk_calendar.service import MarketRiskCalendarService, StaticRiskCalendarProvider


def build_risk_calendar_service() -> MarketRiskCalendarService:
    provider_name = settings.risk_calendar_provider.strip().lower()
    provider = StaticRiskCalendarProvider()
    if provider_name != "static":
        provider = StaticRiskCalendarProvider()
    return MarketRiskCalendarService(provider=provider)
