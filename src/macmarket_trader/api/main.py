"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from macmarket_trader.api.routes.admin import router as admin_router
from macmarket_trader.api.routes.admin import user_router
from macmarket_trader.api.routes.charts import router as charts_router
from macmarket_trader.api.routes.health import router as health_router
from macmarket_trader.api.routes.recommendations import router as recommendation_router
from macmarket_trader.api.routes.replay import router as replay_router
from macmarket_trader.config import settings, validate_auth_runtime_configuration
from macmarket_trader.logging_config import configure_logging

configure_logging()
app = FastAPI(title="MacMarket-Trader API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(health_router)
app.include_router(recommendation_router)
app.include_router(replay_router)
app.include_router(charts_router)

app.include_router(user_router)
app.include_router(admin_router)


@app.on_event("startup")
def validate_runtime_configuration() -> None:
    validate_auth_runtime_configuration(settings)
