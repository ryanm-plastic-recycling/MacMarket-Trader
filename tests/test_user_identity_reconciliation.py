from sqlalchemy import select

from macmarket_trader.domain.models import AppUserModel
from macmarket_trader.storage.db import build_engine, build_session_factory, init_db
from macmarket_trader.storage.repositories import UserRepository


def _build_repo(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path / 'identity.db'}")
    init_db(engine)
    session_factory = build_session_factory(engine)
    return UserRepository(session_factory), session_factory


def test_invited_and_clerk_rows_merge_into_single_user(tmp_path) -> None:
    repo, session_factory = _build_repo(tmp_path)

    with session_factory() as session:
        session.add(
            AppUserModel(
                external_auth_user_id="invited::invitee@example.com",
                email="invitee@example.com",
                display_name="Invitee",
                approval_status="pending",
                app_role="user",
                mfa_enabled=False,
            )
        )
        session.add(
            AppUserModel(
                external_auth_user_id="clerk_invitee",
                email="placeholder+invitee@example.com",
                display_name="Identity pending",
                approval_status="pending",
                app_role="user",
                mfa_enabled=True,
            )
        )
        session.commit()

    user = repo.upsert_from_auth(
        external_auth_user_id="clerk_invitee",
        email="invitee@example.com",
        display_name="Invited Operator",
        mfa_enabled=True,
    )

    assert user.external_auth_user_id == "clerk_invitee"
    assert user.email == "invitee@example.com"
    assert user.display_name == "Invited Operator"
    assert user.mfa_enabled is True

    with session_factory() as session:
        rows = list(session.execute(select(AppUserModel).where(AppUserModel.email == "invitee@example.com")).scalars())
    assert len(rows) == 1


def test_placeholder_email_row_reconciles_to_real_email_row(tmp_path) -> None:
    repo, session_factory = _build_repo(tmp_path)

    with session_factory() as session:
        session.add(
            AppUserModel(
                external_auth_user_id="clerk_partial",
                email="{{user.primary_email_address.email_address}}",
                display_name="{{user.first_name}}",
                approval_status="pending",
                app_role="user",
                mfa_enabled=False,
            )
        )
        session.add(
            AppUserModel(
                external_auth_user_id="invited::real.user@example.com",
                email="real.user@example.com",
                display_name="Real User",
                approval_status="pending",
                app_role="user",
                mfa_enabled=False,
            )
        )
        session.commit()

    user = repo.upsert_from_auth(
        external_auth_user_id="clerk_partial",
        email="real.user@example.com",
        display_name="Real User",
        mfa_enabled=False,
    )

    assert user.external_auth_user_id == "clerk_partial"
    assert user.email == "real.user@example.com"
    assert user.display_name == "Real User"

    with session_factory() as session:
        rows = list(session.execute(select(AppUserModel)).scalars())
    assert len(rows) == 1


def test_merge_preserves_local_admin_and_approval_and_is_idempotent(tmp_path) -> None:
    repo, session_factory = _build_repo(tmp_path)

    with session_factory() as session:
        session.add(
            AppUserModel(
                external_auth_user_id="invited::admin@example.com",
                email="admin@example.com",
                display_name="Admin Invite",
                approval_status="approved",
                app_role="admin",
                mfa_enabled=False,
            )
        )
        session.add(
            AppUserModel(
                external_auth_user_id="clerk_admin_split",
                email="placeholder+admin@example.com",
                display_name="identity pending",
                approval_status="pending",
                app_role="user",
                mfa_enabled=True,
            )
        )
        session.commit()

    first = repo.upsert_from_auth(
        external_auth_user_id="clerk_admin_split",
        email="admin@example.com",
        display_name="Desk Admin",
        mfa_enabled=True,
    )
    second = repo.upsert_from_auth(
        external_auth_user_id="clerk_admin_split",
        email="admin@example.com",
        display_name="Desk Admin",
        mfa_enabled=True,
    )

    assert first.id == second.id
    assert second.approval_status == "approved"
    assert second.app_role == "admin"
    assert second.mfa_enabled is True

    with session_factory() as session:
        rows = list(session.execute(select(AppUserModel).where(AppUserModel.email == "admin@example.com")).scalars())
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# Pass 8 — invite reconciliation on first Clerk sign-in (route-level)
#
# These exercise the end-to-end /user/me path used by the frontend on first
# load, not just the repository unit. They guard against any regression where
# the auth dependency forgets to fall back from the new Clerk sub to the
# invited::email row that POST /admin/invites planted.
# ---------------------------------------------------------------------------

