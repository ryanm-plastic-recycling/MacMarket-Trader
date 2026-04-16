from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from macmarket_trader.api.main import app
from macmarket_trader.domain.models import AppInviteModel, AppUserModel
from macmarket_trader.storage.db import SessionLocal


client = TestClient(app)

def _seed_mock_user(token: str) -> None:
    """Create deterministic mock-auth user rows for isolated tests."""
    resp = client.get('/user/me', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200


def _bars() -> list[dict[str, object]]:
    base = date(2026, 1, 1)
    return [
        {
            "date": (base + timedelta(days=i)).isoformat(),
            "open": 100 + i,
            "high": 101 + i,
            "low": 99 + i,
            "close": 100.5 + i,
            "volume": 1_000_000 + i * 10_000,
            "rel_volume": 1.1,
        }
        for i in range(25)
    ]


def test_unauthenticated_access_denied() -> None:
    resp = client.get('/user/dashboard')
    assert resp.status_code == 401


def test_pending_user_blocked_then_admin_approves() -> None:
    _seed_mock_user('user-token')
    _seed_mock_user('admin-token')

    pending = client.get('/user/dashboard', headers={'Authorization': 'Bearer user-token'})
    assert pending.status_code == 403

    client.get('/user/me', headers={'Authorization': 'Bearer admin-token'})

    with SessionLocal() as session:
        admin = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == 'clerk_admin')).scalar_one()
        admin.app_role = 'admin'
        admin.mfa_enabled = True
        target = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == 'clerk_user')).scalar_one()
        target_id = target.id
        session.commit()

    approve = client.post(
        f'/admin/users/{target_id}/approve',
        headers={'Authorization': 'Bearer admin-token'},
        json={'user_id': target_id, 'note': 'approved for desk access'},
    )
    assert approve.status_code == 200

    ok = client.get('/user/dashboard', headers={'Authorization': 'Bearer user-token'})
    assert ok.status_code == 200


def test_admin_can_reject_user() -> None:
    _seed_mock_user('user-token')
    _seed_mock_user('admin-token')

    with SessionLocal() as session:
        admin = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == 'clerk_admin')).scalar_one()
        admin.app_role = 'admin'
        admin.mfa_enabled = True
        target = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == 'clerk_user')).scalar_one()
        target.approval_status = 'pending'
        target_id = target.id
        session.commit()

    reject = client.post(
        f'/admin/users/{target_id}/reject',
        headers={'Authorization': 'Bearer admin-token'},
        json={'user_id': target_id, 'note': 'risk policy mismatch'},
    )
    assert reject.status_code == 200
    denied = client.get('/user/dashboard', headers={'Authorization': 'Bearer user-token'})
    assert denied.status_code == 403


def test_recommendation_and_replay_routes_require_approved_user() -> None:
    rec_resp = client.post(
        '/recommendations/generate',
        headers={'Authorization': 'Bearer user-token'},
        json={'symbol': 'AAPL', 'event_text': 'earnings beat', 'bars': _bars()},
    )
    assert rec_resp.status_code == 403

    replay_resp = client.post(
        '/replay/run',
        headers={'Authorization': 'Bearer user-token'},
        json={'symbol': 'AAPL', 'event_texts': ['one'], 'bars': _bars()},
    )
    assert replay_resp.status_code == 403


def test_admin_provider_health() -> None:
    _seed_mock_user('admin-token')
    with SessionLocal() as session:
        admin = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == 'clerk_admin')).scalar_one()
        admin.app_role = 'admin'
        admin.approval_status = 'approved'
        admin.mfa_enabled = True
        session.commit()

    resp = client.get('/admin/provider-health', headers={'Authorization': 'Bearer admin-token'})
    assert resp.status_code == 200
    payload = resp.json()
    assert 'providers' in payload
    assert any(item['provider'] == 'auth' for item in payload['providers'])


