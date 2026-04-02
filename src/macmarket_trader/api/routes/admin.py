"""Admin approval and operator routes."""

from fastapi import APIRouter, Depends, HTTPException

from macmarket_trader.api.deps.auth import current_user, require_admin, require_approved_user
from macmarket_trader.config import settings
from macmarket_trader.data.providers.base import EmailMessage
from macmarket_trader.data.providers.registry import build_email_provider, build_market_data_service
from macmarket_trader.domain.enums import ApprovalStatus
from macmarket_trader.domain.time import utc_now
from macmarket_trader.domain.schemas import ApprovalActionRequest
from macmarket_trader.storage.db import SessionLocal
from macmarket_trader.storage.repositories import DashboardRepository, EmailLogRepository, OrderRepository, RecommendationRepository, ReplayRepository, UserRepository

router = APIRouter(prefix="/admin", tags=["admin"])
user_router = APIRouter(prefix="/user", tags=["user"])

user_repo = UserRepository(SessionLocal)
email_repo = EmailLogRepository(SessionLocal)
dashboard_repo = DashboardRepository(SessionLocal)
recommendation_repo = RecommendationRepository(SessionLocal)
replay_repo = ReplayRepository(SessionLocal)
order_repo = OrderRepository(SessionLocal)
email_provider = build_email_provider()
market_data_service = build_market_data_service()


@user_router.get("/me")
def me(user=Depends(current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "approval_status": user.approval_status,
        "app_role": user.app_role,
        "mfa_enabled": user.mfa_enabled,
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
    }


@user_router.get("/recommendations")
def list_recommendations(_user=Depends(require_approved_user)):
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
    return order_repo.list_with_fills()


@router.get("/users/pending")
def pending_users(_admin=Depends(require_admin)):
    users = user_repo.list_by_status(ApprovalStatus.PENDING)
    return [{"id": u.id, "email": u.email, "display_name": u.display_name} for u in users]


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
                "configured": market_health.configured,
                "feed": market_health.feed,
                "sample_symbol": market_health.sample_symbol,
                "latency_ms": market_health.latency_ms,
                "last_success_at": market_health.last_success_at.isoformat() if market_health.last_success_at else None,
            },
        ],
    }
