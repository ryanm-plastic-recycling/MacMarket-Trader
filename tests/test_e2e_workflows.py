"""
Comprehensive end-to-end API workflow tests.

Exercises every major workflow in MacMarket-Trader with realistic dummy data.
Each workflow is independently runnable — conftest.py's autouse
``reset_sqlite_schema`` fixture drops and recreates the schema before each
test function so there is no cross-workflow state leakage.

Auth:     mock provider (user-token / admin-token)
Provider: deterministic fallback — market_data_enabled=False and
          polygon_enabled=False are the defaults in the test environment, so
          ``provider_is_expected`` is False in ``_workflow_bars`` and no
          provider-blocked 503 can be raised.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from macmarket_trader.api.main import app
from macmarket_trader.domain.models import AppUserModel
from macmarket_trader.storage.db import SessionLocal

client = TestClient(app)

_USER_AUTH = {"Authorization": "Bearer user-token"}
_ADMIN_AUTH = {"Authorization": "Bearer admin-token"}


# ---------------------------------------------------------------------------
# Shared seed helpers
# ---------------------------------------------------------------------------

def _seed_approved_user() -> int:
    """Provision clerk_user row via /user/me and promote to approved.

    Returns the local DB integer id.
    """
    resp = client.get("/user/me", headers=_USER_AUTH)
    assert resp.status_code == 200, f"/user/me failed: {resp.text}"
    with SessionLocal() as session:
        user = session.execute(
            select(AppUserModel).where(AppUserModel.external_auth_user_id == "clerk_user")
        ).scalar_one()
        user.approval_status = "approved"
        session.commit()
        return user.id


def _seed_pending_user() -> int:
    """Provision clerk_user row via /user/me (leaves status = pending).

    Returns the local DB integer id.
    """
    resp = client.get("/user/me", headers=_USER_AUTH)
    assert resp.status_code == 200, f"/user/me failed: {resp.text}"
    with SessionLocal() as session:
        user = session.execute(
            select(AppUserModel).where(AppUserModel.external_auth_user_id == "clerk_user")
        ).scalar_one()
        return user.id


def _seed_admin() -> int:
    """Provision clerk_admin row and grant admin role + MFA.

    Returns the local DB integer id.
    """
    resp = client.get("/user/me", headers=_ADMIN_AUTH)
    assert resp.status_code == 200, f"/user/me (admin) failed: {resp.text}"
    with SessionLocal() as session:
        admin = session.execute(
            select(AppUserModel).where(AppUserModel.external_auth_user_id == "clerk_admin")
        ).scalar_one()
        admin.app_role = "admin"
        admin.approval_status = "approved"
        admin.mfa_enabled = True
        session.commit()
        return admin.id


# ---------------------------------------------------------------------------
# WORKFLOW 1 — Full operator click path
# ---------------------------------------------------------------------------

def test_workflow1_full_operator_click_path() -> None:
    """
    Exercise the canonical operator workflow end-to-end with realistic data:

        Analysis setup (equities / AAPL / Event Continuation)
        → Recommendations queue (ranked candidates)
        → Promote candidate to stored recommendation
        → GET stored recommendation detail
        → Create replay run from that recommendation
        → GET replay run steps
        → Stage paper order from recommendation
        → GET order blotter and confirm lineage
    """
    _seed_approved_user()

    # ── Step 1: Analysis setup ──────────────────────────────────────────────
    setup_resp = client.get(
        "/user/analysis/setup",
        params={
            "req_symbol": "AAPL",
            "strategy": "Event Continuation",
            "timeframe": "1D",
            "market_mode": "equities",
        },
        headers=_USER_AUTH,
    )
    assert setup_resp.status_code == 200, f"analysis/setup failed: {setup_resp.text}"
    setup = setup_resp.json()
    assert setup["symbol"] == "AAPL"
    assert setup["strategy"] == "Event Continuation"
    assert setup["market_mode"] == "equities"
    assert "entry_zone" in setup, "setup missing entry_zone"
    assert "invalidation" in setup, "setup missing invalidation"
    assert "targets" in setup, "setup missing targets"
    assert "confidence" in setup, "setup missing confidence"
    # workflow_source should be labeled (provider or fallback)
    assert setup.get("workflow_source"), "setup missing workflow_source"

    # ── Step 2: GET recommendations queue ──────────────────────────────────
    queue_resp = client.post(
        "/user/recommendations/queue",
        headers=_USER_AUTH,
        json={
            "market_mode": "equities",
            "symbols": ["AAPL"],
            "strategies": ["Event Continuation"],
            "timeframe": "1D",
            "top_n": 5,
        },
    )
    assert queue_resp.status_code == 200, f"recommendations/queue failed: {queue_resp.text}"
    queue = queue_resp.json()
    assert "queue" in queue, "queue response missing 'queue'"
    assert "top_candidates" in queue, "queue response missing 'top_candidates'"
    assert "summary" in queue, "queue response missing 'summary'"
    assert queue["market_mode"] == "equities"
    assert isinstance(queue["queue"], list)

    # ── Step 3: Promote a candidate to a stored recommendation ─────────────
    promote_resp = client.post(
        "/user/recommendations/queue/promote",
        headers=_USER_AUTH,
        json={
            "symbol": "AAPL",
            "strategy": "Event Continuation",
            "thesis": "AAPL earnings beat with raised strong guidance breakout continuation",
            "timeframe": "1D",
            "market_mode": "equities",
            "rank": 1,
        },
    )
    assert promote_resp.status_code == 200, f"promote failed: {promote_resp.text}"
    promote = promote_resp.json()
    assert promote["symbol"] == "AAPL", f"promote symbol mismatch: {promote}"
    assert "recommendation_id" in promote, "promote missing recommendation_id"
    assert "id" in promote, "promote missing db row id"
    assert promote["approved"] is True, (
        f"Expected promoted recommendation to be approved; got: {promote}"
    )
    rec_db_id: int = promote["id"]          # integer DB row id (for detail route)
    rec_uid: str = promote["recommendation_id"]  # UID string (for order staging)

    # ── Step 4: GET the stored recommendation detail ────────────────────────
    detail_resp = client.get(
        f"/user/recommendations/{rec_db_id}",
        headers=_USER_AUTH,
    )
    assert detail_resp.status_code == 200, f"recommendation detail failed: {detail_resp.text}"
    detail = detail_resp.json()
    assert detail["recommendation_id"] == rec_uid, (
        f"detail rec_uid mismatch: expected {rec_uid}, got {detail['recommendation_id']}"
    )
    assert detail["symbol"] == "AAPL"
    assert detail["payload"] is not None, "detail payload is None"
    # payload should carry the approval flag
    assert detail["payload"].get("approved") is True

    # ── Step 5: POST create a replay run ────────────────────────────────────
    replay_resp = client.post(
        "/user/replay-runs",
        headers=_USER_AUTH,
        json={
            "symbol": "AAPL",
            "market_mode": "equities",
            "event_texts": [
                "AAPL post-earnings continuation — replay path validation",
                "Deterministic follow-through check for operator paper flow",
            ],
        },
    )
    assert replay_resp.status_code == 200, f"replay-runs POST failed: {replay_resp.text}"
    replay = replay_resp.json()
    assert replay["symbol"] == "AAPL"
    assert replay["id"] is not None, "replay run id is None"
    assert "summary_metrics" in replay, "replay missing summary_metrics"
    run_id: int = replay["id"]

    # ── Step 6: GET replay run steps ───────────────────────────────────────
    steps_resp = client.get(
        f"/user/replay-runs/{run_id}/steps",
        headers=_USER_AUTH,
    )
    assert steps_resp.status_code == 200, f"replay steps failed: {steps_resp.text}"
    steps = steps_resp.json()
    assert isinstance(steps, list), "steps is not a list"
    assert len(steps) > 0, "expected at least one replay step"
    for step in steps:
        assert "step_index" in step, f"step missing step_index: {step}"
        assert "recommendation_id" in step, f"step missing recommendation_id: {step}"

    # ── Step 7: POST stage a paper order from the recommendation ────────────
    order_resp = client.post(
        "/user/orders",
        headers=_USER_AUTH,
        json={"recommendation_id": rec_uid},
    )
    assert order_resp.status_code == 200, f"stage order failed: {order_resp.text}"
    order = order_resp.json()
    assert order["order_id"] is not None, "order_id is None"
    assert order["symbol"] == "AAPL", f"order symbol mismatch: {order}"
    assert order["status"] is not None, "order status is None"

    # ── Step 8: GET order blotter and verify lineage ────────────────────────
    blotter_resp = client.get("/user/orders", headers=_USER_AUTH)
    assert blotter_resp.status_code == 200, f"order blotter failed: {blotter_resp.text}"
    blotter = blotter_resp.json()
    assert isinstance(blotter, list), "blotter is not a list"
    assert len(blotter) > 0, "blotter is empty after staging an order"

    staged = next(
        (o for o in blotter if o.get("recommendation_id") == rec_uid),
        None,
    )
    assert staged is not None, (
        f"Staged order with rec_uid={rec_uid!r} not found in blotter. "
        f"Blotter rec_ids: {[o.get('recommendation_id') for o in blotter]}"
    )
    assert staged["symbol"] == "AAPL"


# ---------------------------------------------------------------------------
# WORKFLOW 2 — Scheduled strategy reports
# ---------------------------------------------------------------------------

def test_workflow2_scheduled_strategy_reports() -> None:
    """
    Exercise the scheduled strategy report workflow with realistic data:

        Create schedule (AAPL + NVDA, weekdays)
        → List schedules (confirm appears)
        → POST run-now
        → List schedules (confirm run recorded in history)
        → Assert payload has top_candidates, summary counts, email_provider

    Actual Resend delivery is NOT exercised — EMAIL_PROVIDER=console is
    enforced by conftest.py so no network calls are made.
    """
    _seed_approved_user()

    # ── Create a schedule ───────────────────────────────────────────────────
    create_resp = client.post(
        "/user/strategy-schedules",
        headers=_USER_AUTH,
        json={
            "name": "Morning Alpha Scan",
            "symbols": ["AAPL", "NVDA"],
            "frequency": "weekdays",
            "run_time": "08:30",
            "timezone": "America/New_York",
            "market_mode": "equities",
            "enabled_strategies": ["Event Continuation"],
            "top_n": 3,
            "email_delivery_target": "operator@example.com",
        },
    )
    assert create_resp.status_code == 200, f"schedule create failed: {create_resp.text}"
    sched_body = create_resp.json()
    assert "id" in sched_body, "schedule response missing id"
    assert sched_body["enabled"] is True
    schedule_id: int = sched_body["id"]

    # ── GET the schedule list — confirm it appears ──────────────────────────
    list_resp = client.get("/user/strategy-schedules", headers=_USER_AUTH)
    assert list_resp.status_code == 200, f"schedule list failed: {list_resp.text}"
    schedules = list_resp.json()
    assert isinstance(schedules, list)
    matching = [s for s in schedules if s["id"] == schedule_id]
    assert len(matching) == 1, (
        f"Schedule {schedule_id} not found in listing. IDs: {[s['id'] for s in schedules]}"
    )
    sched = matching[0]
    assert sched["name"] == "Morning Alpha Scan"
    assert sched["frequency"] == "weekdays"
    assert sched["config_summary"]["market_mode"] == "equities"
    # Before any run, history is empty and latest_payload_summary is None
    assert isinstance(sched["history"], list)

    # ── POST run-now ─────────────────────────────────────────────────────────
    run_resp = client.post(
        f"/user/strategy-schedules/{schedule_id}/run",
        headers=_USER_AUTH,
    )
    assert run_resp.status_code == 200, f"schedule run failed: {run_resp.text}"
    run_payload = run_resp.json()

    # Assert all top-level keys are present in the run payload
    for key in ("top_candidates", "watchlist_only", "no_trade", "queue", "summary"):
        assert key in run_payload, f"run payload missing '{key}'"

    # Assert email_provider is stamped in the run payload
    assert "email_provider" in run_payload, "run payload missing 'email_provider'"
    # In tests EMAIL_PROVIDER=console
    assert run_payload["email_provider"] == "console", (
        f"Expected email_provider=console, got {run_payload['email_provider']!r}"
    )
    assert run_payload["schedule_id"] == schedule_id
    assert run_payload["trigger"] == "run_now"

    # Assert summary counts are present and well-formed
    summary = run_payload["summary"]
    for count_key in ("total", "top_candidate_count", "no_trade_count"):
        assert count_key in summary, f"summary missing '{count_key}'"
    assert isinstance(summary["total"], int)
    assert isinstance(summary["top_candidate_count"], int)

    # ── GET schedule list again — confirm run recorded in history ───────────
    list_after_resp = client.get("/user/strategy-schedules", headers=_USER_AUTH)
    assert list_after_resp.status_code == 200
    sched_after = next(s for s in list_after_resp.json() if s["id"] == schedule_id)

    assert len(sched_after["history"]) > 0, (
        "Expected at least one run in schedule history after run-now"
    )
    latest_run = sched_after["history"][0]
    assert latest_run["status"] == "sent", (
        f"Expected run status 'sent', got {latest_run['status']!r}"
    )
    assert "email_provider" in latest_run, "history run missing email_provider"
    assert "summary" in latest_run, "history run missing summary"

    # latest_payload_summary should be populated after the run
    assert sched_after["latest_payload_summary"] is not None, (
        "latest_payload_summary is None after a completed run"
    )
    assert "top_candidate_count" in sched_after["latest_payload_summary"]


# ---------------------------------------------------------------------------
# WORKFLOW 3 — Watchlist CRUD
# ---------------------------------------------------------------------------

def test_workflow3_watchlist_crud() -> None:
    """
    Exercise full watchlist lifecycle with realistic symbol sets:

        POST create (Core Tech + Large-Cap)
        → GET list (confirm appears)
        → PUT update symbols
        → GET list (confirm update visible)
        → DELETE
        → GET list (confirm gone)
    """
    _seed_approved_user()

    # ── POST create watchlist ───────────────────────────────────────────────
    create_resp = client.post(
        "/user/watchlists",
        headers=_USER_AUTH,
        json={"name": "Core Tech", "symbols": ["AAPL", "MSFT", "GOOGL"]},
    )
    assert create_resp.status_code == 200, f"watchlist create failed: {create_resp.text}"
    wl = create_resp.json()
    assert wl["name"] == "Core Tech"
    assert set(wl["symbols"]) == {"AAPL", "MSFT", "GOOGL"}, (
        f"Unexpected symbols: {wl['symbols']}"
    )
    wl_id: int = wl["id"]

    # ── GET watchlists — confirm it appears ─────────────────────────────────
    list_resp = client.get("/user/watchlists", headers=_USER_AUTH)
    assert list_resp.status_code == 200, f"watchlist list failed: {list_resp.text}"
    watchlists = list_resp.json()
    found = next((w for w in watchlists if w["id"] == wl_id), None)
    assert found is not None, f"Watchlist {wl_id} not found in listing"
    assert found["name"] == "Core Tech"
    assert "AAPL" in found["symbols"]

    # ── PUT update the watchlist symbols ────────────────────────────────────
    update_resp = client.put(
        f"/user/watchlists/{wl_id}",
        headers=_USER_AUTH,
        json={"name": "Core Tech + Semi", "symbols": ["AAPL", "MSFT", "NVDA", "AMD"]},
    )
    assert update_resp.status_code == 200, f"watchlist update failed: {update_resp.text}"
    updated = update_resp.json()
    assert updated["name"] == "Core Tech + Semi"
    assert set(updated["symbols"]) == {"AAPL", "MSFT", "NVDA", "AMD"}, (
        f"Unexpected symbols after update: {updated['symbols']}"
    )

    # Confirm update is visible in subsequent listing
    list_after_update = client.get("/user/watchlists", headers=_USER_AUTH)
    assert list_after_update.status_code == 200
    updated_in_list = next(w for w in list_after_update.json() if w["id"] == wl_id)
    assert "NVDA" in updated_in_list["symbols"], (
        "NVDA not found in updated watchlist symbols"
    )
    assert "GOOGL" not in updated_in_list["symbols"], (
        "GOOGL should have been removed by update"
    )

    # ── DELETE the watchlist ────────────────────────────────────────────────
    delete_resp = client.delete(
        f"/user/watchlists/{wl_id}",
        headers=_USER_AUTH,
    )
    assert delete_resp.status_code == 200, f"watchlist delete failed: {delete_resp.text}"
    assert delete_resp.json()["deleted"] is True

    # ── GET watchlists — confirm it's gone ──────────────────────────────────
    list_final = client.get("/user/watchlists", headers=_USER_AUTH)
    assert list_final.status_code == 200
    ids_final = [w["id"] for w in list_final.json()]
    assert wl_id not in ids_final, (
        f"Deleted watchlist {wl_id} still appears in listing: {ids_final}"
    )


# ---------------------------------------------------------------------------
# WORKFLOW 4 — Admin workflows
# ---------------------------------------------------------------------------

def test_workflow4_admin_workflows() -> None:
    """
    Exercise the admin management workflow end-to-end:

        Seed pending user
        → GET pending-users queue (confirm user appears)
        → POST approve the user
        → GET users list (confirm approval_status=approved)
        → POST send an invite (EMAIL_PROVIDER=console — no real delivery)
        → GET invites list (confirm invite appears)
    """
    # Seed pending user (clerk_user, approval_status=pending by default)
    pending_user_id = _seed_pending_user()

    # Seed admin (clerk_admin with app_role=admin, mfa_enabled=True)
    _seed_admin()

    # ── GET pending users queue — confirm user appears ──────────────────────
    pending_resp = client.get("/admin/users/pending", headers=_ADMIN_AUTH)
    assert pending_resp.status_code == 200, f"pending users failed: {pending_resp.text}"
    pending = pending_resp.json()
    assert isinstance(pending, list)
    pending_ids = [u["id"] for u in pending]
    assert pending_user_id in pending_ids, (
        f"User {pending_user_id} not found in pending queue. "
        f"Pending user ids: {pending_ids}"
    )

    # Confirm user record has expected fields
    pending_record = next(u for u in pending if u["id"] == pending_user_id)
    assert "email" in pending_record
    assert pending_record["email"] == "user@example.com"

    # ── POST approve the user ───────────────────────────────────────────────
    approve_resp = client.post(
        f"/admin/users/{pending_user_id}/approve",
        headers=_ADMIN_AUTH,
        json={"user_id": pending_user_id, "note": "approved for private alpha access"},
    )
    assert approve_resp.status_code == 200, f"user approve failed: {approve_resp.text}"
    approval = approve_resp.json()
    assert approval["id"] == pending_user_id
    assert approval["approval_status"] == "approved", (
        f"Expected approval_status=approved after approve, got {approval['approval_status']!r}"
    )

    # ── GET users list — confirm approval_status=approved ──────────────────
    users_resp = client.get("/admin/users", headers=_ADMIN_AUTH)
    assert users_resp.status_code == 200, f"users list failed: {users_resp.text}"
    users = users_resp.json()
    assert isinstance(users, list)
    user_row = next((u for u in users if u["id"] == pending_user_id), None)
    assert user_row is not None, (
        f"User {pending_user_id} not found in admin users list"
    )
    assert user_row["approval_status"] == "approved", (
        f"Expected approval_status=approved in users list, got {user_row['approval_status']!r}"
    )

    # ── POST send an invite (console provider — no real delivery) ───────────
    invite_resp = client.post(
        "/admin/invites",
        headers=_ADMIN_AUTH,
        json={"email": "newtrader@example.com", "display_name": "New Trader"},
    )
    assert invite_resp.status_code == 200, f"invite send failed: {invite_resp.text}"
    invite = invite_resp.json()
    assert "invite_id" in invite, "invite response missing invite_id"
    assert invite["email"] == "newtrader@example.com"
    assert "invite_token" in invite, "invite response missing invite_token"
    # After creation the invite_repo sets status='sent' (invite is only created
    # when actively dispatched, so it is immediately marked sent).
    assert invite["status"] in {"pending", "sent"}, (
        f"Unexpected invite status: {invite['status']!r}"
    )

    # ── GET invites list — confirm invite appears ───────────────────────────
    invites_resp = client.get("/admin/invites", headers=_ADMIN_AUTH)
    assert invites_resp.status_code == 200, f"invites list failed: {invites_resp.text}"
    invites = invites_resp.json()
    assert isinstance(invites, list)
    found_invite = next(
        (i for i in invites if i["email"] == "newtrader@example.com"),
        None,
    )
    assert found_invite is not None, (
        f"Sent invite for newtrader@example.com not found in invites list. "
        f"Emails present: {[i['email'] for i in invites]}"
    )
    assert found_invite["display_name"] == "New Trader", (
        f"Unexpected display_name: {found_invite['display_name']!r}"
    )
    assert "invite_token" in found_invite
    assert "invited_by" in found_invite


# ---------------------------------------------------------------------------
# WORKFLOW 5 — Provider health
# ---------------------------------------------------------------------------

def test_workflow5_provider_health() -> None:
    """
    Assert the /admin/provider-health endpoint contract:

        - response has providers array
        - market_data provider has workflow_execution_mode field
        - configured_provider field is present
        - effective_read_mode field is present
        - operational_impact copy is present
    """
    _seed_admin()

    resp = client.get("/admin/provider-health", headers=_ADMIN_AUTH)
    assert resp.status_code == 200, f"provider-health failed: {resp.text}"
    payload = resp.json()

    # Top-level structure
    assert "providers" in payload, "response missing 'providers' array"
    assert isinstance(payload["providers"], list), "'providers' is not a list"
    assert len(payload["providers"]) > 0, "providers array is empty"
    assert "checked_at" in payload, "response missing 'checked_at'"

    # All three known providers must be present
    provider_names = {p["provider"] for p in payload["providers"]}
    assert "auth" in provider_names, f"auth provider missing from: {provider_names}"
    assert "email" in provider_names, f"email provider missing from: {provider_names}"
    assert "market_data" in provider_names, f"market_data provider missing from: {provider_names}"

    # Locate the market_data provider entry
    market_data_entry = next(
        p for p in payload["providers"] if p["provider"] == "market_data"
    )

    # Assert workflow_execution_mode field is present and valid
    assert "workflow_execution_mode" in market_data_entry, (
        "market_data provider missing 'workflow_execution_mode'"
    )
    valid_modes = {"provider", "demo_fallback", "blocked"}
    assert market_data_entry["workflow_execution_mode"] in valid_modes, (
        f"Unexpected workflow_execution_mode: {market_data_entry['workflow_execution_mode']!r}"
    )

    # Assert configured_provider field is present and non-empty
    assert "configured_provider" in market_data_entry, (
        "market_data provider missing 'configured_provider'"
    )
    assert isinstance(market_data_entry["configured_provider"], str)
    assert len(market_data_entry["configured_provider"]) > 0, (
        "configured_provider is an empty string"
    )

    # Assert effective_read_mode is present
    assert "effective_read_mode" in market_data_entry, (
        "market_data provider missing 'effective_read_mode'"
    )

    # Assert operational_impact copy is present
    assert "operational_impact" in market_data_entry, (
        "market_data provider missing 'operational_impact'"
    )
    assert isinstance(market_data_entry["operational_impact"], str)
    assert len(market_data_entry["operational_impact"]) > 0

    # Status must be a known sentinel ("warning" is the fallback-provider state)
    assert market_data_entry["status"] in {"ok", "warning", "error", "degraded"}, (
        f"Unexpected market_data status: {market_data_entry['status']!r}"
    )
