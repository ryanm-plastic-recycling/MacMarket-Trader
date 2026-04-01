"""Application configuration models."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed configuration values."""

    app_name: str = "MacMarket-Trader"
    environment: str = "dev"
    database_url: str = "sqlite:///./macmarket_trader.db"
    log_level: str = "INFO"
    risk_dollars_per_trade: float = 1000.0
    max_portfolio_heat: float = 0.06
    max_position_notional: float = 0.20
    audit_persistence_enabled: bool = True

    # auth/email/provider config
    auth_provider: str = "mock"
    clerk_jwt_issuer: str = ""
    clerk_jwks_url: str = ""
    clerk_jwt_audience: str = ""
    require_mfa_for_admin: bool = True
    enforce_global_mfa: bool = False
    email_provider: str = "console"
    resend_api_key: str = ""
    resend_from_email: str = "noreply@macmarket-trader.local"

    # deterministic recommendation quality gates
    min_expected_rr: float = 1.4
    max_event_continuation_volatility: float = 0.045
    min_catalyst_source_quality_score: float = 0.0

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
