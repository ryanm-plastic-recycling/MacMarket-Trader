"""Admin approval and operator routes."""

import json
import logging
import math
from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException

from macmarket_trader.api.deps.auth import current_user, require_admin, require_approved_user
from macmarket_trader.api.routes.workflow_lineage import extract_recommendation_key_levels, extract_recommendation_strategy
from macmarket_trader.api.security import (
    MAX_BULK_SYMBOLS,
    MAX_QUEUE_TOP_N,
    MAX_SELECTED_STRATEGIES,
    MAX_WATCHLIST_SYMBOLS,
    capped_int,
    capped_text,
    normalize_symbol,
    normalize_symbol_list,
)
from macmarket_trader.config import settings
from macmarket_trader.data.providers.base import EmailMessage
from macmarket_trader.data.providers.market_data import (
    DataNotEntitledError,
    DeterministicFallbackMarketDataProvider,
    SymbolNotFoundError,
    build_polygon_option_ticker,
    option_underlying_asset_type,
    unavailable_option_contract_snapshot,
)
from macmarket_trader.data.providers.registry import build_email_provider, build_market_data_service
from macmarket_trader.domain.enums import ApprovalStatus, MarketMode
from macmarket_trader.domain.time import calendar_days_to_expiration, utc_now
from macmarket_trader.domain.schemas import (
    ApprovalActionRequest,
    Bar,
    ExpectedRange,
    InviteCreateRequest,
    BetterElsewhereCandidate,
    OptionPaperExpirationSettleRequest,
    OptionPaperCloseStructureRequest,
    OptionPaperCloseStructureResponse,
    OptionPaperLifecycleSummaryListResponse,
    OptionPaperOpenStructureResponse,
    OptionPaperStructureReview,
    OptionPaperStructureReviewListResponse,
    OptionPaperStructureInput,
    OptionReplayPreviewRequest,
    OptionReplayPreviewResponse,
    OpportunityCandidateSummary,
    OpportunityComparisonMemo,
    OpportunityIntelligenceRequest,
    PortfolioSnapshot,
    RiskCalendarAssessment,
    ReplayRunRequest,
    TradeRecommendation,
)
from macmarket_trader.execution.paper_broker import PaperBroker
from macmarket_trader.llm.base import LLMProviderUnavailable, LLMValidationError
from macmarket_trader.llm.openai_provider import OpenAICompatibleLLMClient, get_last_openai_provider_error
from macmarket_trader.options.paper_close import OptionPaperCloseError, close_paper_option_structure, settle_paper_option_expiration
from macmarket_trader.options.paper_contracts import OptionPaperContractError
from macmarket_trader.options.paper_open import open_paper_option_structure
from macmarket_trader.options.replay_preview import build_options_replay_preview
from macmarket_trader.ranking_engine import DeterministicRankingEngine
from macmarket_trader.replay.engine import ReplayEngine
from macmarket_trader.risk_calendar.registry import build_risk_calendar_service
from macmarket_trader.risk_calendar.service import RiskCalendarBlocked, RiskCalendarRestricted
from macmarket_trader.service import RecommendationService
from macmarket_trader.email_templates import render_approval_html, render_invite_html, render_rejection_html
from macmarket_trader.strategy_reports import StrategyReportService
from macmarket_trader.strategy_registry import get_strategy_by_display_name, list_strategies
from macmarket_trader.storage.db import SessionLocal
from macmarket_trader.storage.repositories import DashboardRepository, EmailLogRepository, InviteRepository, OptionPaperRepository, OrderRepository, PaperPortfolioRepository, RecommendationRepository, ReplayRepository, StrategyReportRepository, SymbolUniverseRepository, UserRepository, WatchlistRepository, commission_paid_for_trade, display_id_or_fallback, gross_pnl_or_fallback, net_pnl_or_fallback
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


def _effective_paper_max_order_notional(user) -> float:
    override = getattr(user, "paper_max_order_notional", None)
    if override is None:
        return float(settings.paper_max_order_notional)
    try:
        return float(override)
    except (TypeError, ValueError):
        return float(settings.paper_max_order_notional)


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
    app_user_id: int | None = None,
) -> dict[str, object]:
    if not recommendation_id:
        return _recommendation_fee_preview(None, commission_per_trade=commission_per_trade)
    rec_row = recommendation_repo.get_by_recommendation_uid(recommendation_id, app_user_id=app_user_id)
    if rec_row is None:
        return _recommendation_fee_preview(None, commission_per_trade=commission_per_trade)
    try:
        rec = TradeRecommendation.model_validate(rec_row.payload or {})
    except Exception:
        return _recommendation_fee_preview(None, commission_per_trade=commission_per_trade)
    return _recommendation_fee_preview(rec, commission_per_trade=commission_per_trade)


def _paper_order_sizing_plan(
    rec: TradeRecommendation,
    *,
    user,
    override_shares: object | None = None,
) -> dict[str, object]:
    try:
        recommended_shares = int(rec.sizing.shares)
        limit_price = (float(rec.entry.zone_low) + float(rec.entry.zone_high)) / 2.0
        stop_price = float(rec.invalidation.price)
    except (AttributeError, TypeError, ValueError):
        raise HTTPException(status_code=409, detail="Recommendation sizing is not usable for paper order staging.")
    if recommended_shares <= 0:
        raise HTTPException(status_code=409, detail="Recommendation has no positive share size for paper order staging.")
    if not math.isfinite(limit_price) or limit_price <= 0:
        raise HTTPException(status_code=409, detail="Recommendation entry price is not usable for paper order staging.")

    max_notional = _effective_paper_max_order_notional(user)
    if not math.isfinite(max_notional) or max_notional <= 0:
        raise HTTPException(status_code=409, detail="paper_max_order_notional must be positive before staging paper orders.")
    notional_cap_shares = max(0, math.floor(max_notional / limit_price))
    if notional_cap_shares <= 0:
        raise HTTPException(
            status_code=409,
            detail="paper_max_order_notional is below the recommendation entry price; increase the paper cap or choose a smaller setup.",
        )

    final_shares = min(recommended_shares, notional_cap_shares)
    operator_override: int | None = None
    if override_shares is not None:
        if isinstance(override_shares, float) and not override_shares.is_integer():
            raise HTTPException(status_code=400, detail="override_shares must be a positive integer.")
        if isinstance(override_shares, str) and not override_shares.strip().isdigit():
            raise HTTPException(status_code=400, detail="override_shares must be a positive integer.")
        try:
            operator_override = int(override_shares)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="override_shares must be a positive integer.")
        if operator_override <= 0:
            raise HTTPException(status_code=400, detail="override_shares must be a positive integer.")
        if operator_override > recommended_shares:
            raise HTTPException(status_code=409, detail="override_shares cannot exceed deterministic recommended shares.")
        if operator_override > notional_cap_shares:
            raise HTTPException(status_code=409, detail="override_shares cannot exceed paper_max_order_notional cap.")
        final_shares = operator_override

    stop_distance = abs(limit_price - stop_price)
    if not math.isfinite(stop_distance):
        stop_distance = 0.0
    risk_at_stop = final_shares * stop_distance
    estimated_notional = final_shares * limit_price
    return {
        "recommended_shares": recommended_shares,
        "final_order_shares": final_shares,
        "operator_override_shares": operator_override,
        "max_paper_order_notional": _round_money(max_notional),
        "notional_cap_shares": notional_cap_shares,
        "estimated_notional": _round_money(estimated_notional),
        "risk_at_stop": _round_money(risk_at_stop),
        "sizing_mode": "risk_and_notional_capped",
        "notional_cap_reduced": final_shares < recommended_shares,
    }


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
symbol_universe_repo = SymbolUniverseRepository(SessionLocal)
strategy_report_repo = StrategyReportRepository(SessionLocal)
email_provider = build_email_provider()
market_data_service = build_market_data_service()
recommendation_service = RecommendationService()
risk_calendar_service = build_risk_calendar_service()
replay_engine = ReplayEngine(service=recommendation_service)
paper_broker = PaperBroker()
strategy_report_service = StrategyReportService(
    report_repo=strategy_report_repo,
    email_provider=email_provider,
    email_log_repo=email_repo,
)
preview_market_data_provider = DeterministicFallbackMarketDataProvider()
ranking_engine = DeterministicRankingEngine()


def _build_options_expected_range(*, latest_close: float, iv_snapshot: float | None, dte: int, as_of: datetime) -> ExpectedRange:
    reference = round(latest_close, 2)
    if iv_snapshot is None:
        return ExpectedRange(
            status="blocked",
            reason="missing_iv_snapshot",
            horizon_value=dte,
            horizon_unit="calendar_days",
            reference_price_type="underlying_last",
            snapshot_timestamp=as_of,
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
            snapshot_timestamp=as_of,
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
        snapshot_timestamp=as_of,
        provenance_notes="Research preview only. Computed from IV 1-sigma method; not execution support.",
        status="computed",
    )


def _options_research_expiration_context(*, expiration: str, as_of: datetime) -> dict[str, object]:
    dte = calendar_days_to_expiration(expiration, as_of=as_of)
    return {
        "expiration": expiration,
        "dte": dte if dte is not None else 0,
        "as_of": as_of.isoformat(),
        "dte_policy": "utc_calendar_days",
    }


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


def _workflow_bars(symbol: str, limit: int = 60, timeframe: str = "1D") -> tuple[list[Bar], str, bool]:
    try:
        bars, source, fallback_mode = market_data_service.historical_bars(symbol=symbol, timeframe=timeframe, limit=limit)
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


def _workflow_bar_metadata() -> dict[str, object]:
    metadata = getattr(market_data_service, "last_historical_metadata", None)
    return dict(metadata) if isinstance(metadata, dict) else {}


def _session_metadata_from_bars(bars: list[Bar], *, timeframe: str) -> dict[str, object]:
    first = bars[0] if bars else None
    last = bars[-1] if bars else None
    return {
        "timeframe": timeframe,
        "session_policy": first.session_policy if first else None,
        "source_session_policy": first.source_session_policy if first else None,
        "source_timeframe": first.source_timeframe if first else None,
        "output_timeframe": timeframe.upper(),
        "rth_bucket_count": len(bars) if first and first.session_policy == "regular_hours" else None,
        "first_bar_timestamp": first.timestamp.isoformat() if first and first.timestamp else None,
        "last_bar_timestamp": last.timestamp.isoformat() if last and last.timestamp else None,
    }


def _workflow_session_metadata(bars: list[Bar], *, timeframe: str) -> dict[str, object]:
    metadata = _workflow_bar_metadata()
    fallback = _session_metadata_from_bars(bars, timeframe=timeframe)
    for key, value in fallback.items():
        metadata.setdefault(key, value)
    return {key: value for key, value in metadata.items() if value is not None}


def _workflow_allows_demo_fallback() -> bool:
    return settings.workflow_demo_fallback and settings.environment.strip().lower() in {"dev", "local", "test"}


def _provider_mark_is_required() -> bool:
    return bool(settings.market_data_enabled or settings.polygon_enabled)


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
        "paper_max_order_notional": user.paper_max_order_notional,
        "paper_max_order_notional_default": settings.paper_max_order_notional,
        "commission_per_trade": user.commission_per_trade,
        "commission_per_trade_default": settings.commission_per_trade,
        "commission_per_contract": user.commission_per_contract,
        "commission_per_contract_default": settings.commission_per_contract,
    }


def _serialize_user_settings(user) -> dict[str, object]:
    return {
        "id": user.id,
        "risk_dollars_per_trade": user.risk_dollars_per_trade,
        "risk_dollars_per_trade_default": settings.risk_dollars_per_trade,
        "paper_max_order_notional": user.paper_max_order_notional,
        "paper_max_order_notional_default": settings.paper_max_order_notional,
        "commission_per_trade": user.commission_per_trade,
        "commission_per_trade_default": settings.commission_per_trade,
        "commission_per_contract": user.commission_per_contract,
        "commission_per_contract_default": settings.commission_per_contract,
    }


@user_router.get("/settings")
def get_user_settings(user=Depends(require_approved_user)):
    return _serialize_user_settings(user)


def _update_user_settings(req: dict[str, object], user) -> dict[str, object]:
    """Update operator-controlled settings for sizing and commission defaults."""
    allowed_keys = {
        "risk_dollars_per_trade",
        "paper_max_order_notional",
        "commission_per_trade",
        "commission_per_contract",
    }
    provided_keys = [key for key in allowed_keys if key in req]
    if not provided_keys:
        raise HTTPException(
            status_code=400,
            detail="At least one of risk_dollars_per_trade, paper_max_order_notional, commission_per_trade, or commission_per_contract is required.",
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

    if "paper_max_order_notional" in req:
        raw = req.get("paper_max_order_notional")
        try:
            value = float(raw) if raw is not None else None
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="paper_max_order_notional must be numeric.")
        if value is None:
            user_repo.set_paper_max_order_notional(user.id, value=None)
        else:
            if value <= 0 or value > 1000000:
                raise HTTPException(
                    status_code=400,
                    detail="paper_max_order_notional must be > 0 and <= 1000000.",
                )
            user_repo.set_paper_max_order_notional(user.id, value=value)

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
    return _serialize_user_settings(refreshed)


@user_router.patch("/settings")
def update_user_settings(req: dict[str, object], user=Depends(require_approved_user)):
    return _update_user_settings(req, user)


@user_router.post("/settings")
def post_user_settings(req: dict[str, object], user=Depends(require_approved_user)):
    return _update_user_settings(req, user)


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
    is_admin = str(user.app_role) == "admin"
    counts = dashboard_repo.summary_counts(app_user_id=user.id)
    recommendations = recommendation_repo.list_recent(limit=5, app_user_id=user.id)
    replay_runs = replay_repo.list_runs(limit=5, app_user_id=user.id)
    orders = order_repo.list_with_fills(limit=5, app_user_id=user.id)
    pending_users = user_repo.list_by_status(ApprovalStatus.PENDING) if is_admin else []
    provider_health = provider_health_summary()
    latest_snapshot = market_data_service.latest_snapshot(symbol="AAPL", timeframe="1D")
    risk_calendar = risk_calendar_service.assess(symbol="SPY", timeframe="1D")

    # Operational audit events — combine email logs, approval events, and schedule runs
    email_events = [
        {
            "event_type": "email_sent",
            "timestamp": row.sent_at.isoformat() if row.sent_at else None,
            "detail": f"{row.template_name} → {row.destination}",
            "status": row.status,
        }
        for row in (email_repo.list_recent(limit=5) if is_admin else [])
    ]
    approval_events = [
        {
            "event_type": "user_approval",
            "timestamp": row.created_at.isoformat() if row.created_at else None,
            "detail": f"approval request: {row.status} ({row.note})",
            "status": row.status,
        }
        for row in (user_repo.list_recent_approval_requests(limit=5) if is_admin else [])
    ]
    schedule_run_events = [
        {
            "event_type": "schedule_run",
            "timestamp": row.created_at.isoformat() if row.created_at else None,
            "detail": f"schedule #{row.schedule_id} → {row.status} / {row.delivered_to}",
            "status": row.status,
        }
        for row in (strategy_report_repo.list_recent_runs_all(limit=5) if is_admin else [])
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
        "risk_calendar": risk_calendar.model_dump(mode="json"),
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
        "quick_links": ["/charts/haco", *([] if not is_admin else ["/admin/users/pending"]), "/recommendations"],
        "workflow_guide": [
            "Start guided paper trade from Dashboard or Analysis to run the canonical Analyze → Recommendation → Replay → Paper Order flow.",
            "Run Replay to validate path-by-path risk transitions before staging paper execution.",
            "Use Orders to review fills and paper blotter outcomes.",
        ],
        "recent_audit_events": all_events,
    }


@user_router.get("/risk-calendar/today")
def risk_calendar_today(symbol: str = "SPY", timeframe: str = "1D", _user=Depends(require_approved_user)):
    assessment = risk_calendar_service.assess(symbol=symbol, timeframe=timeframe)
    return assessment.model_dump(mode="json")


@user_router.get("/recommendations")
def list_recommendations(_user=Depends(require_approved_user)):
    rows = recommendation_repo.list_recent(app_user_id=_user.id)
    already_open_by_symbol = _open_paper_position_context_by_symbol(
        app_user_id=_user.id,
        user=_user,
        recent_rows=rows,
        include_review=True,
    )
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
            **_already_open_context(row.symbol, already_open_by_symbol),
        }
        for row in rows
    ]


def _opportunity_float(value: object) -> float | None:
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _opportunity_int(value: object) -> int | None:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed


def _opportunity_source_display(prefix: str, display_id: str | None, fallback: str) -> str:
    label = display_id_or_fallback(display_id, fallback)
    if label.lower().startswith(prefix.lower()):
        return label
    return f"{prefix}: {label}"


