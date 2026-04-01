"""Auth and app-level approval dependencies."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException

from macmarket_trader.config import settings
from macmarket_trader.data.providers.registry import build_auth_provider
from macmarket_trader.domain.enums import AppRole, ApprovalStatus
from macmarket_trader.storage.db import SessionLocal
from macmarket_trader.storage.repositories import UserRepository

_auth_provider = build_auth_provider()
_user_repo = UserRepository(SessionLocal)


def _parse_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return authorization.replace("Bearer ", "", 1)


def current_user(authorization: str | None = Header(default=None)):
    token = _parse_bearer_token(authorization)
    try:
        claims = _auth_provider.verify_token(token)
    except Exception as exc:  # noqa: BLE001 - upstream provider defines exception behavior
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    role_claim = str(claims.get("role", AppRole.USER.value)).lower()
    app_role = AppRole.ADMIN if role_claim == AppRole.ADMIN.value else AppRole.USER

    user = _user_repo.upsert_from_auth(
        external_auth_user_id=str(claims.get("sub", "")),
        email=str(claims.get("email", "")),
        display_name=str(claims.get("name", "")),
        app_role=app_role,
        mfa_enabled=bool(claims.get("mfa", False)),
    )
    return user


def require_approved_user(user=Depends(current_user)):
    if user.approval_status != ApprovalStatus.APPROVED.value:
        raise HTTPException(status_code=403, detail=f"Approval status is {user.approval_status}")
    return user


def require_admin(user=Depends(current_user)):
    if user.app_role != AppRole.ADMIN.value:
        raise HTTPException(status_code=403, detail="Admin role required")
    if settings.require_mfa_for_admin and not user.mfa_enabled:
        raise HTTPException(status_code=403, detail="Admin MFA required")
    return user
