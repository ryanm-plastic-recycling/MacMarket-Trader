from fastapi.testclient import TestClient
from sqlalchemy import select

from macmarket_trader.api.main import app
from macmarket_trader.domain.models import AppUserModel
from macmarket_trader.storage.db import SessionLocal

client = TestClient(app)


def _seed_and_approve_user() -> int:
    client.get("/user/me", headers={"Authorization": "Bearer user-token"})
    with SessionLocal() as session:
        user = session.execute(
            select(AppUserModel).where(AppUserModel.external_auth_user_id == "clerk_user")
        ).scalar_one()
        user.approval_status = "approved"
        session.commit()
        return user.id


def test_watchlist_create_and_list() -> None:
    _seed_and_approve_user()
    resp = client.post(
        "/user/watchlists",
        headers={"Authorization": "Bearer user-token"},
        json={"name": "Tech picks", "symbols": ["AAPL", "MSFT", "NVDA"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Tech picks"
    assert body["symbols"] == ["AAPL", "MSFT", "NVDA"]
    wl_id = body["id"]

    list_resp = client.get("/user/watchlists", headers={"Authorization": "Bearer user-token"})
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert any(item["id"] == wl_id for item in items)


def test_watchlist_update() -> None:
    _seed_and_approve_user()
    create = client.post(
        "/user/watchlists",
        headers={"Authorization": "Bearer user-token"},
        json={"name": "ETFs", "symbols": ["SPY", "QQQ"]},
    )
    assert create.status_code == 200
    wl_id = create.json()["id"]

    update = client.put(
        f"/user/watchlists/{wl_id}",
        headers={"Authorization": "Bearer user-token"},
        json={"name": "Sector ETFs", "symbols": ["XLK", "XLF", "XLE"]},
    )
    assert update.status_code == 200
    body = update.json()
    assert body["name"] == "Sector ETFs"
    assert body["symbols"] == ["XLK", "XLF", "XLE"]


def test_watchlist_update_symbols_only() -> None:
    _seed_and_approve_user()
    create = client.post(
        "/user/watchlists",
        headers={"Authorization": "Bearer user-token"},
        json={"name": "Biotech", "symbols": ["MRNA"]},
    )
    assert create.status_code == 200
    wl_id = create.json()["id"]

    update = client.put(
        f"/user/watchlists/{wl_id}",
        headers={"Authorization": "Bearer user-token"},
        json={"symbols": ["MRNA", "BNTX", "PFE"]},
    )
    assert update.status_code == 200
    body = update.json()
    assert body["name"] == "Biotech"
    assert body["symbols"] == ["MRNA", "BNTX", "PFE"]


def test_watchlist_delete() -> None:
    _seed_and_approve_user()
    create = client.post(
        "/user/watchlists",
        headers={"Authorization": "Bearer user-token"},
        json={"name": "To delete", "symbols": ["TSLA"]},
    )
    assert create.status_code == 200
    wl_id = create.json()["id"]

    delete = client.delete(
        f"/user/watchlists/{wl_id}",
        headers={"Authorization": "Bearer user-token"},
    )
    assert delete.status_code == 200
    assert delete.json()["deleted"] is True

    list_resp = client.get("/user/watchlists", headers={"Authorization": "Bearer user-token"})
    ids = [item["id"] for item in list_resp.json()]
    assert wl_id not in ids


def test_watchlist_delete_not_found() -> None:
    _seed_and_approve_user()
    resp = client.delete(
        "/user/watchlists/999999",
        headers={"Authorization": "Bearer user-token"},
    )
    assert resp.status_code == 404


def test_watchlist_update_not_found() -> None:
    _seed_and_approve_user()
    resp = client.put(
        "/user/watchlists/999999",
        headers={"Authorization": "Bearer user-token"},
        json={"name": "Ghost"},
    )
    assert resp.status_code == 404


def test_watchlist_create_empty_symbols_rejected() -> None:
    _seed_and_approve_user()
    resp = client.post(
        "/user/watchlists",
        headers={"Authorization": "Bearer user-token"},
        json={"name": "Empty", "symbols": []},
    )
    assert resp.status_code == 400


def test_watchlist_multiple_named_lists_per_user() -> None:
    _seed_and_approve_user()
    client.post(
        "/user/watchlists",
        headers={"Authorization": "Bearer user-token"},
        json={"name": "Morning scan", "symbols": ["AAPL", "GOOGL"]},
    )
    client.post(
        "/user/watchlists",
        headers={"Authorization": "Bearer user-token"},
        json={"name": "Swing setups", "symbols": ["NVDA", "AMD"]},
    )
    list_resp = client.get("/user/watchlists", headers={"Authorization": "Bearer user-token"})
    names = [item["name"] for item in list_resp.json()]
    assert "Morning scan" in names
    assert "Swing setups" in names
