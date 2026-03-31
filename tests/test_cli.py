import json
import subprocess


def test_cli_health_command() -> None:
    result = subprocess.run(
        ["python", "-m", "macmarket_trader.cli", "health"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
