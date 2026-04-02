from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from macmarket_trader.api.main import app
from macmarket_trader.domain.models import AppUserModel
from macmarket_trader.storage.db import SessionLocal, init_db


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


def setup_module() -> None:
    init_db()


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