def test_mock_admin_token_does_not_auto_grant_admin_on_fresh_db() -> None:
    me = client.get('/user/me', headers={'Authorization': 'Bearer admin-token'})
    assert me.status_code == 200
    me_payload = me.json()
    assert me_payload['app_role'] == 'user'
    assert me_payload['approval_status'] == 'pending'

    provider_health = client.get('/admin/provider-health', headers={'Authorization': 'Bearer admin-token'})
    assert provider_health.status_code == 403


def test_admin_role_not_overwritten_by_auth_claims() -> None:
    _seed_mock_user('admin-token')
    with SessionLocal() as session:
        admin = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == 'clerk_admin')).scalar_one()
        admin.app_role = 'admin'
        admin.approval_status = 'approved'
        session.commit()

    resp = client.get('/user/me', headers={'Authorization': 'Bearer admin-token'})
    assert resp.status_code == 200
    assert resp.json()['app_role'] == 'admin'


def test_approval_status_preserved_across_login_sync() -> None:
    _seed_mock_user('user-token')
    with SessionLocal() as session:
        user = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == 'clerk_user')).scalar_one()
        user.approval_status = 'approved'
        session.commit()

    resp = client.get('/user/me', headers={'Authorization': 'Bearer user-token'})
    assert resp.status_code == 200
    assert resp.json()['approval_status'] == 'approved'


def test_clerk_profile_hydrates_missing_identity(monkeypatch) -> None:
    from macmarket_trader.api.deps import auth as auth_deps
    from macmarket_trader.data.providers.clerk_profile import ClerkHydratedIdentity

    monkeypatch.setattr(auth_deps.settings, 'auth_provider', 'clerk')
    monkeypatch.setattr(auth_deps._auth_provider, 'verify_token', lambda _token: {'sub': 'clerk_hydrated', 'mfa': False})
    monkeypatch.setattr(
        auth_deps._clerk_profile_provider,
        'fetch_identity',
        lambda _external_id: ClerkHydratedIdentity(email='hydrated@example.com', display_name='Hydrated User'),
    )

    resp = client.get('/user/me', headers={'Authorization': 'Bearer whatever'})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload['email'] == 'hydrated@example.com'
    assert payload['display_name'] == 'Hydrated User'


def test_new_user_without_email_is_not_provisioned(monkeypatch) -> None:
    from macmarket_trader.api.deps import auth as auth_deps

    monkeypatch.setattr(auth_deps.settings, 'auth_provider', 'clerk')
    monkeypatch.setattr(auth_deps._auth_provider, 'verify_token', lambda _token: {'sub': 'clerk_missing_identity', 'mfa': False})
    monkeypatch.setattr(auth_deps._clerk_profile_provider, 'fetch_identity', lambda _external_id: None)

    resp = client.get('/user/me', headers={'Authorization': 'Bearer clerk-token'})
    assert resp.status_code == 401

    with SessionLocal() as session:
        user = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == 'clerk_missing_identity')).scalar_one_or_none()
    assert user is None


def test_hydration_failure_does_not_corrupt_existing_local_auth_state(monkeypatch) -> None:
    from macmarket_trader.api.deps import auth as auth_deps

    _seed_mock_user('user-token')
    with SessionLocal() as session:
        existing = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == 'clerk_user')).scalar_one()
        existing.email = 'approved-user@example.com'
        existing.display_name = 'Approved Operator'
        existing.app_role = 'admin'
        existing.approval_status = 'approved'
        session.commit()

    monkeypatch.setattr(auth_deps.settings, 'auth_provider', 'clerk')
    monkeypatch.setattr(auth_deps._auth_provider, 'verify_token', lambda _token: {'sub': 'clerk_user', 'mfa': True})
    monkeypatch.setattr(auth_deps._clerk_profile_provider, 'fetch_identity', lambda _external_id: None)

    resp = client.get('/user/me', headers={'Authorization': 'Bearer stale-claims'})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload['email'] == 'approved-user@example.com'
    assert payload['display_name'] == 'Approved Operator'
    assert payload['approval_status'] == 'approved'
    assert payload['app_role'] == 'admin'


