"""Admin approval and operator routes."""

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
from macmarket_trader.storage.db import SessionLocal
from macmarket_trader.storage.repositories import DashboardRepository, EmailLogRepository, InviteRepository, OrderRepository, RecommendationRepository, ReplayRepository, UserRepository

router = APIRouter(prefix="/admin", tags=["admin"])
user_router = APIRouter(prefix="/user", tags=["user"])

user_repo = UserRepository(SessionLocal)
email_repo = EmailLogRepository(SessionLocal)
invite_repo = InviteRepository(SessionLocal)
dashboard_repo = DashboardRepository(SessionLocal)
recommendation_repo = RecommendationRepository(SessionLocal)
replay_repo = ReplayRepository(SessionLocal)
order_repo = OrderRepository(SessionLocal)
email_provider = build_email_provider()
market_data_service = build_market_data_service()
recommendation_service = RecommendationService()
replay_engine = ReplayEngine(service=recommendation_service)
paper_broker = PaperBroker()


def _demo_bars() -> list[Bar]:
    from datetime import date, timedelta

    base = date(2026, 1, 1)
    return [
        Bar(
            date=base + timedelta(days=i),
            open=190 + (i * 0.9),
            high=191 + (i * 0.9),
            low=189 + (i * 0.9),
            close=190.4 + (i * 0.9),
            volume=1_200_000 + i * 15_000,
            rel_volume=1.1,
        )
        for i in range(35)
    ]


def _workflow_bars(symbol: str, limit: int = 60) -> tuple[list[Bar], str, bool]:
    bars, source, fallback_mode = market_data_service.historical_bars(symbol=symbol, timeframe="1D", limit=limit)
    if bars:
        return bars, source, fallback_mode
    demo = _demo_bars()
    return demo, "fallback", True


@user_router.get("/me")
def me(user=Depends(current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "approval_status": user.approval_status,
        "app_role": user.app_role,
        "mfa_enabled": user.mfa_enabled,
        "auth_provider": settings.auth_provider.strip().lower() or "mock",
        "last_seen_at": user.last_seen_at.isoformat() if user.last_seen_at else None,
        "last_authenticated_at": user.last_authenticated_at.isoformat() if user.last_authenticated_at else None,
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
        recommendation_service.generate(
            symbol="AAPL",
            bars=seed_bars,
            event_text="Deterministic seeded recommendation for local operator-console readiness.",
            event=None,
            portfolio=PortfolioSnapshot(),
        )
        rows = recommendation_repo.list_recent()
    return [
        {
            "id": row.id,
            "created_at": row.created_at,
            "symbol": row.symbol,
            "recommendation_id": row.recommendation_id,
            "payload": row.payload,
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
    return [
        {
            "id": row.id,
            "symbol": row.symbol,
            "recommendation_count": row.recommendation_count,
            "approved_count": row.approved_count,
            "fill_count": row.fill_count,
            "ending_heat": row.ending_heat,
            "ending_open_notional": row.ending_open_notional,
            "created_at": row.created_at,
        }
        for row in rows
    ]


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
            recommendation_service.persist_order(order, notes="seed_order")
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
    recommendation_service.persist_order(order, notes="operator_staged_order")
    recommendation_service.persist_fill(fill)
    return {
        "order_id": order.order_id,
        "symbol": order.symbol,
        "status": order.status.value,
        "market_data_source": source,
        "fallback_mode": fallback_mode,
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
            "display_name": user.display_name,
            "email": user.email,
            "app_role": user.app_role,
            "approval_status": user.approval_status,
            "mfa_enabled": user.mfa_enabled,
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
