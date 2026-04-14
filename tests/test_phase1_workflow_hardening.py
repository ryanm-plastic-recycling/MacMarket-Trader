from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from macmarket_trader.api.main import app
from macmarket_trader.api.routes import admin as admin_routes
from macmarket_trader.domain.models import AppUserModel
from macmarket_trader.storage.db import SessionLocal, init_db


client = TestClient(app)


def _bars() -> list[dict[str, object]]:
    base = date(2026, 2, 1)
    return [
        {
            "date": (base + timedelta(days=i)).isoformat(),
            "open": 180 + i,
            "high": 181 + i,
            "low": 179 + i,
            "close": 180.5 + i,
            "volume": 1_200_000 + i * 11_000,
            "rel_volume": 1.15,
        }
        for i in range(40)
    ]


def _approve_user() -> None:
    client.get('/user/me', headers={'Authorization': 'Bearer user-token'})
    with SessionLocal() as session:
        user = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == 'clerk_user')).scalar_one()
        user.approval_status = 'approved'
        session.commit()


def setup_module() -> None:
    init_db()


def test_analysis_to_recommendation_to_replay_to_order_flow_keeps_lineage() -> None:
    _approve_user()

    create_rec = client.post(
        '/user/recommendations/generate',
        headers={'Authorization': 'Bearer user-token'},
        json={'symbol': 'AAPL', 'event_text': 'Earnings beat with raised strong guidance breakout'},
    )
    assert create_rec.status_code == 200
    assert create_rec.json()['approved'] is True
    recommendation_id = create_rec.json()['recommendation_id']

    recs = client.get('/user/recommendations', headers={'Authorization': 'Bearer user-token'})
    assert recs.status_code == 200
    latest = recs.json()[0]
    assert latest['recommendation_id'] == recommendation_id
    assert latest['symbol'] == 'AAPL'
    assert latest['payload']['workflow']['market_data_source']

    replay = client.post(
        '/user/replay-runs',
        headers={'Authorization': 'Bearer user-token'},
        json={'guided': True, 'recommendation_id': recommendation_id, 'event_texts': ['Validate recommendation path']},
    )
    assert replay.status_code == 200
    replay_payload = replay.json()
    assert replay_payload['symbol'] == 'AAPL'
    assert replay_payload['recommendation_id'] == recommendation_id
    assert replay_payload['market_data_source']

    stage_order = client.post(
        '/user/orders',
        headers={'Authorization': 'Bearer user-token'},
        json={'guided': True, 'recommendation_id': recommendation_id, 'replay_run_id': replay_payload['id']},
    )
    assert stage_order.status_code == 200
    order_payload = stage_order.json()
    assert order_payload['order_id']
    assert order_payload['recommendation_id'] == recommendation_id
    assert order_payload['replay_run_id'] == replay_payload['id']
    assert order_payload['market_data_source'] == latest['payload']['workflow']['market_data_source']

    orders = client.get('/user/orders', headers={'Authorization': 'Bearer user-token'})
    assert orders.status_code == 200
    staged = orders.json()[0]
    assert staged['recommendation_id'] == recommendation_id
    assert staged['replay_run_id'] == replay_payload['id']
    assert staged['symbol'] == 'AAPL'
    assert staged['market_data_source'] == latest['payload']['workflow']['market_data_source']


def test_dashboard_and_provider_health_share_provider_truth_model() -> None:
    _approve_user()
    client.get('/user/me', headers={'Authorization': 'Bearer admin-token'})
    with SessionLocal() as session:
        admin = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == 'clerk_admin')).scalar_one()
        admin.app_role = 'admin'
        admin.approval_status = 'approved'
        session.commit()

    dashboard = client.get('/user/dashboard', headers={'Authorization': 'Bearer user-token'})
    assert dashboard.status_code == 200
    dashboard_provider = dashboard.json()['provider_health']

    provider_health = client.get('/admin/provider-health', headers={'Authorization': 'Bearer admin-token'})
    assert provider_health.status_code == 200
    market_provider = next(item for item in provider_health.json()['providers'] if item['provider'] == 'market_data')

    assert dashboard_provider['configured_provider'] == market_provider['configured_provider']
    assert dashboard_provider['effective_read_mode'] == market_provider['effective_read_mode']
    assert dashboard_provider['workflow_execution_mode'] == market_provider['workflow_execution_mode']


