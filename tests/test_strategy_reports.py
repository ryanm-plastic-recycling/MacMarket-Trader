from datetime import date, datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from macmarket_trader.api.main import app
from macmarket_trader.api.routes import admin as admin_routes
from macmarket_trader.config import settings
from macmarket_trader.data.providers.market_data import DeterministicFallbackMarketDataProvider, MarketProviderHealth, OptionContractResolution
from macmarket_trader.domain.enums import MarketMode
from macmarket_trader.domain.models import AppUserModel, StrategyReportRunModel
from macmarket_trader.domain.schemas import ExpectedRange
from macmarket_trader.domain.time import calendar_days_to_expiration
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
    assert 'analysis_packets' in payload
    assert 'watchlist_only' in payload
    assert 'no_trade' in payload
    assert 'queue' in payload
    assert 'summary' in payload

    with SessionLocal() as session:
        run_row = session.execute(select(StrategyReportRunModel).where(StrategyReportRunModel.schedule_id == schedule_id)).scalar_one()
        assert run_row.status == 'sent'

def test_strategy_schedule_non_equity_mode_runs_successfully() -> None:
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
    assert run_now.status_code == 200
    payload = run_now.json()
    assert 'top_candidates' in payload
    assert 'queue' in payload


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


def test_calendar_days_to_expiration_uses_utc_calendar_dates() -> None:
    as_of = datetime(2026, 5, 3, 14, 0, tzinfo=timezone.utc)

    assert calendar_days_to_expiration("2026-05-16", as_of=as_of) == 13
    assert calendar_days_to_expiration("2026-05-02", as_of=as_of) == 0
    assert calendar_days_to_expiration("2026-05-02", as_of=as_of, allow_expired_negative=True) == -1


