from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from macmarket_trader.api.main import app
from macmarket_trader.api.routes import admin as admin_routes
from macmarket_trader.config import settings
from macmarket_trader.domain.enums import Direction, EventSourceType, RegimeType, SetupType
from macmarket_trader.domain.models import AppUserModel
from macmarket_trader.domain.schemas import (
    Bar,
    BetterElsewhereCandidate,
    CatalystMetadata,
    ConstraintCheck,
    ConstraintReport,
    EntryMetadata,
    EventEvidenceBundle,
    EvidenceBundle,
    InvalidationMetadata,
    MarketRiskEvent,
    NewsEvent,
    OpportunityCandidateSummary,
    QualityMetadata,
    RegimeContext,
    SizingMetadata,
    SymbolRiskEvent,
    TargetsMetadata,
    TechnicalContext,
    TimeStopMetadata,
    TradeRecommendation,
)
from macmarket_trader.llm.base import LLMValidationError
from macmarket_trader.service import RecommendationService
from macmarket_trader.domain.time import utc_now
from macmarket_trader.risk_calendar.service import MarketRiskCalendarService, StaticRiskCalendarProvider
from macmarket_trader.storage.db import SessionLocal
from macmarket_trader.storage.repositories import RecommendationRepository


client = TestClient(app)
USER_AUTH = {"Authorization": "Bearer user-token"}


def _now() -> datetime:
    return datetime(2026, 5, 1, 14, 30, tzinfo=timezone.utc)


def _bars(high_vol: bool = False) -> list[Bar]:
    return [
        Bar(date=datetime(2026, 4, 27).date(), open=98, high=100, low=97, close=99, volume=900_000),
        Bar(date=datetime(2026, 4, 28).date(), open=99, high=101, low=98, close=100, volume=950_000),
        Bar(date=datetime(2026, 4, 29).date(), open=100, high=102, low=99, close=101, volume=1_000_000),
        Bar(date=datetime(2026, 4, 30).date(), open=101, high=103, low=100, close=102, volume=1_100_000),
        Bar(
            date=datetime(2026, 5, 1).date(),
            open=107 if high_vol else 102,
            high=112 if high_vol else 104,
            low=100 if high_vol else 101,
            close=109 if high_vol else 103,
            volume=1_200_000,
        ),
    ]


def _macro_event(event_type: str = "cpi", starts_at: datetime | None = None) -> MarketRiskEvent:
    return MarketRiskEvent(
        event_type=event_type,
        title=f"{event_type.upper()} release",
        starts_at=starts_at or _now(),
        impact="high",
        source="test_static",
    )


def _earnings_event(symbol: str = "NKE", starts_at: datetime | None = None) -> SymbolRiskEvent:
    return SymbolRiskEvent(
        event_type="earnings",
        symbol=symbol,
        title=f"{symbol} earnings",
        starts_at=starts_at or _now(),
        impact="high",
        source="test_static",
    )


def _service_with_events(
    events: list[MarketRiskEvent | SymbolRiskEvent],
    evidence: list[EventEvidenceBundle] | None = None,
) -> MarketRiskCalendarService:
    return MarketRiskCalendarService(
        provider=StaticRiskCalendarProvider(events=events, evidence=evidence),
        cfg=settings,
    )