def test_degraded_provider_reports_blocked_or_demo_fallback_explicitly(monkeypatch) -> None:
    _approve_user()

    class DegradedMarketData:
        def provider_health(self, sample_symbol: str):
            from types import SimpleNamespace

            return SimpleNamespace(
                status='error',
                details=f'Probe rejected for {sample_symbol}',
                configured=True,
                feed='starter',
                sample_symbol=sample_symbol,
                latency_ms=None,
                last_success_at=None,
            )

        def latest_snapshot(self, symbol: str, timeframe: str):
            from types import SimpleNamespace

            return SimpleNamespace(
                symbol=symbol,
                as_of=date(2026, 2, 1),
                close=200.0,
                source='fallback',
                fallback_mode=True,
            )

        def historical_bars(self, symbol: str, timeframe: str, limit: int):
            del timeframe, limit
            return _bars(), f'fallback:{symbol}', True

    monkeypatch.setattr(admin_routes, 'market_data_service', DegradedMarketData())
    monkeypatch.setattr(admin_routes.settings, 'market_data_enabled', True)
    monkeypatch.setattr(admin_routes.settings, 'polygon_enabled', True)
    monkeypatch.setattr(admin_routes.settings, 'workflow_demo_fallback', False)

    blocked = client.get('/user/dashboard', headers={'Authorization': 'Bearer user-token'})
    assert blocked.status_code == 200
    assert blocked.json()['provider_health']['workflow_execution_mode'] == 'blocked'

    monkeypatch.setattr(admin_routes.settings, 'workflow_demo_fallback', True)
    monkeypatch.setattr(admin_routes.settings, 'environment', 'local')
    fallback = client.get('/user/dashboard', headers={'Authorization': 'Bearer user-token'})
    assert fallback.status_code == 200
    assert fallback.json()['provider_health']['workflow_execution_mode'] == 'demo_fallback'


def test_onboarding_status_is_user_scoped_for_replay_and_orders() -> None:
    _approve_user()
    client.get('/user/me', headers={'Authorization': 'Bearer admin-token'})
    with SessionLocal() as session:
        second = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == 'clerk_admin')).scalar_one()
        second.approval_status = 'approved'
        session.commit()

    create_rec = client.post(
        '/user/recommendations/generate',
        headers={'Authorization': 'Bearer user-token'},
        json={'symbol': 'AAPL', 'event_text': 'Guided flow seed event'},
    )
    recommendation_id = create_rec.json()['recommendation_id']
    replay = client.post('/user/replay-runs', headers={'Authorization': 'Bearer user-token'}, json={'guided': True, 'recommendation_id': recommendation_id})
    client.post('/user/orders', headers={'Authorization': 'Bearer user-token'}, json={'guided': True, 'recommendation_id': recommendation_id, 'replay_run_id': replay.json()['id']})

    first = client.get('/user/onboarding-status', headers={'Authorization': 'Bearer user-token'})
    second = client.get('/user/onboarding-status', headers={'Authorization': 'Bearer admin-token'})
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()['has_replay'] is True
    assert first.json()['has_order'] is True
    assert second.json()['has_replay'] is False
    assert second.json()['has_order'] is False


def test_guided_mode_blocks_non_equity_replay_and_order_paths() -> None:
    _approve_user()
    replay = client.post('/user/replay-runs', headers={'Authorization': 'Bearer user-token'}, json={'guided': True, 'market_mode': 'options', 'recommendation_id': 'rec_fake'})
    assert replay.status_code == 409
    order = client.post('/user/orders', headers={'Authorization': 'Bearer user-token'}, json={'guided': True, 'market_mode': 'crypto', 'recommendation_id': 'rec_fake'})
    assert order.status_code == 409


def test_empty_workflow_routes_do_not_seed_records() -> None:
    _approve_user()
    recs = client.get('/user/recommendations', headers={'Authorization': 'Bearer user-token'})
    runs = client.get('/user/replay-runs', headers={'Authorization': 'Bearer user-token'})
    orders = client.get('/user/orders', headers={'Authorization': 'Bearer user-token'})
    assert recs.status_code == 200 and isinstance(recs.json(), list)
    assert runs.status_code == 200 and isinstance(runs.json(), list)
    assert orders.status_code == 200 and isinstance(orders.json(), list)
