"""Admin approval and operator routes."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from macmarket_trader.api.deps.auth import current_user, require_admin, require_approved_user
from macmarket_trader.config import settings
from macmarket_trader.data.providers.base import EmailMessage
from macmarket_trader.data.providers.registry import build_email_provider, build_market_data_service
from macmarket_trader.domain.enums import ApprovalStatus
from macmarket_trader.domain.time import utc_now
from macmarket_trader.domain.schemas import ApprovalActionRequest, Bar, InviteCreateRequest, PortfolioSnapshot, ReplayRunRequest
from macmarket_trader.execution.paper_broker import PaperBroker
from macmarket_trader.replay.engine import ReplayEngine
from macmarket_trader.service import RecommendationService
from macmarket_trader.strategy_reports import StrategyReportService
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
    if provider_is_expected and fallback_mode:
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


@user_router.get("/dashboard")
def dashboard(user=Depends(require_approved_user)):
    counts = dashboard_repo.summary_counts()
    recommendations = recommendation_repo.list_recent(limit=5)
    replay_runs = replay_repo.list_runs(limit=5)
    orders = order_repo.list_with_fills(limit=5)
    pending_users = user_repo.list_by_status(ApprovalStatus.PENDING)
    provider_health = provider_health_summary()
    latest_snapshot = market_data_service.latest_snapshot(symbol="AAPL", timeframe="1D")
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
                    f"{provider_health['market_data'].capitalize()} market data is active."
                    if provider_health["summary"] == "ok"
                    else "Deterministic fallback market data mode is active."
                ),
            }
        ],
        "quick_links": ["/charts/haco", "/admin/users/pending", "/recommendations"],
        "workflow_guide": [
            "Start in Recommendations to generate a deterministic setup from current market data mode.",
            "Run Replay to validate path-by-path risk transitions before staging paper execution.",
            "Use Orders to review fills and paper blotter outcomes.",
        ],
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


@user_router.post("/recommendations/generate")
def generate_recommendations(req: dict[str, object], _user=Depends(require_approved_user)):
    symbol = str(req.get("symbol") or "AAPL").upper()
    event_text = str(req.get("event_text") or "Operator-triggered deterministic refresh run.")
    bars, source, fallback_mode = _workflow_bars(symbol)
    rec = recommendation_service.generate(
        symbol=symbol,
        bars=bars,
        event_text=event_text,
        event=None,
        portfolio=PortfolioSnapshot(),
    )
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
    event_texts = req.get("event_texts")
    if not isinstance(event_texts, list) or not event_texts:
        event_texts = [
            "Operator-triggered replay from recommendation context.",
            "Deterministic follow-through check for replay flow.",
        ]
    bars, source, fallback_mode = _workflow_bars(symbol)
    response = replay_engine.run(
        ReplayRunRequest(
            symbol=symbol,
            event_texts=[str(text) for text in event_texts],
            bars=bars,
            portfolio=PortfolioSnapshot(),
        )
    )
    for rec in response.recommendations:
        recommendation_repo.attach_workflow_metadata(rec.recommendation_id, market_data_source=source, fallback_mode=fallback_mode)
    latest_run = replay_repo.list_runs(limit=1)
    return {
        "id": latest_run[0].id if latest_run else None,
        "symbol": symbol,
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
    symbol = str(req.get("symbol") or "AAPL").upper()
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
def analysis_setup(req_symbol: str = "AAPL", strategy: str = "Event Continuation", timeframe: str = "1D", _user=Depends(require_approved_user)):
    symbol = req_symbol.upper()
    bars, source, fallback_mode = _workflow_bars(symbol, limit=120)
    latest = bars[-1]
    prior = bars[-2] if len(bars) > 1 else bars[-1]
    entry_low = round(latest.close * 0.995, 2)
    entry_high = round(latest.close * 1.005, 2)
    payload = {
        "symbol": symbol,
        "timeframe": timeframe,
        "strategy": strategy,
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
    return payload


@user_router.get("/analyze/{symbol}")
def analyze_symbol(symbol: str, _user=Depends(require_approved_user)):
    bars, source, fallback_mode = _workflow_bars(symbol.upper(), limit=120)
    latest = bars[-1]
    low20 = min(item.low for item in bars[-20:])
    high20 = max(item.high for item in bars[-20:])
    avg_volume = sum(item.volume for item in bars[-20:]) / min(len(bars), 20)
    return {
        "symbol": symbol.upper(),
        "source": f"fallback ({source})" if fallback_mode else source,
        "market_regime": "trend" if latest.close >= bars[-5].close else "chop",
        "technical_summary": f"Close {latest.close:.2f}, 20D range {low20:.2f}-{high20:.2f}",
        "strategy_scoreboard": [
            {"strategy": "Event Continuation", "score": 0.69},
            {"strategy": "Breakout / Prior-Day High", "score": 0.66},
            {"strategy": "Pullback / Trend Continuation", "score": 0.62},
            {"strategy": "Gap Follow-Through", "score": 0.54},
            {"strategy": "Mean Reversion", "score": 0.43},
            {"strategy": "HACO Context", "score": 0.58},
        ],
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


@user_router.get("/strategy-schedules")
def list_strategy_schedules(user=Depends(require_approved_user)):
    schedules = strategy_report_repo.list_schedules_for_user(user.id)
    output = []
    for row in schedules:
        runs = strategy_report_repo.list_runs(schedule_id=row.id, limit=5)
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
                "history": [
                    {
                        "id": run.id,
                        "status": run.status,
                        "delivered_to": run.delivered_to,
                        "created_at": run.created_at,
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
    payload = {
        "enabled_strategies": req.get("enabled_strategies") or ["Event Continuation", "Breakout / Prior-Day High"],
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
    payload = strategy_report_service.run_schedule(schedule_id, trigger="run_now")
    return payload


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
    market_mode = market_health.mode if market_health.status == "ok" else "fallback"
    auth_mode = settings.auth_provider.strip().lower() or "mock"
    email_mode = settings.email_provider.strip().lower() or "console"
    summary = "ok" if market_health.status == "ok" else "degraded"
    return {"summary": summary, "auth": auth_mode, "email": email_mode, "market_data": market_mode}


@router.get("/provider-health")
def provider_health(_admin=Depends(require_admin)):
    summary = provider_health_summary()
    market_health = market_data_service.provider_health(sample_symbol="AAPL")
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
                "operational_impact": (
                    "Recommendations, replay, and paper orders are currently running on deterministic fallback bars."
                    if market_health.status != "ok"
                    else "Recommendations, replay, and paper orders are using provider-backed bars."
                ),
                "configured": market_health.configured,
                "feed": market_health.feed,
                "sample_symbol": market_health.sample_symbol,
                "latency_ms": market_health.latency_ms,
                "last_success_at": market_health.last_success_at.isoformat() if market_health.last_success_at else None,
            },
        ],
    }
