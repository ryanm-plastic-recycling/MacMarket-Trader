from datetime import date, timedelta

from fastapi.testclient import TestClient

from macmarket_trader.api.main import app


def test_recommendations_generate_contract() -> None:
    base = date(2026, 1, 1)
    bars = [
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
    client = TestClient(app)
    response = client.post(
        "/recommendations/generate",
        json={"symbol": "AAPL", "event_text": "Earnings beat with strong guidance", "bars": bars},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["thesis"]
    assert payload["catalyst"]["type"]
    assert payload["entry"]["zone_low"] < payload["targets"]["target_2"]
    assert payload["constraints"]["final_share_count"] == payload["sizing"]["shares"]
    assert payload["evidence"]["headlines"] == []