from fastapi.testclient import TestClient

from macmarket_trader.api.main import app as _route_app
from macmarket_trader.storage.db import SessionLocal as _RouteSessionLocal

_route_client = TestClient(_route_app)
_USER_TOKEN_AUTH = {"Authorization": "Bearer user-token"}


def _seed_invited_row(*, email: str, approval_status: str = "pending", display_name: str = "Invited Operator"):
    """Mirror what POST /admin/invites does: create app_users row with
    external_auth_user_id = invited::email and the requested approval status.
    Uses the conftest-patched in-memory SessionLocal so each test starts
    with a clean schema."""
    with _RouteSessionLocal() as session:
        session.add(
            AppUserModel(
                external_auth_user_id=f"invited::{email}",
                email=email,
                display_name=display_name,
                approval_status=approval_status,
                app_role="user",
                mfa_enabled=False,
            )
        )
        session.commit()


def test_invited_user_reconciles_on_first_clerk_signin() -> None:
    """First Clerk sign-in for an invited user (pending approval).
    The mock auth provider returns sub=clerk_user, email=user@example.com for
    user-token. /user/me must NOT 401 and the invited::user@example.com row
    must be updated in place to external_auth_user_id=clerk_user, preserving
    approval_status=pending."""
    _seed_invited_row(email="user@example.com", approval_status="pending")

    response = _route_client.get("/user/me", headers=_USER_TOKEN_AUTH)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["email"] == "user@example.com"
    assert body["approval_status"] == "pending"

    # Row external_auth_user_id is now the real Clerk sub, not "invited::…"
    with _RouteSessionLocal() as session:
        rows = list(session.execute(select(AppUserModel).where(AppUserModel.email == "user@example.com")).scalars())
    assert len(rows) == 1, f"expected exactly one row after reconciliation, got {len(rows)}"
    assert rows[0].external_auth_user_id == "clerk_user"
    assert rows[0].approval_status == "pending"


def test_invited_and_approved_user_keeps_approval_after_signin() -> None:
    """An admin pre-approved the invited user before they signed in. After
    first Clerk sign-in, approval_status stays 'approved' — the merge does
    not regress it back to pending."""
    _seed_invited_row(email="user@example.com", approval_status="approved")

    response = _route_client.get("/user/me", headers=_USER_TOKEN_AUTH)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["approval_status"] == "approved"

    with _RouteSessionLocal() as session:
        rows = list(session.execute(select(AppUserModel).where(AppUserModel.email == "user@example.com")).scalars())
    assert len(rows) == 1
    assert rows[0].external_auth_user_id == "clerk_user"
    assert rows[0].approval_status == "approved"


def test_unknown_clerk_user_creates_new_pending_row() -> None:
    """No invite, no prior row — first sign-in creates a fresh row with
    approval_status=pending. Confirms the unknown-user path is unaffected
    by the invite-reconciliation chain."""
    response = _route_client.get("/user/me", headers=_USER_TOKEN_AUTH)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["email"] == "user@example.com"
    assert body["approval_status"] == "pending"

    with _RouteSessionLocal() as session:
        rows = list(session.execute(select(AppUserModel).where(AppUserModel.email == "user@example.com")).scalars())
    assert len(rows) == 1
    assert rows[0].external_auth_user_id == "clerk_user"
    assert rows[0].approval_status == "pending"
