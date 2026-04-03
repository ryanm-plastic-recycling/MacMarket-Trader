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
