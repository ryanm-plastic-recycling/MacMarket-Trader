from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from macmarket_trader.api.main import app
from macmarket_trader.domain.enums import MarketMode
from macmarket_trader.domain.models import AppUserModel, StrategyReportRunModel
from macmarket_trader.storage.db import SessionLocal
from macmarket_trader.storage.repositories import EmailLogRepository, StrategyReportRepository
from macmarket_trader.ranking_engine import DeterministicRankingEngine
from macmarket_trader.strategy_reports import StrategyReportService
from macmarket_trader.data.providers.mock import ConsoleEmailProvider

client = TestClient(app)


def _seed_and_approve_user() -> None:
    client.get('/user/me', headers={'Authorization': 'Bearer user-token'})
    with SessionLocal() as session:
        user = session.execute(select(AppUserModel).where(AppUserModel.external_auth_user_id == 'clerk_user')).scalar_one()
        user.approval_status = 'approved'
        session.commit()


def test_strategy_schedule_create_and_run_now() -> None:
    _seed_and_approve_user()
    create = client.post(
        '/user/strategy-schedules',
        headers={'Authorization': 'Bearer user-token'},
        json={
            'name': 'Desk morning scan',
            'frequency': 'weekdays',
            'run_time': '08:30',
            'timezone': 'America/New_York',
            'market_mode': 'equities',
            'symbols': ['AAPL', 'MSFT'],
            'enabled_strategies': ['Event Continuation'],
            'top_n': 3,
        },
    )
    assert create.status_code == 200
    schedule_id = create.json()['id']

    run_now = client.post(f'/user/strategy-schedules/{schedule_id}/run', headers={'Authorization': 'Bearer user-token'})
    assert run_now.status_code == 200
    payload = run_now.json()
    assert 'top_candidates' in payload
    assert 'watchlist_only' in payload
    assert 'no_trade' in payload
    assert 'queue' in payload
    assert 'summary' in payload

    with SessionLocal() as session:
        run_row = session.execute(select(StrategyReportRunModel).where(StrategyReportRunModel.schedule_id == schedule_id)).scalar_one()
        assert run_row.status == 'sent'

def test_strategy_schedule_non_equity_mode_blocks_run_cleanly() -> None:
    _seed_and_approve_user()
    create = client.post(
        '/user/strategy-schedules',
        headers={'Authorization': 'Bearer user-token'},
        json={
            'name': 'Options research scan',
            'frequency': 'weekdays',
            'run_time': '08:30',
            'timezone': 'America/New_York',
            'market_mode': 'options',
            'symbols': ['SPY'],
            'enabled_strategies': ['Iron Condor'],
            'top_n': 3,
        },
    )
    assert create.status_code == 200
    schedule_id = create.json()['id']

    run_now = client.post(f'/user/strategy-schedules/{schedule_id}/run', headers={'Authorization': 'Bearer user-token'})
    assert run_now.status_code == 409
    assert 'planned research preview' in run_now.json()['detail']


def test_strategy_report_due_runner_selects_due_schedules() -> None:
    repo = StrategyReportRepository(SessionLocal)
    email_repo = EmailLogRepository(SessionLocal)
    service = StrategyReportService(report_repo=repo, email_provider=ConsoleEmailProvider(), email_log_repo=email_repo)
    with SessionLocal() as session:
        user = AppUserModel(
            external_auth_user_id='scheduler_user',
            email='scheduler@example.com',
            display_name='Scheduler',
            approval_status='approved',
            app_role='user',
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        schedule = repo.create_schedule(
            app_user_id=user.id,
            name='due-test',
            frequency='daily',
            run_time='08:30',
            timezone_name='America/New_York',
            email_target='scheduler@example.com',
            enabled=True,
            next_run_at=datetime.now(timezone.utc),
            payload={'symbols': ['AAPL'], 'enabled_strategies': ['Event Continuation'], 'top_n': 2},
        )
    output = service.run_due_schedules(now=datetime.now(timezone.utc))
    assert output
    assert output[0]['schedule_id'] == schedule.id


def test_symbol_analyze_response_shape() -> None:
    _seed_and_approve_user()
    resp = client.get('/user/analyze/AAPL', headers={'Authorization': 'Bearer user-token'})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload['symbol'] == 'AAPL'
    assert 'market_regime' in payload
    assert 'strategy_scoreboard' in payload
    assert 'levels' in payload


def test_analysis_setup_accepts_market_mode_and_returns_preview_for_options() -> None:
    _seed_and_approve_user()
    resp = client.get(
        '/user/analysis/setup',
        params={'req_symbol': 'AAPL', 'market_mode': 'options', 'strategy': 'Iron Condor'},
        headers={'Authorization': 'Bearer user-token'},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload['market_mode'] == 'options'
    assert payload['status'] == 'planned_research_preview'
    assert payload['execution_enabled'] is False
    assert payload['option_structure']['type'] == 'iron_condor'


def test_analysis_setup_returns_preview_for_crypto() -> None:
    _seed_and_approve_user()
    resp = client.get(
        '/user/analysis/setup',
        params={'req_symbol': 'BTCUSD', 'market_mode': 'crypto', 'strategy': 'Crypto Spot Breakout'},
        headers={'Authorization': 'Bearer user-token'},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload['market_mode'] == 'crypto'
    assert payload['status'] == 'planned_research_preview'
    assert payload['execution_enabled'] is False
    assert 'crypto_context' in payload


def test_strategy_schedule_list_includes_run_summary() -> None:
    _seed_and_approve_user()
    create = client.post(
        '/user/strategy-schedules',
        headers={'Authorization': 'Bearer user-token'},
        json={'name': 'Summary scan', 'symbols': ['AAPL'], 'market_mode': 'equities'},
    )
    schedule_id = create.json()['id']
    run_now = client.post(f'/user/strategy-schedules/{schedule_id}/run', headers={'Authorization': 'Bearer user-token'})
    assert run_now.status_code == 200
    listing = client.get('/user/strategy-schedules', headers={'Authorization': 'Bearer user-token'})
    assert listing.status_code == 200
    row = next(item for item in listing.json() if item['id'] == schedule_id)
    assert row['config_summary']['market_mode'] == 'equities'
    assert row['latest_payload_summary']['top_candidate_count'] >= 0
    assert row['history'][0]['summary']['total'] >= 0


def test_ranking_engine_outputs_explainable_fields() -> None:
    bars, source, fallback_mode = admin_provider_bars()
    result = DeterministicRankingEngine().rank_candidates(
        bars_by_symbol={'AAPL': (bars, source, fallback_mode)},
        strategies=['Event Continuation'],
        market_mode=MarketMode.EQUITIES,
        timeframe='1D',
    )
    candidate = result['queue'][0]
    assert candidate['strategy'] == 'Event Continuation'
    assert 'score_breakdown' in candidate
    assert 'reason_text' in candidate


def admin_provider_bars():
    bars, source, fallback_mode = StrategyReportService(
        report_repo=StrategyReportRepository(SessionLocal),
        email_provider=ConsoleEmailProvider(),
        email_log_repo=EmailLogRepository(SessionLocal),
    ).market_data_service.historical_bars(symbol='AAPL', timeframe='1D', limit=60)
    return bars, source, fallback_mode
