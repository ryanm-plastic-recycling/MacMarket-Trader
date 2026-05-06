"""Application configuration models."""

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed configuration values."""

    app_name: str = "MacMarket-Trader"
    environment: str = "dev"
    database_url: str = "sqlite:///./macmarket_trader.db"
    log_level: str = "INFO"
    risk_dollars_per_trade: float = 1000.0
    paper_max_order_notional: float = 1000.0
    commission_per_trade: float = 0.0
    commission_per_contract: float = 0.65
    max_portfolio_heat: float = 0.06
    max_position_notional: float = 0.20
    audit_persistence_enabled: bool = True
    llm_enabled: bool = False
    llm_provider: str = "mock"
    llm_model: str = ""
    openai_api_key: str = ""
    llm_api_key: str = ""
    llm_timeout_seconds: float = 12.0
    llm_max_output_tokens: int = 1200
    llm_temperature: float = 0.2
    risk_calendar_enabled: bool = True
    risk_calendar_provider: str = "static"
    risk_calendar_mode: str = "warn"
    risk_calendar_default_block_high_impact: bool = True
    earnings_avoidance_enabled: bool = True
    earnings_block_days_before: int = 1
    earnings_block_days_after: int = 1
    macro_event_block_before_minutes: int = 60
    macro_event_block_after_minutes: int = 60
    high_vol_block_enabled: bool = True
    high_vol_intraday_range_threshold: float = 0.04
    high_vol_gap_threshold: float = 0.03
    vix_high_threshold: float = 30.0
    index_risk_enabled: bool = True
    vix_caution_level: float = 20.0
    vix_restricted_level: float = 30.0
    vix_spike_caution_pct: float = 10.0
    spx_gap_caution_pct: float = 1.0
    spx_gap_restricted_pct: float = 2.0
    rut_underperform_caution_pct: float = -1.0
    ndx_underperform_caution_pct: float = -1.0
    index_data_stale_minutes: int = 60
    intraday_rth_session_required: bool = True
    intraday_rth_violation_mode: str = "caution"

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
    security_allowed_origins: list[str] = Field(default_factory=list)
    security_origin_check_enabled: bool = True
    security_rate_limit_enabled: bool = True
    api_docs_enabled: bool = True

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
    market_data_option_snapshot_cache_ttl_seconds: int = 30
    market_data_option_snapshot_stale_seconds: int = 86_400
    market_data_historical_cache_ttl_seconds: int = 120
    options_max_strike_snap_abs: float = 5.0
    options_max_strike_snap_pct: float = 0.025
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
    # Hard product boundary: even with BROKER_PROVIDER=alpaca configured, no
    # broker order routing (paper or live) executes unless this is explicitly
    # set true at runtime. Default false means a misconfigured BROKER_PROVIDER
    # cannot silently start sending orders to a brokerage.
    live_trading_allowed: bool = False

    # deterministic recommendation quality gates
    min_expected_rr: float = 1.4
    max_event_continuation_volatility: float = 0.045
    min_catalyst_source_quality_score: float = 0.0

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    @model_validator(mode="after")
    def prefer_openai_api_key(self) -> "Settings":
        """Prefer OPENAI_API_KEY while preserving LLM_API_KEY as a legacy fallback."""

        if self.openai_api_key.strip():
            self.llm_api_key = self.openai_api_key
        return self

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
