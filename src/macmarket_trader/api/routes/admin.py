"""Admin approval and operator routes."""

import logging
import math
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException

from macmarket_trader.api.deps.auth import current_user, require_admin, require_approved_user
from macmarket_trader.api.routes.workflow_lineage import extract_recommendation_key_levels, extract_recommendation_strategy
from macmarket_trader.config import settings
from macmarket_trader.data.providers.base import EmailMessage
from macmarket_trader.data.providers.market_data import DataNotEntitledError, DeterministicFallbackMarketDataProvider, SymbolNotFoundError
from macmarket_trader.data.providers.registry import build_email_provider, build_market_data_service
from macmarket_trader.domain.enums import ApprovalStatus, MarketMode
from macmarket_trader.domain.time import utc_now
from macmarket_trader.domain.schemas import (
    ApprovalActionRequest,
    Bar,
    ExpectedRange,
    InviteCreateRequest,
    OptionPaperCloseStructureRequest,
    OptionPaperCloseStructureResponse,
    OptionPaperLifecycleSummaryListResponse,
    OptionPaperOpenStructureResponse,
    OptionPaperStructureInput,
    OptionReplayPreviewRequest,
    OptionReplayPreviewResponse,
    PortfolioSnapshot,
    ReplayRunRequest,
    TradeRecommendation,
)
from macmarket_trader.execution.paper_broker import PaperBroker
from macmarket_trader.options.paper_close import OptionPaperCloseError, close_paper_option_structure
from macmarket_trader.options.paper_contracts import OptionPaperContractError
from macmarket_trader.options.paper_open import open_paper_option_structure
from macmarket_trader.options.replay_preview import build_options_replay_preview
from macmarket_trader.ranking_engine import DeterministicRankingEngine
from macmarket_trader.replay.engine import ReplayEngine
from macmarket_trader.service import RecommendationService
from macmarket_trader.email_templates import render_approval_html, render_invite_html, render_rejection_html
from macmarket_trader.strategy_reports import StrategyReportService
from macmarket_trader.strategy_registry import get_strategy_by_display_name, list_strategies
from macmarket_trader.storage.db import SessionLocal
from macmarket_trader.storage.repositories import DashboardRepository, EmailLogRepository, InviteRepository, OptionPaperRepository, OrderRepository, PaperPortfolioRepository, RecommendationRepository, ReplayRepository, StrategyReportRepository, UserRepository, WatchlistRepository, commission_paid_for_trade, display_id_or_fallback, gross_pnl_or_fallback, net_pnl_or_fallback
from macmarket_trader.domain.models import AuditLogModel


def _effective_risk_dollars(user) -> float:
    """Pass 4 — per-user risk override. Falls back to env default
    (settings.risk_dollars_per_trade) when the user has no override set."""
    override = getattr(user, "risk_dollars_per_trade", None)
    if override is None:
        return float(settings.risk_dollars_per_trade)
    try:
        return float(override)
    except (TypeError, ValueError):
        return float(settings.risk_dollars_per_trade)


def _effective_commission_per_trade(user) -> float:
    override = getattr(user, "commission_per_trade", None)
    if override is None:
        return float(settings.commission_per_trade)
    try:
        return float(override)
    except (TypeError, ValueError):
        return float(settings.commission_per_trade)


def _effective_commission_per_contract(user) -> float:
    override = getattr(user, "commission_per_contract", None)
    if override is None:
        return float(settings.commission_per_contract)
    try:
        return float(override)
    except (TypeError, ValueError):
        return float(settings.commission_per_contract)


def _trade_direction_multiplier(side: str | None) -> float:
    normalized = str(side or "").strip().lower()
    return -1.0 if normalized in {"short", "sell"} else 1.0


def _equity_trade_pnl(*, entry_price: float, exit_price: float, quantity: float, side: str | None, commission_per_trade: float) -> tuple[float, float]:
    direction = _trade_direction_multiplier(side)
    gross_pnl = (exit_price - entry_price) * quantity * direction
    net_pnl = gross_pnl - commission_per_trade
    return gross_pnl, net_pnl


# Phase 7 note: keep the fee-preview helper local for now to avoid a broader
# refactor. If Phase 7 grows further, centralize fee math into a dedicated
# module shared across replay/order/provider-readiness surfaces.
def _round_money(value: float | None) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return round(numeric, 2)


def _projected_equity_gross_pnl(rec: TradeRecommendation) -> float | None:
    try:
        shares = float(rec.sizing.shares)
        zone_low = float(rec.entry.zone_low)
        zone_high = float(rec.entry.zone_high)
        target_1 = float(rec.targets.target_1)
    except (AttributeError, TypeError, ValueError):
        return None
    if shares <= 0:
        return None
    values = (shares, zone_low, zone_high, target_1)
    if any(not math.isfinite(value) for value in values):
        return None
    entry_mid = (zone_low + zone_high) / 2.0
    direction = _trade_direction_multiplier(getattr(rec.side, "value", rec.side))
    return (target_1 - entry_mid) * shares * direction


def _equity_fee_preview(
    *,
    commission_per_trade: float,
    projected_gross_pnl: float | None = None,
    trade_event_count: int = 2,
) -> dict[str, object]:
    event_count = max(0, int(trade_event_count))
    estimated_entry_fee = commission_per_trade if event_count >= 1 else 0.0
    estimated_exit_fee = commission_per_trade if event_count >= 2 else 0.0
    estimated_total_fees = estimated_entry_fee + estimated_exit_fee
    projected_net_pnl = (
        None if projected_gross_pnl is None else projected_gross_pnl - estimated_total_fees
    )
    return {
        "estimated_entry_fee": _round_money(estimated_entry_fee),
        "estimated_exit_fee": _round_money(estimated_exit_fee),
        "estimated_total_fees": _round_money(estimated_total_fees),
        "projected_gross_pnl": _round_money(projected_gross_pnl),
        "projected_net_pnl": _round_money(projected_net_pnl),
        "fee_model": "equity_per_trade",
    }


def _position_close_fee_preview(*, commission_per_trade: float) -> dict[str, object]:
    return {
        "estimated_close_fee": _round_money(commission_per_trade),
        "fee_model": "equity_per_trade",
    }


def _recommendation_fee_preview(rec: TradeRecommendation | None, *, commission_per_trade: float) -> dict[str, object]:
    projected_gross_pnl = _projected_equity_gross_pnl(rec) if rec is not None else None
    return _equity_fee_preview(
        commission_per_trade=commission_per_trade,
        projected_gross_pnl=projected_gross_pnl,
        trade_event_count=2,
    )


def _recommendation_fee_preview_from_uid(
    recommendation_id: str | None,
    *,
    commission_per_trade: float,
) -> dict[str, object]:
    if not recommendation_id:
        return _recommendation_fee_preview(None, commission_per_trade=commission_per_trade)
    rec_row = recommendation_repo.get_by_recommendation_uid(recommendation_id)
    if rec_row is None:
        return _recommendation_fee_preview(None, commission_per_trade=commission_per_trade)
    try:
        rec = TradeRecommendation.model_validate(rec_row.payload or {})
    except Exception:
        return _recommendation_fee_preview(None, commission_per_trade=commission_per_trade)
    return _recommendation_fee_preview(rec, commission_per_trade=commission_per_trade)


def _record_audit_event(*, recommendation_id: str, payload: dict[str, object]) -> None:
    """Write a row into audit_logs. Reuses the same table the recommendation
    audit trail uses; the payload's `event` field distinguishes lifecycle
    actions like order_canceled / position_reopened from the recommendation
    snapshots written by RecommendationRepository.create()."""
    with SessionLocal() as session:
        session.add(AuditLogModel(recommendation_id=recommendation_id or "", payload=payload))
        session.commit()

router = APIRouter(prefix="/admin", tags=["admin"])
user_router = APIRouter(prefix="/user", tags=["user"])

user_repo = UserRepository(SessionLocal)
email_repo = EmailLogRepository(SessionLocal)
invite_repo = InviteRepository(SessionLocal)
dashboard_repo = DashboardRepository(SessionLocal)
recommendation_repo = RecommendationRepository(SessionLocal)
replay_repo = ReplayRepository(SessionLocal)
order_repo = OrderRepository(SessionLocal)
option_paper_repo = OptionPaperRepository(SessionLocal)
paper_portfolio_repo = PaperPortfolioRepository(SessionLocal)
watchlist_repo = WatchlistRepository(SessionLocal)
strategy_report_repo = StrategyReportRepository(SessionLocal)
email_provider = build_email_provider()
market_data_service = build_market_data_service()
recommendation_service = RecommendationService()
replay_engine = ReplayEngine(service=recommendation_service)
paper_broker = PaperBroker()
strategy_report_service = StrategyReportService(
    report_repo=strategy_report_repo,
    email_provider=email_provider,
    email_log_repo=email_repo,
)
preview_market_data_provider = DeterministicFallbackMarketDataProvider()
ranking_engine = DeterministicRankingEngine()


def _build_options_expected_range(*, latest_close: float, iv_snapshot: float | None, dte: int) -> ExpectedRange:
    reference = round(latest_close, 2)
    if iv_snapshot is None:
        return ExpectedRange(
            status="blocked",
            reason="missing_iv_snapshot",
            horizon_value=dte,
            horizon_unit="calendar_days",
            reference_price_type="underlying_last",
            snapshot_timestamp=utc_now(),
            provenance_notes="Expected range requires IV input from options chain quality checks.",
        )
    if iv_snapshot < 0.08:
        return ExpectedRange(
            status="blocked",
            reason="insufficient_iv_quality",
            method="iv_1sigma",
            horizon_value=dte,
            horizon_unit="calendar_days",
            reference_price_type="underlying_last",
            snapshot_timestamp=utc_now(),
            provenance_notes="IV snapshot too low-quality for deterministic expected range contract.",
        )

    absolute_move = round(reference * iv_snapshot * ((dte / 365) ** 0.5), 2)
    percent_move = round((absolute_move / reference) * 100, 2) if reference > 0 else None
    return ExpectedRange(
        method="iv_1sigma",
        horizon_value=dte,
        horizon_unit="calendar_days",
        reference_price_type="underlying_last",
        absolute_move=absolute_move,
        percent_move=percent_move,
        lower_bound=round(reference - absolute_move, 2),
        upper_bound=round(reference + absolute_move, 2),
        snapshot_timestamp=utc_now(),
        provenance_notes="Research preview only. Computed from IV 1-sigma method; not execution support.",
        status="computed",
    )


def _build_equity_expected_range(bars: list[Bar], *, horizon_trading_days: int = 5) -> ExpectedRange:
    """Compute equity_realized_vol_1sigma expected range from bar history.

    Formula: spot_price * realized_vol_annualized * sqrt(horizon_trading_days / 252)
    where realized_vol_annualized = daily_log_return_stddev * sqrt(252).
    Uses up to 20 daily closes to estimate recent realized volatility.
    """
    closes = [b.close for b in bars]
    if len(closes) < 3:
        return ExpectedRange(
            status="omitted",
            reason="insufficient_bar_history",
            horizon_value=horizon_trading_days,
            horizon_unit="trading_days",
            reference_price_type="spot_last",
            snapshot_timestamp=utc_now(),
            provenance_notes="Need at least 3 bars to compute realized volatility.",
        )
    # Use the most recent 20 closes to estimate short-term realized vol
    recent = closes[-21:]
    log_returns = [math.log(recent[i] / recent[i - 1]) for i in range(1, len(recent))]
    n = len(log_returns)
    mean_ret = sum(log_returns) / n
    variance = sum((r - mean_ret) ** 2 for r in log_returns) / max(n - 1, 1)
    daily_vol = math.sqrt(variance)
    if daily_vol <= 0:
        return ExpectedRange(
            status="blocked",
            reason="zero_realized_volatility",
            horizon_value=horizon_trading_days,
            horizon_unit="trading_days",
            reference_price_type="spot_last",
            snapshot_timestamp=utc_now(),
            provenance_notes="Realized volatility computed to zero — bars may be synthetic or flat.",
        )
    annualized_vol = daily_vol * math.sqrt(252)
    spot = round(closes[-1], 2)
    absolute_move = round(spot * annualized_vol * math.sqrt(horizon_trading_days / 252), 2)
    percent_move = round((absolute_move / spot) * 100, 2) if spot > 0 else None
    return ExpectedRange(
        method="equity_realized_vol_1sigma",
        horizon_value=horizon_trading_days,
        horizon_unit="trading_days",
        reference_price_type="spot_last",
        absolute_move=absolute_move,
        percent_move=percent_move,
        lower_bound=round(spot - absolute_move, 2),
        upper_bound=round(spot + absolute_move, 2),
        snapshot_timestamp=utc_now(),
        provenance_notes=(
            f"Realized vol from {n}-day log-return history. "
            "Regular-hours session only; scheduled events may dominate actual range."
        ),
        status="computed",
    )