def _opportunity_candidate_from_row(row) -> OpportunityCandidateSummary:
    payload = dict(row.payload or {})
    workflow = payload.get("workflow") if isinstance(payload.get("workflow"), dict) else {}
    ranking = workflow.get("ranking_provenance") if isinstance(workflow.get("ranking_provenance"), dict) else {}
    data_quality = ranking.get("data_quality") if isinstance(ranking.get("data_quality"), dict) else {}
    if not data_quality:
        data_quality = {
            "session_policy": workflow.get("session_policy"),
            "source_session_policy": workflow.get("source_session_policy"),
            "source_timeframe": workflow.get("source_timeframe"),
            "output_timeframe": workflow.get("output_timeframe"),
            "filtered_extended_hours_count": workflow.get("filtered_extended_hours_count"),
            "rth_bucket_count": workflow.get("rth_bucket_count"),
        }
    quality = payload.get("quality") if isinstance(payload.get("quality"), dict) else {}
    sizing = payload.get("sizing") if isinstance(payload.get("sizing"), dict) else {}
    event = payload.get("event") if isinstance(payload.get("event"), dict) else {}
    regime = payload.get("regime_context") if isinstance(payload.get("regime_context"), dict) else payload.get("regime")
    entry = payload.get("entry") if isinstance(payload.get("entry"), dict) else None
    invalidation = payload.get("invalidation") if isinstance(payload.get("invalidation"), dict) else None
    targets = payload.get("targets") if isinstance(payload.get("targets"), dict) else None
    risk_calendar = None
    if isinstance(payload.get("risk_calendar"), dict):
        try:
            risk_calendar = RiskCalendarAssessment.model_validate(payload["risk_calendar"])
        except Exception:
            risk_calendar = None
    reasons: list[str] = []
    if isinstance(ranking.get("reason_text"), str) and ranking.get("reason_text"):
        reasons.append(str(ranking["reason_text"]))
    if isinstance(payload.get("thesis"), str) and payload.get("thesis"):
        reasons.append(str(payload["thesis"]))
    side = payload.get("side")
    if hasattr(side, "value"):
        side = side.value
    source_prefix = "Promoted recommendation" if ranking else "Stored recommendation"
    return OpportunityCandidateSummary(
        recommendation_id=row.recommendation_id,
        display_id=_opportunity_source_display(source_prefix, row.display_id, row.recommendation_id),
        symbol=str(payload.get("symbol") or row.symbol).upper(),
        side=str(side or "long"),
        timeframe=str(ranking.get("timeframe") or workflow.get("timeframe") or "1D"),
        approved=bool(payload.get("approved", False)),
        status=str(payload.get("outcome") or ranking.get("status") or ("approved" if payload.get("approved") else "no_trade")),
        deterministic_score=_opportunity_float(ranking.get("score") or quality.get("score")),
        confidence=_opportunity_float(ranking.get("confidence") or quality.get("confidence")),
        risk_score=_opportunity_float(quality.get("risk_score")),
        expected_rr=_opportunity_float(ranking.get("expected_rr") or quality.get("expected_rr")),
        entry=entry,
        invalidation=invalidation,
        targets=targets,
        risk_dollars=_opportunity_float(sizing.get("risk_dollars")),
        final_order_shares=None,
        final_order_notional=None,
        current_recommendation_rank=_opportunity_int(ranking.get("rank")),
        reasons=reasons[:12],
        rejection_reason=str(payload.get("rejection_reason")) if payload.get("rejection_reason") else None,
        market_regime=regime if isinstance(regime, dict) else None,
        event_summary=str(event.get("summary")) if isinstance(event.get("summary"), str) else None,
        workflow_source=str(workflow.get("market_data_source") or ranking.get("workflow_source") or ranking.get("source") or ""),
        session_policy=str(workflow.get("session_policy") or ranking.get("session_policy") or "") or None,
        data_quality={key: value for key, value in data_quality.items() if value is not None},
        risk_calendar=risk_calendar,
    )


def _better_elsewhere_from_candidate(candidate: OpportunityCandidateSummary) -> BetterElsewhereCandidate:
    return BetterElsewhereCandidate(
        recommendation_id=candidate.recommendation_id,
        symbol=candidate.symbol,
        rank=candidate.current_recommendation_rank,
        deterministic_score=candidate.deterministic_score,
        expected_rr=candidate.expected_rr,
        confidence=candidate.confidence,
        reason=(
            candidate.reasons[0]
            if candidate.reasons
            else "Deterministic stored recommendation has stronger rank/score than the selected set."
        ),
        source="deterministic_scan",
        verified_by_scan=True,
    )


def _label_queue_candidate(candidate: OpportunityCandidateSummary) -> OpportunityCandidateSummary:
    display_id = candidate.display_id or candidate.recommendation_id
    if not display_id.lower().startswith("queue candidate"):
        display_id = f"Queue candidate: {display_id}"
    return OpportunityCandidateSummary.model_validate(candidate.model_copy(update={"display_id": display_id}))


def _dedupe_opportunity_candidates(
    candidates: list[OpportunityCandidateSummary],
) -> list[OpportunityCandidateSummary]:
    deduped: list[OpportunityCandidateSummary] = []
    seen_ids: set[str] = set()
    for candidate in candidates:
        if candidate.recommendation_id in seen_ids:
            continue
        seen_ids.add(candidate.recommendation_id)
        deduped.append(candidate)
    return deduped


def _queue_candidate_id(item: dict[str, object]) -> str:
    symbol = str(item.get("symbol") or "").upper()
    strategy = str(item.get("strategy") or "strategy").replace(" ", "_").lower()
    rank = item.get("rank") if item.get("rank") is not None else "unranked"
    timeframe = str(item.get("timeframe") or "1D").upper()
    return f"queue:{symbol}:{strategy}:{timeframe}:{rank}"


@user_router.post("/recommendations/opportunity-intelligence", response_model=OpportunityComparisonMemo)
def recommendation_opportunity_intelligence(
    req: OpportunityIntelligenceRequest,
    _user=Depends(require_approved_user),
) -> OpportunityComparisonMemo:
    selected_ids = [item.strip() for item in req.selected_recommendation_ids if item.strip()]
    selected_rows = []
    for recommendation_id in selected_ids:
        row = recommendation_repo.get_by_recommendation_uid(recommendation_id, app_user_id=_user.id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"Recommendation not found: {recommendation_id}")
        selected_rows.append(row)
    queue_candidates = [
        _label_queue_candidate(OpportunityCandidateSummary.model_validate(candidate))
        for candidate in req.selected_queue_candidates
    ]
    candidates = _dedupe_opportunity_candidates(
        [_opportunity_candidate_from_row(row) for row in selected_rows] + queue_candidates
    )[: req.max_candidates]
    if len(candidates) < 2:
        raise HTTPException(status_code=400, detail="Select at least two stored recommendations or queue candidates to compare.")

    better_elsewhere: list[BetterElsewhereCandidate] = []
    if req.include_better_elsewhere:
        selected_set = {candidate.recommendation_id for candidate in candidates}
        recent_rows = recommendation_repo.list_recent(limit=max(20, req.max_candidates * 4), app_user_id=_user.id)
        pool = [
            _opportunity_candidate_from_row(row)
            for row in recent_rows
            if row.recommendation_id not in selected_set
        ]
        pool.sort(
            key=lambda candidate: (
                0 if candidate.approved else 1,
                candidate.current_recommendation_rank if candidate.current_recommendation_rank is not None else 999,
                -(candidate.deterministic_score or 0.0),
                -(candidate.expected_rr or 0.0),
            )
        )
        better_elsewhere = [_better_elsewhere_from_candidate(candidate) for candidate in pool[: req.max_candidates]]
        for queue_candidate in req.queue_better_elsewhere_candidates:
            candidate = OpportunityCandidateSummary.model_validate(queue_candidate)
            if candidate.recommendation_id in selected_set:
                continue
            better_elsewhere.append(_better_elsewhere_from_candidate(candidate))
        better_elsewhere = better_elsewhere[: req.max_candidates]

    return recommendation_service.generate_opportunity_intelligence(
        candidates=candidates,
        better_elsewhere=better_elsewhere,
    )


@user_router.post("/recommendations/queue")
def ranked_recommendation_queue(req: dict[str, object], _user=Depends(require_approved_user)):
    market_mode = MarketMode(str(req.get("market_mode") or MarketMode.EQUITIES.value))
    symbols = normalize_symbol_list(
        req.get("symbols") or ["AAPL", "MSFT", "NVDA"],
        max_items=MAX_BULK_SYMBOLS,
    )
    timeframe = capped_text(req.get("timeframe") or "1D", field_name="timeframe", max_length=4).upper()
    if timeframe not in {"1D", "1H", "4H"}:
        raise HTTPException(status_code=400, detail="timeframe must be one of: 1D, 1H, 4H.")
    selected_strategies = [
        capped_text(item, field_name="strategies", max_length=80)
        for item in (req.get("strategies") or [])
        if str(item).strip()
    ]
    if len(selected_strategies) > MAX_SELECTED_STRATEGIES:
        raise HTTPException(status_code=400, detail=f"strategies may include at most {MAX_SELECTED_STRATEGIES} entries.")
    if not selected_strategies:
        selected_strategies = [entry.display_name for entry in list_strategies(market_mode)[:3]]
    top_n = capped_int(req.get("top_n"), default=10, minimum=1, maximum=MAX_QUEUE_TOP_N, field_name="top_n")
    bars_by_symbol: dict[str, tuple[list[Bar], str, bool]] = {}
    session_metadata_by_symbol: dict[str, dict[str, object]] = {}
    for symbol in symbols:
        bars_tuple = _workflow_bars(symbol, limit=120, timeframe=timeframe)
        bars_by_symbol[symbol] = bars_tuple
        session_metadata_by_symbol[symbol] = _workflow_session_metadata(bars_tuple[0], timeframe=timeframe)
    ranking = ranking_engine.rank_candidates(
        bars_by_symbol=bars_by_symbol,
        strategies=selected_strategies,
        market_mode=market_mode,
        timeframe=timeframe,
        top_n=top_n,
    )
    already_open_by_symbol = _open_paper_position_context_by_symbol(
        app_user_id=_user.id,
        user=_user,
        include_review=True,
    )
    for item in ranking["queue"]:
        item_metadata = session_metadata_by_symbol.get(str(item.get("symbol") or "").upper(), {})
        if item_metadata:
            item["session_policy"] = item_metadata.get("session_policy")
            item["data_quality"] = {
                "session_policy": item_metadata.get("session_policy"),
                "source_session_policy": item_metadata.get("source_session_policy"),
                "source_timeframe": item_metadata.get("source_timeframe"),
                "output_timeframe": item_metadata.get("output_timeframe"),
                "filtered_extended_hours_count": item_metadata.get("filtered_extended_hours_count"),
                "rth_bucket_count": item_metadata.get("rth_bucket_count"),
            }
        symbol = str(item.get("symbol") or "").upper()
        bars_tuple = bars_by_symbol.get(symbol)
        if bars_tuple:
            risk = risk_calendar_service.assess(
                symbol=symbol,
                timeframe=timeframe,
                bars=bars_tuple[0],
            )
            item["risk_calendar"] = risk.model_dump(mode="json")
            if not risk.decision.allow_new_entries and item.get("status") == "top_candidate":
                item["status"] = risk.decision.decision_state
                item["rejection_reason"] = risk.decision.block_reason or risk.decision.warning_summary
        item["recommendation_id"] = _queue_candidate_id(item)
        item.update(_already_open_context(symbol, already_open_by_symbol))
    return {
        "market_mode": market_mode.value,
        "timeframe": timeframe,
        "source": "mixed" if len({item["workflow_source"] for item in ranking["queue"]}) > 1 else (ranking["queue"][0]["workflow_source"] if ranking["queue"] else "provider"),
        **ranking,
    }


@user_router.post("/recommendations/queue/promote")
def promote_queue_candidate(req: dict[str, object], _user=Depends(require_approved_user)):
    symbol = normalize_symbol(req.get("symbol"), field_name="symbol")
    strategy = capped_text(req.get("strategy") or "Event Continuation", field_name="strategy", max_length=80)

    action = str(req.get("action") or "make_active")

    timeframe = capped_text(req.get("timeframe") or "1D", field_name="timeframe", max_length=4).upper()
    if timeframe not in {"1D", "1H", "4H"}:
        raise HTTPException(status_code=400, detail="timeframe must be one of: 1D, 1H, 4H.")
    bars, source, fallback_mode = _workflow_bars(symbol, timeframe=timeframe)
    session_metadata = _workflow_session_metadata(bars, timeframe=timeframe)
    event_text = capped_text(req.get("thesis") or f"Queue promotion for {strategy}", field_name="thesis")
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
        timeframe=timeframe,
    )

    ranking_provenance = {
        "action": action,
        "rank": req.get("rank"),
        "symbol": symbol,
        "strategy": strategy,
        "strategy_id": req.get("strategy_id"),
        "strategy_status": req.get("strategy_status") or req.get("status"),
        "timeframe": timeframe,
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
        "session_policy": session_metadata.get("session_policy"),
        "data_quality": {
            "session_policy": session_metadata.get("session_policy"),
            "source_session_policy": session_metadata.get("source_session_policy"),
            "source_timeframe": session_metadata.get("source_timeframe"),
            "output_timeframe": session_metadata.get("output_timeframe"),
            "filtered_extended_hours_count": session_metadata.get("filtered_extended_hours_count"),
            "rth_bucket_count": session_metadata.get("rth_bucket_count"),
        },
    }

    recommendation_repo.attach_workflow_metadata(
        rec.recommendation_id,
        market_data_source=source,
        fallback_mode=fallback_mode,
        market_mode=promote_market_mode.value,
        source_strategy=strategy,
        session_metadata=session_metadata,
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
    already_open_by_symbol = _open_paper_position_context_by_symbol(
        app_user_id=_user.id,
        user=_user,
        include_review=True,
    )
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
        **_already_open_context(rec.symbol, already_open_by_symbol),
    }


@user_router.post("/recommendations/generate")
def generate_recommendations(req: dict[str, object], _user=Depends(require_approved_user)):
    symbol = normalize_symbol(req.get("symbol") or "AAPL", field_name="symbol")
    event_text = capped_text(
        req.get("event_text") or "Operator-triggered deterministic refresh run.",
        field_name="event_text",
    )
    market_mode = MarketMode(str(req.get("market_mode") or MarketMode.EQUITIES.value))
    strategy = capped_text(req.get("strategy") or "", field_name="strategy", max_length=80)
    timeframe = capped_text(req.get("timeframe") or "1D", field_name="timeframe", max_length=4).upper()
    if timeframe not in {"1D", "1H", "4H"}:
        raise HTTPException(status_code=400, detail="timeframe must be one of: 1D, 1H, 4H.")
    workflow_source = capped_text(req.get("workflow_source") or req.get("source") or "", field_name="workflow_source", max_length=80)
    approval_status = getattr(_user.approval_status, "value", _user.approval_status)
    user_is_approved = str(approval_status) == ApprovalStatus.APPROVED.value
    bars, source, fallback_mode = _workflow_bars(symbol, timeframe=timeframe)
    session_metadata = _workflow_session_metadata(bars, timeframe=timeframe)
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
        timeframe=timeframe,
    )
    recommendation_repo.attach_workflow_metadata(
        rec.recommendation_id,
        market_data_source=source,
        fallback_mode=fallback_mode,
        market_mode=market_mode.value,
        source_strategy=strategy,
        session_metadata=session_metadata,
    )
    recommendation_repo.attach_ranking_provenance(
        rec.recommendation_id,
        ranking_provenance={
            "strategy": strategy or None,
            "market_mode": market_mode.value,
            "timeframe": timeframe,
            "workflow_source": workflow_source or source,
            "source": workflow_source or source,
            "session_policy": session_metadata.get("session_policy"),
            "data_quality": {
                "session_policy": session_metadata.get("session_policy"),
                "source_session_policy": session_metadata.get("source_session_policy"),
                "source_timeframe": session_metadata.get("source_timeframe"),
                "output_timeframe": session_metadata.get("output_timeframe"),
                "filtered_extended_hours_count": session_metadata.get("filtered_extended_hours_count"),
                "rth_bucket_count": session_metadata.get("rth_bucket_count"),
            },
        },
    )
    already_open_by_symbol = _open_paper_position_context_by_symbol(
        app_user_id=_user.id,
        user=_user,
        include_review=True,
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
        "session_policy": session_metadata.get("session_policy"),
        **_already_open_context(rec.symbol, already_open_by_symbol),
    }


