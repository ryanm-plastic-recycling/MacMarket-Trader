"""Admin approval and operator routes."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from macmarket_trader.api.deps.auth import current_user, require_admin, require_approved_user
from macmarket_trader.config import settings
from macmarket_trader.data.providers.base import EmailMessage
from macmarket_trader.data.providers.market_data import DeterministicFallbackMarketDataProvider
from macmarket_trader.data.providers.registry import build_email_provider, build_market_data_service
from macmarket_trader.domain.enums import ApprovalStatus, MarketMode
from macmarket_trader.domain.time import utc_now
from macmarket_trader.domain.schemas import ApprovalActionRequest, Bar, InviteCreateRequest, PortfolioSnapshot, ReplayRunRequest, TradeRecommendation
from macmarket_trader.execution.paper_broker import PaperBroker
from macmarket_trader.ranking_engine import DeterministicRankingEngine
from macmarket_trader.replay.engine import ReplayEngine
from macmarket_trader.service import RecommendationService
from macmarket_trader.strategy_reports import StrategyReportService
from macmarket_trader.strategy_registry import get_strategy_by_display_name, list_strategies
from macmarket_trader.storage.db import SessionLocal
from macmarket_trader.storage.repositories import DashboardRepository, EmailLogRepository, InviteRepository, OrderRepository, RecommendationRepository, ReplayRepository, StrategyReportRepository, UserRepository, WatchlistRepository

router = APIRouter(prefix="/admin", tags=["admin"])
user_router = APIRouter(prefix="/user", tags=["user"])

user_repo = UserRepository(SessionLocal)
email_repo = EmailLogRepository(SessionLocal)
invite_repo = InviteRepository(SessionLocal)
dashboard_repo = DashboardRepository(SessionLocal)
recommendation_repo = RecommendationRepository(SessionLocal)
replay_repo = ReplayRepository(SessionLocal)
order_repo = OrderRepository(SessionLocal)
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
    bars, source, fallback_mode = market_data_service.historical_bars(symbol=symbol, timeframe="1D", limit=limit)
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
    }


@user_router.get("/onboarding-status")
def onboarding_status(user=Depends(require_approved_user)):
    has_schedule = bool(strategy_report_repo.list_schedules_for_user(user.id))
    has_replay = bool(replay_repo.list_runs(limit=1))
    has_order = bool(order_repo.list_with_fills(limit=1))
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
    recommendations = recommendation_repo.list_recent(limit=5)
    replay_runs = replay_repo.list_runs(limit=5)
    orders = order_repo.list_with_fills(limit=5)
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
            "Start in Recommendations to generate a deterministic setup from current market data mode.",
            "Run Replay to validate path-by-path risk transitions before staging paper execution.",
            "Use Orders to review fills and paper blotter outcomes.",
        ],
        "recent_audit_events": all_events,
    }


@user_router.get("/recommendations")
def list_recommendations(_user=Depends(require_approved_user)):
    rows = recommendation_repo.list_recent()
    if not rows and settings.environment.lower() in {"dev", "local", "test"}:
        seed_bars, _, _ = _workflow_bars("AAPL")
        seed_rec = recommendation_service.generate(
            symbol="AAPL",
            bars=seed_bars,
            event_text="Deterministic seeded recommendation for local operator-console readiness.",
            event=None,
            portfolio=PortfolioSnapshot(),
        )
        recommendation_repo.attach_workflow_metadata(seed_rec.recommendation_id, market_data_source="seed", fallback_mode=False)
        rows = recommendation_repo.list_recent()
    return [
        {
            "id": row.id,
            "created_at": row.created_at,
            "symbol": row.symbol,
            "recommendation_id": row.recommendation_id,
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

    bars, source, fallback_mode = _workflow_bars(symbol)
    event_text = str(req.get("thesis") or f"Queue promotion for {strategy}")
    approval_status = getattr(_user.approval_status, "value", _user.approval_status)
    user_is_approved = str(approval_status) == ApprovalStatus.APPROVED.value
    rec = recommendation_service.generate(
        symbol=symbol,
        bars=bars,
        event_text=event_text,
        event=None,
        portfolio=PortfolioSnapshot(),
        market_mode=MarketMode.EQUITIES,
        user_is_approved=user_is_approved,
    )

    ranking_provenance = {
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
    )
    recommendation_repo.attach_ranking_provenance(
        rec.recommendation_id,
        ranking_provenance=ranking_provenance,
    )

    persisted = recommendation_repo.get_by_recommendation_uid(rec.recommendation_id)
    workflow = (persisted.payload or {}).get("workflow", {}) if persisted else {}
    return {
        "id": persisted.id if persisted else None,
        "recommendation_id": rec.recommendation_id,
        "symbol": rec.symbol,
        "strategy": strategy,
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
    approval_status = getattr(_user.approval_status, "value", _user.approval_status)
    user_is_approved = str(approval_status) == ApprovalStatus.APPROVED.value
    bars, source, fallback_mode = _workflow_bars(symbol)
    try:
        rec = recommendation_service.generate(
            symbol=symbol,
            bars=bars,
            event_text=event_text,
            event=None,
            portfolio=PortfolioSnapshot(),
            market_mode=market_mode,
            user_is_approved=user_is_approved,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "status": "planned_research_preview",
                "market_mode": market_mode.value,
                "message": str(exc),
            },
        ) from exc
    recommendation_repo.attach_workflow_metadata(
        rec.recommendation_id,
        market_data_source=source,
        fallback_mode=fallback_mode,
    )
    return {
        "id": rec.recommendation_id,
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
    rows = replay_repo.list_runs()
    if not rows and settings.environment.lower() in {"dev", "local", "test"}:
        seed_bars, _, _ = _workflow_bars("AAPL")
        replay_engine.run(
            ReplayRunRequest(
                symbol="AAPL",
                event_texts=["Deterministic replay seed event one.", "Deterministic replay seed event two."],
                bars=seed_bars,
                portfolio=PortfolioSnapshot(),
            )
        )
        rows = replay_repo.list_runs()
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
        output.append(
            {
                "id": row.id,
                "symbol": row.symbol,
                "recommendation_count": row.recommendation_count,
                "approved_count": row.approved_count,
                "fill_count": row.fill_count,
                "ending_heat": row.ending_heat,
                "ending_open_notional": row.ending_open_notional,
                "created_at": row.created_at,
                "market_data_source": source,
                "fallback_mode": fallback_mode,
            }
        )
    return output


@user_router.post("/replay-runs")
def run_user_replay(req: dict[str, object], _user=Depends(require_approved_user)):
    symbol = str(req.get("symbol") or "AAPL").upper()
    market_mode = MarketMode(str(req.get("market_mode") or MarketMode.EQUITIES.value))
    event_texts = req.get("event_texts")
    if not isinstance(event_texts, list) or not event_texts:
        event_texts = [
            "Operator-triggered replay from recommendation context.",
            "Deterministic follow-through check for replay flow.",
        ]
    bars, source, fallback_mode = _workflow_bars(symbol)
    try:
        response = replay_engine.run(
            ReplayRunRequest(
                symbol=symbol,
                market_mode=market_mode,
                event_texts=[str(text) for text in event_texts],
                bars=bars,
                portfolio=PortfolioSnapshot(),
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "status": "planned_research_preview",
                "market_mode": market_mode.value,
                "message": str(exc),
            },
        ) from exc
    for rec in response.recommendations:
        recommendation_repo.attach_workflow_metadata(rec.recommendation_id, market_data_source=source, fallback_mode=fallback_mode)
    latest_run = replay_repo.list_runs(limit=1)
    return {
        "id": latest_run[0].id if latest_run else None,
        "symbol": symbol,
        "market_mode": market_mode.value,
        "summary_metrics": response.summary_metrics.model_dump(mode="json"),
        "market_data_source": source,
        "fallback_mode": fallback_mode,
    }


@user_router.get("/replay-runs/{run_id}/steps")
def replay_steps(run_id: int, _user=Depends(require_approved_user)):
    rows = replay_repo.list_steps_for_run(run_id)
    return [
        {
            "id": row.id,
            "step_index": row.step_index,
            "recommendation_id": row.recommendation_id,
            "approved": row.approved,
            "pre_step_snapshot": row.pre_step_snapshot,
            "post_step_snapshot": row.post_step_snapshot,
        }
        for row in rows
    ]


@user_router.get("/orders")
def list_orders(_user=Depends(require_approved_user)):
    orders = order_repo.list_with_fills()
    if not orders and settings.environment.lower() in {"dev", "local", "test"}:
        seed_bars, _, _ = _workflow_bars("AAPL")
        rec = recommendation_service.generate(
            symbol="AAPL",
            bars=seed_bars,
            event_text="Deterministic paper-order seed for operator blotter readiness.",
            event=None,
            portfolio=PortfolioSnapshot(),
        )
        if rec.approved:
            intent = recommendation_service.to_order_intent(rec)
            order, fill = paper_broker.execute(intent)
            recommendation_service.persist_order(order, notes="seed_order|source=seed|fallback=false")
            recommendation_service.persist_fill(fill)
        orders = order_repo.list_with_fills()
    return orders


@user_router.post("/orders")
def stage_order(req: dict[str, object], _user=Depends(require_approved_user)):
    recommendation_id = str(req.get("recommendation_id") or "").strip()
    rec: TradeRecommendation
    source = "workflow_snapshot_unavailable"
    fallback_mode = False
    symbol = str(req.get("symbol") or "AAPL").upper()

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
        bars, source, fallback_mode = _workflow_bars(symbol)
        rec = recommendation_service.generate(
            symbol=symbol,
            bars=bars,
            event_text="Operator staged deterministic paper order from recommendations workflow.",
            event=None,
            portfolio=PortfolioSnapshot(),
        )

    if not rec.approved:
        raise HTTPException(status_code=409, detail=rec.rejection_reason or "Recommendation was no-trade; order not staged.")
    intent = recommendation_service.to_order_intent(rec)
    order, fill = paper_broker.execute(intent)
    recommendation_service.persist_order(order, notes=f"operator_staged_order|source={source}|fallback={str(fallback_mode).lower()}")
    recommendation_service.persist_fill(fill)
    return {
        "order_id": order.order_id,
        "symbol": order.symbol,
        "status": order.status.value,
        "market_data_source": source,
        "fallback_mode": fallback_mode,
    }




@user_router.get("/analysis/setup")
def analysis_setup(
    req_symbol: str = "AAPL",
    strategy: str = "Event Continuation",
    timeframe: str = "1D",
    market_mode: MarketMode = MarketMode.EQUITIES,
    _user=Depends(require_approved_user),
):
    symbol = req_symbol.upper()
    strategies = list_strategies(market_mode)
    strategy_entry = get_strategy_by_display_name(strategy, market_mode=market_mode) or (strategies[0] if strategies else None)
    if strategy_entry is None:
        raise HTTPException(status_code=400, detail="No strategies configured for selected market mode")

    if market_mode == MarketMode.EQUITIES:
        bars, source, fallback_mode = _workflow_bars(symbol, limit=120)
    else:
        bars = preview_market_data_provider.fetch_historical_bars(symbol=symbol, timeframe=timeframe, limit=120)
        source = "planned_preview_fallback"
        fallback_mode = True

    latest = bars[-1]
    prior = bars[-2] if len(bars) > 1 else bars[-1]
    entry_low = round(latest.close * 0.995, 2)
    entry_high = round(latest.close * 1.005, 2)
    payload = {
        "symbol": symbol,
        "market_mode": market_mode.value,
        "timeframe": timeframe,
        "strategy": strategy_entry.display_name,
        "strategy_metadata": strategy_entry.model_dump(mode="json"),
        "workflow_source": f"fallback ({source})" if fallback_mode else source,
        "active": latest.close >= prior.close,
        "active_reason": "Price structure is above prior close and volume is stable" if latest.close >= prior.close else "Momentum confirmation not present",
        "trigger": "Hold above prior day high with RVOL >= 1.3",
        "entry_zone": {"low": entry_low, "high": entry_high},
        "invalidation": {"price": round(prior.low * 0.995, 2), "reason": "Loss of prior session support"},
        "targets": [round(latest.close * 1.02, 2), round(latest.close * 1.04, 2)],
        "confidence": 0.64,
        "filters": ["breadth_supportive", "liquidity_ok", "volatility_moderate"],
    }
    if market_mode != MarketMode.EQUITIES:
        payload.update(
            {
                "status": "planned_research_preview",
                "execution_enabled": False,
                "operator_guidance": (
                    "Mode is planned research preview only in Phase 1. "
                    "Use setup notes and risk context; do not stage live recommendation generation."
                ),
                "required_data_inputs": strategy_entry.required_data_inputs,
            }
        )
    if market_mode == MarketMode.OPTIONS and strategy_entry.strategy_id == "iron_condor":
        payload["option_structure"] = {
            "type": "iron_condor",
            "expiration": "2026-05-15",
            "legs": [
                {"action": "buy", "right": "put", "strike": 190.0, "label": "lower long put"},
                {"action": "sell", "right": "put", "strike": 195.0, "label": "short put"},
                {"action": "sell", "right": "call", "strike": 210.0, "label": "short call"},
                {"action": "buy", "right": "call", "strike": 215.0, "label": "higher long call"},
            ],
            "net_credit": 1.35,
            "max_profit": 135.0,
            "max_loss": 365.0,
            "breakeven_low": 193.65,
            "breakeven_high": 211.35,
            "dte": 42,
            "iv_snapshot": 0.24,
            "theta_context": 0.07,
            "vega_context": -0.11,
            "event_blockers": ["Avoid binary events inside 7 DTE window", "Review earnings/macro event calendar"],
        }
    if market_mode == MarketMode.CRYPTO:
        payload["crypto_context"] = {
            "venue": "preview_unwired",
            "quote_currency": "USD",
            "mark_price": round(latest.close, 2),
            "index_price": round(latest.close * 0.998, 2),
            "funding_rate": "preview_only_not_live",
            "basis": "preview_only_not_live",
            "open_interest": "preview_only_not_live",
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


@router.post("/users/{user_id}/approve")
def approve_user(user_id: int, req: ApprovalActionRequest, admin=Depends(require_admin)):
    if req.user_id != user_id:
        raise HTTPException(status_code=400, detail="Path and body user id mismatch")
    user = user_repo.set_approval_status(
        user_id=user_id,
        status=ApprovalStatus.APPROVED,
        approved_by=admin.email,
        note=req.note,
    )
    message = EmailMessage(
        to_email=user.email,
        subject="MacMarket-Trader account approved",
        body="Your account has been approved.",
        template_name="account_approved",
    )
    provider_id = email_provider.send(message)
    email_repo.create(user.id, "account_approved", user.email, "sent", provider_id)
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
    message = EmailMessage(
        to_email=user.email,
        subject="MacMarket-Trader account rejected",
        body="Your account request has been rejected.",
        template_name="account_rejected",
    )
    provider_id = email_provider.send(message)
    email_repo.create(user.id, "account_rejected", user.email, "sent", provider_id)
    return {"id": user.id, "approval_status": user.approval_status}


@router.post("/invites")
def create_invite(req: InviteCreateRequest, admin=Depends(require_admin)):
    invited_user = user_repo.create_or_update_invited_pending_user(email=req.email, display_name=req.display_name)
    invite = invite_repo.create(email=req.email, display_name=req.display_name, invited_by=admin.email)
    invite_url = f"{settings.cors_allowed_origins[0]}/sign-up?invite_token={invite.invite_token}&email={req.email.strip().lower()}"
    message = EmailMessage(
        to_email=req.email.strip().lower(),
        subject="MacMarket-Trader private alpha invite",
        body=(
            f"You have been invited to MacMarket-Trader private alpha.\n"
            f"Use this invite link to sign in/up via Clerk: {invite_url}\n"
            "After sign-in your local app account remains pending until admin approval."
        ),
        template_name="private_alpha_invite",
    )
    provider_id = email_provider.send(message)
    email_repo.create(invited_user.id, "private_alpha_invite", invited_user.email, "sent", provider_id)
    return {"invite_id": invite.id, "status": invite.status, "email": invite.email, "invite_token": invite.invite_token}


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
