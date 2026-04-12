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

    def get_by_recommendation_uid(self, recommendation_uid: str) -> RecommendationModel | None:
        with self.session_factory() as session:
            return session.execute(
                select(RecommendationModel).where(RecommendationModel.recommendation_id == recommendation_uid)
            ).scalar_one_or_none()

    def attach_workflow_metadata(self, recommendation_id: str, *, market_data_source: str, fallback_mode: bool) -> None:
        with self.session_factory() as session:
            row = session.execute(
                select(RecommendationModel).where(RecommendationModel.recommendation_id == recommendation_id)
            ).scalar_one_or_none()
            if row is None:
                return
            payload = dict(row.payload or {})
            workflow = dict(payload.get("workflow") or {})
            workflow.update({"market_data_source": market_data_source, "fallback_mode": fallback_mode})
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
                source = None
                fallback_mode = None
                if order.notes and "|source=" in order.notes:
                    parts = {segment.split("=", 1)[0]: segment.split("=", 1)[1] for segment in order.notes.split("|") if "=" in segment}
                    source = parts.get("source")
                    fallback_mode = parts.get("fallback") == "true"
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
                        "symbol": order.symbol,
                        "status": order.status,
                        "side": order.side,
                        "shares": order.shares,
                        "limit_price": order.limit_price,
                        "created_at": order.created_at,
                        "market_data_source": source,
                        "fallback_mode": fallback_mode,
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

    def list_recent(self, limit: int = 100) -> list[AppInviteModel]:
        with self.session_factory() as session:
            stmt = select(AppInviteModel).order_by(AppInviteModel.created_at.desc()).limit(limit)
            return list(session.execute(stmt).scalars())


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