def test_non_admin_blocked_from_pending_users_route() -> None:
    _seed_mock_user('user-token')
    with SessionLocal() as session:
        user = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == 'clerk_user')).scalar_one()
        user.approval_status = 'approved'
        user.app_role = 'user'
        session.commit()

    resp = client.get('/admin/users/pending', headers={'Authorization': 'Bearer user-token'})
    assert resp.status_code == 403


def test_admin_can_send_private_alpha_invite() -> None:
    _seed_mock_user('admin-token')
    with SessionLocal() as session:
        admin = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == 'clerk_admin')).scalar_one()
        admin.app_role = 'admin'
        admin.approval_status = 'approved'
        admin.mfa_enabled = True
        session.commit()

    resp = client.post(
        '/admin/invites',
        headers={'Authorization': 'Bearer admin-token'},
        json={'email': 'invitee@example.com', 'display_name': 'Invitee'},
    )
    assert resp.status_code == 200

    with SessionLocal() as session:
        invited = session.execute(select(AppUserModel).where(AppUserModel.email == 'invitee@example.com')).scalar_one()
        assert invited.approval_status == 'pending'
        assert invited.app_role == 'user'
        assert invited.external_auth_user_id == 'invited::invitee@example.com'


def test_invited_user_sync_keeps_pending_until_approved(monkeypatch) -> None:
    _seed_mock_user('admin-token')
    with SessionLocal() as session:
        admin = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == 'clerk_admin')).scalar_one()
        admin.app_role = 'admin'
        admin.approval_status = 'approved'
        admin.mfa_enabled = True
        session.commit()

    invite = client.post(
        '/admin/invites',
        headers={'Authorization': 'Bearer admin-token'},
        json={'email': 'invitee@example.com', 'display_name': 'Invitee'},
    )
    assert invite.status_code == 200

    from macmarket_trader.api.deps import auth as auth_deps

    monkey_claims = {'sub': 'clerk_invited_user', 'email': 'invitee@example.com', 'name': 'Invitee', 'mfa': False}
    monkeypatch.setattr(auth_deps._auth_provider, 'verify_token', lambda _token: monkey_claims)
    resp = client.get('/user/me', headers={'Authorization': 'Bearer invited-token'})

    assert resp.status_code == 200
    payload = resp.json()
    assert payload['approval_status'] == 'pending'
    assert payload['app_role'] == 'user'


def test_existing_admin_user_remains_admin_after_login_sync() -> None:
    _seed_mock_user('admin-token')
    with SessionLocal() as session:
        admin = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == 'clerk_admin')).scalar_one()
        admin.app_role = 'admin'
        admin.approval_status = 'approved'
        session.commit()

    resp = client.get('/user/me', headers={'Authorization': 'Bearer admin-token'})
    assert resp.status_code == 200
    assert resp.json()['app_role'] == 'admin'
    assert resp.json()['approval_status'] == 'approved'


def test_template_email_claim_is_ignored_and_hydrated(monkeypatch) -> None:
    from macmarket_trader.api.deps import auth as auth_deps
    from macmarket_trader.data.providers.clerk_profile import ClerkHydratedIdentity

    monkeypatch.setattr(auth_deps.settings, 'auth_provider', 'clerk')
    monkeypatch.setattr(
        auth_deps._auth_provider,
        'verify_token',
        lambda _token: {
            'sub': 'clerk_template_email',
            'email': '{{user.primary_email_address.email_address}}',
            'name': '{{user.first_name}}',
            'mfa': False,
        },
    )
    monkeypatch.setattr(
        auth_deps._clerk_profile_provider,
        'fetch_identity',
        lambda _external_id: ClerkHydratedIdentity(email='real.user@example.com', display_name='Real User'),
    )

    resp = client.get('/user/me', headers={'Authorization': 'Bearer template-token'})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload['email'] == 'real.user@example.com'
    assert payload['display_name'] == 'Real User'


