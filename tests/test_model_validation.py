from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str):
    path = REPO_ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_validation_db(path: Path, *, include_daily_bars: bool = True) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE recommendations (
                id INTEGER PRIMARY KEY,
                recommendation_id TEXT,
                app_user_id INTEGER,
                symbol TEXT,
                created_at TEXT,
                payload TEXT,
                display_id TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE paper_trades (
                id INTEGER PRIMARY KEY,
                app_user_id INTEGER,
                symbol TEXT,
                side TEXT,
                entry_price REAL,
                exit_price REAL,
                quantity REAL,
                gross_pnl REAL,
                net_pnl REAL,
                realized_pnl REAL,
                opened_at TEXT,
                closed_at TEXT,
                position_id INTEGER,
                hold_seconds INTEGER,
                recommendation_id TEXT,
                replay_run_id INTEGER,
                order_id TEXT,
                close_reason TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE replay_runs (
                id INTEGER PRIMARY KEY,
                has_stageable_candidate INTEGER
            )
            """
        )
        if include_daily_bars:
            conn.execute(
                """
                CREATE TABLE daily_bars (
                    id INTEGER PRIMARY KEY,
                    symbol TEXT,
                    bar_date TEXT,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER
                )
                """
            )
        rec_payloads = [
            {
                "outcome": "approved",
                "approved": True,
                "symbol": "AAPL",
                "entry": {"setup_type": "event_continuation"},
                "regime_context": {"market_regime": "risk_on_trend"},
                "catalyst": {"type": "earnings"},
                "quality": {"expected_rr": 2.0},
                "workflow": {
                    "timeframe": "1D",
                    "market_data_source": "polygon",
                    "already_open": False,
                },
                "risk_calendar": {"decision": {"decision_state": "clear"}},
            },
            {
                "outcome": "no_trade",
                "approved": False,
                "symbol": "MSFT",
                "entry": {"setup_type": "pullback"},
                "regime_context": {"market_regime": "mixed"},
                "catalyst": {"type": "macro"},
                "quality": {"expected_rr": 1.4},
                "workflow": {
                    "timeframe": "1D",
                    "market_data_source": "sk-proj-" + ("b" * 32),
                    "already_open": True,
                },
                "risk_calendar": {"decision": {"decision_state": "no_trade"}},
            },
        ]
        for idx, payload in enumerate(rec_payloads, start=1):
            conn.execute(
                "INSERT INTO recommendations VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    idx,
                    f"rec_{idx}",
                    1,
                    payload["symbol"],
                    f"2026-01-0{idx}T14:30:00Z",
                    json.dumps(payload),
                    f"REC-{idx}",
                ),
            )
        trades = [
            (1, 1, "AAPL", "long", 100.0, 110.0, 10.0, 100.0, 100.0, 100.0, "2026-01-01T14:30:00Z", "2026-01-02T14:30:00Z", 1, 86400, "rec_1", 1, "ord_1", "manual_close"),
            (2, 1, "AAPL", "long", 100.0, 95.0, 10.0, -50.0, -50.0, -50.0, "2026-01-03T14:30:00Z", "2026-01-04T14:30:00Z", 2, 86400, "rec_1", 1, "ord_2", "manual_close"),
            (3, 1, "MSFT", "long", 200.0, 205.0, 5.0, 25.0, 25.0, 25.0, "2026-01-05T14:30:00Z", "2026-01-06T14:30:00Z", 3, 86400, "rec_2", 1, "ord_3", "manual_close"),
        ]
        conn.executemany("INSERT INTO paper_trades VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", trades)
        conn.execute("INSERT INTO replay_runs VALUES (1, 1)")
        if include_daily_bars:
            bars = [
                ("SPY", "2026-01-01T00:00:00Z", 100.0),
                ("SPY", "2026-01-06T00:00:00Z", 105.0),
                ("QQQ", "2026-01-01T00:00:00Z", 200.0),
                ("QQQ", "2026-01-06T00:00:00Z", 190.0),
                ("SPX", "2026-01-01T00:00:00Z", 5000.0),
                ("SPX", "2026-01-06T00:00:00Z", 5100.0),
                ("NDX", "2026-01-01T00:00:00Z", 18000.0),
                ("NDX", "2026-01-06T00:00:00Z", 18100.0),
                ("RUT", "2026-01-01T00:00:00Z", 2100.0),
                ("RUT", "2026-01-06T00:00:00Z", 2080.0),
                ("VIX", "2026-01-01T00:00:00Z", 18.0),
                ("VIX", "2026-01-06T00:00:00Z", 16.0),
            ]
            for idx, (symbol, date, close) in enumerate(bars, start=1):
                conn.execute(
                    "INSERT INTO daily_bars VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (idx, symbol, date, close, close, close, close, 1_000_000),
                )
        conn.commit()


def test_model_validation_generates_json_and_markdown(tmp_path: Path) -> None:
    module = _load_script("run_model_validation.py")
    database = tmp_path / "validation.sqlite3"
    _create_validation_db(database)

    report = module.generate_model_validation(database=database, evidence_dir=tmp_path / "evidence")

    assert Path(report["evidence_json"]).exists()
    assert Path(report["evidence_markdown"]).exists()
    assert report["paper_only"] is True
    assert report["live_trading_performance"] is False
    assert "SPX" in report["baseline_comparison"]["index_benchmarks"]
    assert "VIX" in report["baseline_comparison"]["volatility_context"]


def test_model_validation_redacts_secrets_from_report(tmp_path: Path) -> None:
    module = _load_script("run_model_validation.py")
    database = tmp_path / "validation.sqlite3"
    _create_validation_db(database)
    secret = "sk-proj-" + ("b" * 32)

    report = module.generate_model_validation(database=database, evidence_dir=tmp_path / "evidence")
    serialized = json.dumps(json.loads(Path(report["evidence_json"]).read_text(encoding="utf-8")))

    assert secret not in serialized
    assert "[REDACTED]" in serialized


def test_model_validation_reports_missing_data_without_fabricating(tmp_path: Path) -> None:
    module = _load_script("run_model_validation.py")
    database = tmp_path / "empty.sqlite3"
    with sqlite3.connect(database):
        pass

    report = module.generate_model_validation(database=database, evidence_dir=tmp_path / "evidence")

    assert report["recommendations"]["count"] == 0
    assert report["paper_trades"]["closed_count"] == 0
    assert report["baseline_comparison"]["status"] == "missing_data"
    assert any("recommendations table not available" in item for item in report["missing_data"])


def test_model_validation_computes_paper_trade_metrics(tmp_path: Path) -> None:
    module = _load_script("run_model_validation.py")
    database = tmp_path / "validation.sqlite3"
    _create_validation_db(database)

    report = module.generate_model_validation(database=database, evidence_dir=tmp_path / "evidence")
    trades = report["paper_trades"]

    assert trades["closed_count"] == 3
    assert trades["total_net_pnl"] == 75.0
    assert trades["win_rate"] == 0.666667
    assert trades["average_win"] == 62.5
    assert trades["average_loss"] == -50.0
    assert trades["max_drawdown"] == 50.0
    assert trades["holding_period_days"]["average"] == 1.0
    assert report["recommendations"]["approved_count"] == 1
    assert report["recommendations"]["rejected_count"] == 1
    assert report["recommendations"]["average_expected_rr"] == 1.7
    assert report["attribution"]["by_setup"]["event_continuation"]["closed_trade_count"] == 2


def test_model_validation_baseline_handles_missing_provider_data_safely(tmp_path: Path) -> None:
    module = _load_script("run_model_validation.py")
    database = tmp_path / "validation.sqlite3"
    _create_validation_db(database, include_daily_bars=False)

    report = module.generate_model_validation(database=database, evidence_dir=tmp_path / "evidence")

    assert report["baseline_comparison"]["status"] == "missing_data"
    assert report["baseline_comparison"]["baselines"] == {}
    assert any("daily_bars table not available" in item for item in report["missing_data"])


def test_model_validation_does_not_use_llm_for_metrics(tmp_path: Path) -> None:
    module = _load_script("run_model_validation.py")
    database = tmp_path / "validation.sqlite3"
    _create_validation_db(database)

    report = module.generate_model_validation(database=database, evidence_dir=tmp_path / "evidence")

    assert report["llm_used_for_metrics"] is False
    assert "llm" not in " ".join(report["validation_inputs_needed"]).lower()