def _safe_identity_value(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.startswith("{{") and normalized.endswith("}}"):
        return None
    return normalized


def _workflow_bars(symbol: str, limit: int = 60) -> tuple[list[Bar], str, bool]:
    try:
        bars, source, fallback_mode = market_data_service.historical_bars(symbol=symbol, timeframe="1D", limit=limit)
    except DataNotEntitledError:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "data_not_entitled",
                "message": f"Your data plan does not include {symbol}. Index bar data (SPX, NDX, VIX) requires a plan upgrade.",
            },
        )
    except SymbolNotFoundError:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "symbol_not_found",
                "message": f"No data found for symbol {symbol}. Verify the ticker is correct and supported.",
            },
        )
    if not bars:
        raise HTTPException(
            status_code=503,
            detail=(
                "No market-data bars available for operator workflow. "
                "Verify provider health and retry from Recommendations."
            ),
        )

    provider_is_expected = settings.market_data_enabled or settings.polygon_enabled
    allow_dev_demo_fallback = settings.workflow_demo_fallback and settings.environment.strip().lower() in {"dev", "local", "test"}
    if provider_is_expected and fallback_mode and not allow_dev_demo_fallback:
        raise HTTPException(
            status_code=503,
            detail=(
                "Provider-backed market data is configured but unavailable. "
                "User-facing recommendations/replay/orders are blocked to avoid hidden demo fallback."
            ),
        )

    return bars, source, fallback_mode


@user_router.get("/me")
def me(user=Depends(current_user)):
    safe_email = _safe_identity_value(user.email)
    safe_name = _safe_identity_value(user.display_name)
    warning = "Identity synchronization incomplete" if safe_email is None else None
    return {
        "id": user.id,
        "email": safe_email,
        "display_name": safe_name,
        "approval_status": user.approval_status,
        "app_role": user.app_role,
        "mfa_enabled": user.mfa_enabled,
        "auth_provider": settings.auth_provider.strip().lower() or "mock",
        "last_seen_at": user.last_seen_at.isoformat() if user.last_seen_at else None,
        "last_authenticated_at": user.last_authenticated_at.isoformat() if user.last_authenticated_at else None,
        "identity_warning": warning,
        # Pass 4 — per-user risk override. NULL → fall back to env default
        # so the UI can render "1000 (default)" vs an explicit user override.
        "risk_dollars_per_trade": user.risk_dollars_per_trade,
        "risk_dollars_per_trade_default": settings.risk_dollars_per_trade,
        "commission_per_trade": user.commission_per_trade,
        "commission_per_trade_default": settings.commission_per_trade,
        "commission_per_contract": user.commission_per_contract,
        "commission_per_contract_default": settings.commission_per_contract,
    }


@user_router.patch("/settings")
def update_user_settings(req: dict[str, object], user=Depends(require_approved_user)):
    """Update operator-controlled settings for sizing and commission defaults."""
    allowed_keys = {
        "risk_dollars_per_trade",
        "commission_per_trade",
        "commission_per_contract",
    }
    provided_keys = [key for key in allowed_keys if key in req]
    if not provided_keys:
        raise HTTPException(
            status_code=400,
            detail="At least one of risk_dollars_per_trade, commission_per_trade, or commission_per_contract is required.",
        )

    if "risk_dollars_per_trade" in req:
        raw = req.get("risk_dollars_per_trade")
        try:
            value = float(raw) if raw is not None else None
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="risk_dollars_per_trade must be numeric.")
        if value is None:
            user_repo.set_risk_dollars_per_trade(user.id, value=None)
        else:
            if value <= 0 or value > 50000:
                raise HTTPException(
                    status_code=400,
                    detail="risk_dollars_per_trade must be > 0 and <= 50000.",
                )
            user_repo.set_risk_dollars_per_trade(user.id, value=value)

    if "commission_per_trade" in req:
        raw = req.get("commission_per_trade")
        try:
            value = float(raw) if raw is not None else None
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="commission_per_trade must be numeric.")
        if value is None:
            user_repo.set_commission_per_trade(user.id, value=None)
        else:
            if value < 0 or value > 1000:
                raise HTTPException(
                    status_code=400,
                    detail="commission_per_trade must be >= 0 and <= 1000.",
                )
            user_repo.set_commission_per_trade(user.id, value=value)

    if "commission_per_contract" in req:
        raw = req.get("commission_per_contract")
        try:
            value = float(raw) if raw is not None else None
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="commission_per_contract must be numeric.")
        if value is None:
            user_repo.set_commission_per_contract(user.id, value=None)
        else:
            if value < 0 or value > 100:
                raise HTTPException(
                    status_code=400,
                    detail="commission_per_contract must be >= 0 and <= 100.",
                )
            user_repo.set_commission_per_contract(user.id, value=value)

    refreshed = user_repo.get_by_id(user.id)
    return {
        "id": refreshed.id,
        "risk_dollars_per_trade": refreshed.risk_dollars_per_trade,
        "risk_dollars_per_trade_default": settings.risk_dollars_per_trade,
        "commission_per_trade": refreshed.commission_per_trade,
        "commission_per_trade_default": settings.commission_per_trade,
        "commission_per_contract": refreshed.commission_per_contract,
        "commission_per_contract_default": settings.commission_per_contract,
    }


@user_router.get("/onboarding-status")
def onboarding_status(user=Depends(require_approved_user)):
    has_schedule = bool(strategy_report_repo.list_schedules_for_user(user.id))
    has_replay = bool(replay_repo.list_runs(limit=1, app_user_id=user.id))
    has_order = bool(order_repo.list_with_fills(limit=1, app_user_id=user.id))
    completed = sum([has_schedule, has_replay, has_order])
    return {
        "has_schedule": has_schedule,
        "has_replay": has_replay,
        "has_order": has_order,
        "has_viewed_haco": None,  # client-side via localStorage
        "completed": completed,
        "total": 4,
    }


@user_router.get("/dashboard")
def dashboard(user=Depends(require_approved_user)):
    counts = dashboard_repo.summary_counts()
    recommendations = recommendation_repo.list_recent(limit=5, app_user_id=user.id)
    replay_runs = replay_repo.list_runs(limit=5, app_user_id=user.id)
    orders = order_repo.list_with_fills(limit=5, app_user_id=user.id)
    pending_users = user_repo.list_by_status(ApprovalStatus.PENDING)
    provider_health = provider_health_summary()
    latest_snapshot = market_data_service.latest_snapshot(symbol="AAPL", timeframe="1D")

    # Operational audit events — combine email logs, approval events, and schedule runs
    email_events = [
        {
            "event_type": "email_sent",
            "timestamp": row.sent_at.isoformat() if row.sent_at else None,
            "detail": f"{row.template_name} → {row.destination}",
            "status": row.status,
        }
        for row in email_repo.list_recent(limit=5)
    ]
    approval_events = [
        {
            "event_type": "user_approval",
            "timestamp": row.created_at.isoformat() if row.created_at else None,
            "detail": f"approval request: {row.status} ({row.note})",
            "status": row.status,
        }
        for row in user_repo.list_recent_approval_requests(limit=5)
    ]
    schedule_run_events = [
        {
            "event_type": "schedule_run",
            "timestamp": row.created_at.isoformat() if row.created_at else None,
            "detail": f"schedule #{row.schedule_id} → {row.status} / {row.delivered_to}",
            "status": row.status,
        }
        for row in strategy_report_repo.list_recent_runs_all(limit=5)
    ]
    all_events = sorted(
        email_events + approval_events + schedule_run_events,
        key=lambda e: e["timestamp"] or "",
        reverse=True,
    )[:10]
    return {
        "status": "ok",
        "last_refresh": utc_now().isoformat(),
        "account": {
            "approval_status": user.approval_status,
            "app_role": user.app_role,
        },
        "market_regime": "event-driven / deterministic-eval",
        "provider_health": provider_health,
        "latest_market_snapshot": {
            "symbol": latest_snapshot.symbol,
            "as_of": latest_snapshot.as_of.isoformat(),
            "close": latest_snapshot.close,
            "source": latest_snapshot.source,
            "fallback_mode": latest_snapshot.fallback_mode,
        },
        "counts": counts,
        "active_recommendations": [
            {
                "id": row.id,
                "recommendation_id": row.recommendation_id,
                "created_at": row.created_at,
                "symbol": row.symbol,
                "payload": row.payload,
            }
            for row in recommendations
        ],
        "recent_replay_runs": [
            {
                "id": row.id,
                "symbol": row.symbol,
                "recommendation_count": row.recommendation_count,
                "approved_count": row.approved_count,
                "fill_count": row.fill_count,
                "created_at": row.created_at,
            }
            for row in replay_runs
        ],
        "recent_orders": orders,
        "pending_admin_actions": [{"id": u.id, "email": u.email, "display_name": u.display_name} for u in pending_users[:5]],
        "alerts": [
            {
                "kind": "provider",
                "level": "warning" if provider_health["summary"] != "ok" else "info",
                "message": (
                    f"{provider_health['configured_provider'].capitalize()} provider-backed workflows are active."
                    if provider_health["workflow_execution_mode"] == "provider"
                    else (
                        "Provider probe degraded and workflow demo fallback is disabled. "
                        "Recommendations, replay, and orders are blocked."
                        if provider_health["workflow_execution_mode"] == "blocked"
                        else "Explicit demo fallback bars are active for workflows."
                    )
                ),
            }
        ],
        "quick_links": ["/charts/haco", "/admin/users/pending", "/recommendations"],
        "workflow_guide": [
            "Start guided paper trade from Dashboard or Analysis to run the canonical Analyze → Recommendation → Replay → Paper Order flow.",
            "Run Replay to validate path-by-path risk transitions before staging paper execution.",
            "Use Orders to review fills and paper blotter outcomes.",
        ],
        "recent_audit_events": all_events,
    }


@user_router.get("/recommendations")
def list_recommendations(_user=Depends(require_approved_user)):
    rows = recommendation_repo.list_recent(app_user_id=_user.id)
    return [
        {
            "id": row.id,
            "created_at": row.created_at,
            "symbol": row.symbol,
            "recommendation_id": row.recommendation_id,
            "display_id": display_id_or_fallback(row.display_id, row.recommendation_id),
            "payload": row.payload,
            "market_data_source": (row.payload or {}).get("workflow", {}).get("market_data_source"),
            "fallback_mode": bool((row.payload or {}).get("workflow", {}).get("fallback_mode", False)),
        }
        for row in rows
    ]


@user_router.post("/recommendations/queue")
def ranked_recommendation_queue(req: dict[str, object], _user=Depends(require_approved_user)):
    market_mode = MarketMode(str(req.get("market_mode") or MarketMode.EQUITIES.value))
    symbols = [str(item).upper() for item in (req.get("symbols") or ["AAPL", "MSFT", "NVDA"]) if str(item).strip()]
    timeframe = str(req.get("timeframe") or "1D")
    selected_strategies = [str(item) for item in (req.get("strategies") or []) if str(item).strip()]
    if not selected_strategies:
        selected_strategies = [entry.display_name for entry in list_strategies(market_mode)[:3]]
    bars_by_symbol = {symbol: _workflow_bars(symbol, limit=120) for symbol in symbols}
    ranking = ranking_engine.rank_candidates(
        bars_by_symbol=bars_by_symbol,
        strategies=selected_strategies,
        market_mode=market_mode,
        timeframe=timeframe,
        top_n=int(req.get("top_n") or 10),
    )
    return {
        "market_mode": market_mode.value,
        "timeframe": timeframe,
        "source": "mixed" if len({item["workflow_source"] for item in ranking["queue"]}) > 1 else (ranking["queue"][0]["workflow_source"] if ranking["queue"] else "provider"),
        **ranking,
    }


