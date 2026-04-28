"""Phase 6A close-trade lifecycle tests.

Covers:
  1. Order fill creates paper_position with correct lineage.
  2. Multiple fills on same (user, symbol, side) aggregate into one position
     with correct weighted-average entry price.
  3. Close endpoint computes realized_pnl correctly for a long position.
  4. Close endpoint computes realized_pnl correctly for a short position.
  5. Close endpoint blocks non-owner with 404.
  6. Close endpoint blocks already-closed position with 400.
  7. List endpoints scope strictly to the owning user.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from macmarket_trader.api.main import app
from macmarket_trader.domain.models import (
    AppUserModel,
    AuditLogModel,
    FillModel,
    OrderModel,
    PaperPositionModel,
    PaperTradeModel,
)
from macmarket_trader.storage.db import SessionLocal

client = TestClient(app)

_USER_AUTH = {"Authorization": "Bearer user-token"}
_ADMIN_AUTH = {"Authorization": "Bearer admin-token"}


def _seed_approved_user(token: str = "user-token", external_id: str = "clerk_user") -> int:
    resp = client.get("/user/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    with SessionLocal() as session:
        user = session.execute(
            select(AppUserModel).where(AppUserModel.external_auth_user_id == external_id)
        ).scalar_one()
        user.approval_status = "approved"
        session.commit()
        return user.id


def _stage_order_and_get_position(rec_uid: str, token: str = "user-token") -> dict:
    """Stage a paper order from a recommendation and return the resulting open position row."""
    order_resp = client.post(
        "/user/orders",
        headers={"Authorization": f"Bearer {token}"},
        json={"recommendation_id": rec_uid},
    )
    assert order_resp.status_code == 200, order_resp.text
    order = order_resp.json()
    pos_resp = client.get(
        "/user/paper-positions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert pos_resp.status_code == 200, pos_resp.text
    open_positions = [p for p in pos_resp.json() if p["status"] == "open"]
    assert open_positions, f"expected an open position after staging order; got: {pos_resp.json()}"
    return {"order": order, "position": open_positions[0]}


def _seed_recommendation(symbol: str = "AAPL") -> str:
    """Generate + promote a queue candidate so a stored, approved recommendation exists."""
    queue_resp = client.post(
        "/user/recommendations/queue",
        headers=_USER_AUTH,
        json={"symbols": [symbol], "timeframe": "1D", "market_mode": "equities"},
    )
    assert queue_resp.status_code == 200, queue_resp.text
    body = queue_resp.json()
    assert body["queue"], f"empty queue: {body}"
    candidate = body["queue"][0]
    promote_resp = client.post(
        "/user/recommendations/queue/promote",
        headers=_USER_AUTH,
        json={**candidate, "action": "make_active"},
    )
    assert promote_resp.status_code == 200, promote_resp.text
    return promote_resp.json()["recommendation_id"]


# ---------------------------------------------------------------------------
# Test 1 — Order fill creates paper_position with correct lineage
# ---------------------------------------------------------------------------

def test_order_fill_creates_paper_position_with_lineage() -> None:
    user_id = _seed_approved_user()
    rec_uid = _seed_recommendation()
    bundle = _stage_order_and_get_position(rec_uid)

    position = bundle["position"]
    assert position["symbol"] == "AAPL"
    assert position["side"] == "long"
    assert position["status"] == "open"
    assert position["opened_qty"] > 0
    assert position["remaining_qty"] == position["opened_qty"]
    assert position["avg_entry_price"] > 0
    assert position["recommendation_id"] == rec_uid
    assert position["order_id"] == bundle["order"]["order_id"]


# ---------------------------------------------------------------------------
# Test 2 — Multiple fills on same symbol+side aggregate with weighted-avg entry
# ---------------------------------------------------------------------------

def test_multiple_fills_aggregate_with_weighted_average() -> None:
    user_id = _seed_approved_user()
    rec_uid = _seed_recommendation()

    # First fill — capture original avg + qty for math.
    first = _stage_order_and_get_position(rec_uid)
    pos_id_first = first["position"]["id"]
    qty_a = float(first["position"]["opened_qty"])
    avg_a = float(first["position"]["avg_entry_price"])

    # Second fill on same (user, symbol, side) — should aggregate, not create a 2nd row.
    second_resp = client.post(
        "/user/orders",
        headers=_USER_AUTH,
        json={"recommendation_id": rec_uid},
    )
    assert second_resp.status_code == 200, second_resp.text

    pos_resp = client.get("/user/paper-positions", headers=_USER_AUTH)
    open_positions = [p for p in pos_resp.json() if p["status"] == "open" and p["symbol"] == "AAPL"]
    assert len(open_positions) == 1, f"expected exactly one open AAPL position; got {open_positions}"
    assert open_positions[0]["id"] == pos_id_first, "second fill should aggregate into first position row"

    qty_total = float(open_positions[0]["opened_qty"])
    remaining_total = float(open_positions[0]["remaining_qty"])
    assert qty_total > qty_a, f"opened_qty did not increase: was {qty_a}, now {qty_total}"
    assert remaining_total == qty_total, "remaining_qty should match opened_qty for never-closed position"

    # Weighted-average sanity: new avg lies in the closed interval bounded by the
    # smaller and larger of (avg_a, fill_b_avg). Since deterministic test runs use the
    # same limit_price for both fills here, the resulting avg should equal avg_a.
    new_avg = float(open_positions[0]["avg_entry_price"])
    assert abs(new_avg - avg_a) < 1e-6, (
        f"weighted avg drifted unexpectedly: avg_a={avg_a}, new_avg={new_avg} "
        "(both fills use the same limit_price so avg should be unchanged)"
    )


# ---------------------------------------------------------------------------
# Test 3 — Close endpoint computes realized_pnl correctly for LONG
# ---------------------------------------------------------------------------

def test_close_position_realized_pnl_long() -> None:
    _seed_approved_user()
    rec_uid = _seed_recommendation()
    bundle = _stage_order_and_get_position(rec_uid)
    position = bundle["position"]

    avg = float(position["avg_entry_price"])
    qty = float(position["remaining_qty"])
    mark = avg + 7.50  # well-defined gain over avg entry
    expected_pnl = (mark - avg) * qty

    close_resp = client.post(
        f"/user/paper-positions/{position['id']}/close",
        headers=_USER_AUTH,
        json={"mark_price": mark, "reason": "target_1 hit"},
    )
    assert close_resp.status_code == 200, close_resp.text
    trade = close_resp.json()

    assert trade["side"] == "long"
    assert trade["entry_price"] == avg
    assert trade["exit_price"] == mark
    assert trade["qty"] == qty
    assert abs(float(trade["realized_pnl"]) - expected_pnl) < 1e-6
    assert trade["close_reason"] == "target_1 hit"
    assert trade["position_id"] == position["id"]
    assert trade["recommendation_id"] == rec_uid

    # Position is now closed with remaining_qty=0
    pos_resp = client.get("/user/paper-positions?status=all", headers=_USER_AUTH)
    closed = [p for p in pos_resp.json() if p["id"] == position["id"]]
    assert closed and closed[0]["status"] == "closed"
    assert float(closed[0]["remaining_qty"]) == 0.0


# ---------------------------------------------------------------------------
# Test 4 — Close endpoint computes realized_pnl correctly for SHORT
# ---------------------------------------------------------------------------

def test_close_position_realized_pnl_short() -> None:
    user_id = _seed_approved_user()
    # Seed a synthetic short position directly — short orders don't flow through
    # stage_order in Phase 1, but the close endpoint must handle short PnL.
    with SessionLocal() as session:
        pos = PaperPositionModel(
            app_user_id=user_id,
            symbol="MSFT",
            side="short",
            quantity=100.0,
            average_price=400.0,
            open_notional=40000.0,
            status="open",
            opened_qty=100.0,
            remaining_qty=100.0,
            recommendation_id="rec-synthetic-short",
            replay_run_id=None,
            order_id="ord-synthetic-short",
        )
        session.add(pos)
        session.commit()
        session.refresh(pos)
        position_id = pos.id

    mark = 380.0  # short profits when mark < avg_entry
    expected_pnl = (mark - 400.0) * 100.0 * -1.0  # = +2000

    close_resp = client.post(
        f"/user/paper-positions/{position_id}/close",
        headers=_USER_AUTH,
        json={"mark_price": mark, "reason": "stop"},
    )
    assert close_resp.status_code == 200, close_resp.text
    trade = close_resp.json()

    assert trade["side"] == "short"
    assert abs(float(trade["realized_pnl"]) - expected_pnl) < 1e-6, (
        f"short PnL incorrect: expected {expected_pnl}, got {trade['realized_pnl']}"
    )
    assert trade["entry_price"] == 400.0
    assert trade["exit_price"] == 380.0


# ---------------------------------------------------------------------------
# Test 5 — Close endpoint blocks non-owner with 404 (scope isolation)
# ---------------------------------------------------------------------------

def test_close_position_blocks_non_owner_with_404() -> None:
    # Owner stages a position
    owner_id = _seed_approved_user(token="user-token", external_id="clerk_user")
    rec_uid = _seed_recommendation()
    bundle = _stage_order_and_get_position(rec_uid, token="user-token")
    position_id = bundle["position"]["id"]

    # Different approved user attempts to close it
    _seed_approved_user(token="admin-token", external_id="clerk_admin")

    close_resp = client.post(
        f"/user/paper-positions/{position_id}/close",
        headers=_ADMIN_AUTH,
        json={"mark_price": 200.0, "reason": "unauthorized attempt"},
    )
    assert close_resp.status_code == 404, close_resp.text
    assert close_resp.json()["detail"] == "Position not found."


# ---------------------------------------------------------------------------
# Test 6 — Close endpoint blocks already-closed position with 400
# ---------------------------------------------------------------------------

def test_close_position_already_closed_returns_400() -> None:
    _seed_approved_user()
    rec_uid = _seed_recommendation()
    bundle = _stage_order_and_get_position(rec_uid)
    position_id = bundle["position"]["id"]

    first = client.post(
        f"/user/paper-positions/{position_id}/close",
        headers=_USER_AUTH,
        json={"mark_price": 150.0, "reason": "first close"},
    )
    assert first.status_code == 200, first.text

    second = client.post(
        f"/user/paper-positions/{position_id}/close",
        headers=_USER_AUTH,
        json={"mark_price": 160.0, "reason": "second close"},
    )
    assert second.status_code == 400, second.text
    assert second.json()["detail"] == "Position is already closed."


# ---------------------------------------------------------------------------
# Test 7 — List endpoints scope to owning user only
# ---------------------------------------------------------------------------

def test_list_endpoints_scope_to_owning_user() -> None:
    # User A stages a position, then closes it (creating a trade row).
    user_a_id = _seed_approved_user(token="user-token", external_id="clerk_user")
    rec_uid = _seed_recommendation()
    bundle = _stage_order_and_get_position(rec_uid, token="user-token")
    pos_id_a = bundle["position"]["id"]
    close_resp = client.post(
        f"/user/paper-positions/{pos_id_a}/close",
        headers=_USER_AUTH,
        json={"mark_price": 150.0, "reason": "exit"},
    )
    assert close_resp.status_code == 200, close_resp.text

    # User B (admin token == different external auth id) sees nothing.
    _seed_approved_user(token="admin-token", external_id="clerk_admin")
    pos_resp_b = client.get("/user/paper-positions?status=all", headers=_ADMIN_AUTH)
    trades_resp_b = client.get("/user/paper-trades", headers=_ADMIN_AUTH)
    assert pos_resp_b.status_code == 200 and pos_resp_b.json() == []
    assert trades_resp_b.status_code == 200 and trades_resp_b.json() == []

    # User A still sees their own (closed position + one trade).
    pos_resp_a = client.get("/user/paper-positions?status=all", headers=_USER_AUTH)
    trades_resp_a = client.get("/user/paper-trades", headers=_USER_AUTH)
    assert pos_resp_a.status_code == 200
    assert any(p["id"] == pos_id_a for p in pos_resp_a.json())
    assert trades_resp_a.status_code == 200
    assert len(trades_resp_a.json()) == 1
    assert trades_resp_a.json()[0]["recommendation_id"] == rec_uid


# ---------------------------------------------------------------------------
# Pass 4 — Cancel staged order
# ---------------------------------------------------------------------------

def _seed_staged_order(*, app_user_id: int, order_id: str = "ord-staged-1") -> str:
    """Seed an OrderModel row with status='staged' and no fills directly via the
    DB — the standard /user/orders POST path always produces a fill, so this is
    the only way to exercise the cancel happy path."""
    with SessionLocal() as session:
        session.add(
            OrderModel(
                order_id=order_id,
                app_user_id=app_user_id,
                recommendation_id="rec-staged",
                replay_run_id=None,
                symbol="AAPL",
                status="staged",
                side="long",
                shares=10,
                limit_price=120.0,
                notes="seeded_for_test",
            )
        )
        session.commit()
    return order_id


def test_cancel_succeeds_when_staged_with_no_fills() -> None:
    user_id = _seed_approved_user()
    order_id = _seed_staged_order(app_user_id=user_id)

    resp = client.post(f"/user/orders/{order_id}/cancel", headers=_USER_AUTH)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["order_id"] == order_id
    assert body["status"] == "canceled"
    assert body["canceled_at"] is not None

    # Audit row written
    with SessionLocal() as session:
        rows = session.execute(
            select(AuditLogModel).where(AuditLogModel.recommendation_id == "rec-staged")
        ).scalars().all()
        assert any(
            (r.payload or {}).get("event") == "order_canceled" and (r.payload or {}).get("order_id") == order_id
            for r in rows
        ), f"audit log missing order_canceled entry: {[r.payload for r in rows]}"


def test_cancel_409s_when_order_has_fills() -> None:
    user_id = _seed_approved_user()
    order_id = _seed_staged_order(app_user_id=user_id, order_id="ord-with-fill")
    with SessionLocal() as session:
        session.add(FillModel(order_id=order_id, fill_price=120.0, filled_shares=10))
        session.commit()

    resp = client.post(f"/user/orders/{order_id}/cancel", headers=_USER_AUTH)
    assert resp.status_code == 409, resp.text
    assert "fills" in resp.json()["detail"].lower()


def test_cancel_409s_when_order_is_not_staged() -> None:
    user_id = _seed_approved_user()
    order_id = _seed_staged_order(app_user_id=user_id, order_id="ord-already-closed")
    # Mutate status away from "staged"
    with SessionLocal() as session:
        row = session.execute(select(OrderModel).where(OrderModel.order_id == order_id)).scalar_one()
        row.status = "filled"
        session.commit()

    resp = client.post(f"/user/orders/{order_id}/cancel", headers=_USER_AUTH)
    assert resp.status_code == 409, resp.text
    assert "staged" in resp.json()["detail"].lower()


def test_cancel_404s_for_non_owner() -> None:
    owner_id = _seed_approved_user(token="user-token", external_id="clerk_user")
    order_id = _seed_staged_order(app_user_id=owner_id, order_id="ord-cancel-other-user")

    # Different approved user
    _seed_approved_user(token="admin-token", external_id="clerk_admin")
    resp = client.post(f"/user/orders/{order_id}/cancel", headers=_ADMIN_AUTH)
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"] == "Order not found."


# ---------------------------------------------------------------------------
# Pass 4 — Reopen closed paper trade
# ---------------------------------------------------------------------------

def _stage_and_close_for_reopen(*, token: str = "user-token", external_id: str = "clerk_user") -> dict:
    """Stage a paper order, close the resulting open position, and return
    {position_id, trade_id, qty, realized_pnl} for use by reopen tests."""
    _seed_approved_user(token=token, external_id=external_id)
    rec_uid = _seed_recommendation()
    bundle = _stage_order_and_get_position(rec_uid, token=token)
    pos_id = bundle["position"]["id"]
    qty = float(bundle["position"]["remaining_qty"])
    avg = float(bundle["position"]["avg_entry_price"])

    close_resp = client.post(
        f"/user/paper-positions/{pos_id}/close",
        headers={"Authorization": f"Bearer {token}"},
        json={"mark_price": avg + 1.0, "reason": "test exit"},
    )
    assert close_resp.status_code == 200, close_resp.text
    trade = close_resp.json()
    return {
        "position_id": pos_id,
        "trade_id": int(trade["id"]),
        "qty": qty,
        "realized_pnl": float(trade["realized_pnl"]),
        "rec_uid": rec_uid,
    }


def test_reopen_succeeds_within_5_minute_window() -> None:
    state = _stage_and_close_for_reopen()
    trade_id = state["trade_id"]
    pos_id = state["position_id"]
    qty = state["qty"]

    resp = client.post(f"/user/paper-trades/{trade_id}/reopen", headers=_USER_AUTH)
    assert resp.status_code == 200, resp.text
    pos = resp.json()
    assert pos["id"] == pos_id
    assert pos["status"] == "open"
    assert float(pos["remaining_qty"]) == qty
    assert pos["closed_at"] is None

    # Trade row hard-deleted
    with SessionLocal() as session:
        assert session.get(PaperTradeModel, trade_id) is None

    # Audit row written
    with SessionLocal() as session:
        rows = session.execute(select(AuditLogModel)).scalars().all()
        assert any(
            (r.payload or {}).get("event") == "position_reopened"
            and (r.payload or {}).get("position_id") == pos_id
            and (r.payload or {}).get("trade_id") == trade_id
            for r in rows
        ), f"audit log missing position_reopened entry: {[r.payload for r in rows]}"


def test_reopen_409s_after_5_minute_window() -> None:
    state = _stage_and_close_for_reopen()
    trade_id = state["trade_id"]

    # Backdate the trade.closed_at so it appears 6 minutes ago
    with SessionLocal() as session:
        trade = session.get(PaperTradeModel, trade_id)
        assert trade is not None
        trade.closed_at = datetime.now(tz=timezone.utc) - timedelta(minutes=6)
        session.commit()

    resp = client.post(f"/user/paper-trades/{trade_id}/reopen", headers=_USER_AUTH)
    assert resp.status_code == 409, resp.text
    assert "reopen window" in resp.json()["detail"].lower()


def test_reopen_409s_when_position_already_open() -> None:
    state = _stage_and_close_for_reopen()
    trade_id = state["trade_id"]
    pos_id = state["position_id"]

    # Manually flip the parent position back to open without removing the trade
    with SessionLocal() as session:
        pos = session.get(PaperPositionModel, pos_id)
        assert pos is not None
        pos.status = "open"
        pos.closed_at = None
        pos.remaining_qty = state["qty"]
        session.commit()

    resp = client.post(f"/user/paper-trades/{trade_id}/reopen", headers=_USER_AUTH)
    assert resp.status_code == 409, resp.text
    assert "not closed" in resp.json()["detail"].lower()


def test_reopen_404s_for_non_owner() -> None:
    state = _stage_and_close_for_reopen(token="user-token", external_id="clerk_user")
    trade_id = state["trade_id"]

    _seed_approved_user(token="admin-token", external_id="clerk_admin")
    resp = client.post(f"/user/paper-trades/{trade_id}/reopen", headers=_ADMIN_AUTH)
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"] == "Trade not found."


def test_reopen_restores_remaining_qty_and_deletes_trade_row() -> None:
    """Spec says 'Reopen properly restores remaining_qty and deletes the trade
    row' — this is the explicit invariant test that the close→reopen cycle
    leaves the position open at the original qty AND removes the trade row
    so portfolio summary's closed_trade_count drops back."""
    state = _stage_and_close_for_reopen()
    trade_id = state["trade_id"]
    pos_id = state["position_id"]

    # Pre-condition: trade row exists, position is closed.
    with SessionLocal() as session:
        assert session.get(PaperTradeModel, trade_id) is not None
        pos = session.get(PaperPositionModel, pos_id)
        assert pos is not None and pos.status == "closed"

    resp = client.post(f"/user/paper-trades/{trade_id}/reopen", headers=_USER_AUTH)
    assert resp.status_code == 200, resp.text

    # Post-condition
    with SessionLocal() as session:
        assert session.get(PaperTradeModel, trade_id) is None, "trade row should be hard-deleted"
        pos = session.get(PaperPositionModel, pos_id)
        assert pos is not None
        assert pos.status == "open"
        assert pos.closed_at is None
        assert float(pos.remaining_qty) == state["qty"]