@user_router.get("/recommendations/{recommendation_id}")
def recommendation_detail(recommendation_id: int, _user=Depends(require_approved_user)):
    row = recommendation_repo.get_by_id(recommendation_id, app_user_id=_user.id)
    if row is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    already_open_by_symbol = _open_paper_position_context_by_symbol(
        app_user_id=_user.id,
        user=_user,
        include_review=True,
    )
    return {
        "id": row.id,
        "created_at": row.created_at,
        "symbol": row.symbol,
        "recommendation_id": row.recommendation_id,
        "display_id": display_id_or_fallback(row.display_id, row.recommendation_id),
        "payload": row.payload,
        "market_data_source": (row.payload or {}).get("workflow", {}).get("market_data_source"),
        "fallback_mode": bool((row.payload or {}).get("workflow", {}).get("fallback_mode", False)),
        **_already_open_context(row.symbol, already_open_by_symbol),
    }


@user_router.patch("/recommendations/{recommendation_uid}/approve")
def set_recommendation_approved(recommendation_uid: str, req: dict[str, object], _user=Depends(require_approved_user)):
    approved = bool(req.get("approved", True))
    row = recommendation_repo.set_approved(recommendation_uid, approved=approved, app_user_id=_user.id)
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
            rec = recommendation_repo.get_by_recommendation_uid(
                first_step[0].recommendation_id,
                app_user_id=_user.id,
            )
            workflow = (rec.payload or {}).get("workflow", {}) if rec else {}
            source = str(workflow.get("market_data_source") or source)
            fallback = workflow.get("fallback_mode")
            if fallback is not None:
                fallback_mode = bool(fallback)
        fee_preview = _recommendation_fee_preview_from_uid(
            row.stageable_recommendation_id,
            commission_per_trade=commission_per_trade,
            app_user_id=_user.id,
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
        req = _resolve_paper_option_structure_contracts(req)
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


@user_router.post(
    "/options/paper-structures/{position_id}/settle-expiration",
    response_model=OptionPaperCloseStructureResponse,
)
def settle_user_option_paper_structure_expiration(
    position_id: int,
    req: OptionPaperExpirationSettleRequest,
    user=Depends(require_approved_user),
) -> OptionPaperCloseStructureResponse:
    position = option_paper_repo.get_position(position_id=position_id, app_user_id=user.id)
    if position is None:
        raise HTTPException(status_code=404, detail="option_position_not_found")
    settlement_price = _finite_float(req.underlying_settlement_price)
    if settlement_price is None:
        mark_payload = _option_underlying_mark(position.underlying_symbol)
        settlement_price = _finite_float(mark_payload.get("underlying_mark_price"))
        if settlement_price is None:
            raise HTTPException(status_code=409, detail="underlying_mark_required_for_expiration_settlement")
    try:
        return settle_paper_option_expiration(
            app_user_id=user.id,
            position_id=position_id,
            confirmation=req.confirmation,
            underlying_settlement_price=settlement_price,
            commission_per_contract=_effective_commission_per_contract(user),
            repository=option_paper_repo,
            notes=req.notes or "",
        )
    except OptionPaperCloseError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.reason) from exc