@user_router.post("/recommendations/queue/promote")
def promote_queue_candidate(req: dict[str, object], _user=Depends(require_approved_user)):
    symbol = str(req.get("symbol") or "").upper()
    strategy = str(req.get("strategy") or "Event Continuation")
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required to promote queue candidate")

    action = str(req.get("action") or "make_active")

    bars, source, fallback_mode = _workflow_bars(symbol)
    event_text = str(req.get("thesis") or f"Queue promotion for {strategy}")
    approval_status = getattr(_user.approval_status, "value", _user.approval_status)
    user_is_approved = str(approval_status) == ApprovalStatus.APPROVED.value
    promote_market_mode = MarketMode(str(req.get("market_mode") or MarketMode.EQUITIES.value))
    rec = recommendation_service.generate(
        symbol=symbol,
        bars=bars,
        event_text=event_text,
        event=None,
        portfolio=PortfolioSnapshot(),
        market_mode=promote_market_mode,
        user_is_approved=user_is_approved,
        app_user_id=_user.id,
        risk_dollars=_effective_risk_dollars(_user),
    )

    ranking_provenance = {
        "action": action,
        "rank": req.get("rank"),
        "symbol": symbol,
        "strategy": strategy,
        "strategy_id": req.get("strategy_id"),
        "strategy_status": req.get("strategy_status") or req.get("status"),
        "timeframe": req.get("timeframe") or "1D",
        "market_mode": req.get("market_mode") or MarketMode.EQUITIES.value,
        "source": req.get("source") or source,
        "workflow_source": req.get("workflow_source") or source,
        "status": req.get("status"),
        "score": req.get("score"),
        "score_breakdown": req.get("score_breakdown") or {},
        "expected_rr": req.get("expected_rr"),
        "confidence": req.get("confidence"),
        "thesis": req.get("thesis") or "",
        "trigger": req.get("trigger") or "",
        "entry_zone": req.get("entry_zone") or {},
        "invalidation": req.get("invalidation") or {},
        "targets": req.get("targets") or [],
        "reason_text": req.get("reason_text") or "",
    }

    recommendation_repo.attach_workflow_metadata(
        rec.recommendation_id,
        market_data_source=source,
        fallback_mode=fallback_mode,
        market_mode=promote_market_mode.value,
        source_strategy=strategy,
    )
    recommendation_repo.attach_ranking_provenance(
        rec.recommendation_id,
        ranking_provenance=ranking_provenance,
    )
    # Pass 4 — refresh display_id now that the friendly strategy name is known
    # (the initial create() defaulted it from setup_type, which is less
    # readable than the promote-time strategy label).
    recommendation_repo.update_display_id_strategy(rec.recommendation_id, strategy=strategy)

    persisted = recommendation_repo.get_by_recommendation_uid(rec.recommendation_id)
    workflow = (persisted.payload or {}).get("workflow", {}) if persisted else {}
    return {
        "id": persisted.id if persisted else None,
        "recommendation_id": rec.recommendation_id,
        "display_id": display_id_or_fallback(persisted.display_id if persisted else None, rec.recommendation_id),
        "symbol": rec.symbol,
        "strategy": strategy,
        "action": action,
        "market_data_source": workflow.get("market_data_source", source),
        "fallback_mode": bool(workflow.get("fallback_mode", fallback_mode)),
        "ranking_provenance": workflow.get("ranking_provenance", ranking_provenance),
        "approved": rec.approved,
    }


@user_router.post("/recommendations/generate")
def generate_recommendations(req: dict[str, object], _user=Depends(require_approved_user)):
    symbol = str(req.get("symbol") or "AAPL").upper()
    event_text = str(req.get("event_text") or "Operator-triggered deterministic refresh run.")
    market_mode = MarketMode(str(req.get("market_mode") or MarketMode.EQUITIES.value))
    strategy = str(req.get("strategy") or "").strip()
    timeframe = str(req.get("timeframe") or "1D")
    workflow_source = str(req.get("workflow_source") or req.get("source") or "")
    approval_status = getattr(_user.approval_status, "value", _user.approval_status)
    user_is_approved = str(approval_status) == ApprovalStatus.APPROVED.value
    bars, source, fallback_mode = _workflow_bars(symbol)
    rec = recommendation_service.generate(
        symbol=symbol,
        bars=bars,
        event_text=event_text,
        event=None,
        portfolio=PortfolioSnapshot(),
        market_mode=market_mode,
        user_is_approved=user_is_approved,
        app_user_id=_user.id,
        risk_dollars=_effective_risk_dollars(_user),
    )
    recommendation_repo.attach_workflow_metadata(
        rec.recommendation_id,
        market_data_source=source,
        fallback_mode=fallback_mode,
        market_mode=market_mode.value,
        source_strategy=strategy,
    )
    recommendation_repo.attach_ranking_provenance(
        rec.recommendation_id,
        ranking_provenance={
            "strategy": strategy or None,
            "market_mode": market_mode.value,
            "timeframe": timeframe,
            "workflow_source": workflow_source or source,
            "source": workflow_source or source,
        },
    )
    return {
        "id": rec.recommendation_id,
        "recommendation_id": rec.recommendation_id,
        "symbol": rec.symbol,
        "approved": rec.approved,
        "outcome": rec.outcome,
        "market_mode": rec.market_mode.value,
        "market_data_source": source,
        "fallback_mode": fallback_mode,
    }


@user_router.get("/recommendations/{recommendation_id}")
def recommendation_detail(recommendation_id: int, _user=Depends(require_approved_user)):
    row = recommendation_repo.get_by_id(recommendation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return {
        "id": row.id,
        "created_at": row.created_at,
        "symbol": row.symbol,
        "recommendation_id": row.recommendation_id,
        "display_id": display_id_or_fallback(row.display_id, row.recommendation_id),
        "payload": row.payload,
        "market_data_source": (row.payload or {}).get("workflow", {}).get("market_data_source"),
        "fallback_mode": bool((row.payload or {}).get("workflow", {}).get("fallback_mode", False)),
    }


@user_router.patch("/recommendations/{recommendation_uid}/approve")
def set_recommendation_approved(recommendation_uid: str, req: dict[str, object], _user=Depends(require_approved_user)):
    approved = bool(req.get("approved", True))
    row = recommendation_repo.set_approved(recommendation_uid, approved=approved)
    if row is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    payload = row.payload or {}
    return {
        "recommendation_id": row.recommendation_id,
        "approved": payload.get("approved"),
        "rejection_reason": payload.get("rejection_reason"),
    }


@user_router.get("/replay-runs")
def replay_runs(_user=Depends(require_approved_user)):
    rows = replay_repo.list_runs(app_user_id=_user.id)
    commission_per_trade = _effective_commission_per_trade(_user)
    output: list[dict[str, object]] = []
    for row in rows:
        source = "workflow_snapshot_unavailable"
        fallback_mode: bool | None = None
        first_step = replay_repo.list_steps_for_run(row.id)[:1]
        if first_step:
            rec = recommendation_repo.get_by_recommendation_uid(first_step[0].recommendation_id)
            workflow = (rec.payload or {}).get("workflow", {}) if rec else {}
            source = str(workflow.get("market_data_source") or source)
            fallback = workflow.get("fallback_mode")
            if fallback is not None:
                fallback_mode = bool(fallback)
        fee_preview = _recommendation_fee_preview_from_uid(
            row.stageable_recommendation_id,
            commission_per_trade=commission_per_trade,
        )
        output.append(
            {
                "id": row.id,
                "symbol": row.symbol,
                "recommendation_id": row.recommendation_id,
                "source_recommendation_id": row.source_recommendation_id,
                "source_strategy": row.source_strategy,
                "source_market_mode": row.source_market_mode,
                "recommendation_count": row.recommendation_count,
                "approved_count": row.approved_count,
                "fill_count": row.fill_count,
                "ending_heat": row.ending_heat,
                "ending_open_notional": row.ending_open_notional,
                "has_stageable_candidate": row.has_stageable_candidate,
                "stageable_recommendation_id": row.stageable_recommendation_id,
                "stageable_reason": row.stageable_reason,
                "created_at": row.created_at,
                "market_data_source": row.source_market_data_source or source,
                "fallback_mode": row.source_fallback_mode if row.source_fallback_mode is not None else fallback_mode,
                **fee_preview,
            }
        )
    return output


@user_router.post("/options/replay-preview", response_model=OptionReplayPreviewResponse)
def options_replay_preview(
    req: OptionReplayPreviewRequest,
    _user=Depends(require_approved_user),
) -> OptionReplayPreviewResponse:
    return build_options_replay_preview(req)


@user_router.post("/options/paper-structures/open", response_model=OptionPaperOpenStructureResponse)
def open_user_option_paper_structure(
    req: OptionPaperStructureInput,
    user=Depends(require_approved_user),
) -> OptionPaperOpenStructureResponse:
    try:
        return open_paper_option_structure(
            app_user_id=user.id,
            structure=req,
            commission_per_contract=_effective_commission_per_contract(user),
            repository=option_paper_repo,
        )
    except OptionPaperContractError as exc:
        raise HTTPException(status_code=409, detail=exc.reason) from exc


@user_router.post(
    "/options/paper-structures/{position_id}/close",
    response_model=OptionPaperCloseStructureResponse,
)
def close_user_option_paper_structure(
    position_id: int,
    req: OptionPaperCloseStructureRequest,
    user=Depends(require_approved_user),
) -> OptionPaperCloseStructureResponse:
    try:
        return close_paper_option_structure(
            app_user_id=user.id,
            position_id=position_id,
            req=req,
            commission_per_contract=_effective_commission_per_contract(user),
            repository=option_paper_repo,
        )
    except OptionPaperCloseError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.reason) from exc


@user_router.get(
    "/options/paper-structures",
    response_model=OptionPaperLifecycleSummaryListResponse,
)
def list_user_option_paper_structures(
    limit: int = 100,
    user=Depends(require_approved_user),
) -> OptionPaperLifecycleSummaryListResponse:
    safe_limit = max(1, min(int(limit), 200))
    return OptionPaperLifecycleSummaryListResponse(
        items=option_paper_repo.list_position_summaries(
            app_user_id=user.id,
            limit=safe_limit,
        )
    )


@user_router.post("/replay-runs")
def run_user_replay(req: dict[str, object], _user=Depends(require_approved_user)):
    guided = bool(req.get("guided"))
    recommendation_id = str(req.get("recommendation_id") or "").strip()
    symbol = str(req.get("symbol") or "").upper()
    market_mode = MarketMode(str(req.get("market_mode") or MarketMode.EQUITIES.value))
    if guided and market_mode != MarketMode.EQUITIES:
        raise HTTPException(status_code=409, detail="Guided mode only supports equities execution-prep. Options/crypto remain research preview only.")
    if guided and not recommendation_id:
        raise HTTPException(status_code=400, detail="Guided replay requires recommendation_id.")
    source_strategy = str(req.get("strategy")).strip() if req.get("strategy") else None
    source_market_mode = market_mode.value
    if recommendation_id:
        rec_row = recommendation_repo.get_by_recommendation_uid(recommendation_id)
        if rec_row is None:
            raise HTTPException(status_code=404, detail="Recommendation not found for replay.")
        symbol = rec_row.symbol
        workflow = (rec_row.payload or {}).get("workflow", {}) if rec_row else {}
        source_strategy = extract_recommendation_strategy(rec_row.payload or {}) or source_strategy
        source_market_mode = str(workflow.get("market_mode") or source_market_mode)
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required when recommendation_id is not provided.")
    event_texts = req.get("event_texts")
    if not isinstance(event_texts, list) or not event_texts:
        if guided:
            event_texts = ["Guided replay validation path from active recommendation lineage."]
        else:
            event_texts = [
                "Operator-triggered replay from recommendation context.",
                "Deterministic follow-through check for replay flow.",
            ]
    bars, source, fallback_mode = _workflow_bars(symbol)
    approval_status = getattr(_user.approval_status, "value", _user.approval_status)
    user_is_approved = str(approval_status) == ApprovalStatus.APPROVED.value
    response = replay_engine.run(
        ReplayRunRequest(
            symbol=symbol,
            market_mode=market_mode,
            event_texts=[str(text) for text in event_texts],
            bars=bars,
            portfolio=PortfolioSnapshot(),
        ),
        app_user_id=_user.id,
        user_is_approved=user_is_approved,
        source_recommendation_id=recommendation_id or None,
        source_strategy=source_strategy,
        source_market_mode=source_market_mode,
        source_market_data_source=source,
        source_fallback_mode=fallback_mode,
    )
    stageable_rec = next((rec for rec in response.recommendations if rec.approved), None)
    fee_preview = _recommendation_fee_preview(
        stageable_rec,
        commission_per_trade=_effective_commission_per_trade(_user),
    )
    for rec in response.recommendations:
        recommendation_repo.attach_workflow_metadata(
            rec.recommendation_id,
            market_data_source=source,
            fallback_mode=fallback_mode,
            market_mode=market_mode.value,
            source_strategy=source_strategy or "",
        )
    latest_run = replay_repo.list_runs(limit=1, app_user_id=_user.id)
    run_id = latest_run[0].id if latest_run else None
    run_row = latest_run[0] if latest_run else None
    key_levels: dict[str, object] = {}
    thesis: str | None = None
    if recommendation_id:
        rec_row = recommendation_repo.get_by_recommendation_uid(recommendation_id)
        payload = (rec_row.payload or {}) if rec_row else {}
        key_levels = extract_recommendation_key_levels(payload)
        thesis = payload.get("thesis") if isinstance(payload.get("thesis"), str) else None
    return {
        "id": run_id,
        "symbol": symbol,
        "recommendation_id": recommendation_id or (run_row.recommendation_id if run_row else None),
        "source_recommendation_id": recommendation_id or (run_row.source_recommendation_id if run_row else None),
        "market_mode": market_mode.value,
        "summary_metrics": response.summary_metrics.model_dump(mode="json"),
        "market_data_source": source,
        "fallback_mode": fallback_mode,
        "strategy": source_strategy,
        "source": source,
        "thesis": thesis,
        "key_levels": key_levels,
        "has_stageable_candidate": bool(run_row.has_stageable_candidate) if run_row else False,
        "stageable_recommendation_id": run_row.stageable_recommendation_id if run_row else None,
        "stageable_reason": run_row.stageable_reason if run_row else None,
        **fee_preview,
    }


