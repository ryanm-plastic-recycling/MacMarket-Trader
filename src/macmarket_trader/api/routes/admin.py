"""Admin approval and operator routes."""

from fastapi import APIRouter, Depends, HTTPException

from macmarket_trader.api.deps.auth import current_user, require_admin, require_approved_user
from macmarket_trader.data.providers.base import EmailMessage
from macmarket_trader.data.providers.registry import build_email_provider
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
    return {
        "status": "ok",
        "approval_status": user.approval_status,
        "provider_health": {"auth": "ok", "email": "ok", "market_data": "placeholder"},
        "counts": counts,
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


@router.get("/provider-health")
def provider_health(_admin=Depends(require_admin)):
    return {
        "checked_at": utc_now().isoformat(),
        "providers": [
            {
                "provider": "auth",
                "mode": "configured",
                "status": "ok",
                "details": "Auth provider configured in backend settings.",
            },
            {
                "provider": "email",
                "mode": "configured",
                "status": "ok",
                "details": "Email provider boundary active with audit logging.",
            },
            {
                "provider": "market_data",
                "mode": "placeholder",
                "status": "unknown",
                "details": "Live provider checks are not wired in this pass; deterministic placeholder status returned.",
            },
        ],
    }
