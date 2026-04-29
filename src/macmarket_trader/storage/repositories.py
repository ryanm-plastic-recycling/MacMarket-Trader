"""SQLAlchemy repositories for audit and app state persistence."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from macmarket_trader.domain.enums import AppRole, ApprovalStatus
from macmarket_trader.domain.models import (
    AppUserModel,
    AuditLogModel,
    AppInviteModel,
    DailyBarModel,
    EmailDeliveryLogModel,
    FillModel,
    OrderModel,
    PaperOptionOrderLegModel,
    PaperOptionOrderModel,
    PaperOptionPositionLegModel,
    PaperOptionPositionModel,
    PaperOptionTradeLegModel,
    PaperOptionTradeModel,
    PaperPositionModel,
    PaperTradeModel,
    ProviderHealthModel,
    RecommendationEvidenceModel,
    RecommendationModel,
    ReplayRunModel,
    ReplayStepModel,
    StrategyReportRunModel,
    StrategyReportScheduleModel,
    UserApprovalRequestModel,
    WatchlistModel,
)
from macmarket_trader.domain.schemas import (
    FillRecord,
    OptionPaperOrderLegRecord,
    OptionPaperOrderRecord,
    OptionPaperPositionLegRecord,
    OptionPaperPositionRecord,
    OptionPaperStructureInput,
    OptionPaperTradeLegRecord,
    OptionPaperTradeRecord,
    OrderRecord,
    PortfolioSnapshot,
    TradeRecommendation,
)
from macmarket_trader.options.paper_contracts import prepare_option_paper_structure

SessionFactory = Callable[[], Session]


# Pass 4 — display_id support.
# Map well-known strategy display names to short abbreviations used in the
# operator-facing display_id label (e.g. "AAPL-EVCONT-20260429-0830").
_STRATEGY_ABBREVIATIONS: dict[str, str] = {
    "event continuation": "EVCONT",
    "breakout / prior-day high": "BRKOUT",
    "pullback / trend continuation": "PULLBK",
    "iron condor": "ICOND",
}


def _abbreviate_strategy(strategy: str | None) -> str:
    """Return a short uppercase strategy code for the display_id middle segment.
    Known strategies map to a curated 6-char code. Unknown strategies fall
    through to the first 6 characters of the upper-cased name with whitespace
    stripped. Empty input returns 'UNKNWN'.
    """
    if not strategy:
        return "UNKNWN"
    key = strategy.strip().lower()
    if key in _STRATEGY_ABBREVIATIONS:
        return _STRATEGY_ABBREVIATIONS[key]
    cleaned = "".join(ch for ch in strategy.upper() if not ch.isspace())
    return cleaned[:6] if cleaned else "UNKNWN"


def make_display_id(*, symbol: str, strategy: str | None, created_at: datetime) -> str:
    """Build the operator-facing display_id label.

    Format: {SYMBOL}-{ABBREV}-{YYYYMMDD}-{HHMM}, where the timestamp is the
    UTC wall-clock of `created_at`. Example: "AAPL-EVCONT-20260429-0830".
    """
    abbrev = _abbreviate_strategy(strategy)
    sym = (symbol or "UNK").upper().strip() or "UNK"
    ts = created_at if created_at.tzinfo is not None else created_at.replace(tzinfo=timezone.utc)
    return f"{sym}-{abbrev}-{ts.strftime('%Y%m%d')}-{ts.strftime('%H%M')}"


def display_id_or_fallback(row_display_id: str | None, recommendation_id: str) -> str:
    """Pick the human-readable label for API responses. Legacy rows without
    display_id (created before the column was added) fall back to a short
    truncation of the canonical recommendation_id."""
    if row_display_id:
        return row_display_id
    tail = (recommendation_id or "")[-6:] if recommendation_id else ""
    return f"Rec #{tail}" if tail else "Rec #—"


def gross_pnl_or_fallback(row: PaperTradeModel) -> float:
    """Phase 7 — prefer stored gross_pnl, but preserve legacy trade rows.

    Existing trade rows created before the gross/net split will have
    realized_pnl populated and newly-added gross/net columns defaulted to 0.0.
    Treat those rows as gross == net == realized so old history still renders
    credibly after schema extension.
    """
    gross = float(getattr(row, "gross_pnl", 0.0) or 0.0)
    net = float(getattr(row, "net_pnl", 0.0) or 0.0)
    realized = float(getattr(row, "realized_pnl", 0.0) or 0.0)
    if gross == 0.0 and net == 0.0 and realized != 0.0:
        return realized
    return gross


def net_pnl_or_fallback(row: PaperTradeModel) -> float:
    gross = float(getattr(row, "gross_pnl", 0.0) or 0.0)
    net = float(getattr(row, "net_pnl", 0.0) or 0.0)
    realized = float(getattr(row, "realized_pnl", 0.0) or 0.0)
    if gross == 0.0 and net == 0.0 and realized != 0.0:
        return realized
    return net if net != 0.0 or gross != 0.0 or realized == 0.0 else realized


def commission_paid_for_trade(row: PaperTradeModel) -> float:
    gross = gross_pnl_or_fallback(row)
    net = net_pnl_or_fallback(row)
    return max(0.0, gross - net)


class RecommendationRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def create(
        self,
        recommendation: TradeRecommendation,
        *,
        app_user_id: int | None = None,
        strategy: str | None = None,
    ) -> RecommendationModel:
        payload = recommendation.model_dump(mode="json")
        # Derive the display_id at insert time so the human-readable label is
        # stable from creation onward. If `strategy` is not provided by the
        # caller, fall back to the lower-level setup_type from the
        # TradeRecommendation payload.
        from macmarket_trader.domain.time import utc_now
        derived_strategy = strategy
        if not derived_strategy:
            entry = payload.get("entry") if isinstance(payload, dict) else None
            if isinstance(entry, dict):
                raw_setup = entry.get("setup_type")
                if isinstance(raw_setup, str):
                    derived_strategy = raw_setup
        created_at_for_id = utc_now()
        display_id = make_display_id(
            symbol=recommendation.symbol,
            strategy=derived_strategy,
            created_at=created_at_for_id,
        )
        with self.session_factory() as session:
            row = RecommendationModel(
                recommendation_id=recommendation.recommendation_id,
                app_user_id=app_user_id,
                symbol=recommendation.symbol,
                payload=payload,
                display_id=display_id,
            )
            session.add(row)
            session.flush()
            session.add(RecommendationEvidenceModel(recommendation_id=row.id, payload=recommendation.evidence.model_dump(mode="json")))
            session.add(AuditLogModel(recommendation_id=recommendation.recommendation_id, payload=payload))
            session.commit()
            session.refresh(row)
            return row

    def update_display_id_strategy(self, recommendation_uid: str, *, strategy: str) -> None:
        """Re-generate display_id once a more specific strategy label becomes
        known after creation (e.g. the promote endpoint's strategy parameter
        is friendlier than the SetupType enum used at create time)."""
        with self.session_factory() as session:
            row = session.execute(
                select(RecommendationModel).where(RecommendationModel.recommendation_id == recommendation_uid)
            ).scalar_one_or_none()
            if row is None:
                return
            row.display_id = make_display_id(
                symbol=row.symbol,
                strategy=strategy,
                created_at=row.created_at,
            )
            session.commit()

    def list_recent(self, limit: int = 200, *, app_user_id: int | None = None) -> list[RecommendationModel]:
        with self.session_factory() as session:
            stmt = select(RecommendationModel)
            if app_user_id is not None:
                stmt = stmt.where(RecommendationModel.app_user_id == app_user_id)
            stmt = stmt.order_by(RecommendationModel.created_at.desc()).limit(limit)
            return list(session.execute(stmt).scalars())

    def get_by_id(self, recommendation_id: int) -> RecommendationModel | None:
        with self.session_factory() as session:
            return session.get(RecommendationModel, recommendation_id)

    def get_by_recommendation_uid(self, recommendation_uid: str) -> RecommendationModel | None:
        with self.session_factory() as session:
            return session.execute(
                select(RecommendationModel).where(RecommendationModel.recommendation_id == recommendation_uid)
            ).scalar_one_or_none()

    def attach_workflow_metadata(
        self,
        recommendation_id: str,
        *,
        market_data_source: str,
        fallback_mode: bool,
        market_mode: str | None = None,
        source_strategy: str | None = None,
    ) -> None:
        with self.session_factory() as session:
            row = session.execute(
                select(RecommendationModel).where(RecommendationModel.recommendation_id == recommendation_id)
            ).scalar_one_or_none()
            if row is None:
                return
            payload = dict(row.payload or {})
            workflow = dict(payload.get("workflow") or {})
            workflow.update({"market_data_source": market_data_source, "fallback_mode": fallback_mode})
            if market_mode:
                workflow["market_mode"] = market_mode
            if source_strategy:
                workflow["source_strategy"] = source_strategy
            payload["workflow"] = workflow
            row.payload = payload
            session.commit()

    def attach_ranking_provenance(self, recommendation_id: str, *, ranking_provenance: dict[str, object]) -> None:
        with self.session_factory() as session:
            row = session.execute(
                select(RecommendationModel).where(RecommendationModel.recommendation_id == recommendation_id)
            ).scalar_one_or_none()
            if row is None:
                return
            payload = dict(row.payload or {})
            workflow = dict(payload.get("workflow") or {})
            workflow["ranking_provenance"] = ranking_provenance
            payload["workflow"] = workflow
            row.payload = payload
            session.commit()

    def set_approved(self, recommendation_uid: str, *, approved: bool) -> "RecommendationModel | None":
        with self.session_factory() as session:
            row = session.execute(
                select(RecommendationModel).where(RecommendationModel.recommendation_id == recommendation_uid)
            ).scalar_one_or_none()
            if row is None:
                return None
            payload = dict(row.payload or {})
            payload["approved"] = approved
            if not approved:
                payload.setdefault("rejection_reason", "operator_rejected")
            else:
                payload.pop("rejection_reason", None)
            row.payload = payload
            session.commit()
            session.refresh(row)
            return row



class OrderRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def create(self, order: OrderRecord, notes: str = "", *, app_user_id: int | None = None) -> OrderModel:
        replay_run_id: int | None = None
        if notes and "replay_run_id=" in notes:
            parts = {segment.split("=", 1)[0]: segment.split("=", 1)[1] for segment in notes.split("|") if "=" in segment}
            raw = parts.get("replay_run_id")
            replay_run_id = int(raw) if raw and raw.isdigit() else None
        with self.session_factory() as session:
            row = OrderModel(
                order_id=order.order_id,
                app_user_id=app_user_id,
                recommendation_id=order.recommendation_id,
                replay_run_id=replay_run_id,
                symbol=order.symbol,
                status=order.status.value,
                side=order.side.value,
                shares=order.shares,
                limit_price=order.limit_price,
                notes=notes,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def list_with_fills(self, limit: int = 200, *, app_user_id: int | None = None) -> list[dict[str, object]]:
        with self.session_factory() as session:
            stmt = select(OrderModel)
            if app_user_id is not None:
                stmt = stmt.where(OrderModel.app_user_id == app_user_id)
            orders = list(session.execute(stmt.order_by(OrderModel.created_at.desc()).limit(limit)).scalars())
            if not orders:
                return []
            fills = list(session.execute(select(FillModel)).scalars())
            fills_by_order: dict[str, list[FillModel]] = {}
            for fill in fills:
                fills_by_order.setdefault(fill.order_id, []).append(fill)

            output: list[dict[str, object]] = []
            for order in orders:
                order_fills = sorted(fills_by_order.get(order.order_id, []), key=lambda item: item.timestamp)
                source = None
                fallback_mode = None
                replay_run_id = order.replay_run_id
                if order.notes and "|source=" in order.notes:
                    parts = {segment.split("=", 1)[0]: segment.split("=", 1)[1] for segment in order.notes.split("|") if "=" in segment}
                    source = parts.get("source")
                    fallback_mode = parts.get("fallback") == "true"
                    raw_run_id = parts.get("replay_run_id")
                    if replay_run_id is None and raw_run_id and raw_run_id.isdigit():
                        replay_run_id = int(raw_run_id)
                if source is None and order.recommendation_id:
                    rec = session.execute(
                        select(RecommendationModel).where(RecommendationModel.recommendation_id == order.recommendation_id)
                    ).scalar_one_or_none()
                    workflow = (rec.payload or {}).get("workflow", {}) if rec else {}
                    source = workflow.get("market_data_source")
                    if workflow.get("fallback_mode") is not None:
                        fallback_mode = bool(workflow.get("fallback_mode"))
                output.append(
                    {
                        "order_id": order.order_id,
                        "recommendation_id": order.recommendation_id,
                        "replay_run_id": replay_run_id,
                        "symbol": order.symbol,
                        "status": order.status,
                        "side": order.side,
                        "shares": order.shares,
                        "limit_price": order.limit_price,
                        "created_at": order.created_at,
                        "canceled_at": order.canceled_at.isoformat() if order.canceled_at else None,
                        "market_data_source": source,
                        "fallback_mode": fallback_mode,
                        "fills": [
                            {"fill_price": fill.fill_price, "filled_shares": fill.filled_shares, "timestamp": fill.timestamp}
                            for fill in order_fills
                        ],
                    }
                )
            return output

    def get_by_order_id(self, order_id: str, *, app_user_id: int | None = None) -> OrderModel | None:
        with self.session_factory() as session:
            stmt = select(OrderModel).where(OrderModel.order_id == order_id)
            if app_user_id is not None:
                stmt = stmt.where(OrderModel.app_user_id == app_user_id)
            return session.execute(stmt).scalar_one_or_none()

    def set_status(self, order_id: str, *, status: str) -> None:
        with self.session_factory() as session:
            row = session.execute(select(OrderModel).where(OrderModel.order_id == order_id)).scalar_one_or_none()
            if row is not None:
                row.status = status
                session.commit()

    def has_fills(self, order_id: str) -> bool:
        """True if any fill exists for this order_id (in the FillModel table)."""
        with self.session_factory() as session:
            row = session.execute(
                select(FillModel.id).where(FillModel.order_id == order_id).limit(1)
            ).first()
            return row is not None

    def cancel(self, order_id: str, *, canceled_at: datetime) -> OrderModel | None:
        """Set status='canceled' and the canceled_at timestamp; return updated row."""
        with self.session_factory() as session:
            row = session.execute(
                select(OrderModel).where(OrderModel.order_id == order_id)
            ).scalar_one_or_none()
            if row is None:
                return None
            row.status = "canceled"
            row.canceled_at = canceled_at
            session.commit()
            session.refresh(row)
            return row


class FillRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def create(self, fill: FillRecord) -> FillModel:
        with self.session_factory() as session:
            row = FillModel(
                order_id=fill.order_id,
                fill_price=fill.fill_price,
                filled_shares=fill.filled_shares,
                timestamp=fill.timestamp,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row


class ReplayRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def create_run(
        self,
        *,
        symbol: str,
        recommendation_id: str | None,
        source_recommendation_id: str | None = None,
        source_strategy: str | None = None,
        source_market_mode: str | None = None,
        source_market_data_source: str | None = None,
        source_fallback_mode: bool | None = None,
        recommendation_count: int,
        approved_count: int,
        fill_count: int,
        ending_heat: float,
        ending_open_notional: float,
        has_stageable_candidate: bool = False,
        stageable_recommendation_id: str | None = None,
        stageable_reason: str | None = None,
        app_user_id: int | None = None,
    ) -> ReplayRunModel:
        with self.session_factory() as session:
            row = ReplayRunModel(
                symbol=symbol,
                app_user_id=app_user_id,
                recommendation_id=recommendation_id,
                source_recommendation_id=source_recommendation_id,
                source_strategy=source_strategy,
                source_market_mode=source_market_mode,
                source_market_data_source=source_market_data_source,
                source_fallback_mode=source_fallback_mode,
                recommendation_count=recommendation_count,
                approved_count=approved_count,
                fill_count=fill_count,
                ending_heat=ending_heat,
                ending_open_notional=ending_open_notional,
                has_stageable_candidate=has_stageable_candidate,
                stageable_recommendation_id=stageable_recommendation_id,
                stageable_reason=stageable_reason,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def create_step(
        self,
        replay_run_id: int,
        step_index: int,
        recommendation_id: str,
        approved: bool,
        pre_step_snapshot: PortfolioSnapshot,
        post_step_snapshot: PortfolioSnapshot,
    ) -> ReplayStepModel:
        with self.session_factory() as session:
            row = ReplayStepModel(
                replay_run_id=replay_run_id,
                step_index=step_index,
                recommendation_id=recommendation_id,
                approved=approved,
                pre_step_snapshot=pre_step_snapshot.model_dump(mode="json"),
                post_step_snapshot=post_step_snapshot.model_dump(mode="json"),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def list_runs(self, limit: int = 200, *, app_user_id: int | None = None) -> list[ReplayRunModel]:
        with self.session_factory() as session:
            stmt = select(ReplayRunModel)
            if app_user_id is not None:
                stmt = stmt.where(ReplayRunModel.app_user_id == app_user_id)
            stmt = stmt.order_by(ReplayRunModel.created_at.desc()).limit(limit)
            return list(session.execute(stmt).scalars())

    def list_steps_for_run(self, replay_run_id: int) -> list[ReplayStepModel]:
        with self.session_factory() as session:
            stmt = select(ReplayStepModel).where(ReplayStepModel.replay_run_id == replay_run_id).order_by(ReplayStepModel.step_index.asc())
            return list(session.execute(stmt).scalars())

    def get_run(self, replay_run_id: int, *, app_user_id: int | None = None) -> ReplayRunModel | None:
        with self.session_factory() as session:
            stmt = select(ReplayRunModel).where(ReplayRunModel.id == replay_run_id)
            if app_user_id is not None:
                stmt = stmt.where(ReplayRunModel.app_user_id == app_user_id)
            return session.execute(stmt).scalar_one_or_none()


class PaperPortfolioRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def summary(self, *, app_user_id: int) -> dict[str, float | int]:
        with self.session_factory() as session:
            open_positions = list(
                session.execute(
                    select(PaperPositionModel).where(
                        PaperPositionModel.app_user_id == app_user_id,
                        PaperPositionModel.status == "open",
                    )
                ).scalars()
            )
            closed_trades = list(
                session.execute(
                    select(PaperTradeModel).where(
                        PaperTradeModel.app_user_id == app_user_id,
                        PaperTradeModel.closed_at.is_not(None),
                    )
                ).scalars()
            )
            closed_count = len(closed_trades)
            wins = sum(1 for trade in closed_trades if net_pnl_or_fallback(trade) > 0)
            gross_realized_pnl = float(sum(gross_pnl_or_fallback(trade) for trade in closed_trades))
            net_realized_pnl = float(sum(net_pnl_or_fallback(trade) for trade in closed_trades))
            return {
                "open_positions": len(open_positions),
                "total_open_notional": float(sum(position.open_notional for position in open_positions)),
                "unrealized_pnl": float(sum(position.unrealized_pnl for position in open_positions)),
                "gross_realized_pnl": gross_realized_pnl,
                "net_realized_pnl": net_realized_pnl,
                "total_commission_paid": float(sum(commission_paid_for_trade(trade) for trade in closed_trades)),
                # Back-compat alias used by existing UI/tests. From Phase 7
                # onward this represents net realized P&L after commission.
                "realized_pnl": net_realized_pnl,
                "closed_trade_count": closed_count,
                "win_rate": float((wins / closed_count) if closed_count else 0.0),
            }

    def get_open_position(self, *, app_user_id: int, symbol: str, side: str | None = None) -> PaperPositionModel | None:
        with self.session_factory() as session:
            stmt = select(PaperPositionModel).where(
                PaperPositionModel.app_user_id == app_user_id,
                PaperPositionModel.symbol == symbol,
                PaperPositionModel.status == "open",
            )
            if side is not None:
                stmt = stmt.where(PaperPositionModel.side == side)
            return session.execute(stmt).scalar_one_or_none()

    def get_position_by_id(self, *, position_id: int) -> PaperPositionModel | None:
        with self.session_factory() as session:
            return session.get(PaperPositionModel, position_id)

    def list_positions(
        self,
        *,
        app_user_id: int,
        status: str = "open",
        limit: int = 50,
    ) -> list[PaperPositionModel]:
        with self.session_factory() as session:
            stmt = select(PaperPositionModel).where(PaperPositionModel.app_user_id == app_user_id)
            if status != "all":
                stmt = stmt.where(PaperPositionModel.status == status)
            stmt = stmt.order_by(PaperPositionModel.opened_at.desc()).limit(limit)
            return list(session.execute(stmt).scalars())

    def list_trades(self, *, app_user_id: int, limit: int = 50) -> list[PaperTradeModel]:
        with self.session_factory() as session:
            stmt = (
                select(PaperTradeModel)
                .where(PaperTradeModel.app_user_id == app_user_id)
                .order_by(PaperTradeModel.closed_at.desc())
                .limit(limit)
            )
            return list(session.execute(stmt).scalars())

    def create_position(
        self,
        *,
        app_user_id: int,
        symbol: str,
        side: str,
        quantity: float,
        average_price: float,
        recommendation_id: str | None = None,
        replay_run_id: int | None = None,
        order_id: str | None = None,
    ) -> PaperPositionModel:
        with self.session_factory() as session:
            row = PaperPositionModel(
                app_user_id=app_user_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                average_price=average_price,
                open_notional=quantity * average_price,
                status="open",
                opened_qty=quantity,
                remaining_qty=quantity,
                recommendation_id=recommendation_id,
                replay_run_id=replay_run_id,
                order_id=order_id,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def upsert_position_on_fill(
        self,
        *,
        app_user_id: int,
        symbol: str,
        side: str,
        fill_qty: float,
        fill_price: float,
        recommendation_id: str | None = None,
        replay_run_id: int | None = None,
        order_id: str | None = None,
    ) -> PaperPositionModel:
        """Aggregate a new fill into an existing open (user, symbol, side) position
        with weighted-average entry price, or create a new position if none open.
        """
        with self.session_factory() as session:
            existing = session.execute(
                select(PaperPositionModel).where(
                    PaperPositionModel.app_user_id == app_user_id,
                    PaperPositionModel.symbol == symbol,
                    PaperPositionModel.side == side,
                    PaperPositionModel.status == "open",
                )
            ).scalar_one_or_none()
            if existing is not None:
                old_remaining = float(existing.remaining_qty if existing.remaining_qty is not None else existing.quantity)
                old_avg = float(existing.average_price)
                new_remaining = old_remaining + fill_qty
                new_avg = ((old_avg * old_remaining) + (fill_price * fill_qty)) / new_remaining if new_remaining > 0 else fill_price
                existing.average_price = new_avg
                existing.quantity = new_remaining
                existing.remaining_qty = new_remaining
                existing.opened_qty = float((existing.opened_qty or old_remaining) + fill_qty)
                existing.open_notional = new_remaining * new_avg
                session.commit()
                session.refresh(existing)
                return existing
            row = PaperPositionModel(
                app_user_id=app_user_id,
                symbol=symbol,
                side=side,
                quantity=fill_qty,
                average_price=fill_price,
                open_notional=fill_qty * fill_price,
                status="open",
                opened_qty=fill_qty,
                remaining_qty=fill_qty,
                recommendation_id=recommendation_id,
                replay_run_id=replay_run_id,
                order_id=order_id,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def close_position(self, *, position_id: int, closed_at: datetime) -> None:
        with self.session_factory() as session:
            row = session.get(PaperPositionModel, position_id)
            if row is not None:
                row.status = "closed"
                row.closed_at = closed_at
                row.remaining_qty = 0.0
                row.quantity = 0.0
                session.commit()

    def get_trade_by_id(self, *, trade_id: int) -> PaperTradeModel | None:
        with self.session_factory() as session:
            return session.get(PaperTradeModel, trade_id)

    def reopen_position(self, *, position_id: int, qty: float) -> PaperPositionModel | None:
        """Restore a closed position to status='open' with remaining_qty=qty.
        Returns the updated row (None if the row no longer exists)."""
        with self.session_factory() as session:
            row = session.get(PaperPositionModel, position_id)
            if row is None:
                return None
            row.status = "open"
            row.closed_at = None
            row.remaining_qty = qty
            row.quantity = qty
            session.commit()
            session.refresh(row)
            return row

    def delete_trade(self, *, trade_id: int) -> bool:
        """Hard-delete a trade row (used by the reopen-position undo path).
        Returns True if a row was removed."""
        with self.session_factory() as session:
            row = session.get(PaperTradeModel, trade_id)
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True

    def create_trade(
        self,
        *,
        app_user_id: int,
        symbol: str,
        side: str,
        entry_price: float,
        exit_price: float,
        quantity: float,
        gross_pnl: float,
        net_pnl: float,
        realized_pnl: float,
        opened_at: datetime,
        closed_at: datetime,
        position_id: int | None = None,
        hold_seconds: int | None = None,
        recommendation_id: str | None = None,
        replay_run_id: int | None = None,
        order_id: str | None = None,
        close_reason: str | None = None,
    ) -> PaperTradeModel:
        with self.session_factory() as session:
            row = PaperTradeModel(
                app_user_id=app_user_id,
                symbol=symbol,
                side=side,
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=quantity,
                gross_pnl=gross_pnl,
                net_pnl=net_pnl,
                realized_pnl=realized_pnl,
                opened_at=opened_at,
                closed_at=closed_at,
                position_id=position_id,
                hold_seconds=hold_seconds,
                recommendation_id=recommendation_id,
                replay_run_id=replay_run_id,
                order_id=order_id,
                close_reason=close_reason,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row


class OptionPaperRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def create_order(
        self,
        *,
        app_user_id: int,
        structure: OptionPaperStructureInput,
        status: str = "created",
        notes: str = "",
    ) -> OptionPaperOrderRecord:
        prepared = prepare_option_paper_structure(structure)
        with self.session_factory() as session:
            row = PaperOptionOrderModel(
                app_user_id=app_user_id,
                underlying_symbol=prepared.underlying_symbol,
                structure_type=prepared.structure_type,
                status=status,
                expiration=prepared.expiration,
                net_debit=prepared.net_debit,
                net_credit=prepared.net_credit,
                max_profit=prepared.max_profit,
                max_loss=prepared.max_loss,
                breakevens=list(prepared.breakevens),
                execution_enabled=False,
                notes=notes or (structure.notes or ""),
            )
            session.add(row)
            session.flush()
            for leg in prepared.legs:
                session.add(
                    PaperOptionOrderLegModel(
                        option_order_id=row.id,
                        action=leg.action,
                        right=leg.right,
                        strike=leg.strike,
                        expiration=leg.expiration,
                        quantity=leg.quantity,
                        multiplier=leg.multiplier,
                        premium=leg.premium,
                        leg_status=status,
                        label=leg.label,
                    )
                )
            session.commit()
            session.refresh(row)
            return self._get_order_record(session, row.id)

    def get_order(
        self,
        *,
        order_id: int,
        app_user_id: int | None = None,
    ) -> OptionPaperOrderRecord | None:
        with self.session_factory() as session:
            stmt = select(PaperOptionOrderModel).where(PaperOptionOrderModel.id == order_id)
            if app_user_id is not None:
                stmt = stmt.where(PaperOptionOrderModel.app_user_id == app_user_id)
            row = session.execute(stmt).scalar_one_or_none()
            if row is None:
                return None
            return self._serialize_order_record(session, row)

    def create_position(
        self,
        *,
        app_user_id: int,
        structure: OptionPaperStructureInput,
        status: str = "open",
        source_order_id: int | None = None,
    ) -> OptionPaperPositionRecord:
        prepared = prepare_option_paper_structure(structure)
        with self.session_factory() as session:
            row = PaperOptionPositionModel(
                app_user_id=app_user_id,
                underlying_symbol=prepared.underlying_symbol,
                structure_type=prepared.structure_type,
                status=status,
                expiration=prepared.expiration,
                opening_net_debit=prepared.net_debit,
                opening_net_credit=prepared.net_credit,
                max_profit=prepared.max_profit,
                max_loss=prepared.max_loss,
                breakevens=list(prepared.breakevens),
                source_order_id=source_order_id,
            )
            session.add(row)
            session.flush()
            for leg in prepared.legs:
                session.add(
                    PaperOptionPositionLegModel(
                        position_id=row.id,
                        action=leg.action,
                        right=leg.right,
                        strike=leg.strike,
                        expiration=leg.expiration,
                        quantity=leg.quantity,
                        multiplier=leg.multiplier,
                        entry_premium=leg.premium,
                        status=status,
                        label=leg.label,
                    )
                )
            session.commit()
            session.refresh(row)
            return self._get_position_record(session, row.id)

    def list_open_positions(
        self,
        *,
        app_user_id: int,
        underlying_symbol: str | None = None,
        limit: int = 50,
    ) -> list[OptionPaperPositionRecord]:
        with self.session_factory() as session:
            stmt = select(PaperOptionPositionModel).where(
                PaperOptionPositionModel.app_user_id == app_user_id,
                PaperOptionPositionModel.status == "open",
            )
            if underlying_symbol:
                stmt = stmt.where(
                    PaperOptionPositionModel.underlying_symbol == underlying_symbol.upper().strip()
                )
            rows = list(
                session.execute(
                    stmt.order_by(PaperOptionPositionModel.opened_at.desc()).limit(limit)
                ).scalars()
            )
            return [self._serialize_position_record(session, row) for row in rows]

    def get_position(
        self,
        *,
        position_id: int,
        app_user_id: int | None = None,
    ) -> OptionPaperPositionRecord | None:
        with self.session_factory() as session:
            stmt = select(PaperOptionPositionModel).where(PaperOptionPositionModel.id == position_id)
            if app_user_id is not None:
                stmt = stmt.where(PaperOptionPositionModel.app_user_id == app_user_id)
            row = session.execute(stmt).scalar_one_or_none()
            if row is None:
                return None
            return self._serialize_position_record(session, row)

    def create_trade(
        self,
        *,
        app_user_id: int,
        structure: OptionPaperStructureInput,
        position_id: int | None = None,
        gross_pnl: float | None = None,
        total_commissions: float | None = None,
        net_pnl: float | None = None,
        settlement_mode: str | None = None,
        notes: str = "",
    ) -> OptionPaperTradeRecord:
        prepared = prepare_option_paper_structure(structure)
        with self.session_factory() as session:
            row = PaperOptionTradeModel(
                app_user_id=app_user_id,
                position_id=position_id,
                structure_type=prepared.structure_type,
                underlying_symbol=prepared.underlying_symbol,
                expiration=prepared.expiration,
                gross_pnl=gross_pnl,
                total_commissions=total_commissions,
                net_pnl=net_pnl,
                settlement_mode=settlement_mode,
                notes=notes or (structure.notes or ""),
            )
            session.add(row)
            session.flush()
            for leg in prepared.legs:
                session.add(
                    PaperOptionTradeLegModel(
                        trade_id=row.id,
                        action=leg.action,
                        right=leg.right,
                        strike=leg.strike,
                        expiration=leg.expiration,
                        quantity=leg.quantity,
                        multiplier=leg.multiplier,
                        entry_premium=leg.premium,
                        label=leg.label,
                    )
                )
            session.commit()
            session.refresh(row)
            return self._get_trade_record(session, row.id)

    def list_trades(self, *, app_user_id: int, limit: int = 50) -> list[OptionPaperTradeRecord]:
        with self.session_factory() as session:
            rows = list(
                session.execute(
                    select(PaperOptionTradeModel)
                    .where(PaperOptionTradeModel.app_user_id == app_user_id)
                    .order_by(
                        func.coalesce(
                            PaperOptionTradeModel.closed_at,
                            PaperOptionTradeModel.opened_at,
                        ).desc()
                    )
                    .limit(limit)
                ).scalars()
            )
            return [self._serialize_trade_record(session, row) for row in rows]

    def _get_order_record(self, session: Session, order_id: int) -> OptionPaperOrderRecord:
        row = session.get(PaperOptionOrderModel, order_id)
        assert row is not None
        return self._serialize_order_record(session, row)

    def _serialize_order_record(
        self,
        session: Session,
        row: PaperOptionOrderModel,
    ) -> OptionPaperOrderRecord:
        legs = list(
            session.execute(
                select(PaperOptionOrderLegModel)
                .where(PaperOptionOrderLegModel.option_order_id == row.id)
                .order_by(PaperOptionOrderLegModel.id.asc())
            ).scalars()
        )
        return OptionPaperOrderRecord(
            id=row.id,
            app_user_id=row.app_user_id,
            underlying_symbol=row.underlying_symbol,
            structure_type=row.structure_type,
            status=row.status,
            expiration=row.expiration,
            net_debit=row.net_debit,
            net_credit=row.net_credit,
            max_profit=row.max_profit,
            max_loss=row.max_loss,
            breakevens=list(row.breakevens or []),
            execution_enabled=bool(row.execution_enabled),
            notes=row.notes or "",
            created_at=row.created_at,
            legs=[
                OptionPaperOrderLegRecord(
                    id=leg.id,
                    option_order_id=leg.option_order_id,
                    action=leg.action,
                    right=leg.right,
                    strike=leg.strike,
                    expiration=leg.expiration,
                    quantity=leg.quantity,
                    multiplier=leg.multiplier,
                    premium=leg.premium,
                    leg_status=leg.leg_status,
                    label=leg.label,
                )
                for leg in legs
            ],
        )

    def _get_position_record(self, session: Session, position_id: int) -> OptionPaperPositionRecord:
        row = session.get(PaperOptionPositionModel, position_id)
        assert row is not None
        return self._serialize_position_record(session, row)

    def _serialize_position_record(
        self,
        session: Session,
        row: PaperOptionPositionModel,
    ) -> OptionPaperPositionRecord:
        legs = list(
            session.execute(
                select(PaperOptionPositionLegModel)
                .where(PaperOptionPositionLegModel.position_id == row.id)
                .order_by(PaperOptionPositionLegModel.id.asc())
            ).scalars()
        )
        return OptionPaperPositionRecord(
            id=row.id,
            app_user_id=row.app_user_id,
            underlying_symbol=row.underlying_symbol,
            structure_type=row.structure_type,
            status=row.status,
            expiration=row.expiration,
            opened_at=row.opened_at,
            closed_at=row.closed_at,
            opening_net_debit=row.opening_net_debit,
            opening_net_credit=row.opening_net_credit,
            max_profit=row.max_profit,
            max_loss=row.max_loss,
            breakevens=list(row.breakevens or []),
            source_order_id=row.source_order_id,
            legs=[
                OptionPaperPositionLegRecord(
                    id=leg.id,
                    position_id=leg.position_id,
                    action=leg.action,
                    right=leg.right,
                    strike=leg.strike,
                    expiration=leg.expiration,
                    quantity=leg.quantity,
                    multiplier=leg.multiplier,
                    entry_premium=leg.entry_premium,
                    exit_premium=leg.exit_premium,
                    status=leg.status,
                    label=leg.label,
                )
                for leg in legs
            ],
        )

    def _get_trade_record(self, session: Session, trade_id: int) -> OptionPaperTradeRecord:
        row = session.get(PaperOptionTradeModel, trade_id)
        assert row is not None
        return self._serialize_trade_record(session, row)

    def _serialize_trade_record(
        self,
        session: Session,
        row: PaperOptionTradeModel,
    ) -> OptionPaperTradeRecord:
        legs = list(
            session.execute(
                select(PaperOptionTradeLegModel)
                .where(PaperOptionTradeLegModel.trade_id == row.id)
                .order_by(PaperOptionTradeLegModel.id.asc())
            ).scalars()
        )
        return OptionPaperTradeRecord(
            id=row.id,
            app_user_id=row.app_user_id,
            position_id=row.position_id,
            structure_type=row.structure_type,
            underlying_symbol=row.underlying_symbol,
            expiration=row.expiration,
            opened_at=row.opened_at,
            closed_at=row.closed_at,
            gross_pnl=row.gross_pnl,
            total_commissions=row.total_commissions,
            net_pnl=row.net_pnl,
            settlement_mode=row.settlement_mode,
            notes=row.notes or "",
            legs=[
                OptionPaperTradeLegRecord(
                    id=leg.id,
                    trade_id=leg.trade_id,
                    action=leg.action,
                    right=leg.right,
                    strike=leg.strike,
                    expiration=leg.expiration,
                    quantity=leg.quantity,
                    multiplier=leg.multiplier,
                    entry_premium=leg.entry_premium,
                    exit_premium=leg.exit_premium,
                    leg_gross_pnl=leg.leg_gross_pnl,
                    leg_commission=leg.leg_commission,
                    leg_net_pnl=leg.leg_net_pnl,
                    label=leg.label,
                )
                for leg in legs
            ],
        )


class UserRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    @staticmethod
    def _normalize_identity(value: str) -> str:
        normalized = value.strip()
        if normalized.startswith("{{") and normalized.endswith("}}"):
            return ""
        return normalized

    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return cls._normalize_identity(value).lower()

    @classmethod
    def _invite_external_id_for_email(cls, email: str) -> str:
        normalized_email = cls._normalize_email(email)
        return f"invited::{normalized_email}" if normalized_email else ""

    @staticmethod
    def _approval_rank(status: str) -> int:
        if status == ApprovalStatus.APPROVED.value:
            return 2
        if status == ApprovalStatus.PENDING.value:
            return 1
        return 0

    @staticmethod
    def _role_rank(role: str) -> int:
        if role == AppRole.ADMIN.value:
            return 1
        return 0

    @classmethod
    def _is_placeholder_display_name(cls, value: str, *, email: str) -> bool:
        normalized = cls._normalize_identity(value).lower()
        if not normalized:
            return True
        email_local = email.split("@", 1)[0] if "@" in email else email
        return normalized in {"identity pending", "pending", "unknown", "user", email_local.lower()}

    def _select_canonical_user(
        self,
        *,
        candidates: list[AppUserModel],
        external_auth_user_id: str,
        normalized_email: str,
    ) -> AppUserModel:
        invite_external_id = self._invite_external_id_for_email(normalized_email)

        def _priority(user: AppUserModel) -> tuple[int, int, int]:
            if normalized_email and user.email == normalized_email:
                id_priority = 0
            elif user.external_auth_user_id == external_auth_user_id:
                id_priority = 1
            elif invite_external_id and user.external_auth_user_id == invite_external_id:
                id_priority = 2
            else:
                id_priority = 3
            auth_priority = -self._approval_rank(user.approval_status) - self._role_rank(user.app_role)
            return (id_priority, auth_priority, user.id)

        return min(candidates, key=_priority)

    def _merge_users(
        self,
        *,
        session: Session,
        candidates: list[AppUserModel],
        external_auth_user_id: str,
        normalized_email: str,
        normalized_display_name: str,
        mfa_enabled: bool,
    ) -> AppUserModel:
        canonical = self._select_canonical_user(
            candidates=candidates,
            external_auth_user_id=external_auth_user_id,
            normalized_email=normalized_email,
        )
        duplicates = [row for row in candidates if row.id != canonical.id]

        for duplicate in duplicates:
            if duplicate.external_auth_user_id == external_auth_user_id:
                duplicate.external_auth_user_id = f"retired::{duplicate.id}::{uuid4().hex[:8]}"
            if normalized_email and duplicate.email == normalized_email:
                duplicate.email = f"retired+{duplicate.id}+{normalized_email}"

        session.flush()

        canonical.external_auth_user_id = external_auth_user_id
        if normalized_email:
            canonical.email = normalized_email

        approved_row = max(candidates, key=lambda row: self._approval_rank(row.approval_status))
        canonical.approval_status = approved_row.approval_status
        canonical.approved_at = approved_row.approved_at
        canonical.approved_by = approved_row.approved_by

        role_row = max(candidates, key=lambda row: self._role_rank(row.app_role))
        canonical.app_role = role_row.app_role

        canonical.mfa_enabled = any(row.mfa_enabled for row in candidates) or mfa_enabled

        if normalized_display_name:
            canonical.display_name = normalized_display_name
        else:
            preferred_name = next(
                (
                    row.display_name
                    for row in candidates
                    if not self._is_placeholder_display_name(row.display_name, email=normalized_email or row.email)
                ),
                "",
            )
            if preferred_name:
                canonical.display_name = preferred_name
            elif normalized_email:
                canonical.display_name = normalized_email.split("@")[0]

        for duplicate in duplicates:
            session.query(UserApprovalRequestModel).filter(UserApprovalRequestModel.app_user_id == duplicate.id).update(
                {UserApprovalRequestModel.app_user_id: canonical.id}
            )
            session.query(WatchlistModel).filter(WatchlistModel.app_user_id == duplicate.id).update(
                {WatchlistModel.app_user_id: canonical.id}
            )
            session.query(StrategyReportScheduleModel).filter(StrategyReportScheduleModel.app_user_id == duplicate.id).update(
                {StrategyReportScheduleModel.app_user_id: canonical.id}
            )
            session.query(EmailDeliveryLogModel).filter(EmailDeliveryLogModel.app_user_id == duplicate.id).update(
                {EmailDeliveryLogModel.app_user_id: canonical.id}
            )
            session.delete(duplicate)

        session.flush()
        return canonical

    def reconcile_identity_duplicates(self, *, external_auth_user_id: str, email: str) -> AppUserModel | None:
        normalized_email = self._normalize_email(email)
        if not external_auth_user_id.strip() and not normalized_email:
            return None
        invite_external_id = self._invite_external_id_for_email(normalized_email)
        with self.session_factory() as session:
            clauses = [AppUserModel.external_auth_user_id == external_auth_user_id.strip()]
            if normalized_email:
                clauses.append(AppUserModel.email == normalized_email)
            if invite_external_id:
                clauses.append(AppUserModel.external_auth_user_id == invite_external_id)
            candidates = list(session.execute(select(AppUserModel).where(or_(*clauses))).scalars())
            if not candidates:
                return None
            merged = self._merge_users(
                session=session,
                candidates=candidates,
                external_auth_user_id=external_auth_user_id.strip(),
                normalized_email=normalized_email,
                normalized_display_name="",
                mfa_enabled=False,
            )
            session.commit()
            session.refresh(merged)
            return merged

    def reconcile_all_duplicate_users(self) -> int:
        merged_count = 0
        with self.session_factory() as session:
            users = list(session.execute(select(AppUserModel)).scalars())
            by_email: dict[str, list[AppUserModel]] = {}
            for user in users:
                normalized_email = self._normalize_email(user.email)
                if not normalized_email:
                    continue
                by_email.setdefault(normalized_email, []).append(user)
            for email, rows in by_email.items():
                if len(rows) < 2:
                    continue
                canonical_external_id = next(
                    (row.external_auth_user_id for row in rows if not row.external_auth_user_id.startswith("invited::")),
                    rows[0].external_auth_user_id,
                )
                self._merge_users(
                    session=session,
                    candidates=rows,
                    external_auth_user_id=canonical_external_id,
                    normalized_email=email,
                    normalized_display_name="",
                    mfa_enabled=any(row.mfa_enabled for row in rows),
                )
                merged_count += len(rows) - 1
            session.commit()
        return merged_count

    def upsert_from_auth(
        self,
        external_auth_user_id: str,
        email: str,
        display_name: str,
        mfa_enabled: bool = False,
    ) -> AppUserModel:
        with self.session_factory() as session:
            normalized_email = self._normalize_email(email)
            normalized_display_name = self._normalize_identity(display_name)
            invite_external_id = self._invite_external_id_for_email(normalized_email)
            lookup_filters = [AppUserModel.external_auth_user_id == external_auth_user_id]
            if normalized_email:
                lookup_filters.append(AppUserModel.email == normalized_email)
            if invite_external_id:
                lookup_filters.append(AppUserModel.external_auth_user_id == invite_external_id)

            users = list(session.execute(select(AppUserModel).where(or_(*lookup_filters))).scalars())
            if not users and not normalized_email:
                raise ValueError("email required to create local app user")

            if not users:
                safe_display_name = normalized_display_name if normalized_display_name else normalized_email.split("@")[0]
                user = AppUserModel(
                    external_auth_user_id=external_auth_user_id,
                    email=normalized_email,
                    display_name=safe_display_name,
                    approval_status=ApprovalStatus.PENDING.value,
                    app_role=AppRole.USER.value,
                    mfa_enabled=mfa_enabled,
                )
                session.add(user)
                session.flush()
                session.add(UserApprovalRequestModel(app_user_id=user.id, status=ApprovalStatus.PENDING.value, note="signup"))
            else:
                user = self._merge_users(
                    session=session,
                    candidates=users,
                    external_auth_user_id=external_auth_user_id,
                    normalized_email=normalized_email,
                    normalized_display_name=normalized_display_name,
                    mfa_enabled=mfa_enabled,
                )
            session.commit()
            session.refresh(user)
            return user

    def touch_last_seen(self, user_id: int) -> AppUserModel:
        from macmarket_trader.domain.time import utc_now

        with self.session_factory() as session:
            user = session.get(AppUserModel, user_id)
            if user is None:
                raise ValueError("User not found")
            now = utc_now()
            user.last_seen_at = now
            user.last_authenticated_at = now
            session.commit()
            session.refresh(user)
            return user

    def create_or_update_invited_pending_user(self, *, email: str, display_name: str | None) -> AppUserModel:
        normalized_email = email.strip().lower()
        if not normalized_email:
            raise ValueError("email required for invite")
        safe_display_name = (display_name or "").strip() or normalized_email.split("@")[0]
        invite_external_id = f"invited::{normalized_email}"
        with self.session_factory() as session:
            user = session.execute(select(AppUserModel).where(AppUserModel.email == normalized_email)).scalar_one_or_none()
            if user is None:
                user = AppUserModel(
                    external_auth_user_id=invite_external_id,
                    email=normalized_email,
                    display_name=safe_display_name,
                    approval_status=ApprovalStatus.PENDING.value,
                    app_role=AppRole.USER.value,
                    mfa_enabled=False,
                )
                session.add(user)
                session.flush()
                session.add(UserApprovalRequestModel(app_user_id=user.id, status=ApprovalStatus.PENDING.value, note="invite"))
            else:
                user.display_name = safe_display_name or user.display_name
            session.commit()
            session.refresh(user)
            return user

    def get_by_external_id(self, external_auth_user_id: str) -> AppUserModel | None:
        with self.session_factory() as session:
            return session.execute(
                select(AppUserModel).where(AppUserModel.external_auth_user_id == external_auth_user_id)
            ).scalar_one_or_none()

    def list_by_status(self, status: ApprovalStatus) -> list[AppUserModel]:
        with self.session_factory() as session:
            return list(session.execute(select(AppUserModel).where(AppUserModel.approval_status == status.value)).scalars())

    def list_recent_users(self, limit: int = 200) -> list[AppUserModel]:
        with self.session_factory() as session:
            stmt = select(AppUserModel).order_by(AppUserModel.created_at.desc()).limit(limit)
            return list(session.execute(stmt).scalars())

    def list_recent_approval_requests(self, limit: int = 10) -> list[UserApprovalRequestModel]:
        with self.session_factory() as session:
            stmt = select(UserApprovalRequestModel).order_by(UserApprovalRequestModel.created_at.desc()).limit(limit)
            return list(session.execute(stmt).scalars())

    def get_by_id(self, user_id: int) -> AppUserModel | None:
        with self.session_factory() as session:
            return session.get(AppUserModel, user_id)

    def delete_user(self, user_id: int) -> bool:
        with self.session_factory() as session:
            user = session.get(AppUserModel, user_id)
            if user is None:
                return False
            session.delete(user)
            session.commit()
            return True

    def set_app_role(self, *, user_id: int, role: str) -> AppUserModel:
        with self.session_factory() as session:
            user = session.get(AppUserModel, user_id)
            if user is None:
                raise ValueError("User not found")
            user.app_role = role
            session.commit()
            session.refresh(user)
            return user

    def set_approval_status(self, *, user_id: int, status: ApprovalStatus, approved_by: str, note: str) -> AppUserModel:
        from macmarket_trader.domain.time import utc_now

        with self.session_factory() as session:
            user = session.get(AppUserModel, user_id)
            if user is None:
                raise ValueError("User not found")
            user.approval_status = status.value
            user.approved_by = approved_by
            user.approved_at = utc_now() if status == ApprovalStatus.APPROVED else None
            session.add(UserApprovalRequestModel(app_user_id=user.id, status=status.value, note=note))
            session.commit()
            session.refresh(user)
            return user

    def set_risk_dollars_per_trade(self, user_id: int, *, value: float | None) -> AppUserModel:
        """Pass 4 — set or clear the per-user risk-dollars override. Pass
        `value=None` to clear and fall back to settings.risk_dollars_per_trade."""
        with self.session_factory() as session:
            user = session.get(AppUserModel, user_id)
            if user is None:
                raise ValueError("User not found")
            user.risk_dollars_per_trade = value
            session.commit()
            session.refresh(user)
            return user

    def set_commission_per_trade(self, user_id: int, *, value: float | None) -> AppUserModel:
        with self.session_factory() as session:
            user = session.get(AppUserModel, user_id)
            if user is None:
                raise ValueError("User not found")
            user.commission_per_trade = value
            session.commit()
            session.refresh(user)
            return user

    def set_commission_per_contract(self, user_id: int, *, value: float | None) -> AppUserModel:
        with self.session_factory() as session:
            user = session.get(AppUserModel, user_id)
            if user is None:
                raise ValueError("User not found")
            user.commission_per_contract = value
            session.commit()
            session.refresh(user)
            return user


class EmailLogRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def create(self, app_user_id: int | None, template_name: str, destination: str, status: str, provider_message_id: str | None = None) -> EmailDeliveryLogModel:
        with self.session_factory() as session:
            row = EmailDeliveryLogModel(
                app_user_id=app_user_id,
                template_name=template_name,
                destination=destination,
                status=status,
                provider_message_id=provider_message_id,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def list_recent(self, limit: int = 10) -> list[EmailDeliveryLogModel]:
        with self.session_factory() as session:
            stmt = select(EmailDeliveryLogModel).order_by(EmailDeliveryLogModel.sent_at.desc()).limit(limit)
            return list(session.execute(stmt).scalars())


class InviteRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def create(self, *, email: str, display_name: str | None, invited_by: str) -> AppInviteModel:
        with self.session_factory() as session:
            row = AppInviteModel(
                email=email.strip().lower(),
                display_name=(display_name or "").strip(),
                invite_token=f"invite_{uuid4().hex[:24]}",
                status="sent",
                invited_by=invited_by.strip().lower(),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def get_by_id(self, invite_id: int) -> AppInviteModel | None:
        with self.session_factory() as session:
            return session.get(AppInviteModel, invite_id)

    def list_recent(self, limit: int = 100) -> list[AppInviteModel]:
        with self.session_factory() as session:
            stmt = select(AppInviteModel).order_by(AppInviteModel.created_at.desc()).limit(limit)
            return list(session.execute(stmt).scalars())

    def delete(self, invite_id: int) -> bool:
        with self.session_factory() as session:
            row = session.get(AppInviteModel, invite_id)
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True

    def update_sent_at(self, invite_id: int) -> AppInviteModel | None:
        from macmarket_trader.domain.time import utc_now

        with self.session_factory() as session:
            row = session.get(AppInviteModel, invite_id)
            if row is None:
                return None
            row.sent_at = utc_now()
            session.commit()
            session.refresh(row)
            return row


class DailyBarRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def list_for_symbol(self, symbol: str, lookback_days: int = 180) -> list[DailyBarModel]:
        since = datetime.now(tz=timezone.utc) - timedelta(days=lookback_days)
        with self.session_factory() as session:
            stmt = (
                select(DailyBarModel)
                .where(DailyBarModel.symbol == symbol.upper(), DailyBarModel.bar_date >= since)
                .order_by(DailyBarModel.bar_date.asc())
            )
            return list(session.execute(stmt).scalars())

class ProviderHealthRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def create(self, *, provider: str, status: str, details: str) -> ProviderHealthModel:
        with self.session_factory() as session:
            row = ProviderHealthModel(provider=provider, status=status, details=details)
            session.add(row)
            session.commit()
            session.refresh(row)
            return row


class DashboardRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def summary_counts(self) -> dict[str, int]:
        with self.session_factory() as session:
            return {
                "recommendations": int(session.scalar(select(func.count(RecommendationModel.id))) or 0),
                "replay_runs": int(session.scalar(select(func.count(ReplayRunModel.id))) or 0),
                "orders": int(session.scalar(select(func.count(OrderModel.id))) or 0),
                "fills": int(session.scalar(select(func.count(FillModel.id))) or 0),
            }


class WatchlistRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def list_for_user(self, app_user_id: int) -> list[WatchlistModel]:
        with self.session_factory() as session:
            stmt = select(WatchlistModel).where(WatchlistModel.app_user_id == app_user_id).order_by(WatchlistModel.created_at.desc())
            return list(session.execute(stmt).scalars())

    def upsert(self, *, app_user_id: int, name: str, symbols: list[str]) -> WatchlistModel:
        with self.session_factory() as session:
            row = session.execute(
                select(WatchlistModel).where(WatchlistModel.app_user_id == app_user_id, WatchlistModel.name == name)
            ).scalar_one_or_none()
            if row is None:
                row = WatchlistModel(app_user_id=app_user_id, name=name, symbols=symbols)
                session.add(row)
            else:
                row.symbols = symbols
            session.commit()
            session.refresh(row)
            return row

    def update(self, *, watchlist_id: int, app_user_id: int, name: str | None, symbols: list[str] | None) -> WatchlistModel | None:
        with self.session_factory() as session:
            row = session.execute(
                select(WatchlistModel).where(WatchlistModel.id == watchlist_id, WatchlistModel.app_user_id == app_user_id)
            ).scalar_one_or_none()
            if row is None:
                return None
            if name is not None:
                row.name = name
            if symbols is not None:
                row.symbols = symbols
            session.commit()
            session.refresh(row)
            return row

    def delete(self, *, watchlist_id: int, app_user_id: int) -> bool:
        with self.session_factory() as session:
            row = session.execute(
                select(WatchlistModel).where(WatchlistModel.id == watchlist_id, WatchlistModel.app_user_id == app_user_id)
            ).scalar_one_or_none()
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True


class StrategyReportRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def create_schedule(
        self,
        *,
        app_user_id: int,
        name: str,
        frequency: str,
        run_time: str,
        timezone_name: str,
        email_target: str,
        enabled: bool,
        next_run_at: datetime,
        payload: dict[str, object],
    ) -> StrategyReportScheduleModel:
        with self.session_factory() as session:
            row = StrategyReportScheduleModel(
                app_user_id=app_user_id,
                name=name,
                frequency=frequency,
                run_time=run_time,
                timezone=timezone_name,
                email_target=email_target,
                enabled=enabled,
                next_run_at=next_run_at,
                payload=payload,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def update_schedule(self, schedule_id: int, *, app_user_id: int, updates: dict[str, object]) -> StrategyReportScheduleModel | None:
        with self.session_factory() as session:
            row = session.execute(
                select(StrategyReportScheduleModel).where(
                    StrategyReportScheduleModel.id == schedule_id,
                    StrategyReportScheduleModel.app_user_id == app_user_id,
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            for key, value in updates.items():
                setattr(row, key, value)
            session.commit()
            session.refresh(row)
            return row

    def list_schedules_for_user(self, app_user_id: int) -> list[StrategyReportScheduleModel]:
        with self.session_factory() as session:
            stmt = select(StrategyReportScheduleModel).where(StrategyReportScheduleModel.app_user_id == app_user_id).order_by(StrategyReportScheduleModel.created_at.desc())
            return list(session.execute(stmt).scalars())

    def get_schedule(self, schedule_id: int) -> StrategyReportScheduleModel | None:
        with self.session_factory() as session:
            return session.get(StrategyReportScheduleModel, schedule_id)

    def list_due_schedules(self, *, now: datetime) -> list[StrategyReportScheduleModel]:
        with self.session_factory() as session:
            stmt = select(StrategyReportScheduleModel).where(
                StrategyReportScheduleModel.enabled.is_(True),
                StrategyReportScheduleModel.next_run_at.is_not(None),
                StrategyReportScheduleModel.next_run_at <= now,
            )
            return list(session.execute(stmt).scalars())

    def create_run(self, *, schedule_id: int, status: str, payload: dict[str, object], delivered_to: str) -> StrategyReportRunModel:
        with self.session_factory() as session:
            row = StrategyReportRunModel(schedule_id=schedule_id, status=status, payload=payload, delivered_to=delivered_to)
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def list_runs(self, *, schedule_id: int, limit: int = 20) -> list[StrategyReportRunModel]:
        with self.session_factory() as session:
            stmt = select(StrategyReportRunModel).where(StrategyReportRunModel.schedule_id == schedule_id).order_by(StrategyReportRunModel.created_at.desc()).limit(limit)
            return list(session.execute(stmt).scalars())

    def list_recent_runs_all(self, limit: int = 10) -> list[StrategyReportRunModel]:
        with self.session_factory() as session:
            stmt = select(StrategyReportRunModel).order_by(StrategyReportRunModel.created_at.desc()).limit(limit)
            return list(session.execute(stmt).scalars())

    def get_run(self, *, run_id: int, schedule_id: int) -> StrategyReportRunModel | None:
        with self.session_factory() as session:
            return session.execute(
                select(StrategyReportRunModel).where(
                    StrategyReportRunModel.id == run_id,
                    StrategyReportRunModel.schedule_id == schedule_id,
                )
            ).scalar_one_or_none()

    def mark_schedule_run(self, *, schedule_id: int, status: str, next_run_at: datetime, latest_run_id: int) -> None:
        with self.session_factory() as session:
            row = session.get(StrategyReportScheduleModel, schedule_id)
            if row is None:
                return
            row.latest_status = status
            row.latest_run_at = datetime.now(timezone.utc)
            row.next_run_at = next_run_at
            row.latest_run_id = latest_run_id
            session.commit()