@user_router.get("/replay-runs/{run_id}")
def replay_run_detail(run_id: int, _user=Depends(require_approved_user)):
    run = replay_repo.get_run(run_id, app_user_id=_user.id)
    if run is None:
        raise HTTPException(status_code=404, detail="Replay run not found")
    source_rec = recommendation_repo.get_by_recommendation_uid(run.source_recommendation_id) if run.source_recommendation_id else None
    source_payload = (source_rec.payload or {}) if source_rec else {}
    fee_preview = _recommendation_fee_preview_from_uid(
        run.stageable_recommendation_id,
        commission_per_trade=_effective_commission_per_trade(_user),
    )
    return {
        "id": run.id,
        "symbol": run.symbol,
        "source_recommendation_id": run.source_recommendation_id,
        "source_strategy": run.source_strategy,
        "source_market_mode": run.source_market_mode,
        "market_data_source": run.source_market_data_source,
        "fallback_mode": run.source_fallback_mode,
        "summary_metrics": {
            "recommendation_count": run.recommendation_count,
            "approved_count": run.approved_count,
            "fill_count": run.fill_count,
            "ending_heat": run.ending_heat,
            "ending_open_notional": run.ending_open_notional,
        },
        "created_at": run.created_at,
        "thesis": source_payload.get("thesis"),
        "key_levels": extract_recommendation_key_levels(source_payload),
        "has_stageable_candidate": run.has_stageable_candidate,
        "stageable_recommendation_id": run.stageable_recommendation_id,
        "stageable_reason": run.stageable_reason,
        **fee_preview,
    }


@user_router.get("/replay-runs/{run_id}/steps")
def replay_steps(run_id: int, _user=Depends(require_approved_user)):
    run = replay_repo.get_run(run_id, app_user_id=_user.id)
    if run is None:
        raise HTTPException(status_code=404, detail="Replay run not found")
    rows = replay_repo.list_steps_for_run(run_id)
    output = []
    for row in rows:
        rec_row = recommendation_repo.get_by_recommendation_uid(row.recommendation_id)
        payload = (rec_row.payload or {}) if rec_row else {}
        quality = payload.get("quality") if isinstance(payload.get("quality"), dict) else {}
        output.append(
            {
                "id": row.id,
                "step_index": row.step_index,
                "recommendation_id": row.recommendation_id,
                "approved": row.approved,
                "rejection_reason": payload.get("rejection_reason"),
                "thesis": payload.get("thesis"),
                "entry": payload.get("entry"),
                "invalidation": payload.get("invalidation"),
                "targets": payload.get("targets"),
                "quality": quality.get("expected_rr"),
                "confidence": quality.get("confidence"),
                "pre_step_snapshot": row.pre_step_snapshot,
                "post_step_snapshot": row.post_step_snapshot,
            }
        )
    return output


@user_router.get("/orders")
def list_orders(_user=Depends(require_approved_user)):
    commission_per_trade = _effective_commission_per_trade(_user)
    rows = order_repo.list_with_fills(app_user_id=_user.id)
    return [
        {
            **row,
            **_recommendation_fee_preview_from_uid(
                str(row.get("recommendation_id") or "") or None,
                commission_per_trade=commission_per_trade,
            ),
        }
        for row in rows
    ]


@user_router.get("/orders/portfolio-summary")
def paper_portfolio_summary(_user=Depends(require_approved_user)):
    summary = paper_portfolio_repo.summary(app_user_id=_user.id)
    return {
        **summary,
        "lifecycle_status": "active",
        "unrealized_pnl": None,
        "win_rate": summary["win_rate"] if summary["closed_trade_count"] > 0 else None,
    }


@user_router.post("/orders/{order_id}/close")
def close_order(order_id: str, req: dict[str, object], _user=Depends(require_approved_user)):
    close_price_raw = req.get("close_price")
    if close_price_raw is None:
        raise HTTPException(status_code=400, detail="close_price is required.")
    close_price = float(close_price_raw)
    order_row = order_repo.get_by_order_id(order_id, app_user_id=_user.id)
    if order_row is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    if order_row.status == "closed":
        raise HTTPException(status_code=409, detail="Order is already closed.")
    position = paper_portfolio_repo.get_open_position(app_user_id=_user.id, symbol=order_row.symbol)
    now = utc_now()
    avg_entry = position.average_price if position is not None else order_row.limit_price
    quantity = position.quantity if position is not None else float(order_row.shares)
    opened_at = position.opened_at if position is not None else order_row.created_at
    commission_per_trade = _effective_commission_per_trade(_user)
    gross_pnl, net_pnl = _equity_trade_pnl(
        entry_price=float(avg_entry),
        exit_price=float(close_price),
        quantity=float(quantity),
        side=order_row.side,
        commission_per_trade=commission_per_trade,
    )
    paper_portfolio_repo.create_trade(
        app_user_id=_user.id,
        symbol=order_row.symbol,
        side=order_row.side,
        entry_price=avg_entry,
        exit_price=close_price,
        quantity=quantity,
        gross_pnl=gross_pnl,
        net_pnl=net_pnl,
        realized_pnl=net_pnl,
        opened_at=opened_at,
        closed_at=now,
        position_id=position.id if position is not None else None,
        recommendation_id=position.recommendation_id if position is not None else order_row.recommendation_id,
        replay_run_id=position.replay_run_id if position is not None else order_row.replay_run_id,
        order_id=order_row.order_id,
    )
    if position is not None:
        paper_portfolio_repo.close_position(position_id=position.id, closed_at=now)
    order_repo.set_status(order_id, status="closed")
    return {
        "order_id": order_id,
        "symbol": order_row.symbol,
        "gross_pnl": round(gross_pnl, 2),
        "net_pnl": round(net_pnl, 2),
        "commission_paid": round(commission_per_trade, 2),
        "realized_pnl": round(net_pnl, 2),
        "entry_price": round(avg_entry, 2),
        "close_price": round(close_price, 2),
        "shares": int(quantity),
    }


@user_router.get("/orders/portfolio-summary")
def paper_portfolio_summary(_user=Depends(require_approved_user)):
    summary = paper_portfolio_repo.summary(app_user_id=_user.id)
    return {
        **summary,
        "lifecycle_status": "scaffolded",
        "notes": "Position/trade lifecycle accounting endpoints are enabled. Realized P&L remains zero until close-trade lifecycle writes are connected.",
    }


@user_router.post("/orders")
def stage_order(req: dict[str, object], _user=Depends(require_approved_user)):
    guided = bool(req.get("guided"))
    recommendation_id = str(req.get("recommendation_id") or "").strip()
    replay_run_id_raw = req.get("replay_run_id")
    replay_run_id = int(replay_run_id_raw) if isinstance(replay_run_id_raw, int) or (isinstance(replay_run_id_raw, str) and replay_run_id_raw.isdigit()) else None
    rec: TradeRecommendation
    source = "workflow_snapshot_unavailable"
    fallback_mode = False
    symbol = str(req.get("symbol") or "").upper()
    market_mode = MarketMode(str(req.get("market_mode") or MarketMode.EQUITIES.value))
    if guided and market_mode != MarketMode.EQUITIES:
        raise HTTPException(status_code=409, detail="Guided mode only supports equities execution-prep. Options/crypto remain research preview only.")
    if guided and not recommendation_id:
        raise HTTPException(status_code=400, detail="Guided order staging requires recommendation_id.")
    if guided and replay_run_id is None:
        raise HTTPException(status_code=400, detail="Guided order staging requires replay_run_id for auditable lineage.")
    stageable_reason: str | None = None
    if guided and replay_run_id is not None:
        run = replay_repo.get_run(replay_run_id, app_user_id=_user.id)
        if run is None:
            raise HTTPException(status_code=404, detail="Replay run not found for guided order staging.")
        if not run.has_stageable_candidate:
            raise HTTPException(
                status_code=409,
                detail=run.stageable_reason or "No paper order can be staged from this replay.",
            )
        stageable_reason = run.stageable_reason
        if run.stageable_recommendation_id:
            recommendation_id = run.stageable_recommendation_id

    if recommendation_id:
        rec_row = recommendation_repo.get_by_recommendation_uid(recommendation_id)
        if rec_row is None:
            raise HTTPException(status_code=404, detail="Recommendation not found for paper-order staging.")
        rec = TradeRecommendation.model_validate(rec_row.payload or {})
        symbol = rec.symbol
        workflow = (rec_row.payload or {}).get("workflow", {})
        source = str(workflow.get("market_data_source") or source)
        fallback_mode = bool(workflow.get("fallback_mode", False))
    else:
        if not symbol:
            raise HTTPException(status_code=400, detail="symbol is required when recommendation_id is not provided.")
        bars, source, fallback_mode = _workflow_bars(symbol)
        rec = recommendation_service.generate(
            symbol=symbol,
            bars=bars,
            event_text="Operator staged deterministic paper order from recommendations workflow.",
            event=None,
            portfolio=PortfolioSnapshot(),
            app_user_id=_user.id,
            risk_dollars=_effective_risk_dollars(_user),
        )

    if not rec.approved:
        raise HTTPException(status_code=409, detail=rec.rejection_reason or "Recommendation was no-trade; order not staged.")
    intent = recommendation_service.to_order_intent(rec)
    order, fill = paper_broker.execute(intent)
    recommendation_service.persist_order(
        order,
        notes=f"operator_staged_order|source={source}|fallback={str(fallback_mode).lower()}|replay_run_id={replay_run_id or ''}|stageable_reason={stageable_reason or ''}",
        app_user_id=_user.id,
    )
    recommendation_service.persist_fill(fill)
    fee_preview = _recommendation_fee_preview(
        rec,
        commission_per_trade=_effective_commission_per_trade(_user),
    )
    # Auto-create / aggregate paper_positions on fill (equities only — Phase 1 scope).
    # Use the actual fill price/shares so weighted-average entry tracks broker reality.
    if market_mode == MarketMode.EQUITIES and fill.filled_shares > 0:
        paper_portfolio_repo.upsert_position_on_fill(
            app_user_id=_user.id,
            symbol=order.symbol,
            side=order.side.value,
            fill_qty=float(fill.filled_shares),
            fill_price=float(fill.fill_price),
            recommendation_id=rec.recommendation_id,
            replay_run_id=replay_run_id,
            order_id=order.order_id,
        )
    return {
        "order_id": order.order_id,
        "recommendation_id": rec.recommendation_id,
        "replay_run_id": replay_run_id,
        "symbol": order.symbol,
        "side": order.side.value,
        "shares": order.shares,
        "limit_price": order.limit_price,
        "status": order.status.value,
        "source": source,
        "market_data_source": source,
        "fallback_mode": fallback_mode,
        **fee_preview,
    }


