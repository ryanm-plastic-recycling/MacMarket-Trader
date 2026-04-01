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
        admin.mfa_enabled = True
        session.commit()

    resp = client.get('/admin/provider-health', headers={'Authorization': 'Bearer admin-token'})
    assert resp.status_code == 200
    payload = resp.json()
    assert 'providers' in payload
    assert any(item['provider'] == 'auth' for item in payload['providers'])
