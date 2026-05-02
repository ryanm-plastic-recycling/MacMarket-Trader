"""Alpha stabilization smoke checks for local/API verification.

The script uses an isolated temporary SQLite database and the mock auth provider
so it can run without touching the operator's local dev database or requiring
external credentials. It intentionally verifies research/paper-only workflows.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone


def _configure_isolated_runtime() -> tempfile.TemporaryDirectory[str]:
    tmp = tempfile.TemporaryDirectory(prefix="macmarket_alpha_smoke_")
    db_path = os.path.join(tmp.name, "smoke.db")
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["ENVIRONMENT"] = os.environ.get("ENVIRONMENT", "test")
    os.environ["AUTH_PROVIDER"] = os.environ.get("AUTH_PROVIDER", "mock")
    os.environ["WORKFLOW_DEMO_FALLBACK"] = os.environ.get("WORKFLOW_DEMO_FALLBACK", "true")
    os.environ["MARKET_DATA_ENABLED"] = os.environ.get("MARKET_DATA_ENABLED", "false")
    os.environ["POLYGON_ENABLED"] = os.environ.get("POLYGON_ENABLED", "false")
    os.environ["LLM_ENABLED"] = os.environ.get("LLM_ENABLED", "false")
    os.environ["LLM_PROVIDER"] = os.environ.get("LLM_PROVIDER", "mock")
    return tmp


_TMP = _configure_isolated_runtime()

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from macmarket_trader.api.main import app  # noqa: E402
from macmarket_trader.api.routes import admin as admin_routes  # noqa: E402
from macmarket_trader.config import settings  # noqa: E402
from macmarket_trader.domain.enums import Direction, EventSourceType, RegimeType, SetupType  # noqa: E402
from macmarket_trader.domain.models import AppUserModel  # noqa: E402
from macmarket_trader.domain.schemas import (  # noqa: E402
    CatalystMetadata,
    ConstraintCheck,
    ConstraintReport,
    EntryMetadata,
    EvidenceBundle,
    InvalidationMetadata,
    MarketRiskEvent,
    NewsEvent,
    QualityMetadata,
    RegimeContext,
    SizingMetadata,
    TargetsMetadata,
    TechnicalContext,
    TimeStopMetadata,
    TradeRecommendation,
)
from macmarket_trader.domain.time import utc_now  # noqa: E402
from macmarket_trader.risk_calendar.service import (  # noqa: E402
    MarketRiskCalendarService,
    StaticRiskCalendarProvider,
)
from macmarket_trader.storage.db import SessionLocal, engine, init_db  # noqa: E402
from macmarket_trader.storage.repositories import RecommendationRepository  # noqa: E402


AUTH = {"Authorization": "Bearer user-token"}


def _ok(message: str) -> None:
    print(f"[ok] {message}")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _client() -> TestClient:
    init_db()
    client = TestClient(app)
    response = client.get("/user/me", headers=AUTH)
    _require(response.status_code == 200, f"user bootstrap failed: {response.text}")
    with SessionLocal() as session:
        user = session.execute(
            select(AppUserModel).where(AppUserModel.external_auth_user_id == "clerk_user")
        ).scalar_one()
        user.approval_status = "approved"
        user.paper_max_order_notional = 1000.0
        session.commit()
    return client


def _seed_recommendation(
    *,
    app_user_id: int,
    symbol: str,
    shares: int = 224,
    entry: float = 354.40,
    stop: float = 350.00,
) -> str:
    now = datetime(2026, 5, 2, 14, 30, tzinfo=timezone.utc)
    rec = TradeRecommendation(
        symbol=symbol,
        side=Direction.LONG,
        thesis="Synthetic approved recommendation for alpha smoke verification.",
        event=NewsEvent(
            symbol=symbol,
            source_type=EventSourceType.NEWS,
            source_timestamp=now,
            headline="Smoke catalyst",
            summary="Deterministic smoke catalyst.",
            sentiment_score=0.5,
        ),
        catalyst=CatalystMetadata(
            type="news",
            novelty="high",
            source_quality="primary",
            event_timestamp=now,
        ),
        regime_context=RegimeContext(
            market_regime=RegimeType.RISK_ON_TREND,
            volatility_regime="moderate",
            breadth_state="supportive",
        ),
        technical_context=TechnicalContext(
            prior_day_high=entry + 2,
            prior_day_low=entry - 5,
            recent_20d_high=entry + 10,
            recent_20d_low=entry - 20,
            atr14=4.0,
            event_day_range=6.0,
            rel_volume=1.4,
        ),
        entry=EntryMetadata(
            setup_type=SetupType.EVENT_CONTINUATION,
            zone_low=entry,
            zone_high=entry,
            trigger_text="Smoke trigger",
        ),
        invalidation=InvalidationMetadata(price=stop, reason="Smoke invalidation"),
        targets=TargetsMetadata(target_1=entry + 8, target_2=entry + 16, trailing_rule="Trail after target 1"),
        time_stop=TimeStopMetadata(max_holding_days=5, reason="Smoke time stop"),
        sizing=SizingMetadata(risk_dollars=1000.0, stop_distance=abs(entry - stop), shares=shares),
        quality=QualityMetadata(expected_rr=1.8, confidence=0.7, risk_score=0.3),
        approved=True,
        constraints=ConstraintReport(
            checks=[ConstraintCheck(name="smoke", passed=True, details="synthetic")],
            risk_based_share_cap=shares,
            notional_share_cap=shares,
            final_share_count=shares,
        ),
        evidence=EvidenceBundle(
            event_id=f"evt_smoke_{symbol.lower()}",
            source_type=EventSourceType.NEWS,
            source_timestamp=now,
            regime_version="smoke",
            setup_engine_version="smoke",
            risk_engine_version="smoke",
            explanatory_notes=["synthetic"],
        ),
    )
    RecommendationRepository(SessionLocal).create(rec, app_user_id=app_user_id, strategy="Event Continuation")
    return rec.recommendation_id


def _approved_user_id() -> int:
    with SessionLocal() as session:
        return session.execute(
            select(AppUserModel.id).where(AppUserModel.external_auth_user_id == "clerk_user")
        ).scalar_one()


def smoke_health_and_charts(client: TestClient) -> None:
    health = client.get("/health")
    _require(health.status_code == 200 and health.json()["status"] == "ok", "health endpoint failed")
    _ok("health endpoint")

    for timeframe in ("1D", "1H", "4H"):
        response = client.post(
            "/charts/haco",
            headers=AUTH,
            json={"symbol": "AAPL", "timeframe": timeframe, "bars": [], "include_heikin_ashi": True},
        )
        _require(response.status_code == 200, f"HACO {timeframe} failed: {response.text}")
        payload = response.json()
        candles = payload["candles"]
        _require(candles, f"HACO {timeframe} returned no candles")
        _require(payload["data_source"], f"HACO {timeframe} did not report data source")
        _require(payload["data_source"] != "daily_bars" or timeframe == "1D", f"HACO {timeframe} used daily bars")
        if timeframe in {"1H", "4H"}:
            times = [candle["time"] for candle in candles]
            _require(all(isinstance(time, int) for time in times), f"HACO {timeframe} did not emit unix seconds")
            _require(times == sorted(times), f"HACO {timeframe} times are not ascending")
            _require(len(times) == len(set(times)), f"HACO {timeframe} times are not unique")
            _require(payload["session_policy"] == "regular_hours", f"HACO {timeframe} is not RTH-normalized")
            _require(payload["fallback_mode"] is not None, f"HACO {timeframe} did not report fallback mode")
        _ok(f"HACO {timeframe} chart payload")


def smoke_llm_optional(client: TestClient) -> None:
    if not (settings.llm_enabled and settings.llm_provider.lower() == "openai" and settings.llm_api_key.strip()):
        _ok("OpenAI LLM smoke skipped: LLM_ENABLED/openai/key not configured")
        return

    response = client.post(
        "/user/recommendations/generate",
        headers=AUTH,
        json={"symbol": "AAPL", "event_text": "AAPL earnings beat with strong guidance"},
    )
    _require(response.status_code == 200, f"OpenAI LLM recommendation smoke failed: {response.text}")
    rec_id = response.json()["recommendation_id"]
    listing = client.get("/user/recommendations", headers=AUTH)
    row = next(row for row in listing.json() if row["recommendation_id"] == rec_id)
    provenance = row["payload"].get("llm_provenance") or {}
    _require(provenance.get("provider") == "openai", "LLM provider was not OpenAI")
    _require(provenance.get("fallback_used") is False, "OpenAI LLM smoke fell back")
    _ok("OpenAI LLM explanation path")


def smoke_paper_sizing(client: TestClient) -> None:
    user_id = _approved_user_id()
    rec_uid = _seed_recommendation(app_user_id=user_id, symbol="GOOG")

    staged = client.post("/user/orders", headers=AUTH, json={"recommendation_id": rec_uid})
    _require(staged.status_code == 200, f"paper order staging failed: {staged.text}")
    body = staged.json()
    _require(body["recommended_shares"] == 224, "recommended sizing was not preserved")
    _require(body["final_order_shares"] == 2, "max notional did not cap final paper shares")
    _require(body["notional_cap_reduced"] is True, "notional cap warning was not set")
    _ok("paper order notional cap")

    rec_override = _seed_recommendation(app_user_id=user_id, symbol="MSFT")
    accepted = client.post(
        "/user/orders",
        headers=AUTH,
        json={"recommendation_id": rec_override, "override_shares": 1},
    )
    _require(accepted.status_code == 200, f"override below cap failed: {accepted.text}")
    _require(accepted.json()["final_order_shares"] == 1, "override below cap did not set final shares")
    _ok("paper order override below cap")

    rec_rejected = _seed_recommendation(app_user_id=user_id, symbol="NVDA")
    rejected = client.post(
        "/user/orders",
        headers=AUTH,
        json={"recommendation_id": rec_rejected, "override_shares": 3},
    )
    _require(rejected.status_code == 409, "override above cap was not rejected")
    _ok("paper order override above cap rejected")


def smoke_market_risk(client: TestClient) -> None:
    normal = MarketRiskCalendarService(provider=StaticRiskCalendarProvider(events=[]), cfg=settings).assess(
        symbol="AAPL",
        as_of=utc_now(),
    )
    _require(normal.decision.allow_new_entries is True, "normal risk state did not allow entries")
    _ok("normal market risk state")

    user_id = _approved_user_id()
    original_service = admin_routes.risk_calendar_service
    original_block = settings.risk_calendar_default_block_high_impact
    try:
        settings.risk_calendar_default_block_high_impact = False
        admin_routes.risk_calendar_service = MarketRiskCalendarService(
            provider=StaticRiskCalendarProvider(
                events=[
                    MarketRiskEvent(
                        event_type="pce",
                        title="PCE release",
                        starts_at=utc_now(),
                        impact="high",
                        source="smoke_static",
                    )
                ]
            ),
            cfg=settings,
        )
        restricted_rec = _seed_recommendation(app_user_id=user_id, symbol="META", shares=2, entry=100.0, stop=96.0)
        restricted = client.post("/user/orders", headers=AUTH, json={"recommendation_id": restricted_rec})
        _require(restricted.status_code == 409, "restricted risk state did not require confirmation")
        _require(restricted.json()["detail"] == "risk_calendar_confirmation_required", "unexpected restricted error")

        confirmed = client.post(
            "/user/orders",
            headers=AUTH,
            json={
                "recommendation_id": restricted_rec,
                "risk_calendar_confirmed": True,
                "risk_calendar_override_reason": "Smoke reviewed macro event risk.",
            },
        )
        _require(confirmed.status_code == 200, f"restricted confirmed order failed: {confirmed.text}")
        _ok("restricted paper order confirmation")

        settings.risk_calendar_default_block_high_impact = True
        admin_routes.risk_calendar_service = MarketRiskCalendarService(
            provider=StaticRiskCalendarProvider(
                events=[
                    MarketRiskEvent(
                        event_type="cpi",
                        title="CPI release",
                        starts_at=utc_now(),
                        impact="high",
                        source="smoke_static",
                    )
                ]
            ),
            cfg=settings,
        )
        blocked_rec = _seed_recommendation(app_user_id=user_id, symbol="TSLA", shares=2, entry=100.0, stop=96.0)
        blocked = client.post("/user/orders", headers=AUTH, json={"recommendation_id": blocked_rec})
        _require(blocked.status_code == 409, "no_trade risk state did not block paper order")
        _require("risk_calendar_blocked" in blocked.json()["detail"], "unexpected no_trade error")
        _ok("no_trade paper order block")
    finally:
        settings.risk_calendar_default_block_high_impact = original_block
        admin_routes.risk_calendar_service = original_service


def main() -> None:
    try:
        client = _client()
        smoke_health_and_charts(client)
        smoke_llm_optional(client)
        smoke_paper_sizing(client)
        smoke_market_risk(client)
        print("[ok] alpha smoke checks completed")
    finally:
        engine.dispose()
        _TMP.cleanup()


if __name__ == "__main__":
    main()