def _serialize_position(row, *, commission_per_trade: float) -> dict[str, object]:
    return {
        "id": row.id,
        "symbol": row.symbol,
        "side": row.side,
        "opened_qty": float(row.opened_qty if row.opened_qty is not None else row.quantity),
        "remaining_qty": float(row.remaining_qty if row.remaining_qty is not None else row.quantity),
        "avg_entry_price": float(row.average_price),
        "open_notional": float(row.open_notional),
        "status": row.status,
        "opened_at": row.opened_at.isoformat() if row.opened_at else None,
        "closed_at": row.closed_at.isoformat() if row.closed_at else None,
        "recommendation_id": row.recommendation_id,
        "replay_run_id": row.replay_run_id,
        "order_id": row.order_id,
        **_position_close_fee_preview(commission_per_trade=commission_per_trade),
    }


def _serialize_trade(row) -> dict[str, object]:
    gross_pnl = gross_pnl_or_fallback(row)
    net_pnl = net_pnl_or_fallback(row)
    commission_paid = commission_paid_for_trade(row)
    return {
        "id": row.id,
        "symbol": row.symbol,
        "side": row.side,
        "qty": float(row.quantity),
        "entry_price": float(row.entry_price),
        "exit_price": float(row.exit_price) if row.exit_price is not None else None,
        "gross_pnl": gross_pnl,
        "net_pnl": net_pnl,
        "commission_paid": commission_paid,
        "realized_pnl": net_pnl,
        "opened_at": row.opened_at.isoformat() if row.opened_at else None,
        "closed_at": row.closed_at.isoformat() if row.closed_at else None,
        "hold_seconds": row.hold_seconds,
        "position_id": row.position_id,
        "recommendation_id": row.recommendation_id,
        "replay_run_id": row.replay_run_id,
        "order_id": row.order_id,
        "close_reason": row.close_reason,
    }


@user_router.get("/paper-positions")
def list_paper_positions(
    status: str = "open",
    limit: int = 50,
    _user=Depends(require_approved_user),
):
    if status not in {"open", "closed", "all"}:
        raise HTTPException(status_code=400, detail="status must be one of: open, closed, all.")
    rows = paper_portfolio_repo.list_positions(app_user_id=_user.id, status=status, limit=limit)
    commission_per_trade = _effective_commission_per_trade(_user)
    return [_serialize_position(row, commission_per_trade=commission_per_trade) for row in rows]


@user_router.get("/paper-trades")
def list_paper_trades(limit: int = 50, _user=Depends(require_approved_user)):
    rows = paper_portfolio_repo.list_trades(app_user_id=_user.id, limit=limit)
    return [_serialize_trade(row) for row in rows]


@user_router.post("/paper-positions/{position_id}/close")
def close_paper_position(position_id: int, req: dict[str, object], _user=Depends(require_approved_user)):
    mark_price_raw = req.get("mark_price")
    if mark_price_raw is None:
        raise HTTPException(status_code=400, detail="mark_price is required.")
    try:
        mark_price = float(mark_price_raw)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="mark_price must be numeric.")
    reason = str(req.get("reason") or "").strip() or None

    position = paper_portfolio_repo.get_position_by_id(position_id=position_id)
    if position is None or position.app_user_id != _user.id:
        # Conceal existence from non-owners with 404, matching scope-isolation pattern elsewhere.
        raise HTTPException(status_code=404, detail="Position not found.")
    if position.status == "closed":
        raise HTTPException(status_code=400, detail="Position is already closed.")

    remaining = float(position.remaining_qty if position.remaining_qty is not None else position.quantity)
    avg_entry = float(position.average_price)
    commission_per_trade = _effective_commission_per_trade(_user)
    gross_pnl, net_pnl = _equity_trade_pnl(
        entry_price=avg_entry,
        exit_price=mark_price,
        quantity=remaining,
        side=position.side,
        commission_per_trade=commission_per_trade,
    )

    now = utc_now()
    opened_at = position.opened_at
    hold_seconds: int | None = None
    if opened_at is not None:
        # SQLite may round-trip naive datetimes; normalize to UTC-aware before subtracting.
        opened_aware = opened_at if opened_at.tzinfo is not None else opened_at.replace(tzinfo=timezone.utc)
        hold_seconds = int(max(0.0, (now - opened_aware).total_seconds()))

    trade = paper_portfolio_repo.create_trade(
        app_user_id=_user.id,
        symbol=position.symbol,
        side=position.side,
        entry_price=avg_entry,
        exit_price=mark_price,
        quantity=remaining,
        gross_pnl=gross_pnl,
        net_pnl=net_pnl,
        realized_pnl=net_pnl,
        opened_at=opened_at or now,
        closed_at=now,
        position_id=position.id,
        hold_seconds=hold_seconds,
        recommendation_id=position.recommendation_id,
        replay_run_id=position.replay_run_id,
        order_id=position.order_id,
        close_reason=reason,
    )
    paper_portfolio_repo.close_position(position_id=position.id, closed_at=now)
    return _serialize_trade(trade)


@user_router.post("/orders/{order_id}/cancel")
def cancel_order(order_id: str, _user=Depends(require_approved_user)):
    """Cancel a staged paper order. Allowed only when status == 'staged' and
    no fills exist. 404 for non-owners (matches the scope-isolation pattern)."""
    order = order_repo.get_by_order_id(order_id, app_user_id=_user.id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    if order.status != "staged":
        raise HTTPException(
            status_code=409,
            detail=f"Order is not staged (current status: {order.status}); only staged orders can be canceled.",
        )
    if order_repo.has_fills(order.order_id):
        raise HTTPException(
            status_code=409,
            detail="Order has fills; canceled is not permitted on filled orders.",
        )
    now = utc_now()
    updated = order_repo.cancel(order.order_id, canceled_at=now)
    _record_audit_event(
        recommendation_id=order.recommendation_id or "",
        payload={
            "event": "order_canceled",
            "order_id": order.order_id,
            "recommendation_id": order.recommendation_id,
            "replay_run_id": order.replay_run_id,
            "app_user_id": _user.id,
            "canceled_at": now.isoformat(),
        },
    )
    return {
        "order_id": updated.order_id,
        "recommendation_id": updated.recommendation_id,
        "replay_run_id": updated.replay_run_id,
        "symbol": updated.symbol,
        "status": updated.status,
        "side": updated.side,
        "shares": updated.shares,
        "limit_price": updated.limit_price,
        "created_at": updated.created_at.isoformat() if updated.created_at else None,
        "canceled_at": updated.canceled_at.isoformat() if updated.canceled_at else None,
    }


# Reopen-window: a closed trade can be undone within REOPEN_WINDOW_SECONDS of
# its closed_at timestamp. Beyond that the realized PnL is treated as final.
REOPEN_WINDOW_SECONDS = 5 * 60


@user_router.post("/paper-trades/{trade_id}/reopen")
def reopen_paper_trade(trade_id: int, _user=Depends(require_approved_user)):
    """Undo a recent paper close. Restores the parent position to status='open'
    with remaining_qty = trade.qty, deletes the paper_trades row, and writes
    an audit_log entry capturing the original closed_at + realized_pnl."""
    trade = paper_portfolio_repo.get_trade_by_id(trade_id=trade_id)
    if trade is None or trade.app_user_id != _user.id:
        raise HTTPException(status_code=404, detail="Trade not found.")
    if trade.closed_at is None:
        raise HTTPException(status_code=409, detail="Trade has no closed_at timestamp; cannot reopen.")

    now = utc_now()
    closed_aware = trade.closed_at if trade.closed_at.tzinfo is not None else trade.closed_at.replace(tzinfo=timezone.utc)
    elapsed_seconds = (now - closed_aware).total_seconds()
    if elapsed_seconds > REOPEN_WINDOW_SECONDS:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Reopen window has expired (closed {int(elapsed_seconds)}s ago, "
                f"limit {REOPEN_WINDOW_SECONDS}s)."
            ),
        )

    if trade.position_id is None:
        raise HTTPException(status_code=409, detail="Trade has no parent position to reopen.")
    position = paper_portfolio_repo.get_position_by_id(position_id=trade.position_id)
    if position is None or position.app_user_id != _user.id:
        raise HTTPException(status_code=404, detail="Parent position not found.")
    if position.status != "closed":
        raise HTTPException(
            status_code=409,
            detail=f"Position is not closed (current status: {position.status}); cannot reopen.",
        )

    original_closed_at = trade.closed_at.isoformat() if trade.closed_at else None
    original_realized_pnl = float(trade.realized_pnl)
    qty = float(trade.quantity)

    updated = paper_portfolio_repo.reopen_position(position_id=position.id, qty=qty)
    paper_portfolio_repo.delete_trade(trade_id=trade.id)

    _record_audit_event(
        recommendation_id=position.recommendation_id or "",
        payload={
            "event": "position_reopened",
            "position_id": position.id,
            "trade_id": trade.id,
            "original_closed_at": original_closed_at,
            "original_realized_pnl": original_realized_pnl,
            "app_user_id": _user.id,
            "reopened_at": now.isoformat(),
        },
    )

    if updated is None:
        # Should not happen — reopen_position only returns None if the row was
        # deleted concurrently. Surface as 500 so the operator retries.
        raise HTTPException(status_code=500, detail="Position vanished during reopen.")
    return _serialize_position(
        updated,
        commission_per_trade=_effective_commission_per_trade(_user),
    )


