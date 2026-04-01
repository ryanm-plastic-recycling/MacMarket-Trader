"""Admin approval and operator routes."""

from fastapi import APIRouter, Depends, HTTPException

from macmarket_trader.api.deps.auth import current_user, require_admin, require_approved_user
from macmarket_trader.data.providers.base import EmailMessage
from macmarket_trader.data.providers.registry import build_email_provider
from macmarket_trader.domain.enums import ApprovalStatus
from macmarket_trader.domain.time import utc_now
from macmarket_trader.domain.schemas import ApprovalActionRequest
from macmarket_trader.storage.db import SessionLocal
from macmarket_trader.storage.repositories import EmailLogRepository, UserRepository

router = APIRouter(prefix="/admin", tags=["admin"])
user_router = APIRouter(prefix="/user", tags=["user"])

user_repo = UserRepository(SessionLocal)
email_repo = EmailLogRepository(SessionLocal)
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
def dashboard(_user=Depends(require_approved_user)):
    return {"status": "ok", "scope": "approved-user"}


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
