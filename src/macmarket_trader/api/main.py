"""FastAPI application entry point."""

from fastapi import FastAPI

from macmarket_trader.api.routes.admin import router as admin_router
from macmarket_trader.api.routes.admin import user_router
from macmarket_trader.api.routes.charts import router as charts_router
from macmarket_trader.api.routes.health import router as health_router
from macmarket_trader.api.routes.recommendations import router as recommendation_router
from macmarket_trader.api.routes.replay import router as replay_router
from macmarket_trader.logging_config import configure_logging

configure_logging()
app = FastAPI(title="MacMarket-Trader API", version="0.1.0")
app.include_router(health_router)
app.include_router(recommendation_router)
app.include_router(replay_router)
app.include_router(charts_router)

app.include_router(user_router)
app.include_router(admin_router)