@user_router.get("/analysis/setup")
def analysis_setup(
    req_symbol: str = "AAPL",
    strategy: str | None = None,
    timeframe: str = "1D",
    market_mode: MarketMode = MarketMode.EQUITIES,
    _user=Depends(require_approved_user),
):
    symbol = req_symbol.upper()
    strategies = list_strategies(market_mode)
    strategy_supplied = strategy is not None and strategy.strip() != ""
    if strategy_supplied:
        strategy_entry = get_strategy_by_display_name(str(strategy), market_mode=market_mode)
        if strategy_entry is None:
            supported = [entry.display_name for entry in strategies]
            raise HTTPException(
                status_code=400,
                detail={
                    "error": f"Unsupported strategy '{strategy}' for market_mode '{market_mode.value}'.",
                    "supported_strategies": supported,
                },
            )
    else:
        strategy_entry = strategies[0] if strategies else None
    if strategy_entry is None:
        raise HTTPException(status_code=400, detail="No strategies configured for selected market mode")

    bars, source, fallback_mode = _workflow_bars(symbol, limit=120)

    latest = bars[-1]
    prior = bars[-2] if len(bars) > 1 else bars[-1]

    # ── Strategy-specific level computation for equities ─────────────────────
    # Levels vary meaningfully by strategy so changing strategy on the same
    # symbol updates the workbench display with a different plan.
    sid = strategy_entry.strategy_id

    if sid == "breakout_prior_day_high":
        # Entry cluster at prior-day high; target is range extension above breakout
        prior_range = round(prior.high - prior.low, 2)
        entry_low = round(prior.high * 0.999, 2)
        entry_high = round(prior.high * 1.003, 2)
        invalidation_price = round(prior.high - prior_range * 0.5, 2)
        targets = [round(prior.high + prior_range, 2), round(prior.high + prior_range * 1.8, 2)]
        trigger = "Break and close above prior-day high with RVOL >= 1.5"
        confidence = 0.69
        active_reason = "Price closing above prior-day high confirms breakout readiness" if latest.close > prior.high else "Price below prior-day high — breakout not confirmed"

    elif sid == "pullback_trend_continuation":
        # Entry near multi-day support zone; tighter stop below recent low
        recent_low = round(min(b.low for b in bars[-7:]), 2)
        atr_proxy = round(sum(b.high - b.low for b in bars[-14:]) / 14, 2)
        entry_low = round(recent_low * 1.002, 2)
        entry_high = round(recent_low * 1.008, 2)
        invalidation_price = round(recent_low - atr_proxy * 0.5, 2)
        targets = [round(latest.close * 1.015, 2), round(latest.close * 1.03, 2)]
        trigger = "Pullback to support with volume declining, then RVOL recovery >= 1.2"
        confidence = 0.66
        active_reason = "Price holding above recent support zone" if latest.close > recent_low * 1.005 else "Price testing support — wait for stabilization"

    elif sid == "gap_follow_through":
        # Entry based on gap from prior close; stop below gap fill level
        gap_pct = (latest.open - prior.close) / prior.close if prior.close > 0 else 0
        is_gap_up = gap_pct > 0.005
        if is_gap_up:
            entry_low = round(latest.open * 0.998, 2)
            entry_high = round(latest.open * 1.004, 2)
            invalidation_price = round(prior.close * 0.998, 2)
            targets = [round(latest.close * 1.025, 2), round(latest.close * 1.05, 2)]
            trigger = "Gap acceptance in first 30 min; no fill of gap; RVOL >= 1.6"
            confidence = 0.62
        else:
            entry_low = round(latest.close * 0.994, 2)
            entry_high = round(latest.close * 1.002, 2)
            invalidation_price = round(latest.low * 0.997, 2)
            targets = [round(latest.close * 1.02, 2), round(latest.close * 1.04, 2)]
            trigger = "No meaningful gap; wait for intraday breakout with RVOL >= 1.4"
            confidence = 0.55
        active_reason = "Gap-up structure present — continuation bias" if is_gap_up else "Flat open — standard continuation conditions apply"

    elif sid == "mean_reversion":
        # Counter-trend entry near extended low; target closer to recent mean
        recent_avg = round(sum(b.close for b in bars[-10:]) / 10, 2)
        entry_low = round(latest.close * 0.978, 2)
        entry_high = round(latest.close * 0.990, 2)
        invalidation_price = round(latest.low * 0.992, 2)
        targets = [round(recent_avg, 2), round(recent_avg * 1.01, 2)]
        trigger = "Close below lower Bollinger band with RSI < 30 and RVOL spike >= 1.8"
        confidence = 0.55
        active_reason = "Extended below 10-day average — mean reversion setup window active" if latest.close < recent_avg * 0.98 else "Price near mean — wait for further extension"

    elif sid == "haco_context":
        # Near-VWAP entry based on HACO signal alignment
        entry_low = round(latest.close * 0.997, 2)
        entry_high = round(latest.close * 1.003, 2)
        invalidation_price = round(prior.low * 0.994, 2)
        targets = [round(latest.close * 1.018, 2), round(latest.close * 1.035, 2)]
        trigger = "HACO bullish flip with HACOLT uptrend; enter near session VWAP"
        confidence = 0.67
        active_reason = "HACO trend context favorable" if latest.close >= prior.close else "HACO context — confirm flip before entry"

    else:
        # Default: Event Continuation and any unrecognized equities strategy
        entry_low = round(latest.close * 1.001, 2)
        entry_high = round(latest.close * 1.007, 2)
        invalidation_price = round(prior.low * 0.995, 2)
        targets = [round(latest.close * 1.025, 2), round(latest.close * 1.05, 2)]
        trigger = "Hold above prior day high with RVOL >= 1.3 and catalyst still active"
        confidence = 0.71
        active_reason = "Post-catalyst continuation setup active" if latest.close >= prior.close else "Catalyst momentum not yet confirmed"

    payload = {
        "symbol": symbol,
        "market_mode": market_mode.value,
        "timeframe": timeframe,
        "strategy": strategy_entry.display_name,
        "strategy_metadata": strategy_entry.model_dump(mode="json"),
        "workflow_source": f"fallback ({source})" if fallback_mode else source,
        "active": latest.close >= prior.close,
        "active_reason": active_reason,
        "trigger": trigger,
        "entry_zone": {"low": entry_low, "high": entry_high},
        "invalidation": {"price": invalidation_price, "reason": "Loss of prior session support"},
        "targets": targets,
        "confidence": confidence,
        "filters": ["breadth_supportive", "liquidity_ok", "volatility_moderate"],
    }

    # Equities expected range: equity_realized_vol_1sigma from bar history
    if market_mode == MarketMode.EQUITIES:
        payload["expected_range"] = _build_equity_expected_range(bars, horizon_trading_days=5).model_dump(mode="json")

    if market_mode == MarketMode.OPTIONS:
        payload["operator_disclaimer"] = "Options research — paper only. Not execution support."
        payload["options_chain_preview"] = market_data_service.options_chain_preview(symbol=symbol)
    elif market_mode == MarketMode.CRYPTO:
        payload["operator_disclaimer"] = "Crypto research — paper only. Not execution support."

    if market_mode == MarketMode.OPTIONS and strategy_entry.strategy_id == "iron_condor":
        # Use a low IV for LOWIV test symbol to exercise the IV quality gate
        iv_snapshot = 0.05 if symbol.upper().startswith("LOW") else 0.24
        short_put = round(latest.close * 0.955, 2)
        long_put = round(latest.close * 0.930, 2)
        short_call = round(latest.close * 1.045, 2)
        long_call = round(latest.close * 1.070, 2)
        net_credit = round(latest.close * 0.0067, 2)
        width = round(short_put - long_put, 2)
        option_structure = {
            "type": "iron_condor",
            "expiration": "2026-05-16",
            "legs": [
                {"action": "buy", "right": "put", "strike": long_put, "label": "lower long put"},
                {"action": "sell", "right": "put", "strike": short_put, "label": "short put"},
                {"action": "sell", "right": "call", "strike": short_call, "label": "short call"},
                {"action": "buy", "right": "call", "strike": long_call, "label": "higher long call"},
            ],
            "net_credit": net_credit,
            "max_profit": round(net_credit * 100, 2),
            "max_loss": round((width - net_credit) * 100, 2),
            "breakeven_low": round(short_put - net_credit, 2),
            "breakeven_high": round(short_call + net_credit, 2),
            "dte": 33,
            "iv_snapshot": iv_snapshot,
            "theta_context": 0.07,
            "vega_context": -0.11,
            "event_blockers": ["Avoid binary events inside 7 DTE window", "Review earnings/macro event calendar"],
        }
        payload["option_structure"] = option_structure
        payload["expected_range"] = _build_options_expected_range(
            latest_close=latest.close,
            iv_snapshot=iv_snapshot,
            dte=option_structure["dte"],
        ).model_dump(mode="json")
    elif market_mode == MarketMode.OPTIONS and strategy_entry.strategy_id == "bull_call_debit_spread":
        iv_snapshot = 0.25
        long_call = round(latest.close * 1.02, 2)
        short_call = round(latest.close * 1.06, 2)
        debit = round(latest.close * 0.012, 2)
        width = round(short_call - long_call, 2)
        option_structure = {
            "type": "bull_call_debit_spread",
            "expiration": "2026-05-16",
            "legs": [
                {"action": "buy", "right": "call", "strike": long_call, "label": "long call"},
                {"action": "sell", "right": "call", "strike": short_call, "label": "short call"},
            ],
            "net_debit": debit,
            "max_profit": round((width - debit) * 100, 2),
            "max_loss": round(debit * 100, 2),
            "breakeven_high": round(long_call + debit, 2),
            "dte": 33,
            "iv_snapshot": iv_snapshot,
        }
        payload["option_structure"] = option_structure
        payload["expected_range"] = _build_options_expected_range(
            latest_close=latest.close,
            iv_snapshot=iv_snapshot,
            dte=option_structure["dte"],
        ).model_dump(mode="json")
    elif market_mode == MarketMode.OPTIONS and strategy_entry.strategy_id == "bear_put_debit_spread":
        iv_snapshot = 0.25
        long_put = round(latest.close * 0.98, 2)
        short_put = round(latest.close * 0.94, 2)
        debit = round(latest.close * 0.012, 2)
        width = round(long_put - short_put, 2)
        option_structure = {
            "type": "bear_put_debit_spread",
            "expiration": "2026-05-16",
            "legs": [
                {"action": "buy", "right": "put", "strike": long_put, "label": "long put"},
                {"action": "sell", "right": "put", "strike": short_put, "label": "short put"},
            ],
            "net_debit": debit,
            "max_profit": round((width - debit) * 100, 2),
            "max_loss": round(debit * 100, 2),
            "breakeven_low": round(long_put - debit, 2),
            "dte": 33,
            "iv_snapshot": iv_snapshot,
        }
        payload["option_structure"] = option_structure
        payload["expected_range"] = _build_options_expected_range(
            latest_close=latest.close,
            iv_snapshot=iv_snapshot,
            dte=option_structure["dte"],
        ).model_dump(mode="json")
    elif market_mode == MarketMode.OPTIONS:
        # Covered Call requires inventory modeling — expected range omitted pending that data
        payload["expected_range"] = ExpectedRange(
            status="omitted",
            reason="strategy_not_configured_for_expected_range_preview",
            horizon_value=30,
            horizon_unit="calendar_days",
            reference_price_type="underlying_last",
            snapshot_timestamp=utc_now(),
            provenance_notes="Expected range for this strategy requires inventory and assignment context not yet wired.",
        ).model_dump(mode="json")
    if market_mode == MarketMode.CRYPTO:
        payload["crypto_context"] = {
            "venue": "spot",
            "quote_currency": "USD",
            "mark_price": round(latest.close, 2),
            "index_price": round(latest.close * 0.998, 2),
            "funding_rate": "unavailable",
            "basis": "unavailable",
            "open_interest": "unavailable",
            "liquidation_buffer_pct": 6.5,
        }
    return payload


@user_router.get("/analyze/{symbol}")
def analyze_symbol(symbol: str, market_mode: MarketMode = MarketMode.EQUITIES, _user=Depends(require_approved_user)):
    bars, source, fallback_mode = _workflow_bars(symbol.upper(), limit=120)
    latest = bars[-1]
    low20 = min(item.low for item in bars[-20:])
    high20 = max(item.high for item in bars[-20:])
    avg_volume = sum(item.volume for item in bars[-20:]) / min(len(bars), 20)
    ranking = ranking_engine.rank_candidates(
        bars_by_symbol={symbol.upper(): (bars, source, fallback_mode)},
        strategies=[entry.display_name for entry in list_strategies(market_mode)[:4]],
        market_mode=market_mode,
        timeframe="1D",
        top_n=5,
    )
    return {
        "symbol": symbol.upper(),
        "market_mode": market_mode.value,
        "timeframe": "1D",
        "source": f"fallback ({source})" if fallback_mode else source,
        "market_regime": "trend" if latest.close >= bars[-5].close else "chop",
        "technical_summary": f"Close {latest.close:.2f}, 20D range {low20:.2f}-{high20:.2f}",
        "strategy_scoreboard": ranking["queue"][:6],
        "levels": {
            "support": [round(low20, 2), round(min(item.low for item in bars[-5:]), 2)],
            "resistance": [round(high20, 2), round(max(item.high for item in bars[-5:]), 2)],
            "pivot": round((latest.high + latest.low + latest.close) / 3, 2),
        },
        "indicator_snapshot": {
            "ema20_vs_price": "above" if latest.close >= sum(item.close for item in bars[-20:]) / 20 else "below",
            "rsi": 58.2,
            "macd": 0.44,
            "atr": round(sum(item.high - item.low for item in bars[-14:]) / min(len(bars), 14), 2),
            "relative_volume": round(latest.volume / max(avg_volume, 1), 2),
        },
        "catalyst_summary": "No live catalyst provider configured; operator should annotate scheduled catalyst events.",
        "scenarios": {
            "bull": "Acceptance above prior day high with rising RVOL opens continuation targets.",
            "base": "Range-bound trade between opening range and recent pivot; prioritize selective entries.",
            "bear": "Failure below support invalidates continuation thesis and flips to defensive posture.",
        },
        "operator_note": "Focus on trigger quality, then promote qualified setup to Recommendations for execution prep.",
        "next_actions": [
            {"label": "Open full workbench", "path": f"/analysis?symbol={symbol.upper()}"},
            {"label": "Seed recommendation queue", "path": f"/recommendations?symbol={symbol.upper()}"},
            {"label": "Create schedule from symbol", "path": f"/schedules?symbols={symbol.upper()}&name={symbol.upper()}%20Morning%20scan"},
        ],
        "status": "live" if market_mode == MarketMode.EQUITIES else "planned_research_preview",
        "execution_enabled": market_mode == MarketMode.EQUITIES,
    }


@user_router.get("/watchlists")
def list_watchlists(user=Depends(require_approved_user)):
    rows = watchlist_repo.list_for_user(user.id)
    return [{"id": row.id, "name": row.name, "symbols": row.symbols, "created_at": row.created_at} for row in rows]


@user_router.post("/watchlists")
def create_or_update_watchlist(req: dict[str, object], user=Depends(require_approved_user)):
    name = str(req.get("name") or "Core watchlist").strip()
    symbols = [str(item).upper() for item in (req.get("symbols") or []) if str(item).strip()]
    if not symbols:
        raise HTTPException(status_code=400, detail="watchlist requires symbols")
    row = watchlist_repo.upsert(app_user_id=user.id, name=name, symbols=symbols)
    return {"id": row.id, "name": row.name, "symbols": row.symbols}