def test_analysis_setup_accepts_market_mode_and_returns_setup_for_options(monkeypatch) -> None:
    monkeypatch.setattr(admin_routes, "utc_now", lambda: datetime(2026, 5, 3, 14, 0, tzinfo=timezone.utc))
    _seed_and_approve_user()
    resp = client.get(
        '/user/analysis/setup',
        params={'req_symbol': 'AAPL', 'market_mode': 'options', 'strategy': 'Iron Condor'},
        headers={'Authorization': 'Bearer user-token'},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload['market_mode'] == 'options'
    assert 'operator_disclaimer' in payload
    assert 'Options research' in payload['operator_disclaimer']
    assert payload['option_structure']['type'] == 'iron_condor'
    assert payload['option_structure']['expiration'] == '2026-05-16'
    assert payload['option_structure']['dte'] == 13
    assert payload['expected_range']['horizon_value'] == 13
    assert payload['expected_range']['horizon_unit'] == 'calendar_days'
    assert payload['option_structure']['dte'] != 33
    assert payload['expected_range']['horizon_value'] != 33
    assert payload['expected_range']['status'] == 'computed'
    assert payload['expected_range']['method'] == 'iv_1sigma'
    assert payload['expected_range']['lower_bound'] < payload['expected_range']['upper_bound']


def test_analysis_setup_snaps_options_research_legs_to_provider_contracts(monkeypatch) -> None:
    monkeypatch.setattr(admin_routes, "utc_now", lambda: datetime(2026, 5, 3, 14, 0, tzinfo=timezone.utc))
    monkeypatch.setattr(settings, "polygon_enabled", True)
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    monkeypatch.setattr(settings, "polygon_base_url", "https://api.polygon.io")

    class StubMarketDataService:
        def historical_bars(self, symbol: str, timeframe: str, limit: int):
            return DeterministicFallbackMarketDataProvider().fetch_historical_bars(symbol, timeframe, limit), "polygon", False

        def latest_snapshot(self, symbol: str, timeframe: str):
            return DeterministicFallbackMarketDataProvider().fetch_latest_snapshot(symbol, timeframe)

        def options_chain_preview(self, symbol: str, limit: int = 50):
            return {"underlying": symbol, "expiry": "2026-05-16", "calls": [], "puts": [], "source": "test"}

        def resolve_option_contract(self, *, underlying_symbol: str, expiration, option_type: str, target_strike: float):
            selected = round(target_strike)
            right = "C" if option_type == "call" else "P"
            return OptionContractResolution(
                requested_underlying=underlying_symbol.upper(),
                underlying_asset_type="equity",
                target_expiration=expiration,
                selected_expiration=expiration,
                option_type=option_type,
                target_strike=target_strike,
                selected_strike=float(selected),
                option_symbol=f"O:{underlying_symbol.upper()}260516{right}{int(selected * 1000):08d}",
                provider="polygon",
                contract_selection_method="provider_reference_exact_expiration",
                strike_snap_distance=abs(float(selected) - target_strike),
            )

        def provider_health(self, sample_symbol: str = "AAPL") -> MarketProviderHealth:
            return MarketProviderHealth(
                provider="market_data", mode="polygon", status="ok",
                details="stub", configured=True, feed="stocks", sample_symbol=sample_symbol,
            )

    monkeypatch.setattr(admin_routes, "market_data_service", StubMarketDataService())
    _seed_and_approve_user()
    resp = client.get(
        "/user/analysis/setup",
        params={"req_symbol": "AAPL", "market_mode": "options", "strategy": "Iron Condor"},
        headers={"Authorization": "Bearer user-token"},
    )

    assert resp.status_code == 200, resp.text
    structure = resp.json()["option_structure"]
    assert structure["contract_resolution_status"] == "resolved"
    assert structure["paper_persistence_allowed"] is True
    assert structure["contract_resolution_summary"] == "Selected listed contracts from provider chain."
    assert all(leg["option_symbol"].startswith("O:AAPL260516") for leg in structure["legs"])
    assert all(leg["target_strike"] != leg["strike"] for leg in structure["legs"])


def test_analysis_setup_blocks_iron_condor_when_provider_chain_missing_puts(monkeypatch) -> None:
    monkeypatch.setattr(admin_routes, "utc_now", lambda: datetime(2026, 5, 3, 14, 0, tzinfo=timezone.utc))
    monkeypatch.setattr(settings, "polygon_enabled", True)
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    monkeypatch.setattr(settings, "polygon_base_url", "https://api.polygon.io")

    class CallsOnlyOptionsService:
        def historical_bars(self, symbol: str, timeframe: str, limit: int):
            return DeterministicFallbackMarketDataProvider().fetch_historical_bars(symbol, timeframe, limit), "polygon", False

        def latest_snapshot(self, symbol: str, timeframe: str):
            return DeterministicFallbackMarketDataProvider().fetch_latest_snapshot(symbol, timeframe)

        def options_chain_preview(self, symbol: str, limit: int = 50):
            return {
                "underlying": symbol,
                "expiry": "2026-05-16",
                "calls": [{"ticker": "O:QQQ260516C00480000", "strike": 480.0, "expiry": "2026-05-16", "option_type": "call"}],
                "puts": None,
                "source": "test",
            }

        def option_contracts(self, *, underlying_symbol: str, expiration, option_type: str | None = None, limit: int = 1000):
            del underlying_symbol, expiration, option_type, limit
            return [
                {"ticker": "O:QQQ260516C00480000", "contract_type": "call", "strike_price": 480.0, "expiration_date": "2026-05-16"},
                {"ticker": "O:QQQ260516C00485000", "contract_type": "call", "strike_price": 485.0, "expiration_date": "2026-05-16"},
            ]

        def provider_health(self, sample_symbol: str = "AAPL") -> MarketProviderHealth:
            return MarketProviderHealth(provider="market_data", mode="polygon", status="ok", details="stub", configured=True, feed="stocks", sample_symbol=sample_symbol)

    monkeypatch.setattr(admin_routes, "market_data_service", CallsOnlyOptionsService())
    _seed_and_approve_user()

    resp = client.get(
        "/user/analysis/setup",
        params={"req_symbol": "QQQ", "market_mode": "options", "strategy": "Iron Condor"},
        headers={"Authorization": "Bearer user-token"},
    )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    structure = payload["option_structure"]
    assert structure["paper_persistence_allowed"] is False
    assert structure["contract_resolution_status"] == "unresolved"
    assert structure["contract_resolution_summary"] == "Cannot build iron condor: provider returned incomplete chain; puts missing."
    assert structure["max_profit"] is None
    assert structure["max_loss"] is None
    assert structure["breakeven_low"] is None
    assert structure["breakeven_high"] is None
    assert payload["expected_range"]["status"] == "blocked"


def test_analysis_setup_rejects_all_four_iron_condor_legs_at_same_strike(monkeypatch) -> None:
    monkeypatch.setattr(admin_routes, "utc_now", lambda: datetime(2026, 5, 3, 14, 0, tzinfo=timezone.utc))
    monkeypatch.setattr(settings, "polygon_enabled", True)
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    monkeypatch.setattr(settings, "polygon_base_url", "https://api.polygon.io")

    class CollisionResolvingService:
        def historical_bars(self, symbol: str, timeframe: str, limit: int):
            return DeterministicFallbackMarketDataProvider().fetch_historical_bars(symbol, timeframe, limit), "polygon", False

        def latest_snapshot(self, symbol: str, timeframe: str):
            return DeterministicFallbackMarketDataProvider().fetch_latest_snapshot(symbol, timeframe)

        def options_chain_preview(self, symbol: str, limit: int = 50):
            return {"underlying": symbol, "expiry": "2026-05-16", "calls": [], "puts": [], "source": "test"}

        def resolve_option_contract(self, *, underlying_symbol: str, expiration, option_type: str, target_strike: float):
            right = "C" if option_type == "call" else "P"
            return OptionContractResolution(
                requested_underlying=underlying_symbol.upper(),
                underlying_asset_type="etf",
                target_expiration=expiration,
                selected_expiration=expiration,
                option_type=option_type,
                target_strike=target_strike,
                selected_strike=480.0,
                option_symbol=f"O:{underlying_symbol.upper()}260516{right}00480000",
                provider="polygon",
                contract_selection_method="provider_reference_exact_expiration",
                strike_snap_distance=abs(480.0 - target_strike),
            )

        def provider_health(self, sample_symbol: str = "AAPL") -> MarketProviderHealth:
            return MarketProviderHealth(provider="market_data", mode="polygon", status="ok", details="stub", configured=True, feed="stocks", sample_symbol=sample_symbol)

    monkeypatch.setattr(admin_routes, "market_data_service", CollisionResolvingService())
    _seed_and_approve_user()

    resp = client.get(
        "/user/analysis/setup",
        params={"req_symbol": "SPY", "market_mode": "options", "strategy": "Iron Condor"},
        headers={"Authorization": "Bearer user-token"},
    )

    assert resp.status_code == 200, resp.text
    structure = resp.json()["option_structure"]
    assert structure["paper_persistence_allowed"] is False
    assert structure["structure_validation_status"] == "invalid"
    assert structure["structure_validation_summary"] == "iron_condor_requires_ordered_strikes"
    assert {leg["strike"] for leg in structure["legs"]} == {480.0}
    assert structure["max_loss"] is None


def test_analysis_setup_selects_distinct_ordered_listed_iron_condor_contracts(monkeypatch) -> None:
    monkeypatch.setattr(admin_routes, "utc_now", lambda: datetime(2026, 5, 3, 14, 0, tzinfo=timezone.utc))
    monkeypatch.setattr(settings, "polygon_enabled", True)
    monkeypatch.setattr(settings, "polygon_api_key", "polygon-key")
    monkeypatch.setattr(settings, "polygon_base_url", "https://api.polygon.io")
    expiration = date(2026, 5, 16)

    def _row(right: str, strike: float) -> dict[str, object]:
        suffix = "C" if right == "call" else "P"
        return {
            "ticker": f"O:AAPL260516{suffix}{int(strike * 1000):08d}",
            "contract_type": right,
            "strike_price": strike,
            "expiration_date": expiration.isoformat(),
            "open_interest": 100,
        }

    class ListedContractService:
        def historical_bars(self, symbol: str, timeframe: str, limit: int):
            return DeterministicFallbackMarketDataProvider().fetch_historical_bars(symbol, timeframe, limit), "polygon", False

        def latest_snapshot(self, symbol: str, timeframe: str):
            return DeterministicFallbackMarketDataProvider().fetch_latest_snapshot(symbol, timeframe)

        def options_chain_preview(self, symbol: str, limit: int = 50):
            return {
                "underlying": symbol,
                "expiry": expiration.isoformat(),
                "calls": [{"ticker": "O:AAPL260516C00110000", "strike": 110.0, "expiry": expiration.isoformat()}],
                "puts": [{"ticker": "O:AAPL260516P00095000", "strike": 95.0, "expiry": expiration.isoformat()}],
                "source": "test",
            }

        def option_contracts(self, *, underlying_symbol: str, expiration, option_type: str | None = None, limit: int = 1000):
            del underlying_symbol, option_type, limit
            assert expiration == date(2026, 5, 16)
            return [
                _row("put", 90.0),
                _row("put", 95.0),
                _row("put", 100.0),
                _row("call", 105.0),
                _row("call", 110.0),
                _row("call", 115.0),
            ]

        def provider_health(self, sample_symbol: str = "AAPL") -> MarketProviderHealth:
            return MarketProviderHealth(provider="market_data", mode="polygon", status="ok", details="stub", configured=True, feed="stocks", sample_symbol=sample_symbol)

    monkeypatch.setattr(admin_routes, "market_data_service", ListedContractService())
    _seed_and_approve_user()

    resp = client.get(
        "/user/analysis/setup",
        params={"req_symbol": "AAPL", "market_mode": "options", "strategy": "Iron Condor"},
        headers={"Authorization": "Bearer user-token"},
    )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    structure = payload["option_structure"]
    strikes = [leg["strike"] for leg in structure["legs"]]
    assert structure["contract_resolution_status"] == "resolved"
    assert structure["structure_validation_status"] == "valid"
    assert structure["paper_persistence_allowed"] is True
    assert strikes == sorted(strikes)
    assert len(set(strikes)) == 4
    assert all(leg["option_symbol"].startswith("O:AAPL260516") for leg in structure["legs"])
    assert all(leg["contract_selection"]["contract_selection_method"] == "provider_reference_exact_expiration" for leg in structure["legs"])
    assert all(leg["target_strike"] is not None for leg in structure["legs"])
    assert structure["max_loss"] > 0
    assert structure["breakeven_low"] < structure["breakeven_high"]
    assert payload["expected_range"]["status"] == "computed"


def test_analysis_setup_invalid_strategy_for_market_mode_returns_400_with_supported_labels() -> None:
    _seed_and_approve_user()
    resp = client.get(
        '/user/analysis/setup',
        params={'req_symbol': 'AAPL', 'market_mode': 'options', 'strategy': 'Event Continuation'},
        headers={'Authorization': 'Bearer user-token'},
    )
    assert resp.status_code == 400
    payload = resp.json()
    assert "Unsupported strategy" in payload['detail']['error']
    assert 'Iron Condor' in payload['detail']['supported_strategies']
    assert 'Covered Call Preview' in payload['detail']['supported_strategies']


def test_analysis_setup_defaults_to_first_strategy_only_when_strategy_not_supplied() -> None:
    _seed_and_approve_user()
    resp = client.get(
        '/user/analysis/setup',
        params={'req_symbol': 'BTCUSD', 'market_mode': 'crypto'},
        headers={'Authorization': 'Bearer user-token'},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload['market_mode'] == 'crypto'
    assert payload['strategy'] == 'Crypto Spot Breakout'


def test_analysis_setup_accepts_valid_crypto_strategy_label() -> None:
    _seed_and_approve_user()
    resp = client.get(
        '/user/analysis/setup',
        params={'req_symbol': 'BTCUSD', 'market_mode': 'crypto', 'strategy': 'Funding Extreme Reversion'},
        headers={'Authorization': 'Bearer user-token'},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload['strategy'] == 'Funding Extreme Reversion'


def test_expected_range_schema_serialization_contract() -> None:
    payload = ExpectedRange(
        method='atm_straddle_mid',
        horizon_value=30,
        horizon_unit='calendar_days',
        reference_price_type='underlying_last',
        absolute_move=4.2,
        percent_move=2.1,
        lower_bound=196.0,
        upper_bound=204.4,
        status='computed',
        reason=None,
    ).model_dump(mode='json')
    assert payload['method'] == 'atm_straddle_mid'
    assert payload['horizon_value'] == 30
    assert payload['status'] == 'computed'


def test_analysis_setup_expected_range_blocked_reason_for_low_iv() -> None:
    _seed_and_approve_user()
    resp = client.get(
        '/user/analysis/setup',
        params={'req_symbol': 'LOWIV', 'market_mode': 'options', 'strategy': 'Iron Condor'},
        headers={'Authorization': 'Bearer user-token'},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload['expected_range']['status'] == 'blocked'
    assert payload['expected_range']['reason'] == 'insufficient_iv_quality'


def test_analysis_setup_expected_range_omitted_reason_for_non_iron_condor() -> None:
    _seed_and_approve_user()
    resp = client.get(
        '/user/analysis/setup',
        params={'req_symbol': 'AAPL', 'market_mode': 'options', 'strategy': 'Covered Call Preview'},
        headers={'Authorization': 'Bearer user-token'},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload['expected_range']['status'] == 'omitted'
    assert payload['expected_range']['reason'] == 'strategy_not_configured_for_expected_range_preview'
    assert payload['expected_range']['method'] is None


def test_analysis_setup_returns_functional_setup_for_crypto() -> None:
    _seed_and_approve_user()
    resp = client.get(
        '/user/analysis/setup',
        params={'req_symbol': 'BTCUSD', 'market_mode': 'crypto', 'strategy': 'Crypto Spot Breakout'},
        headers={'Authorization': 'Bearer user-token'},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload['market_mode'] == 'crypto'
    assert 'operator_disclaimer' in payload
    assert 'Crypto research' in payload['operator_disclaimer']
    assert 'crypto_context' in payload
    assert payload['crypto_context']['mark_price'] > 0


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
