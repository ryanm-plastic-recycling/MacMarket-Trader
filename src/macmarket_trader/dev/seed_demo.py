"""Deterministic local/demo seed data for operator console workflows."""

from __future__ import annotations

from datetime import date, timedelta

from macmarket_trader.domain.enums import ApprovalStatus
from macmarket_trader.domain.schemas import Bar, PortfolioSnapshot, ReplayRunRequest
from macmarket_trader.replay.engine import ReplayEngine
from macmarket_trader.service import RecommendationService
from macmarket_trader.storage.db import init_db
from macmarket_trader.storage.repositories import ProviderHealthRepository, UserRepository


def _sample_bars() -> list[Bar]:
    base = date(2026, 1, 1)
    return [
        Bar(
            date=base + timedelta(days=i),
            open=100 + i,
            high=101 + i,
            low=99 + i,
            close=100.5 + i,
            volume=1_000_000 + i * 10_000,
            rel_volume=1.15,
        )
        for i in range(25)
    ]


def seed_demo_data() -> dict[str, object]:
    """Seed enough deterministic records for local operator-console demos."""
    from macmarket_trader.storage.db import SessionLocal

    init_db()
    service = RecommendationService()
    replay = ReplayEngine(service=service)
    user_repo = UserRepository(SessionLocal)
    provider_health_repo = ProviderHealthRepository(SessionLocal)

    user_repo.upsert_from_auth(
        external_auth_user_id="demo_pending_user",
        email="pending.operator@example.com",
        display_name="Pending Operator",
        mfa_enabled=False,
    )
    pending_user = user_repo.get_by_external_id("demo_pending_user")

    service.generate(
        symbol="AAPL",
        bars=_sample_bars(),
        event_text="Earnings beat with raised guidance and stable demand.",
        event=None,
        portfolio=PortfolioSnapshot(),
    )

    replay.run(
        ReplayRunRequest(
            symbol="AAPL",
            event_texts=[
                "Earnings beat and guide up.",
                "Analyst follow-through and sector momentum.",
            ],
            bars=_sample_bars(),
            portfolio=PortfolioSnapshot(),
        )
    )

    provider_health_repo.create(provider="auth", status="ok", details="Clerk identity boundary active; local authorization authoritative.")
    provider_health_repo.create(provider="email", status="ok", details="Approval notifications routed through configured email provider.")
    provider_health_repo.create(provider="market_data", status="warning", details="Deterministic fallback market-data mode for local demo.")

    return {
        "status": "seeded",
        "recommendation_count_min": 1,
        "replay_runs_count_min": 1,
        "orders_count_min": 1,
        "pending_user_id": pending_user.id if pending_user and pending_user.approval_status == ApprovalStatus.PENDING.value else None,
        "provider_health_snapshots_added": 3,
    }