@user_router.put("/watchlists/{watchlist_id}")
def update_watchlist(watchlist_id: int, req: dict[str, object], user=Depends(require_approved_user)):
    name_raw = req.get("name")
    name = str(name_raw).strip() if name_raw is not None else None
    symbols_raw = req.get("symbols")
    symbols: list[str] | None = None
    if symbols_raw is not None:
        symbols = [str(item).upper() for item in symbols_raw if str(item).strip()]
        if not symbols:
            raise HTTPException(status_code=400, detail="watchlist requires symbols")
    row = watchlist_repo.update(watchlist_id=watchlist_id, app_user_id=user.id, name=name, symbols=symbols)
    if row is None:
        raise HTTPException(status_code=404, detail="watchlist not found")
    return {"id": row.id, "name": row.name, "symbols": row.symbols}


@user_router.delete("/watchlists/{watchlist_id}")
def delete_watchlist(watchlist_id: int, user=Depends(require_approved_user)):
    deleted = watchlist_repo.delete(watchlist_id=watchlist_id, app_user_id=user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="watchlist not found")
    return {"deleted": True}


@user_router.get("/strategy-registry")
def strategy_registry(market_mode: MarketMode | None = None, _user=Depends(require_approved_user)):
    return [entry.model_dump(mode="json") for entry in list_strategies(market_mode)]


@user_router.get("/strategy-schedules")
def list_strategy_schedules(user=Depends(require_approved_user)):
    schedules = strategy_report_repo.list_schedules_for_user(user.id)
    output = []
    for row in schedules:
        runs = strategy_report_repo.list_runs(schedule_id=row.id, limit=5)
        latest_payload_summary = None
        if runs and runs[0].payload:
            summary = (runs[0].payload or {}).get("summary") or {}
            latest_payload_summary = {
                "top_candidate_count": summary.get("top_candidate_count", 0),
                "watchlist_count": summary.get("watchlist_count", 0),
                "no_trade_count": summary.get("no_trade_count", 0),
            }
        output.append(
            {
                "id": row.id,
                "name": row.name,
                "frequency": row.frequency,
                "run_time": row.run_time,
                "timezone": row.timezone,
                "enabled": row.enabled,
                "email_target": row.email_target,
                "latest_status": row.latest_status,
                "latest_run_at": row.latest_run_at,
                "next_run_at": row.next_run_at,
                "payload": row.payload,
                "config_summary": {
                    "market_mode": (row.payload or {}).get("market_mode", "equities"),
                    "symbols_count": len((row.payload or {}).get("symbols") or []),
                    "strategy_count": len((row.payload or {}).get("enabled_strategies") or []),
                    "top_n": (row.payload or {}).get("top_n", 5),
                    "delivery_target": (row.payload or {}).get("email_delivery_target") or row.email_target,
                },
                "latest_payload_summary": latest_payload_summary,
                "history": [
                    {
                        "id": run.id,
                        "status": run.status,
                        "delivered_to": run.delivered_to,
                        "created_at": run.created_at,
                        "email_provider": (run.payload or {}).get("email_provider", "console"),
                        "summary": (run.payload or {}).get("summary"),
                    }
                    for run in runs
                ],
            }
        )
    return output


@user_router.post("/strategy-schedules")
def create_strategy_schedule(req: dict[str, object], user=Depends(require_approved_user)):
    frequency = str(req.get("frequency") or "weekdays")
    run_time = str(req.get("run_time") or "08:30")
    timezone_name = str(req.get("timezone") or "America/New_York")
    now = datetime.now(timezone.utc)
    next_run = strategy_report_service._next_run_at(now=now, frequency=frequency, run_time=run_time, timezone_name=timezone_name)
    market_mode = MarketMode(str(req.get("market_mode") or MarketMode.EQUITIES.value))
    default_strategies = [entry.display_name for entry in list_strategies(market_mode)[:3]]
    payload = {
        "market_mode": market_mode.value,
        "enabled_strategies": req.get("enabled_strategies") or default_strategies,
        "symbols": req.get("symbols") or ["AAPL", "MSFT", "NVDA"],
        "ranking_preferences": req.get("ranking_preferences") or ["strategy_fit", "expected_rr", "liquidity"],
        "top_n": int(req.get("top_n") or 5),
        "email_delivery_target": str(req.get("email_delivery_target") or user.email),
    }
    row = strategy_report_repo.create_schedule(
        app_user_id=user.id,
        name=str(req.get("name") or "Morning strategy scan"),
        frequency=frequency,
        run_time=run_time,
        timezone_name=timezone_name,
        email_target=payload["email_delivery_target"],
        enabled=bool(req.get("enabled", True)),
        next_run_at=next_run,
        payload=payload,
    )
    return {"id": row.id, "name": row.name, "next_run_at": row.next_run_at, "enabled": row.enabled}


@user_router.put("/strategy-schedules/{schedule_id}")
def update_strategy_schedule(schedule_id: int, req: dict[str, object], user=Depends(require_approved_user)):
    updates: dict[str, object] = {}
    for key in ["name", "frequency", "run_time", "timezone", "email_target", "enabled", "payload"]:
        if key in req:
            updates[key] = req[key]
    row = strategy_report_repo.update_schedule(schedule_id, app_user_id=user.id, updates=updates)
    if row is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"id": row.id, "enabled": row.enabled, "latest_status": row.latest_status}


@user_router.post("/strategy-schedules/{schedule_id}/run")
def run_strategy_schedule(schedule_id: int, _user=Depends(require_approved_user)):
    try:
        payload = strategy_report_service.run_schedule(schedule_id, trigger="run_now")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return payload


