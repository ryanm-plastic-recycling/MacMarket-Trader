from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from macmarket_trader.api.main import app
from macmarket_trader.api.routes import admin as admin_routes
from macmarket_trader.config import settings
from macmarket_trader.data.providers.market_data import MarketSnapshot
from macmarket_trader.domain.enums import Direction, EventSourceType, RegimeType, SetupType
from macmarket_trader.domain.models import AppUserModel, PaperPositionModel, RecommendationModel
from macmarket_trader.domain.schemas import (
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
from macmarket_trader.domain.time import utc_now
from macmarket_trader.risk_calendar.service import MarketRiskCalendarService, StaticRiskCalendarProvider
from macmarket_trader.storage.db import SessionLocal
from macmarket_trader.storage.repositories import PaperPortfolioRepository, RecommendationRepository


client = TestClient(app)
USER_AUTH = {"Authorization": "Bearer user-token"}


class StubMarketDataService:
    def __init__(self, marks: dict[str, float]) -> None:
        self.marks = {symbol.upper(): value for symbol, value in marks.items()}

    def latest_snapshot(self, symbol: str, timeframe: str = "1D") -> MarketSnapshot:
        mark = self.marks.get(symbol.upper(), 100.0)
        return MarketSnapshot(
            symbol=symbol.upper(),
            timeframe=timeframe,
            as_of=datetime(2026, 5, 2, 15, 59, tzinfo=timezone.utc),
            open=mark,
            high=mark,
            low=mark,
            close=mark,
            volume=1_000_000,
            source="polygon",
            fallback_mode=False,
        )


def _approve_user() -> int:
    resp = client.get("/user/me", headers=USER_AUTH)
    assert resp.status_code == 200, resp.text
    with SessionLocal() as session:
        user = session.execute(
            select(AppUserModel).where(AppUserModel.external_auth_user_id == "clerk_user")
        ).scalar_one()
        user.approval_status = "approved"
        session.commit()
        return user.id


def _risk_service(events: list[MarketRiskEvent] | None = None) -> MarketRiskCalendarService:
    return MarketRiskCalendarService(provider=StaticRiskCalendarProvider(events=events or []), cfg=settings)


def _rec(
    *,
    symbol: str = "GOOG",
    entry: float = 100.0,
    stop: float = 96.0,
    target_1: float = 106.0,
    target_2: float = 112.0,
    max_hold: int = 5,
    shares: int = 10,
) -> TradeRecommendation:
    now = datetime(2026, 5, 1, 14, 30, tzinfo=timezone.utc)
    return TradeRecommendation(
        symbol=symbol,
        side=Direction.LONG,
        thesis="Synthetic active position review recommendation.",
        event=NewsEvent(
            symbol=symbol,
            source_type=EventSourceType.NEWS,
            source_timestamp=now,
            headline="Test catalyst",
            summary="Deterministic test catalyst.",
            sentiment_score=0.5,
        ),
        catalyst=CatalystMetadata(type="news", novelty="high", source_quality="primary", event_timestamp=now),
        regime_context=RegimeContext(
            market_regime=RegimeType.RISK_ON_TREND,
            volatility_regime="moderate",
            breadth_state="supportive",
        ),
        technical_context=TechnicalContext(
            prior_day_high=entry + 2,
            prior_day_low=entry - 4,
            recent_20d_high=entry + 12,
            recent_20d_low=entry - 8,
            atr14=3.0,
            event_day_range=4.0,
            rel_volume=1.2,
        ),
        entry=EntryMetadata(setup_type=SetupType.EVENT_CONTINUATION, zone_low=entry, zone_high=entry, trigger_text="Test trigger"),
        invalidation=InvalidationMetadata(price=stop, reason="Test invalidation"),
        targets=TargetsMetadata(target_1=target_1, target_2=target_2, trailing_rule="Trail after target 1"),
        time_stop=TimeStopMetadata(max_holding_days=max_hold, reason="Test time stop"),
        sizing=SizingMetadata(risk_dollars=1000.0, stop_distance=abs(entry - stop), shares=shares),
        quality=QualityMetadata(expected_rr=1.8, confidence=0.7, risk_score=0.3),
        approved=True,
        constraints=ConstraintReport(
            checks=[ConstraintCheck(name="test", passed=True, details="synthetic")],
            risk_based_share_cap=shares,
            notional_share_cap=shares,
            final_share_count=shares,
        ),
        evidence=EvidenceBundle(
            event_id="evt_position_review",
            source_type=EventSourceType.NEWS,
            source_timestamp=now,
            regime_version="test",
            setup_engine_version="test",
            risk_engine_version="test",
            explanatory_notes=["synthetic"],
        ),
    )


def _seed_position(
    *,
    app_user_id: int,
    symbol: str = "GOOG",
    entry: float = 100.0,
    stop: float = 96.0,
    target_1: float = 106.0,
    target_2: float = 112.0,
    rank: int | None = 1,
    ranking_status: str = "top_candidate",
    opened_days_ago: int = 1,
    missing_levels: bool = False,
    closed: bool = False,
) -> int:
    rec = _rec(symbol=symbol, entry=entry, stop=stop, target_1=target_1, target_2=target_2)
    rec_repo = RecommendationRepository(SessionLocal)
    rec_repo.create(rec, app_user_id=app_user_id, strategy="Event Continuation")
    rec_repo.attach_workflow_metadata(
        rec.recommendation_id,
        market_data_source="polygon",
        fallback_mode=False,
        market_mode="equities",
        source_strategy="Event Continuation",
        session_metadata={"session_policy": "regular_hours"},
    )
    rec_repo.attach_ranking_provenance(
        rec.recommendation_id,
        ranking_provenance={
            "rank": rank,
            "status": ranking_status,
            "score": 0.8 if ranking_status == "top_candidate" else 0.4,
            "timeframe": "1D",
        },
    )
    if missing_levels:
        with SessionLocal() as session:
            row = session.execute(
                select(RecommendationModel).where(RecommendationModel.recommendation_id == rec.recommendation_id)
            ).scalar_one()
            payload = dict(row.payload or {})
            payload.pop("invalidation", None)
            payload.pop("targets", None)
            row.payload = payload
            session.commit()

    position = PaperPortfolioRepository(SessionLocal).create_position(
        app_user_id=app_user_id,
        symbol=symbol,
        side="long",
        quantity=10,
        average_price=entry,
        recommendation_id=rec.recommendation_id,
        order_id=f"ord-{symbol.lower()}",
    )
    with SessionLocal() as session:
        row = session.get(PaperPositionModel, position.id)
        assert row is not None
        row.opened_at = utc_now() - timedelta(days=opened_days_ago)
        if closed:
            row.status = "closed"
            row.closed_at = utc_now()
            row.quantity = 0
            row.remaining_qty = 0
        session.commit()
    return position.id


def _setup(monkeypatch, marks: dict[str, float]) -> int:
    user_id = _approve_user()
    monkeypatch.setattr(admin_routes, "market_data_service", StubMarketDataService(marks))
    monkeypatch.setattr(admin_routes, "risk_calendar_service", _risk_service())
    return user_id


def test_open_goog_long_returns_mark_pnl_and_excludes_closed_positions(monkeypatch) -> None:
    user_id = _setup(monkeypatch, {"GOOG": 105.0, "MSFT": 260.0})
    _seed_position(app_user_id=user_id, symbol="GOOG", entry=100.0, stop=96.0, target_1=110.0)
    _seed_position(app_user_id=user_id, symbol="MSFT", entry=250.0, stop=245.0, target_1=270.0, closed=True)

    resp = client.get("/user/paper-positions/review", headers=USER_AUTH)

    assert resp.status_code == 200, resp.text
    reviews = resp.json()
    assert [item["symbol"] for item in reviews] == ["GOOG"]
    review = reviews[0]
    assert review["position_id"]
    assert review["current_mark_price"] == 105.0
    assert review["unrealized_pnl"] == 50.0
    assert review["unrealized_return_pct"] == 5.0
    assert review["already_open"] is True
    assert review["current_recommendation_status"] == "top_candidate"


def test_mark_below_stop_returns_stop_triggered(monkeypatch) -> None:
    user_id = _setup(monkeypatch, {"GOOG": 95.0})
    _seed_position(app_user_id=user_id, stop=96.0)

    review = client.get("/user/paper-positions/review", headers=USER_AUTH).json()[0]

    assert review["action_classification"] == "stop_triggered"
    assert review["distance_to_stop_pct"] < 0


def test_above_target_and_still_ranked_holds(monkeypatch) -> None:
    user_id = _setup(monkeypatch, {"GOOG": 107.0})
    _seed_position(app_user_id=user_id, target_1=106.0, rank=1, ranking_status="top_candidate")

    review = client.get("/user/paper-positions/review", headers=USER_AUTH).json()[0]

    assert review["action_classification"] == "target_reached_hold"


def test_above_target_and_weakened_takes_profit_review(monkeypatch) -> None:
    user_id = _setup(monkeypatch, {"GOOG": 107.0})
    _seed_position(app_user_id=user_id, target_1=106.0, rank=9, ranking_status="watchlist")

    review = client.get("/user/paper-positions/review", headers=USER_AUTH).json()[0]

    assert review["current_recommendation_status"] == "weakened"
    assert review["action_classification"] == "target_reached_take_profit"


def test_old_position_beyond_max_hold_returns_time_stop_exit(monkeypatch) -> None:
    user_id = _setup(monkeypatch, {"GOOG": 102.0})
    _seed_position(app_user_id=user_id, target_1=110.0, opened_days_ago=6)

    review = client.get("/user/paper-positions/review", headers=USER_AUTH).json()[0]

    assert review["holding_period_status"] == "exceeded"
    assert review["action_classification"] == "time_stop_exit"


def test_scale_in_candidate_is_blocked_by_notional_cap(monkeypatch) -> None:
    user_id = _setup(monkeypatch, {"GOOG": 105.0})
    with SessionLocal() as session:
        user = session.get(AppUserModel, user_id)
        assert user is not None
        user.paper_max_order_notional = 500.0
        session.commit()
    _seed_position(app_user_id=user_id, target_1=120.0, rank=1, ranking_status="top_candidate")

    review = client.get("/user/paper-positions/review", headers=USER_AUTH).json()[0]

    assert review["already_open"] is True
    assert review["action_classification"] != "scale_in_candidate"
    assert any("max_paper_order_notional" in warning for warning in review["warnings"])


def test_missing_levels_are_reported_without_fabrication(monkeypatch) -> None:
    user_id = _setup(monkeypatch, {"GOOG": 102.0})
    _seed_position(app_user_id=user_id, target_1=110.0, missing_levels=True)

    review = client.get("/user/paper-positions/review", headers=USER_AUTH).json()[0]

    assert review["stop_price"] is None
    assert review["target_1"] is None
    assert "stop_price" in review["missing_data"]
    assert "target_1" in review["missing_data"]


def test_risk_calendar_no_trade_warns_but_does_not_auto_close(monkeypatch) -> None:
    user_id = _setup(monkeypatch, {"GOOG": 102.0})
    event = MarketRiskEvent(
        event_type="cpi",
        title="CPI release",
        starts_at=utc_now(),
        impact="high",
        source="test",
    )
    monkeypatch.setattr(admin_routes, "risk_calendar_service", _risk_service([event]))
    _seed_position(app_user_id=user_id, target_1=110.0)

    review = client.get("/user/paper-positions/review", headers=USER_AUTH).json()[0]

    assert review["risk_calendar"]["decision"]["allow_new_entries"] is False
    assert review["action_classification"] != "stop_triggered"
    assert review["provenance"]["no_automatic_exits"] is True
    assert any("does not auto-close" in warning for warning in review["warnings"])


def test_options_positions_are_excluded_from_equity_position_review(monkeypatch) -> None:
    _setup(monkeypatch, {"SPY": 100.0})
    option_open = client.post(
        "/user/options/paper-structures/open",
        headers=USER_AUTH,
        json={
            "market_mode": "options",
            "structure_type": "vertical_debit_spread",
            "underlying_symbol": "SPY",
            "legs": [
                {
                    "action": "buy",
                    "right": "call",
                    "strike": 500.0,
                    "expiration": date(2026, 5, 15).isoformat(),
                    "premium": 4.2,
                    "label": "long call",
                },
                {
                    "action": "sell",
                    "right": "call",
                    "strike": 510.0,
                    "expiration": date(2026, 5, 15).isoformat(),
                    "premium": 1.7,
                    "label": "short call",
                },
            ],
            "notes": "active review exclusion test",
        },
    )
    assert option_open.status_code == 200, option_open.text

    review = client.get("/user/paper-positions/review", headers=USER_AUTH)

    assert review.status_code == 200, review.text
    assert review.json() == []
