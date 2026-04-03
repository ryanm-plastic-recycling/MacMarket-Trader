import subprocess
import sys


def test_cli_health_command() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "macmarket_trader.cli", "health"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "ok" in result.stdout.lower()


def test_cli_run_due_strategy_schedules_command() -> None:
    result = subprocess.run([sys.executable, "-m", "macmarket_trader.cli", "run-due-strategy-schedules"], check=True, capture_output=True, text=True)
    assert "runs" in result.stdout