@user_router.get("/strategy-schedules/{schedule_id}/runs/{run_id}")
def get_strategy_schedule_run(schedule_id: int, run_id: int, user=Depends(require_approved_user)):
    schedule = strategy_report_repo.get_schedule(schedule_id)
    if schedule is None or schedule.app_user_id != user.id:
        raise HTTPException(status_code=404, detail="Schedule not found")
    run = strategy_report_repo.get_run(run_id=run_id, schedule_id=schedule_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    p = run.payload or {}
    return {
        "id": run.id,
        "schedule_id": run.schedule_id,
        "status": run.status,
        "delivered_to": run.delivered_to,
        "created_at": run.created_at,
        "trigger": p.get("trigger"),
        "ran_at": p.get("ran_at"),
        "source": p.get("source"),
        "top_candidates": p.get("top_candidates", []),
        "watchlist_only": p.get("watchlist_only", []),
        "no_trade": p.get("no_trade", []),
        "summary": p.get("summary", {}),
    }


@router.get("/users/pending")
def pending_users(_admin=Depends(require_admin)):
    users = user_repo.list_by_status(ApprovalStatus.PENDING)
    return [{"id": u.id, "email": u.email, "display_name": u.display_name} for u in users]


@router.get("/users")
def list_users(_admin=Depends(require_admin)):
    users = user_repo.list_recent_users(limit=500)
    invites = invite_repo.list_recent(limit=500)
    invite_by_email = {item.email.strip().lower(): item for item in invites}
    return [
        {
            "id": user.id,
            "display_name": _safe_identity_value(user.display_name) or "-",
            "email": _safe_identity_value(user.email) or "(identity pending)",
            "app_role": user.app_role,
            "approval_status": user.approval_status,
            "mfa_enabled": user.mfa_enabled,
            "external_auth_user_id": user.external_auth_user_id,
            "identity_warning": "placeholder identity" if _safe_identity_value(user.email) is None else None,
            "invite_status": invite_by_email.get(user.email.strip().lower()).status if invite_by_email.get(user.email.strip().lower()) else None,
            "last_seen_at": user.last_seen_at.isoformat() if user.last_seen_at else None,
            "last_authenticated_at": user.last_authenticated_at.isoformat() if user.last_authenticated_at else None,
        }
        for user in users
    ]


@router.delete("/users/{user_id}")
def delete_user(user_id: int, admin=Depends(require_admin)):
    if user_id == admin.id:
        raise HTTPException(status_code=409, detail="Cannot delete your own account")
    deleted = user_repo.delete_user(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return {"deleted": True, "user_id": user_id}


@router.post("/users/{user_id}/force-password-reset")
def force_password_reset(user_id: int, admin=Depends(require_admin)):
    if user_id == admin.id:
        raise HTTPException(status_code=409, detail="Cannot force re-login on your own account")
    target = user_repo.get_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    clerk_id = target.external_auth_user_id or ""
    if not clerk_id or clerk_id.startswith("invited::") or clerk_id.startswith("retired::"):
        raise HTTPException(status_code=409, detail="User does not have an active Clerk identity — cannot invalidate sessions")
    if not settings.clerk_secret_key:
        raise HTTPException(status_code=409, detail="CLERK_SECRET_KEY not configured")
    try:
        import httpx
        resp = httpx.delete(
            f"{settings.clerk_api_base_url}/v1/users/{clerk_id}/sessions",
            headers={"Authorization": f"Bearer {settings.clerk_secret_key}"},
            timeout=10.0,
        )
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("Clerk session invalidation failed for user %s: %s", user_id, exc)
        raise HTTPException(status_code=502, detail=f"Clerk session invalidation failed: {exc}") from exc
    return {"user_id": user_id, "clerk_id": clerk_id, "sessions_invalidated": True}


@router.post("/users/{user_id}/approve")
def approve_user(user_id: int, req: ApprovalActionRequest, admin=Depends(require_admin)):
    if req.user_id != user_id:
        raise HTTPException(status_code=400, detail="Path and body user id mismatch")
    if user_id == admin.id:
        raise HTTPException(status_code=409, detail="Cannot change your own approval status")
    user = user_repo.set_approval_status(
        user_id=user_id,
        status=ApprovalStatus.APPROVED,
        approved_by=admin.email,
        note=req.note,
    )
    approval_html = render_approval_html(
        to_email=user.email,
        display_name=user.display_name or "",
        console_url=settings.console_url,
    )
    message = EmailMessage(
        to_email=user.email,
        subject="MacMarket-Trader account approved",
        body=(
            "Your operator account is approved and ready. "
            f"Sign in at {settings.console_url} to access the console."
        ),
        html=approval_html,
        template_name="account_approved",
    )
    email_status = "sent"
    provider_id: str | None = None
    try:
        provider_id = email_provider.send(message)
    except Exception as e:
        logger.warning("Approval email failed (non-fatal): %s", e)
        email_status = "failed"
    email_repo.create(user.id, "account_approved", user.email, email_status, provider_id or "")
    return {"id": user.id, "approval_status": user.approval_status}


@router.post("/users/{user_id}/reject")
def reject_user(user_id: int, req: ApprovalActionRequest, admin=Depends(require_admin)):
    if req.user_id != user_id:
        raise HTTPException(status_code=400, detail="Path and body user id mismatch")
    user = user_repo.set_approval_status(
        user_id=user_id,
        status=ApprovalStatus.REJECTED,
        approved_by=admin.email,
        note=req.note,
    )
    rejection_html = render_rejection_html(
        to_email=user.email,
        display_name=user.display_name or "",
    )
    message = EmailMessage(
        to_email=user.email,
        subject="MacMarket-Trader account access update",
        body="Your account request has not been approved at this time. Reply to this email if you believe this is an error.",
        html=rejection_html,
        template_name="account_rejected",
    )
    email_status = "sent"
    provider_id: str | None = None
    try:
        provider_id = email_provider.send(message)
    except Exception as e:
        logger.warning("Rejection email failed (non-fatal): %s", e)
        email_status = "failed"
    email_repo.create(user.id, "account_rejected", user.email, email_status, provider_id or "")
    return {"id": user.id, "approval_status": user.approval_status}


@router.post("/invites")
def create_invite(req: InviteCreateRequest, admin=Depends(require_admin)):
    invited_user = user_repo.create_or_update_invited_pending_user(email=req.email, display_name=req.display_name)
    invite = invite_repo.create(email=req.email, display_name=req.display_name, invited_by=admin.email)
    invite_url = (
        f"{settings.app_base_url.rstrip('/')}/sign-up"
        f"?invite_token={invite.invite_token}&email={req.email.strip().lower()}"
    )
    welcome_url = f"{settings.console_url.rstrip('/')}/welcome"
    invite_html = render_invite_html(
        to_email=req.email.strip().lower(),
        invite_url=invite_url,
        display_name=req.display_name or "",
        invited_by=admin.email,
        welcome_url=welcome_url,
    )
    plain_body = (
        "You've been invited to MacMarket-Trader's private alpha.\n\n"
        "This is paper-only operator-grade trading workflow software. It is invite-only and unstable by design.\n\n"
        f"Before you sign in, please read the alpha welcome guide (5 min):\n{welcome_url}\n\n"
        f"When you're ready to sign in:\n{invite_url}\n\n"
        "Two auth gates: Cloudflare Access PIN, then Clerk sign-in. Use the email this invitation was sent to.\n\n"
        "Questions: reply to this email."
    )
    message = EmailMessage(
        to_email=req.email.strip().lower(),
        subject="MacMarket-Trader — you're invited to the private alpha",
        body=plain_body,
        html=invite_html,
        template_name="private_alpha_invite",
    )
    email_status = "sent"
    provider_id: str | None = None
    try:
        provider_id = email_provider.send(message)
    except Exception as e:
        logger.warning("Invite email failed (non-fatal): %s", e)
        email_status = "failed"
    email_repo.create(invited_user.id, "private_alpha_invite", invited_user.email, email_status, provider_id or "")
    return {"invite_id": invite.id, "status": invite.status, "email": invite.email, "invite_token": invite.invite_token}


@router.delete("/invites/{invite_id}")
def delete_invite(invite_id: int, _admin=Depends(require_admin)):
    deleted = invite_repo.delete(invite_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Invite not found")
    return {"deleted": True, "invite_id": invite_id}


@router.post("/invites/{invite_id}/resend")
def resend_invite(invite_id: int, admin=Depends(require_admin)):
    invite = invite_repo.get_by_id(invite_id)
    if invite is None:
        raise HTTPException(status_code=404, detail="Invite not found")
    invite_url = (
        f"{settings.app_base_url.rstrip('/')}/sign-up"
        f"?invite_token={invite.invite_token}&email={invite.email.strip().lower()}"
    )
    welcome_url = f"{settings.console_url.rstrip('/')}/welcome"
    invite_html = render_invite_html(
        to_email=invite.email.strip().lower(),
        invite_url=invite_url,
        display_name=invite.display_name or "",
        invited_by=admin.email,
        welcome_url=welcome_url,
    )
    plain_body = (
        "You've been invited to MacMarket-Trader's private alpha.\n\n"
        "This is paper-only operator-grade trading workflow software. It is invite-only and unstable by design.\n\n"
        f"Before you sign in, please read the alpha welcome guide (5 min):\n{welcome_url}\n\n"
        f"When you're ready to sign in:\n{invite_url}\n\n"
        "Two auth gates: Cloudflare Access PIN, then Clerk sign-in. Use the email this invitation was sent to.\n\n"
        "Questions: reply to this email."
    )
    message = EmailMessage(
        to_email=invite.email.strip().lower(),
        subject="MacMarket-Trader — your invite (resent)",
        body=plain_body,
        html=invite_html,
        template_name="private_alpha_invite_resend",
    )
    email_status = "sent"
    provider_id: str | None = None
    try:
        provider_id = email_provider.send(message)
    except Exception as e:
        logger.warning("Resend invite email failed (non-fatal): %s", e)
        email_status = "failed"
    invite_repo.update_sent_at(invite_id)
    invited_user = user_repo.create_or_update_invited_pending_user(email=invite.email, display_name=invite.display_name or None)
    email_repo.create(invited_user.id, "private_alpha_invite_resend", invite.email, email_status, provider_id or "")
    return {"invite_id": invite.id, "status": invite.status, "email": invite.email, "email_status": email_status}


@router.post("/users/{user_id}/set-role")
def set_user_role(user_id: int, req: dict[str, object], admin=Depends(require_admin)):
    role = str(req.get("role") or "").strip().lower()
    if role not in {"admin", "user"}:
        raise HTTPException(status_code=400, detail="role must be 'admin' or 'user'")
    if user_id == admin.id:
        raise HTTPException(status_code=409, detail="Cannot change your own role")
    target = user_repo.get_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    updated = user_repo.set_app_role(user_id=user_id, role=role)
    return {"id": updated.id, "app_role": updated.app_role}


@router.post("/users/{user_id}/suspend")
def suspend_user(user_id: int, admin=Depends(require_admin)):
    if user_id == admin.id:
        raise HTTPException(status_code=409, detail="Cannot suspend your own account")
    target = user_repo.get_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    updated = user_repo.set_approval_status(
        user_id=user_id,
        status=ApprovalStatus.SUSPENDED,
        approved_by=admin.email,
        note="Suspended by admin",
    )
    return {"id": updated.id, "approval_status": updated.approval_status}


@router.post("/users/{user_id}/unsuspend")
def unsuspend_user(user_id: int, admin=Depends(require_admin)):
    if user_id == admin.id:
        raise HTTPException(status_code=409, detail="Cannot unsuspend your own account")
    target = user_repo.get_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    updated = user_repo.set_approval_status(
        user_id=user_id,
        status=ApprovalStatus.APPROVED,
        approved_by=admin.email,
        note="Unsuspended by admin",
    )
    return {"id": updated.id, "approval_status": updated.approval_status}


@router.get("/invites")
def list_invites(_admin=Depends(require_admin)):
    rows = invite_repo.list_recent(limit=50)
    return [
        {
            "id": row.id,
            "email": row.email,
            "display_name": row.display_name,
            "status": row.status,
            "invite_token": row.invite_token,
            "invited_by": row.invited_by,
            "created_at": row.created_at,
            "market_data_source": "workflow_snapshot_unavailable",
            "fallback_mode": None,
        }
        for row in rows
    ]


def provider_health_summary() -> dict[str, str]:
    market_health = market_data_service.provider_health(sample_symbol="AAPL")
    configured_provider = "fallback"
    if settings.polygon_enabled:
        configured_provider = "polygon"
    elif settings.market_data_enabled:
        configured_provider = settings.market_data_provider.strip().lower() or "fallback"

    env = settings.environment.strip().lower()
    allow_demo_fallback = settings.workflow_demo_fallback and env in {"dev", "local", "test"}
    provider_degraded = market_health.status != "ok"

    effective_read_mode = configured_provider if not provider_degraded else "fallback"
    if provider_degraded and configured_provider != "fallback" and not allow_demo_fallback:
        workflow_execution_mode = "blocked"
    elif configured_provider == "fallback" or (provider_degraded and allow_demo_fallback):
        workflow_execution_mode = "demo_fallback"
    else:
        workflow_execution_mode = "provider"

    if workflow_execution_mode == "blocked":
        market_mode = "blocked"
    elif effective_read_mode == "fallback":
        market_mode = "fallback"
    else:
        market_mode = configured_provider

    auth_mode = settings.auth_provider.strip().lower() or "mock"
    email_mode = settings.email_provider.strip().lower() or "console"
    summary = "ok" if workflow_execution_mode == "provider" else "degraded"
    return {
        "summary": summary,
        "auth": auth_mode,
        "email": email_mode,
        "market_data": market_mode,
        "configured_provider": configured_provider,
        "effective_read_mode": effective_read_mode,
        "workflow_execution_mode": workflow_execution_mode,
        "failure_reason": market_health.details if provider_degraded else "",
    }


def _readiness_status(*, configured: bool) -> str:
    return "configured" if configured else "unconfigured"


def _alpaca_paper_readiness() -> dict[str, object]:
    broker_mode = settings.broker_provider.strip().lower() or "mock"
    api_key_present = bool(settings.alpaca_api_key_id.strip())
    api_secret_present = bool(settings.alpaca_api_secret_key.strip())
    base_url_present = bool(settings.alpaca_paper_base_url.strip())
    configured = api_key_present and api_secret_present and base_url_present
    selected_note = (
        "BROKER_PROVIDER is currently alpaca paper."
        if broker_mode == "alpaca"
        else "BROKER_PROVIDER is currently mock; Alpaca remains a readiness gate only."
    )
    details = (
        "Alpaca paper credentials and base URL appear present. "
        "This surface reports paper-provider readiness only and does not enable live trading or order routing. "
        f"{selected_note}"
        if configured
        else "Alpaca paper readiness is incomplete: API key, secret, or paper base URL is missing. "
        "This surface reports readiness only and does not enable live trading or order routing."
    )
    return {
        "provider": "alpaca_paper",
        "mode": broker_mode,
        "status": _readiness_status(configured=configured),
        "details": details,
        "configured": configured,
        "selected_provider": broker_mode,
        "probe_status": "unavailable" if configured else "not_configured",
        "readiness_scope": "paper_provider",
        "operational_impact": (
            "Use this as a paper-provider readiness gate before deeper provider expansion. "
            "It does not activate brokerage execution."
        ),
    }


def _fred_readiness() -> dict[str, object]:
    macro_mode = settings.macro_calendar_provider.strip().lower() or "mock"
    api_key_present = bool(settings.fred_api_key.strip())
    base_url_present = bool(settings.fred_base_url.strip())
    configured = api_key_present and base_url_present
    selected_note = (
        "MACRO_CALENDAR_PROVIDER is currently fred."
        if macro_mode == "fred"
        else "MACRO_CALENDAR_PROVIDER is currently mock; FRED remains a readiness gate only."
    )
    details = (
        "FRED API key and base URL appear present. This surface currently reports configuration readiness only; "
        f"no dedicated lightweight live probe exists here. {selected_note}"
        if configured
        else "FRED readiness is incomplete: API key or base URL is missing. "
        "This surface currently reports configuration readiness only."
    )
    return {
        "provider": "fred",
        "mode": macro_mode,
        "status": _readiness_status(configured=configured),
        "details": details,
        "configured": configured,
        "selected_provider": macro_mode,
        "probe_status": "unavailable" if configured else "not_configured",
        "readiness_scope": "macro_context",
        "operational_impact": (
            "Use this to verify macro-calendar input readiness before broader provider expansion. "
            "It does not affect brokerage execution."
        ),
    }


def _news_readiness() -> dict[str, object]:
    news_mode = settings.news_provider.strip().lower() or "mock"
    polygon_key_present = bool(settings.polygon_api_key.strip())
    base_url_present = bool(settings.polygon_base_url.strip())
    configured = polygon_key_present and base_url_present
    selected_note = (
        "NEWS_PROVIDER is currently polygon."
        if news_mode == "polygon"
        else "NEWS_PROVIDER is currently mock; provider-backed news remains a readiness gate only."
    )
    details = (
        "Provider-backed news configuration appears present via Polygon API key and base URL. "
        f"This surface currently reports configuration readiness only. {selected_note}"
        if configured
        else "Provider-backed news readiness is incomplete: Polygon API key or base URL is missing. "
        "This surface currently reports configuration readiness only."
    )
    return {
        "provider": "news",
        "mode": news_mode,
        "status": _readiness_status(configured=configured),
        "details": details,
        "configured": configured,
        "selected_provider": news_mode,
        "probe_status": "unavailable" if configured else "not_configured",
        "readiness_scope": "news_context",
        "operational_impact": (
            "Use this to verify provider-backed news context readiness before deeper provider expansion. "
            "Recommendation, replay, and orders remain paper-only."
        ),
    }


@router.get("/provider-health")
def provider_health(_admin=Depends(require_admin)):
    summary = provider_health_summary()
    market_health = market_data_service.provider_health(sample_symbol="AAPL")
    workflow_mode = summary["workflow_execution_mode"]
    operational_impact = "Recommendations, replay, and paper orders are using provider-backed bars."
    if workflow_mode == "blocked":
        operational_impact = (
            "Configured provider probe failed and WORKFLOW_DEMO_FALLBACK=false. "
            "Recommendations, replay, and paper orders are blocked until provider health recovers."
        )
    elif workflow_mode == "demo_fallback":
        operational_impact = (
            "Recommendations, replay, and paper orders are running on explicit deterministic demo fallback bars."
        )
    return {
        "checked_at": utc_now().isoformat(),
        "providers": [
            {
                "provider": "auth",
                "mode": summary["auth"],
                "status": "ok",
                "details": "Auth provider verifies identity; app_role and approval stay local.",
            },
            {
                "provider": "email",
                "mode": summary["email"],
                "status": "ok",
                "details": "Approval notifications are sent through provider boundary with audit logs.",
            },
            _alpaca_paper_readiness(),
            _fred_readiness(),
            _news_readiness(),
            {
                "provider": "market_data",
                "mode": summary["market_data"],
                "status": market_health.status,
                "details": market_health.details,
                "configured_provider": summary["configured_provider"],
                "effective_read_mode": summary["effective_read_mode"],
                "workflow_execution_mode": workflow_mode,
                "failure_reason": summary["failure_reason"] or None,
                "operational_impact": operational_impact,
                "configured": market_health.configured,
                "feed": market_health.feed,
                "sample_symbol": market_health.sample_symbol,
                "latency_ms": market_health.latency_ms,
                "last_success_at": market_health.last_success_at.isoformat() if market_health.last_success_at else None,
            },
        ],
    }