@user_router.get(
    "/options/paper-structures/review",
    response_model=OptionPaperStructureReviewListResponse,
)
def review_user_option_paper_structures(
    limit: int = 100,
    user=Depends(require_approved_user),
) -> OptionPaperStructureReviewListResponse:
    safe_limit = max(1, min(int(limit), 200))
    now = utc_now()
    return OptionPaperStructureReviewListResponse(
        items=[
            _build_option_paper_structure_review(position, user=user, now=now)
            for position in option_paper_repo.list_open_positions(
                app_user_id=user.id,
                limit=safe_limit,
            )
        ]
    )


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
        rec_row = recommendation_repo.get_by_recommendation_uid(recommendation_id, app_user_id=_user.id)
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
    source_rec = (
        recommendation_repo.get_by_recommendation_uid(run.source_recommendation_id, app_user_id=_user.id)
        if run.source_recommendation_id
        else None
    )
    source_payload = (source_rec.payload or {}) if source_rec else {}
    fee_preview = _recommendation_fee_preview_from_uid(
        run.stageable_recommendation_id,
        commission_per_trade=_effective_commission_per_trade(_user),
        app_user_id=_user.id,
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
        rec_row = recommendation_repo.get_by_recommendation_uid(row.recommendation_id, app_user_id=_user.id)
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
                app_user_id=_user.id,
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
        rec_row = recommendation_repo.get_by_recommendation_uid(recommendation_id, app_user_id=_user.id)
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
            timeframe="1D",
        )

    if not rec.approved:
        raise HTTPException(status_code=409, detail=rec.rejection_reason or "Recommendation was no-trade; order not staged.")
    order_risk_calendar = risk_calendar_service.assess(symbol=rec.symbol, timeframe="1D")
    risk_confirmed = bool(req.get("risk_calendar_confirmed"))
    risk_override_reason = str(req.get("risk_calendar_override_reason") or "").strip()
    try:
        risk_calendar_service.assert_order_allowed(
            order_risk_calendar,
            confirmed=risk_confirmed,
            reason=risk_override_reason,
        )
    except RiskCalendarBlocked as exc:
        raise HTTPException(status_code=409, detail=f"risk_calendar_blocked:{exc}") from exc
    except RiskCalendarRestricted as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    sizing_plan = _paper_order_sizing_plan(
        rec,
        user=_user,
        override_shares=req.get("override_shares") if "override_shares" in req else None,
    )
    intent = recommendation_service.to_order_intent(rec).model_copy(
        update={"shares": int(sizing_plan["final_order_shares"])}
    )
    order, fill = paper_broker.execute(intent)
    sizing_note_parts = [
        "sizing_mode=risk_and_notional_capped",
        f"recommended_shares={sizing_plan['recommended_shares']}",
        f"final_order_shares={sizing_plan['final_order_shares']}",
        f"operator_override_shares={sizing_plan['operator_override_shares'] or ''}",
        f"max_paper_order_notional={sizing_plan['max_paper_order_notional']}",
        f"notional_cap_shares={sizing_plan['notional_cap_shares']}",
        f"estimated_notional={sizing_plan['estimated_notional']}",
        f"risk_at_stop={sizing_plan['risk_at_stop']}",
        f"notional_cap_reduced={str(bool(sizing_plan['notional_cap_reduced'])).lower()}",
        f"risk_calendar_state={order_risk_calendar.decision.decision_state}",
        f"risk_calendar_level={order_risk_calendar.decision.risk_level}",
        f"risk_calendar_confirmed={str(risk_confirmed).lower()}",
        f"risk_calendar_override_reason={risk_override_reason}",
    ]
    recommendation_service.persist_order(
        order,
        notes=(
            f"operator_staged_order|source={source}|fallback={str(fallback_mode).lower()}"
            f"|replay_run_id={replay_run_id or ''}|stageable_reason={stageable_reason or ''}"
            f"|{'|'.join(sizing_note_parts)}"
        ),
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
        "risk_calendar": order_risk_calendar.model_dump(mode="json"),
        **sizing_plan,
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
        "entry_notional": _round_money(float(row.quantity) * float(row.entry_price)),
        "exit_notional": _round_money(float(row.quantity) * float(row.exit_price)) if row.exit_price is not None else None,
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


def _finite_float(value: object) -> float | None:
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _finite_int(value: object) -> int | None:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed


def _iso_or_none(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _position_recommendation_row(position, *, app_user_id: int):
    recommendation_id = str(position.recommendation_id or "").strip()
    if not recommendation_id and position.order_id:
        order = order_repo.get_by_order_id(str(position.order_id), app_user_id=app_user_id)
        recommendation_id = str(order.recommendation_id or "").strip() if order else ""
    if not recommendation_id:
        return None
    row = recommendation_repo.get_by_recommendation_uid(recommendation_id)
    if row is None:
        return None
    if row.app_user_id not in {None, app_user_id}:
        return None
    return row


def _recover_position_levels(position, *, app_user_id: int) -> tuple[dict[str, float | None], str | None, dict[str, Any]]:
    row = _position_recommendation_row(position, app_user_id=app_user_id)
    payload: dict[str, Any] = dict(row.payload or {}) if row else {}
    invalidation = payload.get("invalidation") if isinstance(payload.get("invalidation"), dict) else {}
    targets = payload.get("targets") if isinstance(payload.get("targets"), dict) else {}
    levels = {
        "stop_price": _finite_float(invalidation.get("price")),
        "target_1": _finite_float(targets.get("target_1")),
        "target_2": _finite_float(targets.get("target_2")),
    }
    return levels, row.recommendation_id if row else None, payload


def _max_holding_days_from_payload(payload: dict[str, Any]) -> int | None:
    time_stop = payload.get("time_stop") if isinstance(payload.get("time_stop"), dict) else {}
    parsed = _finite_int(time_stop.get("max_holding_days"))
    return parsed if parsed is not None and parsed > 0 else None


def _days_held(opened_at: datetime | None, *, now: datetime) -> int | None:
    if opened_at is None:
        return None
    opened = opened_at if opened_at.tzinfo is not None else opened_at.replace(tzinfo=timezone.utc)
    return int(max(0.0, (now - opened).total_seconds()) // 86400)


def _holding_period_status(days_held: int | None, max_holding_days: int | None) -> str:
    if days_held is None or max_holding_days is None:
        return "unavailable"
    if days_held >= max_holding_days:
        return "exceeded"
    if days_held >= max(max_holding_days - 1, 0):
        return "warning"
    return "within_window"


def _safe_mark_as_of(value: datetime | None) -> str | None:
    if value is None:
        return None
    aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    # Some provider snapshot payloads omit a timestamp; lower-level adapters can
    # surface that as Unix epoch. Do not present that as an ancient live mark.
    if aware <= datetime(2001, 1, 1, tzinfo=timezone.utc):
        return None
    return aware.isoformat()


def _latest_position_mark(symbol: str) -> dict[str, object]:
    try:
        snapshot = market_data_service.latest_snapshot(symbol=symbol, timeframe="1D")
    except DataNotEntitledError:
        return {
            "current_mark_price": None,
            "market_data_source": "provider",
            "market_data_fallback_mode": False,
            "mark_as_of": None,
            "missing_data": ["current_mark_data_not_entitled"],
            "warnings": [f"Provider plan does not include current mark data for {symbol}."],
        }
    except SymbolNotFoundError:
        return {
            "current_mark_price": None,
            "market_data_source": "provider",
            "market_data_fallback_mode": False,
            "mark_as_of": None,
            "missing_data": ["current_mark_symbol_not_found"],
            "warnings": [f"No provider current mark was found for {symbol}."],
        }
    except Exception as exc:
        return {
            "current_mark_price": None,
            "market_data_source": "provider",
            "market_data_fallback_mode": False,
            "mark_as_of": None,
            "missing_data": ["current_mark_unavailable"],
            "warnings": [f"Current mark unavailable: {exc}"],
        }

    mark = _finite_float(snapshot.close)
    source = str(snapshot.source or "provider")
    fallback_mode = bool(snapshot.fallback_mode)
    missing_data: list[str] = []
    warnings: list[str] = []
    if mark is None or mark <= 0:
        missing_data.append("current_mark_price")
        mark = None
    if _provider_mark_is_required() and fallback_mode and not _workflow_allows_demo_fallback():
        missing_data.append("provider_backed_current_mark")
        warnings.append("Provider-backed market data is configured, so fallback current marks are not used for review.")
        mark = None
    return {
        "current_mark_price": mark,
        "market_data_source": source,
        "market_data_fallback_mode": fallback_mode,
        "mark_as_of": _safe_mark_as_of(snapshot.as_of),
        "missing_data": missing_data,
        "warnings": warnings,
    }


def _ranked_context_for_symbol(
    *,
    symbol: str,
    recent_rows: list,
) -> dict[str, object]:
    symbol_rows = [row for row in recent_rows if str(row.symbol or "").upper() == symbol.upper()]
    if not recent_rows:
        return {"current_recommendation_status": "unavailable", "current_rank": None, "current_recommendation_id": None}
    if not symbol_rows:
        return {"current_recommendation_status": "not_currently_ranked", "current_rank": None, "current_recommendation_id": None}

    row = symbol_rows[0]
    payload = dict(row.payload or {})
    workflow = payload.get("workflow") if isinstance(payload.get("workflow"), dict) else {}
    ranking = workflow.get("ranking_provenance") if isinstance(workflow.get("ranking_provenance"), dict) else {}
    rank = _finite_int(ranking.get("rank"))
    score = _finite_float(ranking.get("score"))
    status = str(ranking.get("status") or payload.get("outcome") or "").strip().lower()
    approved = bool(payload.get("approved", False))

    if rank == 1 or status == "top_candidate":
        recommendation_status = "top_candidate"
    elif rank is not None and rank <= 5 and status in {"top_candidate", "watchlist", "approved", ""}:
        recommendation_status = "still_ranked"
    elif status in {"no_trade", "rejected"} or not approved:
        recommendation_status = "weakened"
    elif rank is None:
        recommendation_status = "unavailable"
    else:
        recommendation_status = "weakened"

    return {
        "current_recommendation_status": recommendation_status,
        "current_rank": rank,
        "current_recommendation_id": row.recommendation_id,
        "current_recommendation_score": score,
    }


def _scale_in_blockers(
    *,
    quantity: float,
    average_entry_price: float,
    current_mark_price: float | None,
    stop_price: float | None,
    user,
    risk_calendar: RiskCalendarAssessment,
) -> list[str]:
    blockers: list[str] = []
    decision = risk_calendar.decision
    if not decision.allow_new_entries:
        blockers.append("risk_calendar_blocks_new_additions")
    if current_mark_price is None or current_mark_price <= 0:
        blockers.append("current_mark_unavailable")
        return blockers
    max_notional = _effective_paper_max_order_notional(user)
    current_notional = quantity * current_mark_price
    if current_notional + current_mark_price > max_notional:
        blockers.append("max_paper_order_notional_prevents_addition")
    if stop_price is None:
        blockers.append("stop_price_missing_for_incremental_risk")
    else:
        stop_distance = abs(average_entry_price - stop_price)
        if stop_distance <= 0:
            blockers.append("stop_distance_unusable_for_incremental_risk")
        else:
            current_risk = quantity * stop_distance
            if current_risk + stop_distance > _effective_risk_dollars(user):
                blockers.append("risk_budget_at_stop_prevents_addition")
    return blockers


def _classify_position_review(
    *,
    review_unavailable: bool,
    stop_triggered: bool,
    invalidated: bool,
    holding_period_status: str,
    target_reached: bool,
    current_recommendation_status: str,
    scale_in_candidate: bool,
) -> str:
    if review_unavailable:
        return "review_unavailable"
    if stop_triggered:
        return "stop_triggered"
    if invalidated:
        return "invalidated"
    if holding_period_status == "exceeded":
        return "time_stop_exit"
    if target_reached and current_recommendation_status in {"weakened", "not_currently_ranked", "unavailable"}:
        return "target_reached_take_profit"
    if target_reached:
        return "target_reached_hold"
    if scale_in_candidate:
        return "scale_in_candidate"
    if holding_period_status == "warning":
        return "time_stop_warning"
    return "hold_valid"


def _position_review_summary(action: str, symbol: str, warnings: list[str]) -> str:
    summaries = {
        "review_unavailable": f"{symbol} needs manual review because required mark or position data is missing.",
        "stop_triggered": f"{symbol} has crossed the recovered stop/invalidation level. Review only; no automatic exit is created.",
        "invalidated": f"{symbol} has contradictory deterministic context. Review the thesis before adding or holding.",
        "time_stop_exit": f"{symbol} is beyond the recovered max holding period. Review only; manual close remains operator-controlled.",
        "target_reached_take_profit": f"{symbol} reached a recovered target while current ranking support has weakened.",
        "target_reached_hold": f"{symbol} reached a recovered target and current deterministic context still supports holding or trailing.",
        "scale_in_candidate": f"{symbol} remains strongly ranked and risk/notional/calendar checks leave room for an explicit paper scale-in review.",
        "time_stop_warning": f"{symbol} is nearing the recovered max holding period.",
        "hold_valid": f"{symbol} remains inside recovered stop/target/time-stop context.",
    }
    base = summaries.get(action, summaries["review_unavailable"])
    if warnings:
        return f"{base} {warnings[0]}"
    return base


def _build_position_review(position, *, app_user_id: int, user, recent_rows: list, now: datetime) -> dict[str, object]:
    quantity = _finite_float(position.remaining_qty if position.remaining_qty is not None else position.quantity)
    average_entry_price = _finite_float(position.average_price)
    levels, recommendation_id, rec_payload = _recover_position_levels(position, app_user_id=app_user_id)
    max_holding_days = _max_holding_days_from_payload(rec_payload)
    days_held = _days_held(position.opened_at, now=now)
    holding_status = _holding_period_status(days_held, max_holding_days)
    mark_payload = _latest_position_mark(position.symbol)
    mark = _finite_float(mark_payload.get("current_mark_price"))
    risk_calendar = risk_calendar_service.assess(symbol=position.symbol, timeframe="1D")
    ranking_context = _ranked_context_for_symbol(symbol=position.symbol, recent_rows=recent_rows)

    warnings = list(mark_payload.get("warnings") or [])
    missing_data = list(mark_payload.get("missing_data") or [])
    if quantity is None or quantity <= 0:
        missing_data.append("quantity")
    if average_entry_price is None or average_entry_price <= 0:
        missing_data.append("average_entry_price")
    for key in ("stop_price", "target_1", "target_2"):
        if levels[key] is None:
            missing_data.append(key)
    if max_holding_days is None:
        missing_data.append("max_holding_days")
    if risk_calendar.decision.allow_new_entries is False:
        warnings.append("Risk calendar blocks or restricts new additions; it does not auto-close existing paper positions.")
    if risk_calendar.decision.missing_evidence:
        missing_data.extend(f"risk_calendar:{item}" for item in risk_calendar.decision.missing_evidence)
        warnings.append("Risk calendar evidence is incomplete for this holding.")

    direction = _trade_direction_multiplier(position.side)
    unrealized_pnl = None
    unrealized_return_pct = None
    estimated_current_notional = None
    entry_notional = None
    distance_to_stop_pct = None
    distance_to_target_1_pct = None
    distance_to_target_2_pct = None
    stop_triggered = False
    target_reached = False
    if quantity is not None and average_entry_price is not None:
        entry_notional = _round_money(quantity * average_entry_price)
    if quantity is not None and mark is not None:
        estimated_current_notional = _round_money(quantity * mark)
    if quantity is not None and average_entry_price is not None and mark is not None:
        unrealized_pnl = _round_money((mark - average_entry_price) * quantity * direction)
        unrealized_return_pct = round(((mark - average_entry_price) / average_entry_price) * direction * 100, 2) if average_entry_price > 0 else None
    if mark is not None and mark > 0:
        stop_price = levels["stop_price"]
        target_1 = levels["target_1"]
        target_2 = levels["target_2"]
        if stop_price is not None:
            distance_to_stop_pct = round(((mark - stop_price) * direction / mark) * 100, 2)
            stop_triggered = distance_to_stop_pct <= 0
        if target_1 is not None:
            distance_to_target_1_pct = round(((target_1 - mark) * direction / mark) * 100, 2)
            target_reached = target_reached or distance_to_target_1_pct <= 0
        if target_2 is not None:
            distance_to_target_2_pct = round(((target_2 - mark) * direction / mark) * 100, 2)
            target_reached = target_reached or distance_to_target_2_pct <= 0

    current_status = str(ranking_context["current_recommendation_status"])
    scale_blockers = _scale_in_blockers(
        quantity=float(quantity or 0.0),
        average_entry_price=float(average_entry_price or 0.0),
        current_mark_price=mark,
        stop_price=levels["stop_price"],
        user=user,
        risk_calendar=risk_calendar,
    )
    strong_rank = current_status == "top_candidate" or (
        current_status == "still_ranked" and isinstance(ranking_context.get("current_rank"), int) and int(ranking_context["current_rank"]) <= 3
    )
    profitable_or_valid = unrealized_pnl is not None and unrealized_pnl >= 0 and not stop_triggered
    scale_candidate = strong_rank and profitable_or_valid and not scale_blockers and not target_reached
    if strong_rank and profitable_or_valid and scale_blockers:
        warnings.append(f"Scale-in blocked: {', '.join(scale_blockers)}.")

    review_unavailable = "current_mark_price" in missing_data or "provider_backed_current_mark" in missing_data or quantity is None or average_entry_price is None
    invalidated = current_status == "weakened" and not target_reached
    action = _classify_position_review(
        review_unavailable=review_unavailable,
        stop_triggered=stop_triggered,
        invalidated=invalidated,
        holding_period_status=holding_status,
        target_reached=target_reached,
        current_recommendation_status=current_status,
        scale_in_candidate=scale_candidate,
    )

    workflow = rec_payload.get("workflow") if isinstance(rec_payload.get("workflow"), dict) else {}
    market_session_policy = workflow.get("session_policy") or "latest_snapshot"
    return {
        "position_id": position.id,
        "symbol": position.symbol,
        "side": position.side,
        "quantity": quantity,
        "average_entry_price": average_entry_price,
        "current_mark_price": mark,
        "market_data_source": mark_payload["market_data_source"],
        "market_data_fallback_mode": mark_payload["market_data_fallback_mode"],
        "mark_as_of": mark_payload["mark_as_of"],
        "market_session_policy": market_session_policy,
        "unrealized_pnl": unrealized_pnl,
        "unrealized_return_pct": unrealized_return_pct,
        "estimated_current_notional": estimated_current_notional,
        "entry_notional": entry_notional,
        "stop_price": levels["stop_price"],
        "target_1": levels["target_1"],
        "target_2": levels["target_2"],
        "distance_to_stop_pct": distance_to_stop_pct,
        "distance_to_target_1_pct": distance_to_target_1_pct,
        "distance_to_target_2_pct": distance_to_target_2_pct,
        "days_held": days_held,
        "max_holding_days": max_holding_days,
        "holding_period_status": holding_status,
        "risk_calendar": risk_calendar.model_dump(mode="json"),
        "current_recommendation_status": current_status,
        "current_rank": ranking_context.get("current_rank"),
        "current_recommendation_id": ranking_context.get("current_recommendation_id"),
        "already_open": True,
        "action_classification": action,
        "action_summary": _position_review_summary(action, position.symbol, warnings),
        "warnings": warnings,
        "missing_data": sorted(set(missing_data)),
        "provenance": {
            "position_source": "paper_positions",
            "level_source": "linked_recommendation" if recommendation_id else "unavailable",
            "recommendation_id": recommendation_id,
            "order_id": position.order_id,
            "replay_run_id": position.replay_run_id,
            "paper_only": True,
            "review_only": True,
            "no_automatic_exits": True,
            "no_broker_routing": True,
            "deterministic_engine_owns": ["action_classification", "risk_calendar", "position_sizing"],
            "reviewed_at": _iso_or_none(now),
        },
    }


_SUPPORTED_OPTION_REVIEW_STRATEGIES = {"long_call", "long_put", "vertical_debit_spread", "iron_condor"}
_SYNTHETIC_OPTION_NOT_FOUND_WARNING = (
    "Saved leg contract was not found by provider. This may be an older synthetic/generated strike. "
    "Create a fresh paper options structure after listed-contract resolution."
)


def _option_contract_resolution_required() -> bool:
    return bool(settings.polygon_enabled and settings.polygon_api_key.strip() and settings.polygon_base_url.strip())


def _option_asset_metadata(symbol: str) -> dict[str, str | None]:
    asset_type = option_underlying_asset_type(symbol)
    if asset_type == "index":
        return {
            "underlying_asset_type": "index",
            "settlement_style": "cash_settled",
            "deliverable_type": "cash_index",
        }
    if symbol.upper() in {"SPY", "QQQ", "IWM"}:
        return {"underlying_asset_type": "etf", "settlement_style": "physical", "deliverable_type": "shares"}
    return {"underlying_asset_type": "equity", "settlement_style": "physical", "deliverable_type": "shares"}


def _resolve_option_contract(symbol: str, expiration, right: str, target_strike: float):
    resolver = getattr(market_data_service, "resolve_option_contract", None)
    if not callable(resolver):
        return None
    try:
        return resolver(
            underlying_symbol=symbol,
            expiration=expiration,
            option_type=right,
            target_strike=target_strike,
        )
    except Exception:
        return None


def _resolved_contract_dict(resolution) -> dict[str, object]:
    if resolution is None:
        return {
            "resolved": False,
            "contract_selection_method": "provider_reference_unavailable",
            "unavailable_reason": "Listed option contract resolver is unavailable.",
        }
    as_dict = getattr(resolution, "as_dict", None)
    if callable(as_dict):
        return as_dict()
    return dict(resolution) if isinstance(resolution, dict) else {"resolved": False}


def _refresh_research_option_payoff(option_structure: dict[str, object], *, as_of: datetime) -> None:
    structure_type = str(option_structure.get("type") or "")
    legs = [leg for leg in option_structure.get("legs", []) if isinstance(leg, dict)]
    expiration = str(option_structure.get("expiration") or "")
    if expiration:
        option_structure["dte"] = calendar_days_to_expiration(expiration, as_of=as_of)
        option_structure["dte_as_of"] = as_of.isoformat()
    if structure_type == "iron_condor" and len(legs) == 4:
        puts = sorted([leg for leg in legs if leg.get("right") == "put"], key=lambda leg: float(leg.get("strike") or 0.0))
        calls = sorted([leg for leg in legs if leg.get("right") == "call"], key=lambda leg: float(leg.get("strike") or 0.0))
        credit = _finite_float(option_structure.get("net_credit"))
        if len(puts) == 2 and len(calls) == 2 and credit is not None:
            put_width = float(puts[1]["strike"]) - float(puts[0]["strike"])
            call_width = float(calls[1]["strike"]) - float(calls[0]["strike"])
            width = max(put_width, call_width)
            short_put = next((leg for leg in puts if leg.get("action") == "sell"), puts[1])
            short_call = next((leg for leg in calls if leg.get("action") == "sell"), calls[0])
            option_structure["max_profit"] = _round_money(credit * 100)
            option_structure["max_loss"] = _round_money((width - credit) * 100)
            option_structure["breakeven_low"] = _round_money(float(short_put["strike"]) - credit)
            option_structure["breakeven_high"] = _round_money(float(short_call["strike"]) + credit)
    elif structure_type in {"bull_call_debit_spread", "bear_put_debit_spread"} and len(legs) == 2:
        debit = _finite_float(option_structure.get("net_debit"))
        if debit is None:
            return
        strikes = sorted(float(leg.get("strike") or 0.0) for leg in legs)
        width = strikes[-1] - strikes[0]
        option_structure["max_profit"] = _round_money((width - debit) * 100)
        option_structure["max_loss"] = _round_money(debit * 100)
        if structure_type == "bull_call_debit_spread":
            option_structure["breakeven_high"] = _round_money(strikes[0] + debit)
        else:
            option_structure["breakeven_low"] = _round_money(strikes[-1] - debit)


def _apply_research_contract_resolution(symbol: str, option_structure: dict[str, object], *, as_of: datetime) -> dict[str, object]:
    required = _option_contract_resolution_required()
    expiration_raw = option_structure.get("expiration")
    try:
        expiration = datetime.fromisoformat(str(expiration_raw)).date()
    except (TypeError, ValueError):
        return option_structure
    legs = option_structure.get("legs")
    if not isinstance(legs, list) or not legs:
        return option_structure

    resolved_count = 0
    warnings: list[str] = []
    updated_legs: list[dict[str, object]] = []
    for raw_leg in legs:
        leg = dict(raw_leg) if isinstance(raw_leg, dict) else {}
        target_strike = _finite_float(leg.get("strike"))
        if target_strike is None:
            updated_legs.append(leg)
            continue
        resolution = _resolve_option_contract(symbol, expiration, str(leg.get("right") or ""), target_strike)
        selection = _resolved_contract_dict(resolution)
        if selection.get("resolved"):
            resolved_count += 1
            selected_strike = _finite_float(selection.get("selected_listed_strike"))
            selected_expiration = selection.get("selected_expiration")
            if selected_strike is not None:
                leg["strike"] = selected_strike
            if isinstance(selected_expiration, str) and selected_expiration:
                leg["expiration"] = selected_expiration
            leg["option_symbol"] = selection.get("provider_contract_symbol")
            leg["target_strike"] = target_strike
            leg["selected_listed_strike"] = selected_strike
            leg["strike_snap_distance"] = selection.get("strike_snap_distance")
            leg["contract_selection_method"] = selection.get("contract_selection_method")
            leg["contract_selection"] = selection
            warnings.extend(str(item) for item in selection.get("warnings") or [] if item)
        else:
            leg["target_strike"] = target_strike
            leg["contract_selection"] = selection
            if selection.get("unavailable_reason"):
                warnings.append(str(selection["unavailable_reason"]))
        updated_legs.append(leg)

    option_structure["legs"] = updated_legs
    if resolved_count == len(updated_legs):
        expirations = {
            str(leg.get("expiration"))
            for leg in updated_legs
            if isinstance(leg.get("expiration"), str) and str(leg.get("expiration")).strip()
        }
        if len(expirations) == 1:
            option_structure["expiration"] = next(iter(expirations))
        option_structure["contract_resolution_status"] = "resolved"
        option_structure["contract_resolution_summary"] = "Selected listed contracts from provider chain."
        option_structure["paper_persistence_allowed"] = True
        option_structure["contract_resolution_warnings"] = sorted(set(warnings))
        _refresh_research_option_payoff(option_structure, as_of=as_of)
    elif required:
        option_structure["contract_resolution_status"] = "unresolved"
        option_structure["contract_resolution_summary"] = "Unable to resolve listed contracts; paper position cannot be marked."
        option_structure["paper_persistence_allowed"] = False
        option_structure["contract_resolution_warnings"] = sorted(set(warnings))
    else:
        option_structure["contract_resolution_status"] = "unavailable"
        option_structure["contract_resolution_summary"] = "Listed contract resolution is unavailable in the current local provider mode."
        option_structure["paper_persistence_allowed"] = True
        option_structure["contract_resolution_warnings"] = sorted(set(warnings))
    return option_structure


def _resolve_paper_option_structure_contracts(req: OptionPaperStructureInput) -> OptionPaperStructureInput:
    if not _option_contract_resolution_required():
        return req
    resolved_legs = []
    failures: list[str] = []
    for leg in req.legs:
        target_strike = _finite_float(leg.target_strike if leg.target_strike is not None else leg.strike)
        if target_strike is None:
            failures.append("invalid_target_strike")
            continue
        resolution = _resolve_option_contract(req.underlying_symbol, leg.expiration, leg.right, target_strike)
        selection = _resolved_contract_dict(resolution)
        if not selection.get("resolved"):
            failures.append(str(selection.get("unavailable_reason") or "listed_option_contract_unresolved"))
            continue
        selected_strike = _finite_float(selection.get("selected_listed_strike"))
        selected_expiration = selection.get("selected_expiration")
        option_symbol = selection.get("provider_contract_symbol")
        if selected_strike is None or not isinstance(selected_expiration, str) or not option_symbol:
            failures.append("listed_option_contract_incomplete")
            continue
        resolved_legs.append(
            leg.model_copy(
                update={
                    "strike": selected_strike,
                    "expiration": datetime.fromisoformat(selected_expiration).date(),
                    "option_symbol": str(option_symbol),
                    "target_strike": target_strike,
                    "contract_selection": selection,
                }
            )
        )
    if failures or len(resolved_legs) != len(req.legs):
        raise OptionPaperContractError("listed_option_contract_resolution_required")
    expirations = {leg.expiration for leg in resolved_legs}
    resolved_expiration = next(iter(expirations)) if len(expirations) == 1 else req.expiration
    return req.model_copy(update={"legs": resolved_legs, "expiration": resolved_expiration})


def _option_leg_side(action: str | None) -> str:
    return "short" if str(action or "").strip().lower() == "sell" else "long"


def _option_structure_side(structure_type: str | None) -> str:
    normalized = str(structure_type or "").strip().lower()
    if normalized in {"long_call", "long_put", "vertical_debit_spread"}:
        return "long_debit"
    if normalized == "iron_condor":
        return "neutral_credit"
    return "unknown"


def _option_contract_count(legs: list) -> int | None:
    quantities = [_finite_int(getattr(leg, "quantity", None)) for leg in legs]
    safe_quantities = [quantity for quantity in quantities if quantity is not None and quantity > 0]
    if not safe_quantities:
        return None
    if len(set(safe_quantities)) == 1:
        return safe_quantities[0]
    return sum(safe_quantities)


def _option_multiplier_assumption(legs: list) -> int | None:
    multipliers = [_finite_int(getattr(leg, "multiplier", None)) for leg in legs]
    safe_multipliers = [multiplier for multiplier in multipliers if multiplier is not None and multiplier > 0]
    if not safe_multipliers:
        return None
    if len(set(safe_multipliers)) == 1:
        return safe_multipliers[0]
    return None


def _option_opening_debit_credit(position) -> tuple[float | None, str]:
    debit = _finite_float(getattr(position, "opening_net_debit", None))
    credit = _finite_float(getattr(position, "opening_net_credit", None))
    if debit is not None:
        return _round_money(debit), "debit"
    if credit is not None:
        return _round_money(credit), "credit"
    return None, "unknown"


def _option_current_debit_credit(legs: list[tuple[object, float]]) -> tuple[float | None, str]:
    if not legs:
        return None, "unknown"
    signed_total = 0.0
    for leg, mark in legs:
        side = str(getattr(leg, "action", "") or "").strip().lower()
        signed_total += mark if side == "buy" else -mark
    if signed_total >= 0:
        return _round_money(signed_total), "debit"
    return _round_money(abs(signed_total)), "credit"


def _option_event_commissions_for_legs(legs: list, *, commission_per_contract: float) -> float | None:
    if not legs:
        return None
    total = 0.0
    for leg in legs:
        quantity = _finite_int(getattr(leg, "quantity", None))
        if quantity is None or quantity < 0:
            return None
        total += quantity * commission_per_contract
    return _round_money(total)


def _option_leg_roundtrip_commission(leg, *, commission_per_contract: float) -> float | None:
    quantity = _finite_int(getattr(leg, "quantity", None))
    if quantity is None or quantity < 0:
        return None
    return _round_money(quantity * commission_per_contract * 2.0)


def _option_leg_unrealized_pnl(leg, *, current_mark: float, commission_per_contract: float) -> tuple[float | None, float | None]:
    entry = _finite_float(getattr(leg, "entry_premium", None))
    quantity = _finite_int(getattr(leg, "quantity", None))
    multiplier = _finite_int(getattr(leg, "multiplier", None))
    if entry is None or quantity is None or multiplier is None:
        return None, None
    direction = 1.0 if str(getattr(leg, "action", "") or "").strip().lower() == "buy" else -1.0
    gross = _round_money((current_mark - entry) * quantity * multiplier * direction)
    commission = _option_leg_roundtrip_commission(leg, commission_per_contract=commission_per_contract)
    net = _round_money(gross - commission) if gross is not None and commission is not None else None
    return gross, net


def _option_return_denominator(position, *, opening_debit_credit: float | None, contracts: int | None, multiplier: int | None) -> float | None:
    max_loss = _finite_float(getattr(position, "max_loss", None))
    if max_loss is not None and max_loss > 0:
        return max_loss
    if opening_debit_credit is not None and contracts is not None and multiplier is not None:
        value = opening_debit_credit * contracts * multiplier
        return value if value > 0 else None
    return None


def _option_snapshot_for_leg(symbol: str, leg):
    persisted_symbol = str(getattr(leg, "option_symbol", "") or "").strip().upper()
    option_symbol = persisted_symbol or build_polygon_option_ticker(
        underlying_symbol=symbol,
        expiration=leg.expiration,
        option_type=leg.right,
        strike=leg.strike,
    )
    snapshot_fn = getattr(market_data_service, "option_contract_snapshot", None)
    if not callable(snapshot_fn):
        return unavailable_option_contract_snapshot(
            underlying_symbol=symbol,
            option_symbol=option_symbol,
            provider="unavailable",
            missing_fields=["provider_option_snapshot_not_supported"],
        )
    try:
        return snapshot_fn(underlying_symbol=symbol, option_symbol=option_symbol)
    except Exception as exc:
        return unavailable_option_contract_snapshot(
            underlying_symbol=symbol,
            option_symbol=option_symbol,
            provider="provider",
            missing_fields=["provider_option_snapshot_unavailable"],
            provider_error=_sanitize_provider_error(exc),
        )


def _option_days_to_expiration(position, now: datetime) -> tuple[object | None, int | None]:
    expiration = getattr(position, "expiration", None)
    if expiration is None:
        legs = list(getattr(position, "legs", []) or [])
        expiration = getattr(legs[0], "expiration", None) if legs else None
    if expiration is None:
        return None, None
    return expiration, calendar_days_to_expiration(expiration, as_of=now, allow_expired_negative=True)


def _option_expiration_status(days_to_expiration: int | None) -> str:
    if days_to_expiration is None:
        return "expiration_unavailable"
    if days_to_expiration < 0:
        return "expired_unsettled"
    if days_to_expiration == 0:
        return "expires_today"
    if days_to_expiration <= 7:
        return "expiration_warning"
    return "active"


def _option_underlying_mark(symbol: str) -> dict[str, object]:
    payload = _latest_position_mark(symbol)
    mark = _finite_float(payload.get("current_mark_price"))
    source = str(payload.get("market_data_source") or "provider")
    fallback_mode = bool(payload.get("market_data_fallback_mode"))
    missing_data = list(payload.get("missing_data") or [])
    warnings = [_sanitize_provider_error(item) for item in list(payload.get("warnings") or [])]
    if fallback_mode:
        mark = None
        if "provider_backed_underlying_mark" not in missing_data:
            missing_data.append("provider_backed_underlying_mark")
        warnings.append("Provider-backed underlying mark is required for options expiration review and settlement.")
    return {
        "underlying_mark_price": mark,
        "underlying_mark_source": source,
        "underlying_mark_as_of": payload.get("mark_as_of"),
        "missing_data": missing_data,
        "warnings": warnings,
    }


def _option_intrinsic_value(*, right: str, strike: float, underlying_mark: float | None) -> float | None:
    if underlying_mark is None or underlying_mark <= 0:
        return None
    normalized_right = str(right or "").strip().lower()
    if normalized_right == "call":
        return _round_money(max(underlying_mark - float(strike), 0.0))
    if normalized_right == "put":
        return _round_money(max(float(strike) - underlying_mark, 0.0))
    return None


def _option_distance_to_strike_pct(*, strike: float, underlying_mark: float | None) -> float | None:
    if underlying_mark is None or underlying_mark <= 0:
        return None
    return round(((underlying_mark - float(strike)) / underlying_mark) * 100, 2)


def _option_moneyness(*, right: str, strike: float, underlying_mark: float | None) -> str:
    distance_pct = _option_distance_to_strike_pct(strike=strike, underlying_mark=underlying_mark)
    if distance_pct is None:
        return "unknown"
    if abs(distance_pct) <= 0.5:
        return "atm"
    normalized_right = str(right or "").strip().lower()
    if normalized_right == "call":
        return "itm" if underlying_mark is not None and underlying_mark > float(strike) else "otm"
    if normalized_right == "put":
        return "itm" if underlying_mark is not None and underlying_mark < float(strike) else "otm"
    return "unknown"


_OPTION_RISK_RANK = {"none": 0, "low": 1, "elevated": 2, "high": 3, "unknown": -1}


def _max_option_risk(values: list[str]) -> str:
    known = [value for value in values if value in _OPTION_RISK_RANK and value != "unknown"]
    if not known:
        return "unknown" if any(value == "unknown" for value in values) else "none"
    return max(known, key=lambda value: _OPTION_RISK_RANK[value])


def _is_option_snapshot_entitlement_error(value: object) -> bool:
    text = str(value or "").strip().lower()
    return any(token in text for token in ("not entitled", "entitlement", "permission", "not authorized"))


def _option_assignment_risk(*, side: str, moneyness: str, days_to_expiration: int | None) -> str:
    if side != "short":
        return "none"
    if moneyness == "unknown" or days_to_expiration is None:
        return "unknown"
    if moneyness == "itm":
        if days_to_expiration <= 0:
            return "high"
        if days_to_expiration <= 2:
            return "elevated"
        if days_to_expiration <= 7:
            return "low"
    if moneyness == "atm" and days_to_expiration <= 2:
        return "elevated"
    return "none"


def _option_exercise_risk(*, side: str, moneyness: str, days_to_expiration: int | None) -> str:
    if side != "long":
        return "none"
    if moneyness == "unknown" or days_to_expiration is None:
        return "unknown"
    if moneyness == "itm":
        if days_to_expiration <= 0:
            return "high"
        if days_to_expiration <= 2:
            return "elevated"
        if days_to_expiration <= 7:
            return "low"
    if moneyness == "atm" and days_to_expiration <= 2:
        return "low"
    return "none"


def _option_leg_gross_pnl_at_premium(leg, *, exit_premium: float) -> float | None:
    entry = _finite_float(getattr(leg, "entry_premium", None))
    quantity = _finite_int(getattr(leg, "quantity", None))
    multiplier = _finite_int(getattr(leg, "multiplier", None))
    if entry is None or quantity is None or multiplier is None:
        return None
    direction = 1.0 if str(getattr(leg, "action", "") or "").strip().lower() == "buy" else -1.0
    return _round_money((float(exit_premium) - entry) * quantity * multiplier * direction)


def _option_expiration_summary(
    *,
    expiration_status: str,
    assignment_risk: str,
    exercise_risk: str,
    settlement_available: bool,
    settlement_blocked: bool,
) -> str:
    if settlement_available:
        return "Expired paper structure can be manually settled from intrinsic value. Paper-only settlement; no broker action."
    if settlement_blocked:
        return "Expired paper structure needs a provider-backed underlying mark before paper settlement can be previewed or confirmed."
    if expiration_status == "expired_unsettled":
        return "Expired paper structure remains open and requires manual paper settlement review."
    if expiration_status == "expires_today":
        return "Structure expires today. Review ITM/OTM, assignment, and exercise risk; no automatic exercise or assignment occurs."
    if assignment_risk in {"elevated", "high"} or exercise_risk in {"elevated", "high"}:
        return "Near-expiration option risk is elevated. Review only; no automatic close, roll, exercise, or assignment occurs."
    if expiration_status == "expiration_warning":
        return "Structure is near expiration. Review time decay and event overlap; no automatic roll or adjustment occurs."
    return "Structure is not near expiration; continue normal paper review."


def _option_payoff_summary(position, opening_type: str) -> str:
    structure = str(getattr(position, "structure_type", "") or "option structure")
    if opening_type == "debit":
        return f"{structure} is a defined-risk debit paper structure using persisted payoff bounds."
    if opening_type == "credit":
        return f"{structure} is a defined-risk credit paper structure using persisted payoff bounds."
    return f"{structure} has persisted option legs, but opening debit/credit could not be recovered."


def _classify_option_structure_review(
    *,
    review_unavailable: bool,
    mark_unavailable: bool,
    expiration_status: str,
    expired_unsettled: bool,
    settlement_blocked_missing_underlying: bool,
    settlement_available: bool,
    assignment_risk_review: bool,
    exercise_risk_review: bool,
    max_loss_near: bool,
    max_profit_near: bool,
    close_candidate: bool,
    adjustment_review: bool,
    profitable: bool | None,
    losing: bool | None,
) -> str:
    if review_unavailable:
        return "review_unavailable"
    if mark_unavailable:
        return "mark_unavailable"
    if expired_unsettled:
        return "expired_unsettled"
    if settlement_blocked_missing_underlying:
        return "settlement_blocked_missing_underlying"
    if settlement_available:
        return "settlement_available"
    if expiration_status == "expires_today":
        return "expiration_due"
    if assignment_risk_review:
        return "assignment_risk_review"
    if exercise_risk_review:
        return "exercise_risk_review"
    if max_loss_near:
        return "max_loss_near"
    if max_profit_near:
        return "max_profit_near"
    if close_candidate:
        return "close_candidate"
    if adjustment_review:
        return "adjustment_review"
    if expiration_status == "expiration_warning":
        return "expiration_warning"
    if profitable:
        return "profitable_hold"
    if losing:
        return "losing_hold"
    return "hold_valid"


def _option_structure_review_summary(action: str, symbol: str, warnings: list[str]) -> str:
    summaries = {
        "review_unavailable": f"{symbol} options structure needs manual review because required lifecycle data is missing or unsupported.",
        "mark_unavailable": f"{symbol} options structure has no provider-backed option mark available; review is limited to opening, payoff, expiration, and risk-calendar context.",
        "expiration_warning": f"{symbol} options structure is nearing expiration. Review only; no roll or close is created.",
        "expiration_due": f"{symbol} options structure expires today. Review only; no exercise, assignment, roll, or close is automatic.",
        "expired_unsettled": f"{symbol} options structure is expired and still open. Manual paper settlement review is required.",
        "settlement_blocked_missing_underlying": f"{symbol} options structure is expired, but paper settlement is blocked until an underlying mark is available.",
        "settlement_available": f"{symbol} options structure is expired and has a paper-only settlement preview available. Manual confirmation is required.",
        "assignment_risk_review": f"{symbol} options structure has elevated short-leg assignment risk. Review only; no assignment is automated.",
        "exercise_risk_review": f"{symbol} options structure has elevated long-leg exercise risk. Review only; no exercise is automated.",
        "max_profit_near": f"{symbol} options structure is near persisted max profit. Review only; no automatic close is created.",
        "max_loss_near": f"{symbol} options structure is near persisted max loss. Review only; no automatic close is created.",
        "profitable_hold": f"{symbol} options structure is profitable on available marks and remains a hold review candidate.",
        "losing_hold": f"{symbol} options structure is losing on available marks but not otherwise invalidated by deterministic review.",
        "adjustment_review": f"{symbol} options structure needs human adjustment review only; no automatic adjustment is created.",
        "close_candidate": f"{symbol} options structure is a manual close review candidate. No close order is staged.",
        "hold_valid": f"{symbol} options structure has no deterministic review flags on available data.",
    }
    base = summaries.get(action, summaries["review_unavailable"])
    if warnings:
        return f"{base} {warnings[0]}"
    return base


def _build_option_paper_structure_review(position, *, user, now: datetime) -> OptionPaperStructureReview:
    legs = list(getattr(position, "legs", []) or [])
    structure_type = str(getattr(position, "structure_type", "") or "").strip().lower()
    symbol = str(getattr(position, "underlying_symbol", "") or "").upper()
    asset_metadata = _option_asset_metadata(symbol)
    is_index_option = asset_metadata["underlying_asset_type"] == "index"
    expiration, days_to_expiration = _option_days_to_expiration(position, now)
    expiration_status = _option_expiration_status(days_to_expiration)
    opening_debit_credit, opening_type = _option_opening_debit_credit(position)
    commission_per_contract = _effective_commission_per_contract(user)
    opening_commissions = _option_event_commissions_for_legs(
        legs,
        commission_per_contract=commission_per_contract,
    )
    contracts = _option_contract_count(legs)
    multiplier_assumption = _option_multiplier_assumption(legs)
    underlying_payload = _option_underlying_mark(symbol) if symbol else {
        "underlying_mark_price": None,
        "underlying_mark_source": None,
        "underlying_mark_as_of": None,
        "missing_data": ["underlying_symbol"],
        "warnings": [],
    }
    underlying_mark = _finite_float(underlying_payload.get("underlying_mark_price"))
    underlying_mark_missing = underlying_mark is None

    warnings: list[str] = []
    missing_data: list[str] = []
    if not legs:
        missing_data.append("option_legs")
    if structure_type not in _SUPPORTED_OPTION_REVIEW_STRATEGIES:
        missing_data.append("unsupported_strategy_type")
    if not symbol:
        missing_data.append("underlying_symbol")
    if expiration is None:
        missing_data.append("expiration_date")
    if opening_debit_credit is None:
        missing_data.append("opening_debit_credit")
    if opening_commissions is None:
        missing_data.append("opening_commissions")

    if expiration_status == "expiration_warning":
        warnings.append("Expiration is within seven calendar days; review time decay and event risk manually.")
    elif expiration_status == "expires_today":
        warnings.append("Structure expires today; assignment/exercise risk is informational and no exercise or assignment is automated.")
    elif expiration_status == "expired_unsettled":
        warnings.append("Structure is expired and still open; manual paper settlement review is required.")
    if expiration_status in {"expiration_warning", "expires_today", "expired_unsettled"}:
        missing_data.extend(underlying_payload.get("missing_data") or [])
        warnings.extend(underlying_payload.get("warnings") or [])
    if is_index_option:
        warnings.append("Index option research. Cash-settled. No share delivery modeled.")
        warnings.append("Paper-only. No exercise/assignment automation.")

    risk_calendar = risk_calendar_service.assess(symbol=symbol, timeframe="1D") if symbol else None
    if risk_calendar is not None:
        if risk_calendar.decision.allow_new_entries is False:
            warnings.append("Risk calendar blocks or restricts new option additions/adjustments; it does not auto-close existing paper structures.")
        if risk_calendar.decision.active_events:
            warnings.append("Risk calendar has active event exposure for this underlying.")
            if expiration_status in {"expiration_warning", "expires_today", "expired_unsettled"}:
                warnings.append("Earnings or macro event exposure overlaps with near-expiration option risk.")
        if risk_calendar.decision.missing_evidence:
            missing_data.extend(f"risk_calendar:{item}" for item in risk_calendar.decision.missing_evidence)
            warnings.append("Risk calendar evidence is incomplete for this underlying.")
    else:
        missing_data.append("risk_calendar")

    leg_reviews = []
    marked_legs: list[tuple[object, float]] = []
    settlement_legs: list[tuple[object, float, float | None]] = []
    leg_moneyness_values: list[str] = []
    assignment_risk_values: list[str] = []
    exercise_risk_values: list[str] = []
    entitlement_blocked_leg_count = 0
    not_found_leg_count = 0
    gross_pnl_total = 0.0
    net_pnl_total = 0.0
    all_leg_marks_available = bool(legs)
    any_stale_mark = False
    for leg in legs:
        snapshot = _option_snapshot_for_leg(symbol, leg) if symbol else unavailable_option_contract_snapshot(
            underlying_symbol=symbol,
            option_symbol="",
            provider="unavailable",
            missing_fields=["underlying_symbol"],
        )
        snapshot_missing = list(snapshot.missing_fields or [])
        mark = _finite_float(snapshot.mark_price)
        leg_net_pnl = None
        intrinsic_value = _option_intrinsic_value(
            right=str(getattr(leg, "right", "")),
            strike=float(getattr(leg, "strike", 0.0) or 0.0),
            underlying_mark=underlying_mark,
        )
        extrinsic_value = _round_money(mark - intrinsic_value) if mark is not None and intrinsic_value is not None and not snapshot.stale else None
        distance_to_strike_pct = _option_distance_to_strike_pct(
            strike=float(getattr(leg, "strike", 0.0) or 0.0),
            underlying_mark=underlying_mark,
        )
        moneyness = _option_moneyness(
            right=str(getattr(leg, "right", "")),
            strike=float(getattr(leg, "strike", 0.0) or 0.0),
            underlying_mark=underlying_mark,
        )
        side = _option_leg_side(leg.action)
        assignment_risk = _option_assignment_risk(
            side=side,
            moneyness=moneyness,
            days_to_expiration=days_to_expiration,
        )
        exercise_risk = _option_exercise_risk(
            side=side,
            moneyness=moneyness,
            days_to_expiration=days_to_expiration,
        )
        leg_moneyness_values.append(moneyness)
        assignment_risk_values.append(assignment_risk)
        exercise_risk_values.append(exercise_risk)
        if intrinsic_value is not None:
            settlement_legs.append(
                (
                    leg,
                    intrinsic_value,
                    _option_leg_gross_pnl_at_premium(leg, exit_premium=intrinsic_value),
                )
            )
        if snapshot.stale:
            any_stale_mark = True
            if "stale_option_mark" not in snapshot_missing:
                snapshot_missing.append("stale_option_mark")
        if mark is None or snapshot.mark_method == "unavailable" or snapshot.stale:
            all_leg_marks_available = False
            if "option_mark_data" not in snapshot_missing and mark is None:
                snapshot_missing.append("option_mark_data")
            if "provider_option_snapshot_not_found" in snapshot_missing:
                not_found_leg_count += 1
        else:
            gross_leg, net_leg = _option_leg_unrealized_pnl(
                leg,
                current_mark=mark,
                commission_per_contract=commission_per_contract,
            )
            if gross_leg is None or net_leg is None:
                all_leg_marks_available = False
                snapshot_missing.append("leg_pnl_inputs")
            else:
                next_gross = _round_money(gross_pnl_total + gross_leg)
                next_net = _round_money(net_pnl_total + net_leg)
                gross_pnl_total = next_gross if next_gross is not None else gross_pnl_total
                net_pnl_total = next_net if next_net is not None else net_pnl_total
                leg_net_pnl = net_leg
                marked_legs.append((leg, mark))
        if snapshot.provider_error:
            if _is_option_snapshot_entitlement_error(snapshot.provider_error):
                entitlement_blocked_leg_count += 1
            elif "provider_option_snapshot_not_found" not in snapshot_missing:
                warnings.append(f"Option mark unavailable for leg {leg.id}: {_sanitize_provider_error(snapshot.provider_error)}")
        contract_selection = getattr(leg, "contract_selection", None) or {}
        leg_reviews.append(
            {
                "leg_id": leg.id,
                "option_symbol": snapshot.option_symbol or None,
                "underlying_symbol": symbol,
                "expiration": leg.expiration,
                "option_type": str(leg.right).lower(),
                "strike": leg.strike,
                "side": side,
                "contracts": leg.quantity,
                "opening_premium": leg.entry_premium,
                "current_mark_premium": mark,
                "mark_method": snapshot.mark_method,
                "implied_volatility": snapshot.implied_volatility,
                "open_interest": snapshot.open_interest,
                "delta": snapshot.delta,
                "gamma": snapshot.gamma,
                "theta": snapshot.theta,
                "vega": snapshot.vega,
                "underlying_price": snapshot.underlying_price,
                "estimated_leg_unrealized_pnl": leg_net_pnl,
                "intrinsic_value": intrinsic_value,
                "extrinsic_value": extrinsic_value,
                "moneyness": moneyness,
                "distance_to_strike_pct": distance_to_strike_pct,
                "assignment_risk": assignment_risk,
                "exercise_risk": exercise_risk,
                "market_data_source": snapshot.provider,
                "market_data_fallback_mode": bool(snapshot.fallback_mode),
                "mark_as_of": _safe_mark_as_of(snapshot.as_of),
                "stale": bool(snapshot.stale),
                "missing_data": sorted(set(snapshot_missing)),
                "target_strike": getattr(leg, "target_strike", None),
                "selected_listed_strike": contract_selection.get("selected_listed_strike"),
                "strike_snap_distance": contract_selection.get("strike_snap_distance"),
                "contract_selection_method": contract_selection.get("contract_selection_method"),
            }
        )

    if entitlement_blocked_leg_count:
        warnings.append(
            "Option marks unavailable: provider plan is not entitled to option snapshot data. "
            f"{entitlement_blocked_leg_count} leg{'s' if entitlement_blocked_leg_count != 1 else ''} affected."
        )
    if not_found_leg_count:
        warnings.append(_SYNTHETIC_OPTION_NOT_FOUND_WARNING)

    if not all_leg_marks_available:
        missing_data.append("option_mark_data")
        if any_stale_mark:
            missing_data.append("stale_option_mark")
        warnings.append("One or more option leg marks are unavailable or stale; structure-level mark and P&L are not computed.")

    current_mark_debit_credit = None
    current_mark_debit_credit_type = "unknown"
    estimated_gross_pnl = None
    estimated_net_pnl = None
    estimated_return_pct = None
    estimated_closing_commissions = None
    estimated_total_commissions = None
    if all_leg_marks_available:
        current_mark_debit_credit, current_mark_debit_credit_type = _option_current_debit_credit(marked_legs)
        estimated_gross_pnl = _round_money(gross_pnl_total)
        estimated_net_pnl = _round_money(net_pnl_total)
        estimated_closing_commissions = opening_commissions
        estimated_total_commissions = _round_money((opening_commissions or 0.0) * 2.0) if opening_commissions is not None else None
        denominator = _option_return_denominator(
            position,
            opening_debit_credit=opening_debit_credit,
            contracts=contracts,
            multiplier=multiplier_assumption,
        )
        if estimated_net_pnl is not None and denominator is not None and denominator > 0:
            estimated_return_pct = round((estimated_net_pnl / denominator) * 100, 2)

    moneyness_counts = {key: leg_moneyness_values.count(key) for key in ("itm", "atm", "otm", "unknown")}
    itm_otm_summary = (
        f"{moneyness_counts['itm']} ITM, {moneyness_counts['atm']} ATM, {moneyness_counts['otm']} OTM"
        if underlying_mark is not None
        else "Moneyness unavailable because underlying mark is missing."
    )
    assignment_risk_level = _max_option_risk(assignment_risk_values)
    exercise_risk_level = _max_option_risk(exercise_risk_values)
    if is_index_option:
        assignment_risk_summary = (
            f"Highest short-leg cash-settlement risk: {assignment_risk_level}. Informational only; no share delivery is modeled."
        )
        exercise_risk_summary = (
            f"Highest long-leg cash-settlement risk: {exercise_risk_level}. Informational only; no live exercise is modeled."
        )
    else:
        assignment_risk_summary = (
            f"Highest short-leg assignment risk: {assignment_risk_level}. Informational only; no assignment is automated."
        )
        exercise_risk_summary = (
            f"Highest long-leg exercise risk: {exercise_risk_level}. Informational only; no exercise is automated."
        )

    max_profit = _round_money(_finite_float(position.max_profit))
    max_loss = _round_money(_finite_float(position.max_loss))
    settlement_required = expiration_status == "expired_unsettled"
    settlement_blocked_missing_underlying = bool(settlement_required and underlying_mark_missing)
    settlement_preview = None
    settlement_available = False
    if settlement_required and not settlement_blocked_missing_underlying:
        if len(settlement_legs) != len(legs):
            missing_data.append("settlement_leg_inputs")
        elif opening_commissions is None:
            missing_data.append("opening_commissions")
        else:
            settlement_available = True
            settlement_mark, settlement_mark_type = _option_current_debit_credit(
                [(leg, intrinsic) for leg, intrinsic, _gross in settlement_legs]
            )
            gross_values = [gross for _leg, _intrinsic, gross in settlement_legs if gross is not None]
            gross_settlement_pnl = _round_money(sum(gross_values)) if len(gross_values) == len(settlement_legs) else None
            closing_commissions = opening_commissions
            total_commissions = _round_money(opening_commissions + closing_commissions)
            net_realized_pnl_estimate = (
                _round_money(gross_settlement_pnl - total_commissions)
                if gross_settlement_pnl is not None and total_commissions is not None
                else None
            )
            leg_previews = []
            for leg, intrinsic, leg_gross in settlement_legs:
                leg_commission = _option_leg_roundtrip_commission(leg, commission_per_contract=commission_per_contract)
                leg_net = _round_money(leg_gross - leg_commission) if leg_gross is not None and leg_commission is not None else None
                outcome = "flat"
                if leg_gross is not None and leg_gross > 0:
                    outcome = "winning"
                elif leg_gross is not None and leg_gross < 0:
                    outcome = "losing"
                leg_previews.append(
                    {
                        "leg_id": leg.id,
                        "settlement_premium": intrinsic,
                        "leg_gross_pnl": leg_gross,
                        "leg_commission": leg_commission,
                        "leg_net_pnl": leg_net,
                        "outcome": outcome,
                    }
                )
            comparison = "inside_payoff_range"
            if gross_settlement_pnl is not None and max_profit is not None and max_profit > 0 and gross_settlement_pnl >= max_profit * 0.95:
                comparison = "near_or_at_max_profit"
            elif gross_settlement_pnl is not None and max_loss is not None and max_loss > 0 and gross_settlement_pnl <= -max_loss * 0.95:
                comparison = "near_or_at_max_loss"
            settlement_preview = {
                "paper_only": True,
                "requires_confirmation": True,
                "underlying_settlement_price": underlying_mark,
                "underlying_mark_source": underlying_payload.get("underlying_mark_source"),
                "underlying_mark_as_of": underlying_payload.get("underlying_mark_as_of"),
                "settlement_mark_debit_credit": settlement_mark,
                "settlement_mark_debit_credit_type": settlement_mark_type,
                "gross_settlement_value": settlement_mark,
                "gross_settlement_pnl": gross_settlement_pnl,
                "closing_commissions": closing_commissions,
                "total_commissions": total_commissions,
                "net_realized_pnl_estimate": net_realized_pnl_estimate,
                "winning_leg_ids": [item["leg_id"] for item in leg_previews if item["outcome"] == "winning"],
                "losing_leg_ids": [item["leg_id"] for item in leg_previews if item["outcome"] == "losing"],
                "max_profit_loss_comparison": comparison,
                "legs": leg_previews,
                "operator_disclaimer": "Paper-only expiration settlement preview. No broker action, exercise, assignment, or live order.",
            }
    if settlement_blocked_missing_underlying:
        missing_data.append("underlying_mark_price")

    expiration_action_summary = _option_expiration_summary(
        expiration_status=expiration_status,
        assignment_risk=assignment_risk_level,
        exercise_risk=exercise_risk_level,
        settlement_available=settlement_available,
        settlement_blocked=settlement_blocked_missing_underlying,
    )
    if is_index_option:
        if settlement_available:
            expiration_action_summary = "Expired index option paper structure can be manually cash-settled from intrinsic value. Paper-only settlement; no broker action."
        elif expiration_status in {"expires_today", "expiration_warning", "expired_unsettled"}:
            expiration_action_summary = "Index option expiration risk is cash-settlement review only. No share delivery, exercise automation, assignment automation, roll, or broker action occurs."
    max_profit_near = estimated_net_pnl is not None and max_profit is not None and max_profit > 0 and estimated_net_pnl >= max_profit * 0.9
    max_loss_near = estimated_net_pnl is not None and max_loss is not None and max_loss > 0 and estimated_net_pnl <= -max_loss * 0.9
    profitable = estimated_net_pnl is not None and estimated_net_pnl > 0
    losing = estimated_net_pnl is not None and estimated_net_pnl < 0
    close_candidate = profitable and days_to_expiration is not None and 0 < days_to_expiration <= 3
    adjustment_review = losing and risk_calendar is not None and risk_calendar.decision.allow_new_entries is False
    assignment_risk_review = assignment_risk_level in {"elevated", "high"}
    exercise_risk_review = exercise_risk_level in {"elevated", "high"}
    review_unavailable = bool({"option_legs", "unsupported_strategy_type", "underlying_symbol"}.intersection(missing_data))
    mark_unavailable_for_action = (
        not all_leg_marks_available
        and expiration_status not in {"expires_today", "expired_unsettled"}
        and not assignment_risk_review
        and not exercise_risk_review
    )
    action = _classify_option_structure_review(
        review_unavailable=review_unavailable,
        mark_unavailable=mark_unavailable_for_action,
        expiration_status=expiration_status,
        expired_unsettled=bool(settlement_required and not settlement_available and not settlement_blocked_missing_underlying),
        settlement_blocked_missing_underlying=settlement_blocked_missing_underlying,
        settlement_available=settlement_available,
        assignment_risk_review=assignment_risk_review,
        exercise_risk_review=exercise_risk_review,
        max_loss_near=max_loss_near,
        max_profit_near=max_profit_near,
        close_candidate=bool(close_candidate),
        adjustment_review=bool(adjustment_review),
        profitable=profitable,
        losing=losing,
    )
    action_summary = _option_structure_review_summary(action, symbol or "Option", warnings)
    if is_index_option and action in {"assignment_risk_review", "exercise_risk_review", "expiration_due"}:
        action_summary = (
            f"{symbol} index option structure needs cash-settlement expiration review. "
            "Paper-only; no share delivery, live exercise, assignment, roll, or broker order is automated."
        )

    return OptionPaperStructureReview(
        structure_id=position.id,
        underlying_symbol=symbol,
        underlying_asset_type=str(asset_metadata["underlying_asset_type"] or "unknown"),
        settlement_style=asset_metadata["settlement_style"],
        deliverable_type=asset_metadata["deliverable_type"],
        strategy_type=structure_type or "unknown",
        side=_option_structure_side(structure_type),
        opened_at=position.opened_at,
        expiration_date=expiration,
        days_to_expiration=days_to_expiration,
        contracts=contracts,
        quantity=contracts,
        multiplier_assumption=multiplier_assumption,
        opening_debit_credit=opening_debit_credit,
        opening_debit_credit_type=opening_type,
        opening_commissions=opening_commissions,
        current_mark_debit_credit=current_mark_debit_credit,
        current_mark_debit_credit_type=current_mark_debit_credit_type,
        estimated_unrealized_gross_pnl=estimated_gross_pnl,
        estimated_closing_commissions=estimated_closing_commissions,
        estimated_total_commissions=estimated_total_commissions,
        estimated_unrealized_pnl=estimated_net_pnl,
        estimated_unrealized_return_pct=estimated_return_pct,
        max_profit=max_profit,
        max_loss=max_loss,
        breakevens=list(position.breakevens or []),
        payoff_summary=_option_payoff_summary(position, opening_type),
        risk_calendar=risk_calendar.model_dump(mode="json") if risk_calendar is not None else {},
        underlying_mark_price=underlying_mark,
        underlying_mark_source=underlying_payload.get("underlying_mark_source"),
        underlying_mark_as_of=underlying_payload.get("underlying_mark_as_of"),
        itm_otm_summary=itm_otm_summary,
        assignment_risk_summary=assignment_risk_summary,
        exercise_risk_summary=exercise_risk_summary,
        expiration_action_summary=expiration_action_summary,
        settlement_available=settlement_available,
        settlement_required=settlement_required,
        settlement_preview=settlement_preview,
        expiration_status=expiration_status,
        action_classification=action,
        action_summary=action_summary,
        warnings=warnings,
        missing_data=sorted(set(missing_data)),
        provenance={
            "position_source": "paper_option_positions",
            "leg_source": "paper_option_position_legs",
            "valuation_source": "provider_option_snapshots" if all_leg_marks_available else "option_marks_partial_or_unavailable",
            "provider_option_marks_available": bool(all_leg_marks_available),
            "fallback_option_marks_used": False,
            "payoff_source": "persisted_option_payoff_fields",
            "commission_source": "current_user_commission_per_contract",
            "paper_only": True,
            "review_only": True,
            "no_live_trading": True,
            "no_broker_routing": True,
            "no_automatic_exits": True,
            "no_automatic_rolling": True,
            "no_automatic_adjustment": True,
            "deterministic_engine_owns": ["action_classification", "risk_calendar", "payoff_context"],
            "reviewed_at": _iso_or_none(now),
            "underlying_asset_type": asset_metadata["underlying_asset_type"],
            "settlement_style": asset_metadata["settlement_style"],
            "deliverable_type": asset_metadata["deliverable_type"],
        },
        legs=leg_reviews,
    )


def _already_open_default_context() -> dict[str, object]:
    return {
        "already_open": False,
        "open_position_id": None,
        "open_position_quantity": None,
        "open_position_average_entry": None,
        "active_review_action_classification": None,
        "active_review_summary": None,
        "open_position_review_path": "/orders#active-position-review",
    }


def _already_open_context(symbol: object, open_context_by_symbol: dict[str, dict[str, object]]) -> dict[str, object]:
    normalized = str(symbol or "").upper()
    context = open_context_by_symbol.get(normalized)
    if context is None:
        return _already_open_default_context()
    return {**_already_open_default_context(), **context}


def _open_paper_position_context_by_symbol(
    *,
    app_user_id: int,
    user,
    recent_rows: list | None = None,
    include_review: bool = True,
) -> dict[str, dict[str, object]]:
    rows = paper_portfolio_repo.list_positions(app_user_id=app_user_id, status="open", limit=100)
    if not rows:
        return {}

    review_rows = recent_rows
    if include_review and review_rows is None:
        review_rows = recommendation_repo.list_recent(limit=100, app_user_id=app_user_id)
    now = utc_now()
    context_by_symbol: dict[str, dict[str, object]] = {}
    for position in rows:
        symbol = str(position.symbol or "").upper()
        if not symbol or symbol in context_by_symbol:
            continue
        quantity = _finite_float(position.remaining_qty if position.remaining_qty is not None else position.quantity)
        average_entry = _finite_float(position.average_price)
        context: dict[str, object] = {
            "already_open": True,
            "open_position_id": position.id,
            "open_position_quantity": quantity,
            "open_position_average_entry": average_entry,
            "active_review_action_classification": None,
            "active_review_summary": None,
            "open_position_review_path": "/orders#active-position-review",
        }
        if include_review:
            try:
                review = _build_position_review(
                    position,
                    app_user_id=app_user_id,
                    user=user,
                    recent_rows=review_rows or [],
                    now=now,
                )
            except Exception:
                review = {}
            context["active_review_action_classification"] = review.get("action_classification")
            context["active_review_summary"] = review.get("action_summary")
        context_by_symbol[symbol] = context
    return context_by_symbol


@user_router.get("/paper-positions/review")
def review_paper_positions(_user=Depends(require_approved_user)):
    rows = paper_portfolio_repo.list_positions(app_user_id=_user.id, status="open", limit=100)
    recent_rows = recommendation_repo.list_recent(limit=100, app_user_id=_user.id)
    now = utc_now()
    return [
        _build_position_review(position, app_user_id=_user.id, user=_user, recent_rows=recent_rows, now=now)
        for position in rows
    ]


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


@user_router.post("/paper/reset")
def reset_paper_sandbox(req: dict[str, object], _user=Depends(require_approved_user)):
    if str(req.get("confirmation") or "").strip() != "RESET":
        raise HTTPException(status_code=400, detail="Type RESET to confirm paper sandbox reset.")
    counts = paper_portfolio_repo.reset_equity_paper_for_user(app_user_id=_user.id)
    _record_audit_event(
        recommendation_id="",
        payload={
            "event": "paper_sandbox_reset",
            "paper_only": True,
            "scope": "equity_paper_current_user",
            "app_user_id": _user.id,
            "counts": counts,
        },
    )
    return {"status": "reset", "counts": counts}


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

    bars, source, fallback_mode = _workflow_bars(symbol, limit=120, timeframe=timeframe)
    session_metadata = _workflow_session_metadata(bars, timeframe=timeframe)

    latest = bars[-1]
    prior = bars[-2] if len(bars) > 1 else bars[-1]
    analysis_as_of = utc_now()

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
        "session_policy": session_metadata.get("session_policy"),
        "data_quality": {
            "session_policy": session_metadata.get("session_policy"),
            "source_session_policy": session_metadata.get("source_session_policy"),
            "source_timeframe": session_metadata.get("source_timeframe"),
            "output_timeframe": session_metadata.get("output_timeframe"),
            "filtered_extended_hours_count": session_metadata.get("filtered_extended_hours_count"),
            "rth_bucket_count": session_metadata.get("rth_bucket_count"),
        },
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
        expiration_context = _options_research_expiration_context(expiration="2026-05-16", as_of=analysis_as_of)
        short_put = round(latest.close * 0.955, 2)
        long_put = round(latest.close * 0.930, 2)
        short_call = round(latest.close * 1.045, 2)
        long_call = round(latest.close * 1.070, 2)
        net_credit = round(latest.close * 0.0067, 2)
        width = round(short_put - long_put, 2)
        option_structure = {
            "type": "iron_condor",
            "expiration": expiration_context["expiration"],
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
            "dte": expiration_context["dte"],
            "dte_policy": expiration_context["dte_policy"],
            "dte_as_of": expiration_context["as_of"],
            "iv_snapshot": iv_snapshot,
            "theta_context": 0.07,
            "vega_context": -0.11,
            "event_blockers": ["Avoid binary events inside 7 DTE window", "Review earnings/macro event calendar"],
        }
        option_structure = _apply_research_contract_resolution(symbol, option_structure, as_of=analysis_as_of)
        payload["option_structure"] = option_structure
        payload["expected_range"] = _build_options_expected_range(
            latest_close=latest.close,
            iv_snapshot=iv_snapshot,
            dte=option_structure["dte"],
            as_of=analysis_as_of,
        ).model_dump(mode="json")
    elif market_mode == MarketMode.OPTIONS and strategy_entry.strategy_id == "bull_call_debit_spread":
        iv_snapshot = 0.25
        expiration_context = _options_research_expiration_context(expiration="2026-05-16", as_of=analysis_as_of)
        long_call = round(latest.close * 1.02, 2)
        short_call = round(latest.close * 1.06, 2)
        debit = round(latest.close * 0.012, 2)
        width = round(short_call - long_call, 2)
        option_structure = {
            "type": "bull_call_debit_spread",
            "expiration": expiration_context["expiration"],
            "legs": [
                {"action": "buy", "right": "call", "strike": long_call, "label": "long call"},
                {"action": "sell", "right": "call", "strike": short_call, "label": "short call"},
            ],
            "net_debit": debit,
            "max_profit": round((width - debit) * 100, 2),
            "max_loss": round(debit * 100, 2),
            "breakeven_high": round(long_call + debit, 2),
            "dte": expiration_context["dte"],
            "dte_policy": expiration_context["dte_policy"],
            "dte_as_of": expiration_context["as_of"],
            "iv_snapshot": iv_snapshot,
        }
        option_structure = _apply_research_contract_resolution(symbol, option_structure, as_of=analysis_as_of)
        payload["option_structure"] = option_structure
        payload["expected_range"] = _build_options_expected_range(
            latest_close=latest.close,
            iv_snapshot=iv_snapshot,
            dte=option_structure["dte"],
            as_of=analysis_as_of,
        ).model_dump(mode="json")
    elif market_mode == MarketMode.OPTIONS and strategy_entry.strategy_id == "bear_put_debit_spread":
        iv_snapshot = 0.25
        expiration_context = _options_research_expiration_context(expiration="2026-05-16", as_of=analysis_as_of)
        long_put = round(latest.close * 0.98, 2)
        short_put = round(latest.close * 0.94, 2)
        debit = round(latest.close * 0.012, 2)
        width = round(long_put - short_put, 2)
        option_structure = {
            "type": "bear_put_debit_spread",
            "expiration": expiration_context["expiration"],
            "legs": [
                {"action": "buy", "right": "put", "strike": long_put, "label": "long put"},
                {"action": "sell", "right": "put", "strike": short_put, "label": "short put"},
            ],
            "net_debit": debit,
            "max_profit": round((width - debit) * 100, 2),
            "max_loss": round(debit * 100, 2),
            "breakeven_low": round(long_put - debit, 2),
            "dte": expiration_context["dte"],
            "dte_policy": expiration_context["dte_policy"],
            "dte_as_of": expiration_context["as_of"],
            "iv_snapshot": iv_snapshot,
        }
        option_structure = _apply_research_contract_resolution(symbol, option_structure, as_of=analysis_as_of)
        payload["option_structure"] = option_structure
        payload["expected_range"] = _build_options_expected_range(
            latest_close=latest.close,
            iv_snapshot=iv_snapshot,
            dte=option_structure["dte"],
            as_of=analysis_as_of,
        ).model_dump(mode="json")
    elif market_mode == MarketMode.OPTIONS:
        # Covered Call requires inventory modeling — expected range omitted pending that data
        payload["expected_range"] = ExpectedRange(
            status="omitted",
            reason="strategy_not_configured_for_expected_range_preview",
            horizon_value=calendar_days_to_expiration("2026-05-16", as_of=analysis_as_of) or 0,
            horizon_unit="calendar_days",
            reference_price_type="underlying_last",
            snapshot_timestamp=analysis_as_of,
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


def _symbol_preview_values(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list | tuple | set):
        return [str(item) for item in value]
    return [str(value)]


def _normalized_symbols_and_duplicates(values: list[str]) -> tuple[list[str], int]:
    output: list[str] = []
    seen: set[str] = set()
    duplicates = 0
    for raw in values:
        for token in str(raw).replace(",", " ").split():
            normalized = symbol_universe_repo.normalize_symbol(token)
            if normalized is None:
                continue
            if normalized in seen:
                duplicates += 1
                continue
            seen.add(normalized)
            output.append(normalized)
    return output, duplicates


def _symbol_preview_watchlist_ids(req: dict[str, object]) -> list[int]:
    values: list[object] = []
    if req.get("watchlist_id") is not None:
        values.append(req["watchlist_id"])
    raw_ids = req.get("watchlist_ids")
    if isinstance(raw_ids, list | tuple | set):
        values.extend(raw_ids)
    elif raw_ids is not None:
        values.append(raw_ids)

    output: list[int] = []
    seen: set[int] = set()
    for value in values:
        try:
            watchlist_id = int(value)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="watchlist_id must be numeric")
        if watchlist_id <= 0:
            raise HTTPException(status_code=400, detail="watchlist_id must be positive")
        if watchlist_id not in seen:
            seen.add(watchlist_id)
            output.append(watchlist_id)
    return output


def _symbol_preview_source_label(source_type: str, watchlist_names: list[str]) -> str:
    if source_type == "manual":
        return "Manual symbols"
    if source_type == "watchlist":
        return f"Watchlist: {watchlist_names[0]}" if watchlist_names else "Watchlist"
    if source_type == "watchlist_plus_manual":
        return f"Watchlist plus manual: {', '.join(watchlist_names)}" if watchlist_names else "Watchlist plus manual"
    if source_type == "all_active":
        return "All active user symbols"
    return "Mixed symbol universe"


@user_router.post("/symbol-universe/preview")
def preview_symbol_universe(req: dict[str, object], user=Depends(require_approved_user)):
    source_type = str(req.get("source_type") or "manual").strip().lower()
    allowed_source_types = {"manual", "watchlist", "watchlist_plus_manual", "all_active", "mixed"}
    if source_type not in allowed_source_types:
        raise HTTPException(status_code=400, detail="unsupported_symbol_universe_source_type")
    if req.get("tags") or req.get("groups") or source_type == "tags":
        raise HTTPException(status_code=400, detail="symbol_tags_not_yet_supported")

    manual_values = _symbol_preview_values(req.get("manual_symbols") or req.get("symbols"))
    pinned_values = _symbol_preview_values(req.get("pinned_symbols"))
    excluded_values = _symbol_preview_values(req.get("excluded_symbols") or req.get("exclusions"))
    _, manual_duplicate_count = _normalized_symbols_and_duplicates(manual_values)
    normalized_pinned, pinned_duplicate_count = _normalized_symbols_and_duplicates(pinned_values)
    _, excluded_duplicate_count = _normalized_symbols_and_duplicates(excluded_values)

    watchlist_ids = _symbol_preview_watchlist_ids(req)
    if source_type in {"watchlist", "watchlist_plus_manual"} and not watchlist_ids:
        raise HTTPException(status_code=400, detail="watchlist_id_required")

    watchlist_names: list[str] = []
    for watchlist_id in watchlist_ids:
        watchlist = watchlist_repo.get_for_user(watchlist_id=watchlist_id, app_user_id=user.id)
        if watchlist is None:
            raise HTTPException(status_code=404, detail="watchlist not found")
        watchlist_names.append(watchlist.name)

    active_only = bool(req.get("active_only", True))
    include_all_active = source_type == "all_active" or bool(req.get("include_all_active", False))
    if source_type == "manual":
        watchlist_ids = []
        include_all_active = False
    elif source_type == "watchlist":
        manual_values = []
        include_all_active = False
    elif source_type == "watchlist_plus_manual":
        include_all_active = False

    resolution = symbol_universe_repo.resolve_symbols(
        app_user_id=user.id,
        manual_symbols=manual_values,
        watchlist_ids=watchlist_ids,
        include_all_active=include_all_active,
        include_inactive=not active_only,
        exclusions=excluded_values,
        pinned_symbols=pinned_values,
    )
    provenance = dict(resolution.provenance)
    duplicates_ignored = (
        int(provenance.get("duplicate_count") or 0)
        + manual_duplicate_count
        + pinned_duplicate_count
        + excluded_duplicate_count
    )
    exclusions_applied = int(provenance.get("excluded_count") or 0)
    pinned_symbols_applied = [symbol for symbol in normalized_pinned if symbol in resolution.symbols]
    warnings = ["provider_metadata_not_used"]
    if not resolution.symbols:
        warnings.insert(0, "resolved_universe_empty")

    provenance.update(
        {
            "requested_source_type": source_type,
            "watchlist_names": watchlist_names,
            "active_only": active_only,
            "preview_only": True,
            "provider_metadata_available": False,
        }
    )
    return {
        "resolved_symbols": resolution.symbols,
        "symbol_count": len(resolution.symbols),
        "duplicates_ignored": duplicates_ignored,
        "exclusions_applied": exclusions_applied,
        "pinned_symbols_applied": pinned_symbols_applied,
        "source_type": source_type,
        "resolved_source": resolution.source,
        "source_label": _symbol_preview_source_label(source_type, watchlist_names),
        "warnings": warnings,
        "provider_metadata_available": False,
        "provider_metadata_note": "Provider metadata is not used by this read-only preview.",
        "preview_only": True,
        "execution_enabled": False,
        "does_not_submit_recommendations": True,
        "does_not_mutate_schedules": True,
        "does_not_mutate_watchlists": True,
        "provenance": provenance,
    }


@user_router.get("/watchlists")
def list_watchlists(user=Depends(require_approved_user)):
    rows = watchlist_repo.list_for_user(user.id)
    return [{"id": row.id, "name": row.name, "symbols": row.symbols, "created_at": row.created_at} for row in rows]


@user_router.post("/watchlists")
def create_or_update_watchlist(req: dict[str, object], user=Depends(require_approved_user)):
    name = capped_text(req.get("name") or "Core watchlist", field_name="name", max_length=80)
    symbols = normalize_symbol_list(
        req.get("symbols") or [],
        max_items=MAX_WATCHLIST_SYMBOLS,
        field_name="watchlist symbols",
    )
    row = watchlist_repo.upsert(app_user_id=user.id, name=name, symbols=symbols)
    return {"id": row.id, "name": row.name, "symbols": row.symbols}


@user_router.put("/watchlists/{watchlist_id}")
def update_watchlist(watchlist_id: int, req: dict[str, object], user=Depends(require_approved_user)):
    name_raw = req.get("name")
    name = capped_text(name_raw, field_name="name", max_length=80) if name_raw is not None else None
    symbols_raw = req.get("symbols")
    symbols: list[str] | None = None
    if symbols_raw is not None:
        symbols = normalize_symbol_list(
            symbols_raw,
            max_items=MAX_WATCHLIST_SYMBOLS,
            field_name="watchlist symbols",
        )
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
    symbols = normalize_symbol_list(
        req.get("symbols") or ["AAPL", "MSFT", "NVDA"],
        max_items=MAX_BULK_SYMBOLS,
        field_name="symbols",
    )
    top_n = capped_int(req.get("top_n"), default=5, minimum=1, maximum=MAX_QUEUE_TOP_N, field_name="top_n")
    payload = {
        "market_mode": market_mode.value,
        "enabled_strategies": req.get("enabled_strategies") or default_strategies,
        "symbols": symbols,
        "ranking_preferences": req.get("ranking_preferences") or ["strategy_fit", "expected_rr", "liquidity"],
        "top_n": top_n,
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
    schedule = strategy_report_repo.get_schedule(schedule_id)
    if schedule is None or schedule.app_user_id != _user.id:
        raise HTTPException(status_code=404, detail="Schedule not found")
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
    return {
        "invite_id": invite.id,
        "status": invite.status,
        "email": invite.email,
        "invite_token": _masked_invite_token(invite.invite_token),
        "invite_token_masked": True,
    }


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
            "invite_token": _masked_invite_token(row.invite_token),
            "invite_token_masked": True,
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


def _config_state(*, enabled: bool = True, configured: bool) -> str:
    if not enabled:
        return "disabled"
    return "configured" if configured else "missing_config"


def _readiness_status(*, config_state: str, probe_state: str) -> str:
    if probe_state == "ok":
        return "ok"
    if probe_state == "failed":
        return "degraded"
    if config_state == "disabled":
        return "disabled"
    if config_state == "missing_config":
        return "unconfigured"
    return "configured"


def _readiness_json_probe(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout_seconds: float = 8.0,
) -> tuple[dict[str, object], float]:
    started = perf_counter()
    request = Request(url, headers=headers or {})
    with urlopen(request, timeout=timeout_seconds) as response:
        raw = response.read(32768)
    elapsed_ms = round((perf_counter() - started) * 1000, 1)
    if not raw:
        return {}, elapsed_ms
    payload = json.loads(raw.decode("utf-8"))
    if isinstance(payload, dict):
        return payload, elapsed_ms
    return {"payload": payload}, elapsed_ms


def _masked_invite_token(token: str | None) -> str | None:
    if not token:
        return None
    normalized = str(token)
    if len(normalized) <= 8:
        return "****"
    return f"{normalized[:7]}...{normalized[-4:]}"


def _alpaca_paper_readiness() -> dict[str, object]:
    broker_mode = settings.broker_provider.strip().lower() or "mock"
    api_key_present = bool(settings.alpaca_api_key_id.strip())
    api_secret_present = bool(settings.alpaca_api_secret_key.strip())
    base_url_present = bool(settings.alpaca_paper_base_url.strip())
    configured = api_key_present and api_secret_present and base_url_present
    config_state = _config_state(configured=configured)
    probe_state = "unavailable"
    latency_ms: float | None = None
    account_status: str | None = None
    selected_note = (
        "BROKER_PROVIDER is currently alpaca paper."
        if broker_mode == "alpaca"
        else "Paper routing disabled / mock broker mode. Alpaca credentials may be present, but BROKER_PROVIDER=mock keeps paper routing on the deterministic mock broker."
    )
    details = (
        "Alpaca paper readiness is incomplete: API key, secret, or paper base URL is missing. "
        "This surface reports readiness only and does not enable live trading or order routing."
    )
    if configured and broker_mode != "alpaca":
        probe_state = "skipped"
        details = (
            "Alpaca paper credentials and base URL appear present, but BROKER_PROVIDER=mock keeps paper routing "
            "on the deterministic mock broker. Read-only paper account probe skipped in mock broker mode."
        )
    elif configured:
        try:
            payload, latency_ms = _readiness_json_probe(
                f"{settings.alpaca_paper_base_url.rstrip('/')}/v2/account",
                headers={
                    "APCA-API-KEY-ID": settings.alpaca_api_key_id.strip(),
                    "APCA-API-SECRET-KEY": settings.alpaca_api_secret_key.strip(),
                    "Accept": "application/json",
                },
                timeout_seconds=float(settings.market_data_request_timeout_seconds),
            )
            account_status = str(payload.get("status") or payload.get("account_status") or "available")
            probe_state = "ok"
            details = (
                "Read-only Alpaca paper account probe succeeded. This probe used GET /v2/account only; "
                "no order route was called. It does not enable live trading or broker routing. "
                f"{selected_note}"
            )
        except Exception as exc:
            probe_state = "failed"
            details = (
                "Read-only Alpaca paper account probe failed. No order route was called. "
                f"Sanitized error: {_sanitize_provider_error(exc)}"
            )
    return {
        "provider": "alpaca_paper",
        "mode": broker_mode,
        "status": _readiness_status(config_state=config_state, probe_state=probe_state),
        "details": details,
        "config_state": config_state,
        "probe_state": probe_state,
        "configured": configured,
        "selected_provider": broker_mode,
        "probe_status": probe_state,
        "readiness_scope": "paper_provider",
        "credentials_present": api_key_present and api_secret_present,
        "paper_routing_enabled": False,
        "account_probe_endpoint": "/v2/account" if configured and broker_mode == "alpaca" else None,
        "order_route_probe": "not_performed",
        "account_status": account_status,
        "latency_ms": latency_ms,
        "operational_impact": (
            "Paper routing disabled / mock broker mode. This is a readiness gate only and does not activate brokerage execution."
            if broker_mode != "alpaca"
            else "Use this as a paper-provider readiness gate before deeper provider expansion. It does not activate live brokerage execution or broker order routing."
        ),
    }


def _fred_readiness() -> dict[str, object]:
    macro_mode = settings.macro_calendar_provider.strip().lower() or "mock"
    api_key_present = bool(settings.fred_api_key.strip())
    base_url_present = bool(settings.fred_base_url.strip())
    configured = api_key_present and base_url_present
    config_state = _config_state(configured=configured)
    probe_state = "unavailable"
    latency_ms: float | None = None
    selected_note = (
        "MACRO_CALENDAR_PROVIDER is currently fred."
        if macro_mode == "fred"
        else "MACRO_CALENDAR_PROVIDER is currently mock; FRED remains a readiness gate only."
    )
    details = "FRED readiness is incomplete: API key or base URL is missing."
    if configured and macro_mode != "fred":
        probe_state = "skipped"
        details = "FRED API key and base URL appear present. Live probe skipped because MACRO_CALENDAR_PROVIDER is not fred."
    elif configured:
        query = urlencode(
            {
                "series_id": "DGS10",
                "api_key": settings.fred_api_key.strip(),
                "file_type": "json",
                "sort_order": "desc",
                "limit": "1",
            }
        )
        try:
            payload, latency_ms = _readiness_json_probe(
                f"{settings.fred_base_url.rstrip('/')}/series/observations?{query}",
                timeout_seconds=float(settings.fred_timeout_seconds),
            )
            observations = payload.get("observations")
            if not isinstance(observations, list) or not observations:
                raise ValueError("FRED probe returned no observations for DGS10")
            probe_state = "ok"
            details = "FRED read-only observation probe succeeded for DGS10. " + selected_note
        except Exception as exc:
            probe_state = "failed"
            details = f"FRED read-only observation probe failed. Sanitized error: {_sanitize_provider_error(exc)}"
    return {
        "provider": "fred",
        "mode": macro_mode,
        "status": _readiness_status(config_state=config_state, probe_state=probe_state),
        "details": details,
        "config_state": config_state,
        "probe_state": probe_state,
        "configured": configured,
        "selected_provider": macro_mode,
        "probe_status": probe_state,
        "readiness_scope": "macro_context",
        "sample_series": "DGS10" if configured else None,
        "latency_ms": latency_ms,
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
    config_state = _config_state(configured=configured)
    probe_state = "unavailable"
    latency_ms: float | None = None
    selected_note = (
        "NEWS_PROVIDER is currently polygon."
        if news_mode == "polygon"
        else "NEWS_PROVIDER is currently mock; provider-backed news remains a readiness gate only."
    )
    details = "Provider-backed news readiness is incomplete: Polygon API key or base URL is missing."
    if configured and news_mode != "polygon":
        probe_state = "skipped"
        details = "Provider-backed news configuration appears present. Live probe skipped because NEWS_PROVIDER is not polygon."
    elif configured:
        query = urlencode({"ticker": "AAPL", "limit": "1", "apiKey": settings.polygon_api_key.strip()})
        try:
            payload, latency_ms = _readiness_json_probe(
                f"{settings.polygon_base_url.rstrip('/')}/v2/reference/news?{query}",
                timeout_seconds=float(settings.polygon_timeout_seconds),
            )
            results = payload.get("results")
            if not isinstance(results, list):
                raise ValueError("Polygon news probe returned malformed results")
            probe_state = "ok"
            details = "Polygon news read-only probe succeeded for AAPL with limit=1. " + selected_note
        except Exception as exc:
            probe_state = "failed"
            details = f"Polygon news read-only probe failed. Sanitized error: {_sanitize_provider_error(exc)}"
    return {
        "provider": "news",
        "mode": news_mode,
        "status": _readiness_status(config_state=config_state, probe_state=probe_state),
        "details": details,
        "config_state": config_state,
        "probe_state": probe_state,
        "configured": configured,
        "selected_provider": news_mode,
        "probe_status": probe_state,
        "readiness_scope": "news_context",
        "sample_symbol": "AAPL" if configured else None,
        "latency_ms": latency_ms,
        "operational_impact": (
            "Use this to verify provider-backed news context readiness before deeper provider expansion. "
            "Recommendation, replay, and orders remain paper-only."
        ),
    }


def _options_data_readiness() -> dict[str, object]:
    mode = "polygon" if settings.polygon_enabled else "disabled"
    configured = bool(settings.polygon_enabled and settings.polygon_api_key.strip() and settings.polygon_base_url.strip())
    config_state = _config_state(enabled=settings.polygon_enabled, configured=configured)
    probe_state = "skipped" if not settings.polygon_enabled else "unavailable"
    probe_payload: dict[str, object] = {}
    if configured:
        health_fn = getattr(market_data_service, "options_data_health", None)
        if callable(health_fn):
            try:
                probe_payload = dict(health_fn(sample_symbol="SPY") or {})
                probe_state = str(probe_payload.get("probe_state") or probe_payload.get("probe_status") or "unavailable")
            except Exception as exc:
                probe_state = "failed"
                probe_payload = {"details": _sanitize_provider_error(exc)}
        else:
            probe_state = "unavailable"

    details = str(
        probe_payload.get("details")
        or (
            "Options data readiness requires Polygon/Massive option contract snapshot access."
            if settings.polygon_enabled
            else "Options data readiness is disabled because Polygon/Massive market data is not selected."
        )
    )
    if probe_state == "failed":
        details = _sanitize_provider_error(details)
    entitlement_blocked = probe_state == "failed" and _is_option_snapshot_entitlement_error(details)
    if entitlement_blocked:
        details = "Option marks unavailable: provider plan is not entitled to option snapshot data."

    return {
        "provider": "options_data",
        "mode": mode,
        "status": _readiness_status(config_state=config_state, probe_state=probe_state),
        "details": details,
        "config_state": config_state,
        "probe_state": probe_state,
        "configured": configured,
        "selected_provider": "polygon" if settings.polygon_enabled else "none",
        "probe_status": probe_state,
        "sample_underlying": probe_payload.get("sample_underlying") or "SPY",
        "sample_option_symbol": probe_payload.get("sample_option_symbol"),
        "sample_selection_method": probe_payload.get("sample_selection_method") or "unavailable",
        "sample_mark_method": probe_payload.get("sample_mark_method") or "unavailable",
        "latency_ms": probe_payload.get("latency_ms"),
        "last_success_at": probe_payload.get("last_success_at"),
        "readiness_scope": "options_research_marks_only",
        "operational_impact": (
            (
                "Options data is configured, but snapshot marks are unavailable because the provider plan is not entitled. "
                "Options Position Review will show mark_unavailable rather than fake P&L. "
            )
            if entitlement_blocked
            else "Options snapshot readiness can populate paper Options Position Review marks only. "
        )
        + "It does not enable live trading, broker routing, automatic exits, rolls, or adjustments.",
        "entitlement_state": "not_entitled" if entitlement_blocked else None,
    }


def _sanitize_provider_error(value: object) -> str:
    if isinstance(value, dict):
        return "; ".join(f"{key}={_sanitize_provider_error(val)}" for key, val in value.items())
    text = str(value or "").replace("\n", " ").replace("\r", " ").strip()
    for secret in (
        settings.llm_api_key,
        settings.openai_api_key,
        settings.polygon_api_key,
        settings.alpaca_api_key_id,
        settings.alpaca_api_secret_key,
        settings.clerk_secret_key,
        settings.resend_api_key,
        settings.fred_api_key,
    ):
        if secret and secret.strip():
            text = text.replace(secret.strip(), "[redacted]")
    if "Authorization" in text:
        text = text.split("Authorization", 1)[0].strip()
    return text[:500]


def _llm_readiness(*, probe: bool = False) -> dict[str, object]:
    provider = settings.llm_provider.strip().lower() or "mock"
    model = settings.llm_model.strip() or None
    key_present = bool(settings.llm_api_key.strip() or settings.openai_api_key.strip())
    enabled = bool(settings.llm_enabled)
    configured = provider == "mock" or (provider == "openai" and key_present)
    config_state = _config_state(enabled=enabled, configured=configured)
    probe_state = "skipped" if not enabled else "unavailable"
    fallback_reason = None
    last_error = None
    last_openai_error = get_last_openai_provider_error() if provider == "openai" else None

    if not enabled:
        fallback_reason = "LLM_ENABLED=false; deterministic mock explanation fallback is active."
    elif provider == "mock":
        probe_state = "unavailable"
        fallback_reason = "LLM_PROVIDER=mock; deterministic explanation provider selected."
    elif provider != "openai":
        config_state = "missing_config"
        probe_state = "unavailable"
        fallback_reason = f"Unsupported LLM_PROVIDER={provider}; deterministic mock fallback will be used."
    elif not key_present:
        config_state = "missing_config"
        probe_state = "unavailable"
        fallback_reason = "OPENAI_API_KEY is not present; deterministic mock fallback will be used."
    elif not probe:
        probe_state = "skipped"
        if last_openai_error:
            probe_state = "failed"
            last_error = _sanitize_provider_error(last_openai_error)
            fallback_reason = "Latest OpenAI request failed; deterministic mock fallback is active until the provider succeeds."
    else:
        try:
            client = OpenAICompatibleLLMClient(
                api_key=settings.llm_api_key or settings.openai_api_key,
                model=model,
                timeout_seconds=settings.llm_timeout_seconds,
                max_output_tokens=min(settings.llm_max_output_tokens, 200),
                temperature=settings.llm_temperature,
            )
            summary = client.summarize_event_text(
                symbol="AAPL",
                text="Provider readiness probe. Return a short JSON summary only.",
            )
            if not summary:
                raise LLMValidationError("empty LLM probe response")
            probe_state = "ok"
            last_openai_error = None
        except (LLMProviderUnavailable, LLMValidationError, ValueError, TypeError) as exc:
            probe_state = "failed"
            last_error = _sanitize_provider_error(exc)
            last_openai_error = get_last_openai_provider_error()
            fallback_reason = "OpenAI probe failed; deterministic mock fallback will be used for explanations."
    status = _readiness_status(config_state=config_state, probe_state=probe_state)

    return {
        "provider": "llm",
        "mode": provider,
        "status": status,
        "details": (
            "LLM provider is explanation/research support only. Deterministic systems own approval, "
            "entry, stop, target, sizing, risk gates, and paper order creation."
        ),
        "config_state": config_state,
        "probe_state": probe_state,
        "configured": configured,
        "llm_enabled": enabled,
        "selected_provider": provider,
        "model": model,
        "key_present": key_present,
        "probe_status": probe_state,
        "fallback_active": bool(fallback_reason),
        "fallback_reason": fallback_reason,
        "last_error": last_error,
        "last_openai_error": last_openai_error,
        "readiness_scope": "explanation_research_only",
        "operational_impact": (
            "A degraded or disabled LLM never blocks deterministic recommendations; it only falls back "
            "to deterministic mock explanations."
        ),
    }


@router.get("/provider-health")
def provider_health(
    _admin=Depends(require_admin),
    probe_llm: bool = False,
):
    summary = provider_health_summary()
    market_health = market_data_service.provider_health(sample_symbol="AAPL")
    market_config_state = _config_state(configured=bool(market_health.configured))
    market_probe_state = "ok" if market_health.status == "ok" else "failed"
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
                "config_state": "configured",
                "probe_state": "ok",
                "details": "Auth provider verifies identity; app_role and approval stay local.",
            },
            {
                "provider": "email",
                "mode": summary["email"],
                "status": "ok",
                "config_state": "configured",
                "probe_state": "ok",
                "details": "Approval notifications are sent through provider boundary with audit logs.",
            },
            _alpaca_paper_readiness(),
            _fred_readiness(),
            _news_readiness(),
            _options_data_readiness(),
            _llm_readiness(probe=probe_llm),
            {
                "provider": "market_data",
                "mode": summary["market_data"],
                "status": market_health.status,
                "details": market_health.details,
                "config_state": market_config_state,
                "probe_state": market_probe_state,
                "configured_provider": summary["configured_provider"],
                "effective_read_mode": summary["effective_read_mode"],
                "workflow_execution_mode": workflow_mode,
                "failure_reason": summary["failure_reason"] or None,
                "operational_impact": operational_impact,
                "configured": market_health.configured,
                "probe_status": market_probe_state,
                "feed": market_health.feed,
                "sample_symbol": market_health.sample_symbol,
                "latency_ms": market_health.latency_ms,
                "last_success_at": market_health.last_success_at.isoformat() if market_health.last_success_at else None,
            },
        ],
    }