def _seed_approved_user(token: str = "user-token", external_id: str = "clerk_user") -> int:
    resp = client.get("/user/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    with SessionLocal() as session:
        user = session.execute(
            select(AppUserModel).where(AppUserModel.external_auth_user_id == external_id)
        ).scalar_one()
        user.approval_status = "approved"
        session.commit()
        return user.id


def _seed_recommendation(app_user_id: int, symbol: str = "AAPL") -> str:
    rec = TradeRecommendation(
        symbol=symbol,
        side=Direction.LONG,
        thesis="Synthetic approved recommendation for risk calendar tests.",
        event=NewsEvent(
            symbol=symbol,
            source_type=EventSourceType.NEWS,
            source_timestamp=_now(),
            headline="Test catalyst",
            summary="Deterministic test catalyst.",
            sentiment_score=0.5,
        ),
        catalyst=CatalystMetadata(type="news", novelty="high", source_quality="primary", event_timestamp=_now()),
        regime_context=RegimeContext(
            market_regime=RegimeType.RISK_ON_TREND,
            volatility_regime="moderate",
            breadth_state="supportive",
        ),
        technical_context=TechnicalContext(
            prior_day_high=102,
            prior_day_low=98,
            recent_20d_high=110,
            recent_20d_low=94,
            atr14=2.0,
            event_day_range=3.0,
        ),
        entry=EntryMetadata(setup_type=SetupType.EVENT_CONTINUATION, zone_low=100, zone_high=100, trigger_text="Test"),
        invalidation=InvalidationMetadata(price=96, reason="Test invalidation"),
        targets=TargetsMetadata(target_1=106, target_2=112, trailing_rule="Trail"),
        time_stop=TimeStopMetadata(max_holding_days=5, reason="Test"),
        sizing=SizingMetadata(risk_dollars=1000.0, stop_distance=4.0, shares=10),
        quality=QualityMetadata(expected_rr=1.8, confidence=0.7, risk_score=0.3),
        approved=True,
        constraints=ConstraintReport(
            checks=[ConstraintCheck(name="test", passed=True, details="synthetic")],
            risk_based_share_cap=10,
            notional_share_cap=10,
            final_share_count=10,
        ),
        evidence=EvidenceBundle(
            event_id="evt_risk_test",
            source_type=EventSourceType.NEWS,
            source_timestamp=_now(),
            regime_version="test",
            setup_engine_version="test",
            risk_engine_version="test",
            explanatory_notes=["synthetic"],
        ),
    )
    RecommendationRepository(SessionLocal).create(rec, app_user_id=app_user_id)
    return rec.recommendation_id


def test_cpi_macro_event_blocks_or_restricts_based_on_config(monkeypatch) -> None:
    monkeypatch.setattr(settings, "risk_calendar_default_block_high_impact", True)
    service = _service_with_events([_macro_event("cpi")])

    blocked = service.assess(symbol="SPY", as_of=_now())

    assert blocked.decision.decision_state == "no_trade"
    assert blocked.decision.allow_new_entries is False
    assert blocked.decision.recommended_action == "sit_out"

    monkeypatch.setattr(settings, "risk_calendar_default_block_high_impact", False)
    restricted = service.assess(symbol="SPY", as_of=_now())

    assert restricted.decision.decision_state == "restricted"
    assert restricted.decision.requires_confirmation is True


def test_earnings_inside_window_requires_verified_evidence() -> None:
    service = _service_with_events([_earnings_event("NKE")])

    assessment = service.assess(symbol="NKE", as_of=_now())

    assert assessment.decision.decision_state == "requires_event_evidence"
    assert assessment.decision.allow_new_entries is False
    assert "earnings evidence missing" in assessment.decision.warning_summary
    assert assessment.decision.missing_evidence


def test_earnings_with_verified_evidence_is_event_trade_review_not_normal() -> None:
    evidence = EventEvidenceBundle(
        source="test_fixture",
        as_of=_now(),
        event_type="earnings",
        symbol="NKE",
        summary="Verified expected move and sector context supplied by test fixture.",
        metrics={"expected_move_pct": 6.5},
        confidence=0.8,
        provenance={"fixture": "risk_calendar"},
        stale=False,
    )
    service = _service_with_events([_earnings_event("NKE")], evidence=[evidence])

    assessment = service.assess(symbol="NKE", as_of=_now())

    assert assessment.decision.decision_state == "restricted"
    assert assessment.decision.recommended_action == "event_trade_review"
    assert assessment.decision.decision_state != "normal"
    assert not assessment.decision.missing_evidence


def test_high_volatility_circuit_breaker_restricts_new_entries() -> None:
    service = _service_with_events([])

    assessment = service.assess(symbol="QQQ", bars=_bars(high_vol=True), as_of=_now())

    assert assessment.decision.decision_state == "restricted"
    assert assessment.decision.risk_level == "high"
    assert assessment.volatility_flags
    assert "VIX data unavailable" in assessment.decision.missing_evidence[0]


def test_rth_normalized_intraday_data_passes_session_policy_check(monkeypatch) -> None:
    monkeypatch.setattr(settings, "intraday_rth_session_required", True)
    service = _service_with_events([])
    bars = [
        Bar(
            date=datetime(2026, 5, 1).date(),
            timestamp=datetime(2026, 5, 1, 13, 30, tzinfo=timezone.utc),
            open=100,
            high=101,
            low=99,
            close=100.5,
            volume=1000,
            session_policy="regular_hours",
        ),
        Bar(
            date=datetime(2026, 5, 1).date(),
            timestamp=datetime(2026, 5, 1, 14, 30, tzinfo=timezone.utc),
            open=100.5,
            high=101.5,
            low=100,
            close=101,
            volume=1200,
            session_policy="regular_hours",
        ),
    ]

    assessment = service.assess(symbol="AAPL", timeframe="1H", bars=bars, as_of=_now())

    assert assessment.decision.decision_state == "normal"
    assert assessment.data_quality_flags == []


def test_provider_session_intraday_data_creates_data_quality_caution(monkeypatch) -> None:
    monkeypatch.setattr(settings, "intraday_rth_session_required", True)
    monkeypatch.setattr(settings, "intraday_rth_violation_mode", "caution")
    service = _service_with_events([])
    bars = [
        Bar(
            date=datetime(2026, 5, 1).date(),
            timestamp=datetime(2026, 5, 1, 12, 30, tzinfo=timezone.utc),
            open=100,
            high=101,
            low=99,
            close=100.5,
            volume=1000,
            session_policy="provider_session",
        )
    ]

    assessment = service.assess(symbol="AAPL", timeframe="1H", bars=bars, as_of=_now())

    assert assessment.decision.decision_state == "caution"
    assert assessment.decision.allow_new_entries is True
    assert assessment.data_quality_flags == ["intraday_equity_bars_not_regular_hours_normalized"]


def test_provider_session_intraday_data_can_block_by_config(monkeypatch) -> None:
    monkeypatch.setattr(settings, "intraday_rth_session_required", True)
    monkeypatch.setattr(settings, "intraday_rth_violation_mode", "block")
    service = _service_with_events([])
    bars = [
        Bar(
            date=datetime(2026, 5, 1).date(),
            timestamp=datetime(2026, 5, 1, 12, 30, tzinfo=timezone.utc),
            open=100,
            high=101,
            low=99,
            close=100.5,
            volume=1000,
            session_policy="provider_session",
        )
    ]

    assessment = service.assess(symbol="AAPL", timeframe="4H", bars=bars, as_of=_now())

    assert assessment.decision.decision_state == "data_quality_block"
    assert assessment.decision.allow_new_entries is False


def test_provider_data_issue_creates_data_quality_block() -> None:
    service = _service_with_events([
        MarketRiskEvent(
            event_type="provider_data_issue",
            title="Provider bars stale",
            starts_at=_now(),
            impact="high",
            source="test_static",
        )
    ])

    assessment = service.assess(symbol="SPY", as_of=_now())

    assert assessment.decision.decision_state == "data_quality_block"
    assert assessment.decision.allow_new_entries is False
    assert assessment.data_quality_flags == ["Provider bars stale"]


def test_recommendation_is_calendar_blocked_without_changing_levels() -> None:
    service = _service_with_events([_macro_event("fomc_decision", starts_at=utc_now())])
    rec = RecommendationService(
        persist_audit=False,
        risk_calendar_service=service,
    ).generate(
        symbol="AAPL",
        bars=_bars(),
        event_text="earnings beat with strong guidance",
        event=None,
        portfolio=None,
        user_is_approved=True,
    )

    assert rec.approved is False
    assert rec.outcome == "calendar_blocked"
    assert rec.risk_calendar is not None
    assert rec.risk_calendar.decision.decision_state == "no_trade"
    assert rec.entry.zone_low > 0
    assert rec.invalidation.price > 0
    assert rec.targets.target_1 > rec.entry.zone_low


def test_paper_order_staging_blocked_during_no_trade(monkeypatch) -> None:
    user_id = _seed_approved_user()
    rec_uid = _seed_recommendation(user_id)
    monkeypatch.setattr(admin_routes, "risk_calendar_service", _service_with_events([_macro_event("cpi", starts_at=utc_now())]))

    resp = client.post("/user/orders", headers=USER_AUTH, json={"recommendation_id": rec_uid})

    assert resp.status_code == 409
    assert "risk_calendar_blocked" in resp.json()["detail"]


def test_restricted_paper_order_requires_confirmation_and_reason(monkeypatch) -> None:
    user_id = _seed_approved_user()
    rec_uid = _seed_recommendation(user_id, symbol="MSFT")
    monkeypatch.setattr(settings, "risk_calendar_default_block_high_impact", False)
    monkeypatch.setattr(admin_routes, "risk_calendar_service", _service_with_events([_macro_event("pce", starts_at=utc_now())]))

    missing = client.post("/user/orders", headers=USER_AUTH, json={"recommendation_id": rec_uid})
    assert missing.status_code == 409
    assert missing.json()["detail"] == "risk_calendar_confirmation_required"

    no_reason = client.post(
        "/user/orders",
        headers=USER_AUTH,
        json={"recommendation_id": rec_uid, "risk_calendar_confirmed": True},
    )
    assert no_reason.status_code == 409
    assert no_reason.json()["detail"] == "risk_calendar_override_reason_required"

    ok = client.post(
        "/user/orders",
        headers=USER_AUTH,
        json={
            "recommendation_id": rec_uid,
            "risk_calendar_confirmed": True,
            "risk_calendar_override_reason": "Reviewed macro event risk for paper-only demo.",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["risk_calendar"]["decision"]["decision_state"] == "restricted"


def test_opportunity_intelligence_cannot_change_risk_decision_or_add_unscanned_candidate() -> None:
    risk = _service_with_events([_earnings_event("NKE")]).assess(symbol="NKE", as_of=_now())
    candidate = OpportunityCandidateSummary(
        recommendation_id="rec_nke",
        symbol="NKE",
        side="long",
        approved=False,
        status="calendar_blocked",
        rejection_reason="earnings_event_requires_verified_evidence",
        risk_calendar=risk,
    )
    service = RecommendationService(persist_audit=False)

    memo = service.generate_opportunity_intelligence(candidates=[candidate])

    assert memo.candidates[0].risk_calendar is not None
    assert memo.candidates[0].risk_calendar.decision.decision_state == "requires_event_evidence"
    assert "deterministic gate owns" in memo.market_desk_memo.lower()

    bad_elsewhere = [
        BetterElsewhereCandidate(
            symbol="FAKE",
            reason="LLM invented symbol",
            source="deterministic_scan",
            verified_by_scan=True,
        )
    ]
    try:
        service._validate_opportunity_memo(
            memo=memo.model_copy(update={"better_elsewhere": bad_elsewhere}),
            candidates=[candidate],
            better_elsewhere=[],
        )
    except LLMValidationError:
        pass
    else:
        raise AssertionError("unscanned deterministic candidates must be rejected")
