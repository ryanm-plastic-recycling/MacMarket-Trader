"""Auth and app-level approval dependencies."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, Header, HTTPException

from macmarket_trader.config import settings
from macmarket_trader.data.providers.clerk_profile import ClerkProfileProvider
from macmarket_trader.data.providers.registry import build_auth_provider
from macmarket_trader.domain.enums import AppRole, ApprovalStatus
from macmarket_trader.storage.db import SessionLocal
from macmarket_trader.storage.repositories import UserRepository

_auth_provider = build_auth_provider()
_user_repo = UserRepository(SessionLocal)
_clerk_profile_provider = ClerkProfileProvider(
    secret_key=settings.clerk_secret_key,
    api_base_url=settings.clerk_api_base_url,
)


def _parse_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return authorization.replace("Bearer ", "", 1)


def _claim_string(claims: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = claims.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_identity(claims: dict[str, Any]) -> tuple[str, str]:
    email = _claim_string(claims, ["email", "email_address", "primary_email_address"])
    display_name = _claim_string(claims, ["name", "full_name", "display_name", "username", "given_name"])

    # Clerk JWT claims are often sparse for email/name; backend fetch fills gaps.
    external_id = str(claims.get("sub", ""))
    if (not email or not display_name) and settings.auth_provider.strip().lower() == "clerk":
        hydrated = _clerk_profile_provider.fetch_identity(external_id)
        if hydrated is not None:
            if not email:
                email = hydrated.email
            if not display_name:
                display_name = hydrated.display_name

    return email, display_name


def current_user(authorization: str | None = Header(default=None)):
    token = _parse_bearer_token(authorization)
    try:
        claims = _auth_provider.verify_token(token)
    except Exception as exc:  # noqa: BLE001 - upstream provider defines exception behavior
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    external_id = str(claims.get("sub", "")).strip()
    if not external_id:
        raise HTTPException(status_code=401, detail="Token missing subject claim")

    email, display_name = _extract_identity(claims)

    existing_user = _user_repo.get_by_external_id(external_id)
    if existing_user is None and not email:
        # Auth identity is valid but local app-user provisioning is blocked until
        # we have a stable email identifier (claims or Clerk backend hydration).
        raise HTTPException(status_code=401, detail="Unable to provision local user without email")

    try:
        user = _user_repo.upsert_from_auth(
            external_auth_user_id=external_id,
            email=email,
            display_name=display_name,
            mfa_enabled=bool(claims.get("mfa", False)),
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
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
