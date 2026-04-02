"""SQLAlchemy repositories for audit and app state persistence."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from macmarket_trader.domain.enums import AppRole, ApprovalStatus
from macmarket_trader.domain.models import (
    AppUserModel,
    AuditLogModel,
    DailyBarModel,
    EmailDeliveryLogModel,
    FillModel,
    OrderModel,
    ProviderHealthModel,
    RecommendationEvidenceModel,
    RecommendationModel,
    ReplayRunModel,
    ReplayStepModel,
    UserApprovalRequestModel,
)
from macmarket_trader.domain.schemas import FillRecord, OrderRecord, PortfolioSnapshot, TradeRecommendation

SessionFactory = Callable[[], Session]


class RecommendationRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def create(self, recommendation: TradeRecommendation) -> RecommendationModel:
        payload = recommendation.model_dump(mode="json")
        with self.session_factory() as session:
            row = RecommendationModel(
                recommendation_id=recommendation.recommendation_id,
                symbol=recommendation.symbol,
                payload=payload,
            )
            session.add(row)
            session.flush()
            session.add(RecommendationEvidenceModel(recommendation_id=row.id, payload=recommendation.evidence.model_dump(mode="json")))
            session.add(AuditLogModel(recommendation_id=recommendation.recommendation_id, payload=payload))
            session.commit()
            session.refresh(row)
            return row

    def list_recent(self, limit: int = 200) -> list[RecommendationModel]:
        with self.session_factory() as session:
            stmt = select(RecommendationModel).order_by(RecommendationModel.created_at.desc()).limit(limit)
            return list(session.execute(stmt).scalars())

    def get_by_id(self, recommendation_id: int) -> RecommendationModel | None:
        with self.session_factory() as session:
            return session.get(RecommendationModel, recommendation_id)


class OrderRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def create(self, order: OrderRecord, notes: str = "") -> OrderModel:
        with self.session_factory() as session:
            row = OrderModel(
                order_id=order.order_id,
                recommendation_id=order.recommendation_id,
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

    def list_with_fills(self, limit: int = 200) -> list[dict[str, object]]:
        with self.session_factory() as session:
            orders = list(session.execute(select(OrderModel).order_by(OrderModel.created_at.desc()).limit(limit)).scalars())
            if not orders:
                return []
            fills = list(session.execute(select(FillModel)).scalars())
            fills_by_order: dict[str, list[FillModel]] = {}
            for fill in fills:
                fills_by_order.setdefault(fill.order_id, []).append(fill)

            output: list[dict[str, object]] = []
            for order in orders:
                order_fills = sorted(fills_by_order.get(order.order_id, []), key=lambda item: item.timestamp)
                output.append(
                    {
                        "order_id": order.order_id,
                        "recommendation_id": order.recommendation_id,
                        "symbol": order.symbol,
                        "status": order.status,
                        "side": order.side,
                        "shares": order.shares,
                        "limit_price": order.limit_price,
                        "created_at": order.created_at,
                        "fills": [
                            {"fill_price": fill.fill_price, "filled_shares": fill.filled_shares, "timestamp": fill.timestamp}
                            for fill in order_fills
                        ],
                    }
                )
            return output


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
        recommendation_count: int,
        approved_count: int,
        fill_count: int,
        ending_heat: float,
        ending_open_notional: float,
    ) -> ReplayRunModel:
        with self.session_factory() as session:
            row = ReplayRunModel(
                symbol=symbol,
                recommendation_count=recommendation_count,
                approved_count=approved_count,
                fill_count=fill_count,
                ending_heat=ending_heat,
                ending_open_notional=ending_open_notional,
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

    def list_runs(self, limit: int = 200) -> list[ReplayRunModel]:
        with self.session_factory() as session:
            stmt = select(ReplayRunModel).order_by(ReplayRunModel.created_at.desc()).limit(limit)
            return list(session.execute(stmt).scalars())

    def list_steps_for_run(self, replay_run_id: int) -> list[ReplayStepModel]:
        with self.session_factory() as session:
            stmt = select(ReplayStepModel).where(ReplayStepModel.replay_run_id == replay_run_id).order_by(ReplayStepModel.step_index.asc())
            return list(session.execute(stmt).scalars())


class UserRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def upsert_from_auth(
        self,
        external_auth_user_id: str,
        email: str,
        display_name: str,
        mfa_enabled: bool = False,
    ) -> AppUserModel:
        with self.session_factory() as session:
            user = session.execute(
                select(AppUserModel).where(AppUserModel.external_auth_user_id == external_auth_user_id)
            ).scalar_one_or_none()
            if user is None:
                if not email.strip():
                    raise ValueError("email required to create local app user")
                safe_display_name = display_name.strip() if display_name.strip() else email.strip().split("@")[0]
                user = AppUserModel(
                    external_auth_user_id=external_auth_user_id,
                    email=email.strip().lower(),
                    display_name=safe_display_name,
                    approval_status=ApprovalStatus.PENDING.value,
                    app_role=AppRole.USER.value,
                    mfa_enabled=mfa_enabled,
                )
                session.add(user)
                session.flush()
                session.add(UserApprovalRequestModel(app_user_id=user.id, status=ApprovalStatus.PENDING.value, note="signup"))
            else:
                # Local authorization state is authoritative. Never overwrite
                # approval/app_role from external auth claims during sync.
                if email.strip():
                    user.email = email.strip().lower()
                if display_name.strip():
                    user.display_name = display_name.strip()
                user.mfa_enabled = mfa_enabled
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
