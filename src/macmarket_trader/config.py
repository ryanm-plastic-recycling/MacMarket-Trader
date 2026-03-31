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

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