def test_template_identity_claims_do_not_create_duplicate_blank_users(monkeypatch) -> None:
    from macmarket_trader.api.deps import auth as auth_deps

    monkeypatch.setattr(auth_deps.settings, 'auth_provider', 'clerk')
    monkeypatch.setattr(
        auth_deps._auth_provider,
        'verify_token',
        lambda _token: {
            'sub': 'clerk_template_missing',
            'email': '{{user.primary_email_address.email_address}}',
            'name': '{{user.first_name}}',
            'mfa': False,
        },
    )
    monkeypatch.setattr(auth_deps._clerk_profile_provider, 'fetch_identity', lambda _external_id: None)

    first = client.get('/user/me', headers={'Authorization': 'Bearer template-missing-token'})
    second = client.get('/user/me', headers={'Authorization': 'Bearer template-missing-token'})
    assert first.status_code == 401
    assert second.status_code == 401

    with SessionLocal() as session:
        rows = list(
            session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == 'clerk_template_missing')).scalars()
        )
    assert rows == []


def test_user_me_includes_last_seen_metadata() -> None:
    _seed_mock_user('user-token')
    resp = client.get('/user/me', headers={'Authorization': 'Bearer user-token'})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload['last_seen_at'] is not None
    assert payload['last_authenticated_at'] is not None


def test_admin_users_listing_returns_current_users() -> None:
    _seed_mock_user('admin-token')
    _seed_mock_user('user-token')
    with SessionLocal() as session:
        admin = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == 'clerk_admin')).scalar_one()
        admin.app_role = 'admin'
        admin.approval_status = 'approved'
        admin.mfa_enabled = True
        session.commit()

    resp = client.get('/admin/users', headers={'Authorization': 'Bearer admin-token'})
    assert resp.status_code == 200
    users = resp.json()
    assert isinstance(users, list)
    assert any(item['email'] == 'user@example.com' for item in users)


def test_user_me_returns_real_email_after_duplicate_identity_reconciliation(monkeypatch) -> None:
    from macmarket_trader.api.deps import auth as auth_deps

    with SessionLocal() as session:
        session.add(
            AppUserModel(
                external_auth_user_id='clerk_split_identity',
                email='{{user.primary_email_address.email_address}}',
                display_name='{{user.first_name}}',
                approval_status='pending',
                app_role='user',
                mfa_enabled=False,
            )
        )
        session.add(
            AppUserModel(
                external_auth_user_id='invited::split.identity@example.com',
                email='split.identity@example.com',
                display_name='Split Identity',
                approval_status='approved',
                app_role='admin',
                mfa_enabled=True,
            )
        )
        session.commit()

    monkeypatch.setattr(
        auth_deps._auth_provider,
        'verify_token',
        lambda _token: {'sub': 'clerk_split_identity', 'email': 'split.identity@example.com', 'name': 'Split Identity', 'mfa': True},
    )
    resp = client.get('/user/me', headers={'Authorization': 'Bearer split-token'})

    assert resp.status_code == 200
    payload = resp.json()
    assert payload['email'] == 'split.identity@example.com'
    assert payload['identity_warning'] is None
    assert payload['approval_status'] == 'approved'
    assert payload['app_role'] == 'admin'

    with SessionLocal() as session:
        rows = list(session.execute(select(AppUserModel).where(AppUserModel.email == 'split.identity@example.com')).scalars())
    assert len(rows) == 1


# ── New admin user-management tests ──────────────────────────────────────────

def _seed_admin(session_local=SessionLocal) -> int:
    """Seed admin-token user as approved admin and return their id."""
    client.get('/user/me', headers={'Authorization': 'Bearer admin-token'})
    with session_local() as session:
        admin = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == 'clerk_admin')).scalar_one()
        admin.app_role = 'admin'
        admin.approval_status = 'approved'
        admin.mfa_enabled = True
        session.commit()
        return admin.id


