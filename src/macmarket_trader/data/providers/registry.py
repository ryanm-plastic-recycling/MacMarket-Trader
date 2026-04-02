"""Provider registry/factory helpers."""

from __future__ import annotations

from macmarket_trader.config import settings
from macmarket_trader.data.providers.base import AuthProvider, EmailProvider
from macmarket_trader.data.providers.market_data import MarketDataService
from macmarket_trader.data.providers.clerk import ClerkAuthProvider
from macmarket_trader.data.providers.mock import ConsoleEmailProvider, MockAuthProvider
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
        return ResendEmailProvider(api_key=settings.resend_api_key, from_email=settings.resend_from_email)
    raise ValueError(f"Unsupported EMAIL_PROVIDER mode: {settings.email_provider}")


_market_data_service: MarketDataService | None = None


def build_market_data_service() -> MarketDataService:
    global _market_data_service
    if _market_data_service is None:
        _market_data_service = MarketDataService()
    return _market_data_service
