"""Provider registry/factory helpers."""

from __future__ import annotations

from macmarket_trader.config import settings
from macmarket_trader.data.providers.base import AuthProvider, BrokerProvider, EmailProvider, MacroCalendarProvider, NewsProvider
from macmarket_trader.data.providers.market_data import MarketDataService
from macmarket_trader.data.providers.broker import AlpacaBrokerProvider
from macmarket_trader.data.providers.clerk import ClerkAuthProvider
from macmarket_trader.data.providers.macro_calendar import FredMacroCalendarProvider
from macmarket_trader.data.providers.mock import ConsoleEmailProvider, MockAuthProvider, MockBrokerProvider, MockMacroCalendarProvider, MockNewsProvider
from macmarket_trader.data.providers.news import PolygonNewsProvider
from macmarket_trader.data.providers.resend import ResendEmailProvider


def build_auth_provider() -> AuthProvider:
    mode = settings.auth_provider.strip().lower()
    if mode == "mock":
        return MockAuthProvider()
    if mode == "clerk":
        return ClerkAuthProvider(
            issuer=settings.clerk_jwt_issuer,
            jwks_url=settings.clerk_jwks_url,
            audience=settings.clerk_jwt_audience or None,
        )
    raise ValueError(f"Unsupported AUTH_PROVIDER mode: {settings.auth_provider}")


def build_email_provider() -> EmailProvider:
    mode = settings.email_provider.strip().lower()
    if mode == "console":
        return ConsoleEmailProvider()
    if mode == "resend":
        return ResendEmailProvider(
            api_key=settings.resend_api_key,
            from_email=settings.resend_from_email,
            from_name=settings.brand_from_name,
        )
    raise ValueError(f"Unsupported EMAIL_PROVIDER mode: {settings.email_provider}")


def build_news_provider() -> NewsProvider:
    mode = settings.news_provider.strip().lower()
    if mode == "polygon":
        return PolygonNewsProvider()
    return MockNewsProvider()


def build_macro_calendar_provider() -> MacroCalendarProvider:
    mode = settings.macro_calendar_provider.strip().lower()
    if mode == "fred":
        return FredMacroCalendarProvider()
    return MockMacroCalendarProvider()


def build_broker_provider() -> BrokerProvider:
    mode = settings.broker_provider.strip().lower()
    if mode == "alpaca":
        return AlpacaBrokerProvider()
    return MockBrokerProvider()


_market_data_service: MarketDataService | None = None


def build_market_data_service() -> MarketDataService:
    global _market_data_service
    if _market_data_service is None:
        _market_data_service = MarketDataService()
    return _market_data_service
