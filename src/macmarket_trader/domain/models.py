"""SQLAlchemy models for persistence and Alembic-ready metadata."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from macmarket_trader.domain.time import utc_now


class Base(DeclarativeBase):
    """Base SQLAlchemy declarative class."""


class RawIngestEventModel(Base):
    __tablename__ = "raw_ingest_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    external_id: Mapped[str] = mapped_column(String(128), index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class NormalizedEventModel(Base):
    __tablename__ = "normalized_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_ingest_event_id: Mapped[int | None] = mapped_column(ForeignKey("raw_ingest_events.id"), nullable=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class EventEntityModel(Base):
    __tablename__ = "event_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    normalized_event_id: Mapped[int] = mapped_column(ForeignKey("normalized_events.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_value: Mapped[str] = mapped_column(String(128), index=True)


class DailyBarModel(Base):
    __tablename__ = "daily_bars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    bar_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(Integer)


class MacroCalendarEventModel(Base):
    __tablename__ = "macro_calendar_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_name: Mapped[str] = mapped_column(String(128), index=True)
    country: Mapped[str] = mapped_column(String(32), default="US")
    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON)


class ProviderCursorModel(Base):
    __tablename__ = "provider_cursors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(64), unique=True)
    cursor: Mapped[str] = mapped_column(String(256))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ProviderHealthModel(Base):
    __tablename__ = "provider_health"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    details: Mapped[str] = mapped_column(Text, default="")
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class RecommendationModel(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recommendation_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    app_user_id: Mapped[int | None] = mapped_column(ForeignKey("app_users.id"), nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON)


class RecommendationEvidenceModel(Base):
    __tablename__ = "recommendation_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recommendation_id: Mapped[int] = mapped_column(ForeignKey("recommendations.id"), index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class OrderModel(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    app_user_id: Mapped[int | None] = mapped_column(ForeignKey("app_users.id"), nullable=True, index=True)
    recommendation_id: Mapped[str] = mapped_column(String(64), index=True)
    replay_run_id: Mapped[int | None] = mapped_column(ForeignKey("replay_runs.id"), nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    side: Mapped[str] = mapped_column(String(8))
    shares: Mapped[int] = mapped_column(Integer)
    limit_price: Mapped[float] = mapped_column(Float)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)


class FillModel(Base):
    __tablename__ = "fills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(64), index=True)
    fill_price: Mapped[float] = mapped_column(Float)
    filled_shares: Mapped[int] = mapped_column(Integer)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class PortfolioSnapshotModel(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_context: Mapped[str] = mapped_column(String(64), index=True)
    equity: Mapped[float] = mapped_column(Float)
    current_heat: Mapped[float] = mapped_column(Float)
    open_positions_notional: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class ReplayRunModel(Base):
    __tablename__ = "replay_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    app_user_id: Mapped[int | None] = mapped_column(ForeignKey("app_users.id"), nullable=True, index=True)
    recommendation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source_recommendation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    source_strategy: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_market_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_market_data_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_fallback_mode: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    recommendation_count: Mapped[int] = mapped_column(Integer)
    approved_count: Mapped[int] = mapped_column(Integer)
    fill_count: Mapped[int] = mapped_column(Integer)
    ending_heat: Mapped[float] = mapped_column(Float)
    ending_open_notional: Mapped[float] = mapped_column(Float)
    has_stageable_candidate: Mapped[bool] = mapped_column(Boolean, default=False)
    stageable_recommendation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    stageable_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class ReplayStepModel(Base):
    __tablename__ = "replay_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    replay_run_id: Mapped[int] = mapped_column(ForeignKey("replay_runs.id"), index=True)
    step_index: Mapped[int] = mapped_column(Integer)
    recommendation_id: Mapped[str] = mapped_column(String(64), index=True)
    approved: Mapped[bool] = mapped_column(Boolean)
    pre_step_snapshot: Mapped[dict[str, object]] = mapped_column(JSON)
    post_step_snapshot: Mapped[dict[str, object]] = mapped_column(JSON)


class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recommendation_id: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class AppUserModel(Base):
    __tablename__ = "app_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_auth_user_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    approval_status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    app_role: Mapped[str] = mapped_column(String(24), default="user", index=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_authenticated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)


class UserApprovalRequestModel(Base):
    __tablename__ = "user_approval_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    app_user_id: Mapped[int] = mapped_column(ForeignKey("app_users.id"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EmailDeliveryLogModel(Base):
    __tablename__ = "email_delivery_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    app_user_id: Mapped[int | None] = mapped_column(ForeignKey("app_users.id"), nullable=True)
    template_name: Mapped[str] = mapped_column(String(64), index=True)
    destination: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(24), index=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class AppInviteModel(Base):
    __tablename__ = "app_invites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    display_name: Mapped[str] = mapped_column(String(255), default="")
    invite_token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="sent", index=True)
    invited_by: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WatchlistModel(Base):
    __tablename__ = "watchlists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    app_user_id: Mapped[int] = mapped_column(ForeignKey("app_users.id"), index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    symbols: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class StrategyReportScheduleModel(Base):
    __tablename__ = "strategy_report_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    app_user_id: Mapped[int] = mapped_column(ForeignKey("app_users.id"), index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    frequency: Mapped[str] = mapped_column(String(24), default="weekdays", index=True)
    run_time: Mapped[str] = mapped_column(String(16), default="08:30")
    timezone: Mapped[str] = mapped_column(String(64), default="America/New_York")
    email_target: Mapped[str] = mapped_column(String(255))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    latest_status: Mapped[str] = mapped_column(String(24), default="idle")
    latest_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    latest_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class StrategyReportRunModel(Base):
    __tablename__ = "strategy_report_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("strategy_report_schedules.id"), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    delivered_to: Mapped[str] = mapped_column(String(255))
    payload: Mapped[dict[str, object]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class PaperPositionModel(Base):
    __tablename__ = "paper_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    app_user_id: Mapped[int] = mapped_column(ForeignKey("app_users.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    side: Mapped[str] = mapped_column(String(8))
    quantity: Mapped[float] = mapped_column(Float)
    average_price: Mapped[float] = mapped_column(Float)
    open_notional: Mapped[float] = mapped_column(Float, default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    opened_qty: Mapped[float | None] = mapped_column(Float, nullable=True)
    remaining_qty: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommendation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    replay_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    order_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)


class PaperTradeModel(Base):
    __tablename__ = "paper_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    app_user_id: Mapped[int] = mapped_column(ForeignKey("app_users.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(16), index=True)
    side: Mapped[str] = mapped_column(String(8))
    entry_price: Mapped[float] = mapped_column(Float)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    quantity: Mapped[float] = mapped_column(Float)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    position_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    hold_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recommendation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    replay_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    order_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    close_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
