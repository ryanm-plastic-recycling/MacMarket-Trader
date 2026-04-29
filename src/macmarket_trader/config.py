"""Application configuration models."""

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed configuration values."""

    app_name: str = "MacMarket-Trader"
    environment: str = "dev"
    database_url: str = "sqlite:///./macmarket_trader.db"
    log_level: str = "INFO"
    risk_dollars_per_trade: float = 1000.0
    commission_per_trade: float = 0.0
    commission_per_contract: float = 0.65
    max_portfolio_heat: float = 0.06
    max_position_notional: float = 0.20
    audit_persistence_enabled: bool = True

    # auth/email/provider config
    auth_provider: str = "mock"
    clerk_jwt_issuer: str = ""
    clerk_jwks_url: str = ""
    clerk_jwt_audience: str = ""
    clerk_secret_key: str = ""
    clerk_api_base_url: str = "https://api.clerk.com"
    require_mfa_for_admin: bool = True
    enforce_global_mfa: bool = False
    email_provider: str = "console"
    cors_allowed_origins: list[str] = Field(default_factory=lambda: ["http://127.0.0.1:9500", "http://localhost:9500"])

    app_base_url: str = "http://localhost:9500"

    resend_api_key: str = ""
    resend_from_email: str = "noreply@macmarket-trader.local"
    brand_from_name: str = "MacMarket Trader"
    # Self-hosted at /brand/<file> from the Next.js public dir, served by the
    # production tunnel. The base64 embed in email_templates.py is the deeper
    # fallback so emails render even if this URL fails to load.
    brand_logo_url: str = "https://macmarket.io/brand/square_console_ticks_lockup_light.png"
    # console_url is no longer a separately-configurable field. It always
    # mirrors app_base_url — outbound emails (invite welcome CTA, approval CTA)
    # build their links off the same base URL the operator already configures
    # via APP_BASE_URL. Eliminating the localhost fallback prevents production
    # invites from emitting localhost URLs when CONSOLE_URL was not also set.

    # market data provider config
    market_data_provider: str = "fallback"
    market_data_enabled: bool = False
    alpaca_api_key_id: str = Field(default="", validation_alias=AliasChoices("APCA_API_KEY_ID", "APCA-API-KEY-ID"))
    alpaca_api_secret_key: str = Field(default="", validation_alias=AliasChoices("APCA_API_SECRET_KEY", "APCA-API-SECRET-KEY"))
    alpaca_market_data_base_url: str = "https://data.alpaca.markets"
    alpaca_market_data_feed: str = "iex"
    market_data_request_timeout_seconds: int = 8
    market_data_latest_cache_ttl_seconds: int = 10
    market_data_historical_cache_ttl_seconds: int = 120
    polygon_enabled: bool = False
    polygon_api_key: str = ""
    polygon_base_url: str = "https://api.polygon.io"
    polygon_timeout_seconds: int = 8
    workflow_demo_fallback: bool = False

    # news provider config
    news_provider: str = "mock"
    news_polygon_max_articles: int = 10
    news_cache_ttl_seconds: int = 300

    # macro calendar provider config
    macro_calendar_provider: str = "mock"
    fred_api_key: str = ""
    fred_base_url: str = "https://api.stlouisfed.org/fred"
    fred_timeout_seconds: int = 8

    # broker provider config
    broker_provider: str = "mock"
    alpaca_paper_base_url: str = "https://paper-api.alpaca.markets"

    # deterministic recommendation quality gates
    min_expected_rr: float = 1.4
    max_event_continuation_volatility: float = 0.045
    min_catalyst_source_quality_score: float = 0.0

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    @property
    def console_url(self) -> str:
        return self.app_base_url


settings = Settings()


def validate_auth_runtime_configuration(cfg: Settings = settings) -> None:
    """Fail closed when mock auth is configured outside explicit local/test environments."""

    auth_provider = cfg.auth_provider.strip().lower()
    environment = cfg.environment.strip().lower()
    if auth_provider == "mock" and environment not in {"dev", "local", "test"}:
        raise RuntimeError(
            "AUTH_PROVIDER=mock is only allowed when ENVIRONMENT is one of: dev, local, test. "
            f"Received ENVIRONMENT={cfg.environment!r}."
        )