def test_delete_invite_scoped_to_admin() -> None:
    admin_id = _seed_admin()

    # Create an invite
    resp = client.post(
        '/admin/invites',
        headers={'Authorization': 'Bearer admin-token'},
        json={'email': 'revoke-me@example.com', 'display_name': 'Revoke Test'},
    )
    assert resp.status_code == 200
    invite_id = resp.json()['invite_id']

    # Non-admin cannot delete
    _seed_mock_user('user-token')
    with SessionLocal() as session:
        user = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == 'clerk_user')).scalar_one()
        user.approval_status = 'approved'
        user.app_role = 'user'
        session.commit()
    denied = client.delete(f'/admin/invites/{invite_id}', headers={'Authorization': 'Bearer user-token'})
    assert denied.status_code == 403

    # Admin can delete
    ok = client.delete(f'/admin/invites/{invite_id}', headers={'Authorization': 'Bearer admin-token'})
    assert ok.status_code == 200
    assert ok.json()['deleted'] is True

    # Second delete returns 404
    not_found = client.delete(f'/admin/invites/{invite_id}', headers={'Authorization': 'Bearer admin-token'})
    assert not_found.status_code == 404


def test_resend_invite_updates_sent_at() -> None:
    _seed_admin()

    resp = client.post(
        '/admin/invites',
        headers={'Authorization': 'Bearer admin-token'},
        json={'email': 'resend-me@example.com', 'display_name': 'Resend Test'},
    )
    assert resp.status_code == 200
    invite_id = resp.json()['invite_id']

    # sent_at should be null before resend
    with SessionLocal() as session:
        invite = session.execute(select(AppInviteModel).where(AppInviteModel.id == invite_id)).scalar_one()
        assert invite.sent_at is None

    resend = client.post(
        f'/admin/invites/{invite_id}/resend',
        headers={'Authorization': 'Bearer admin-token'},
    )
    assert resend.status_code == 200
    assert resend.json()['email'] == 'resend-me@example.com'

    # sent_at should now be populated
    with SessionLocal() as session:
        invite = session.execute(select(AppInviteModel).where(AppInviteModel.id == invite_id)).scalar_one()
        assert invite.sent_at is not None


def test_set_role_cannot_demote_self() -> None:
    admin_id = _seed_admin()

    # Admin tries to change their own role
    resp = client.post(
        f'/admin/users/{admin_id}/set-role',
        headers={'Authorization': 'Bearer admin-token'},
        json={'role': 'user'},
    )
    assert resp.status_code == 409

    # Admin can change another user's role
    _seed_mock_user('user-token')
    with SessionLocal() as session:
        user = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == 'clerk_user')).scalar_one()
        user_id = user.id
        session.commit()

    resp2 = client.post(
        f'/admin/users/{user_id}/set-role',
        headers={'Authorization': 'Bearer admin-token'},
        json={'role': 'admin'},
    )
    assert resp2.status_code == 200
    assert resp2.json()['app_role'] == 'admin'


def test_suspend_cannot_suspend_self() -> None:
    admin_id = _seed_admin()

    resp = client.post(
        f'/admin/users/{admin_id}/suspend',
        headers={'Authorization': 'Bearer admin-token'},
    )
    assert resp.status_code == 409

    # Admin can suspend another user
    _seed_mock_user('user-token')
    with SessionLocal() as session:
        user = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == 'clerk_user')).scalar_one()
        user_id = user.id
        user.approval_status = 'approved'
        session.commit()

    resp2 = client.post(
        f'/admin/users/{user_id}/suspend',
        headers={'Authorization': 'Bearer admin-token'},
    )
    assert resp2.status_code == 200
    assert resp2.json()['approval_status'] == 'suspended'


def test_suspended_user_blocked_from_console_routes() -> None:
    _seed_mock_user('user-token')
    _seed_admin()

    with SessionLocal() as session:
        user = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == 'clerk_user')).scalar_one()
        user.approval_status = 'approved'
        user_id = user.id
        session.commit()

    # Confirm access while approved
    ok = client.get('/user/dashboard', headers={'Authorization': 'Bearer user-token'})
    assert ok.status_code == 200

    # Suspend the user
    client.post(f'/admin/users/{user_id}/suspend', headers={'Authorization': 'Bearer admin-token'})

    # Suspended user is blocked from protected routes (same as pending)
    blocked = client.get('/user/dashboard', headers={'Authorization': 'Bearer user-token'})
    assert blocked.status_code == 403
