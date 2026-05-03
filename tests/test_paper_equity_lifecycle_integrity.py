from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from macmarket_trader.api.main import app
from macmarket_trader.domain.models import (
    AppUserModel,
    FillModel,
    OrderModel,
    PaperPositionModel,
    PaperTradeModel,
    RecommendationModel,
)
from macmarket_trader.storage.db import SessionLocal


client = TestClient(app)

USER_A_TOKEN = "user-token"
USER_B_TOKEN = "admin-token"
USER_A_AUTH = {"Authorization": f"Bearer {USER_A_TOKEN}"}
USER_B_AUTH = {"Authorization": f"Bearer {USER_B_TOKEN}"}


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _seed_approved_user(*, token: str, external_id: str, commission_per_trade: float = 0.0) -> int:
    resp = client.get("/user/me", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    with SessionLocal() as session:
        user = session.execute(
            select(AppUserModel).where(AppUserModel.external_auth_user_id == external_id)
        ).scalar_one()
        user.approval_status = "approved"
        user.commission_per_trade = commission_per_trade
        session.commit()
        return int(user.id)


def _promote_ranked_candidate(*, token: str, symbol: str) -> dict[str, object]:
    queue = client.post(
        "/user/recommendations/queue",
        headers=_auth(token),
        json={"symbols": [symbol], "timeframe": "1D", "market_mode": "equities", "top_n": 1},
    )
    assert queue.status_code == 200, queue.text
    candidates = queue.json()["queue"]
    assert candidates, queue.json()
    candidate = candidates[0]
    assert candidate["symbol"] == symbol

    promoted = client.post(
        "/user/recommendations/queue/promote",
        headers=_auth(token),
        json={**candidate, "action": "make_active"},
    )
    assert promoted.status_code == 200, promoted.text
    return promoted.json()


def _stage_and_fill_order(*, token: str, recommendation_id: str) -> dict[str, object]:
    order = client.post(
        "/user/orders",
        headers=_auth(token),
        json={"recommendation_id": recommendation_id},
    )
    assert order.status_code == 200, order.text
    body = order.json()
    assert body["status"] == "filled"
    assert body["shares"] > 0
    return body


def _db_rows(*, order_id: str, position_id: int, recommendation_uid: str) -> dict[str, object]:
    with SessionLocal() as session:
        order = session.execute(select(OrderModel).where(OrderModel.order_id == order_id)).scalar_one()
        fills = list(session.execute(select(FillModel).where(FillModel.order_id == order_id)).scalars())
        position = session.get(PaperPositionModel, position_id)
        recommendation = session.execute(
            select(RecommendationModel).where(RecommendationModel.recommendation_id == recommendation_uid)
        ).scalar_one()
        trades = list(
            session.execute(select(PaperTradeModel).where(PaperTradeModel.position_id == position_id)).scalars()
        )
        return {
            "order": order,
            "fills": fills,
            "position": position,
            "recommendation": recommendation,
            "trades": trades,
        }


def _assert_no_orphaned_lifecycle_rows() -> None:
    with SessionLocal() as session:
        order_ids = set(session.execute(select(OrderModel.order_id)).scalars())
        for fill in session.execute(select(FillModel)).scalars():
            assert fill.order_id in order_ids

        position_ids = {int(value) for value in session.execute(select(PaperPositionModel.id)).scalars()}
        recommendation_uids = set(session.execute(select(RecommendationModel.recommendation_id)).scalars())
        for trade in session.execute(select(PaperTradeModel)).scalars():
            assert trade.position_id in position_ids
            assert trade.order_id is None or trade.order_id in order_ids
            assert trade.recommendation_id is None or trade.recommendation_id in recommendation_uids


def test_paper_equity_lifecycle_data_integrity_and_user_isolation() -> None:
    user_a_id = _seed_approved_user(
        token=USER_A_TOKEN,
        external_id="clerk_user",
        commission_per_trade=2.25,
    )
    user_b_id = _seed_approved_user(
        token=USER_B_TOKEN,
        external_id="clerk_admin",
        commission_per_trade=1.00,
    )

    promoted_a = _promote_ranked_candidate(token=USER_A_TOKEN, symbol="GOOG")
    rec_uid_a = str(promoted_a["recommendation_id"])
    rec_db_id_a = int(promoted_a["id"])
    order_a = _stage_and_fill_order(token=USER_A_TOKEN, recommendation_id=rec_uid_a)

    orders_a = client.get("/user/orders", headers=USER_A_AUTH)
    assert orders_a.status_code == 200, orders_a.text
    listed_order_a = next(order for order in orders_a.json() if order["order_id"] == order_a["order_id"])
    assert listed_order_a["recommendation_id"] == rec_uid_a
    assert len(listed_order_a["fills"]) == 1
    assert listed_order_a["fills"][0]["filled_shares"] == order_a["shares"]

    positions_a = client.get("/user/paper-positions", headers=USER_A_AUTH)
    assert positions_a.status_code == 200, positions_a.text
    position_a = next(position for position in positions_a.json() if position["order_id"] == order_a["order_id"])
    position_id_a = int(position_a["id"])
    assert position_a["symbol"] == "GOOG"
    assert position_a["status"] == "open"
    assert position_a["recommendation_id"] == rec_uid_a
    assert position_a["remaining_qty"] == float(order_a["shares"])

    rows = _db_rows(order_id=str(order_a["order_id"]), position_id=position_id_a, recommendation_uid=rec_uid_a)
    assert rows["order"].app_user_id == user_a_id
    assert rows["order"].recommendation_id == rec_uid_a
    assert rows["recommendation"].app_user_id == user_a_id
    assert rows["position"].app_user_id == user_a_id
    assert rows["position"].order_id == order_a["order_id"]
    assert rows["position"].recommendation_id == rec_uid_a
    assert len(rows["fills"]) == 1

    review_open = client.get("/user/paper-positions/review", headers=USER_A_AUTH)
    assert review_open.status_code == 200, review_open.text
    review_for_position = next(item for item in review_open.json() if item["position_id"] == position_id_a)
    assert review_for_position["symbol"] == "GOOG"
    assert review_for_position["already_open"] is True

    assert client.get("/user/orders", headers=USER_B_AUTH).json() == []
    assert client.get("/user/paper-positions?status=all", headers=USER_B_AUTH).json() == []
    assert all(
        row["recommendation_id"] != rec_uid_a
        for row in client.get("/user/recommendations", headers=USER_B_AUTH).json()
    )
    assert client.get(f"/user/recommendations/{rec_db_id_a}", headers=USER_B_AUTH).status_code == 404
    assert client.post(
        "/user/orders",
        headers=USER_B_AUTH,
        json={"recommendation_id": rec_uid_a},
    ).status_code == 404
    assert client.post(
        f"/user/paper-positions/{position_id_a}/close",
        headers=USER_B_AUTH,
        json={"mark_price": float(position_a["avg_entry_price"]) + 1.0, "reason": "foreign close attempt"},
    ).status_code == 404
    assert client.post(f"/user/orders/{order_a['order_id']}/cancel", headers=USER_B_AUTH).status_code == 404

    promoted_b = _promote_ranked_candidate(token=USER_B_TOKEN, symbol="MSFT")
    rec_uid_b = str(promoted_b["recommendation_id"])
    order_b = _stage_and_fill_order(token=USER_B_TOKEN, recommendation_id=rec_uid_b)
    positions_b = client.get("/user/paper-positions", headers=USER_B_AUTH)
    assert positions_b.status_code == 200, positions_b.text
    position_b = next(position for position in positions_b.json() if position["order_id"] == order_b["order_id"])
    assert int(position_b["id"]) != position_id_a

    entry_price = float(position_a["avg_entry_price"])
    qty = float(position_a["remaining_qty"])
    exit_price = entry_price + 4.50
    expected_gross = (exit_price - entry_price) * qty
    expected_net = expected_gross - 2.25
    close = client.post(
        f"/user/paper-positions/{position_id_a}/close",
        headers=USER_A_AUTH,
        json={"mark_price": exit_price, "reason": "lifecycle audit manual close"},
    )
    assert close.status_code == 200, close.text
    trade = close.json()
    assert trade["position_id"] == position_id_a
    assert trade["order_id"] == order_a["order_id"]
    assert trade["recommendation_id"] == rec_uid_a
    assert trade["qty"] == qty
    assert trade["entry_price"] == entry_price
    assert trade["exit_price"] == exit_price
    assert abs(float(trade["gross_pnl"]) - expected_gross) < 1e-6
    assert abs(float(trade["net_pnl"]) - expected_net) < 1e-6
    assert abs(float(trade["commission_paid"]) - 2.25) < 1e-6
    assert abs(float(trade["realized_pnl"]) - expected_net) < 1e-6

    positions_after_close = client.get("/user/paper-positions?status=all", headers=USER_A_AUTH)
    assert positions_after_close.status_code == 200, positions_after_close.text
    closed_position = next(position for position in positions_after_close.json() if position["id"] == position_id_a)
    assert closed_position["status"] == "closed"
    assert closed_position["remaining_qty"] == 0.0

    summary = client.get("/user/orders/portfolio-summary", headers=USER_A_AUTH)
    assert summary.status_code == 200, summary.text
    summary_body = summary.json()
    assert summary_body["open_positions"] == 0
    assert summary_body["closed_trade_count"] == 1
    assert abs(float(summary_body["gross_realized_pnl"]) - expected_gross) < 1e-6
    assert abs(float(summary_body["net_realized_pnl"]) - expected_net) < 1e-6
    assert abs(float(summary_body["total_commission_paid"]) - 2.25) < 1e-6
    assert summary_body["realized_pnl"] == summary_body["net_realized_pnl"]

    review_after_close = client.get("/user/paper-positions/review", headers=USER_A_AUTH)
    assert review_after_close.status_code == 200, review_after_close.text
    assert all(item["position_id"] != position_id_a for item in review_after_close.json())

    rows_after_close = _db_rows(order_id=str(order_a["order_id"]), position_id=position_id_a, recommendation_uid=rec_uid_a)
    assert rows_after_close["position"].status == "closed"
    assert len(rows_after_close["trades"]) == 1
    assert rows_after_close["trades"][0].app_user_id == user_a_id
    assert rows_after_close["trades"][0].order_id == order_a["order_id"]
    assert rows_after_close["trades"][0].recommendation_id == rec_uid_a
    _assert_no_orphaned_lifecycle_rows()

    reset = client.post("/user/paper/reset", headers=USER_A_AUTH, json={"confirmation": "RESET"})
    assert reset.status_code == 200, reset.text
    assert reset.json()["counts"] == {
        "orders": 1,
        "fills": 1,
        "paper_positions": 1,
        "paper_trades": 1,
    }

    assert client.get("/user/orders", headers=USER_A_AUTH).json() == []
    assert client.get("/user/paper-positions?status=all", headers=USER_A_AUTH).json() == []
    assert client.get("/user/paper-trades", headers=USER_A_AUTH).json() == []
    assert client.get("/user/paper-positions/review", headers=USER_A_AUTH).json() == []
    assert any(
        row["recommendation_id"] == rec_uid_a
        for row in client.get("/user/recommendations", headers=USER_A_AUTH).json()
    )

    orders_b_after_reset = client.get("/user/orders", headers=USER_B_AUTH)
    positions_b_after_reset = client.get("/user/paper-positions", headers=USER_B_AUTH)
    assert orders_b_after_reset.status_code == 200, orders_b_after_reset.text
    assert positions_b_after_reset.status_code == 200, positions_b_after_reset.text
    assert any(order["order_id"] == order_b["order_id"] for order in orders_b_after_reset.json())
    assert any(position["id"] == position_b["id"] for position in positions_b_after_reset.json())

    with SessionLocal() as session:
        assert session.get(AppUserModel, user_b_id) is not None
        assert session.execute(select(OrderModel).where(OrderModel.order_id == order_a["order_id"])).first() is None
        assert session.execute(select(FillModel).where(FillModel.order_id == order_a["order_id"])).first() is None
        assert session.get(PaperPositionModel, position_id_a) is None
        assert session.execute(
            select(PaperTradeModel).where(PaperTradeModel.position_id == position_id_a)
        ).first() is None
        assert session.execute(select(OrderModel).where(OrderModel.order_id == order_b["order_id"])).scalar_one().app_user_id == user_b_id
        assert session.get(PaperPositionModel, int(position_b["id"])).app_user_id == user_b_id
        assert session.execute(
            select(RecommendationModel).where(RecommendationModel.recommendation_id == rec_uid_a)
        ).scalar_one().app_user_id == user_a_id
        assert session.execute(
            select(RecommendationModel).where(RecommendationModel.recommendation_id == rec_uid_b)
        ).scalar_one().app_user_id == user_b_id

    _assert_no_orphaned_lifecycle_rows()
