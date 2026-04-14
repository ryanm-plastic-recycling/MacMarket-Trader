from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from macmarket_trader.config import settings as _app_settings
from macmarket_trader.data.providers.base import EmailMessage, EmailProvider
from macmarket_trader.data.providers.registry import build_market_data_service
from macmarket_trader.domain.enums import MarketMode
from macmarket_trader.email_templates import render_strategy_report_html, render_strategy_report_text
from macmarket_trader.ranking_engine import DeterministicRankingEngine
from macmarket_trader.strategy_registry import list_strategies
from macmarket_trader.storage.repositories import (
    EmailLogRepository,
    StrategyReportRepository,
)


class StrategyReportService:
    def __init__(
        self,
        *,
        report_repo: StrategyReportRepository,
        email_provider: EmailProvider,
        email_log_repo: EmailLogRepository,
    ) -> None:
        self.report_repo = report_repo
        self.email_provider = email_provider
        self.email_log_repo = email_log_repo
        self.market_data_service = build_market_data_service()
        self.ranking_engine = DeterministicRankingEngine()

    @staticmethod
    def _next_run_at(*, now: datetime, frequency: str, run_time: str, timezone_name: str) -> datetime:
        tz = ZoneInfo(timezone_name)
        local_now = now.astimezone(tz)
        hour, minute = [int(part) for part in run_time.split(":", 1)]
        candidate = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        weekdays = {"weekdays"}
        if frequency in weekdays:
            while candidate.weekday() >= 5 or candidate <= local_now:
                candidate = candidate + timedelta(days=1)
                candidate = candidate.replace(hour=hour, minute=minute, second=0, microsecond=0)
        elif frequency == "weekly":
            while candidate.weekday() != 0 or candidate <= local_now:
                candidate = candidate + timedelta(days=1)
                candidate = candidate.replace(hour=hour, minute=minute, second=0, microsecond=0)
        else:
            if candidate <= local_now:
                candidate = (candidate + timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0)
        return candidate.astimezone(timezone.utc)

    def run_schedule(self, schedule_id: int, *, trigger: str = "manual") -> dict[str, object]:
        schedule = self.report_repo.get_schedule(schedule_id)
        if schedule is None:
            raise ValueError("schedule not found")
        settings = dict(schedule.payload or {})
        market_mode = MarketMode(str(settings.get("market_mode") or MarketMode.EQUITIES.value))
        symbols = [str(item).upper() for item in settings.get("symbols", []) if str(item).strip()]
        strategies = [str(item) for item in settings.get("enabled_strategies", []) if str(item).strip()]
        allowed = {entry.display_name for entry in list_strategies(market_mode)}
        strategies = [strategy for strategy in strategies if strategy in allowed]
        top_n = int(settings.get("top_n", 5))
        if not symbols:
            raise ValueError("schedule requires at least one symbol")
        if not strategies:
            default_strategy = next(iter(allowed), None)
            strategies = [default_strategy] if default_strategy else []
        if not strategies:
            raise ValueError("no runnable strategies configured for this market mode")

        bars_by_symbol = {}
        last_source = "provider"
        last_fallback = False
        for symbol in symbols:
            bars, source, fallback_mode = self.market_data_service.historical_bars(symbol=symbol, timeframe="1D", limit=60)
            if not bars:
                continue
            bars_by_symbol[symbol] = (bars, source, fallback_mode)
            last_source = source
            last_fallback = fallback_mode

        ranking = self.ranking_engine.rank_candidates(
            bars_by_symbol=bars_by_symbol,
            strategies=strategies,
            market_mode=market_mode,
            timeframe="1D",
            top_n=top_n,
        )

        payload = {
            "schedule_id": schedule.id,
            "trigger": trigger,
            "ran_at": datetime.now(timezone.utc).isoformat(),
            "source": f"fallback ({last_source})" if last_fallback else last_source,
            "email_provider": _app_settings.email_provider,
            "top_candidates": ranking["top_candidates"],
            "watchlist_only": ranking["watchlist_only"],
            "no_trade": ranking["no_trade"],
            "queue": ranking["queue"],
            "summary": ranking["summary"],
        }
        run_row = self.report_repo.create_run(
            schedule_id=schedule.id,
            status="sent",
            payload=payload,
            delivered_to=str(settings.get("email_delivery_target") or schedule.email_target),
        )

        target_email = str(settings.get("email_delivery_target") or schedule.email_target)
        ran_at = str(payload.get("ran_at") or datetime.now(timezone.utc).isoformat())

        # Build the subject line: "MacMarket · {name} · Apr 13 · 5 candidates"
        try:
            _ran_dt = datetime.fromisoformat(ran_at.replace("Z", "+00:00")).astimezone(timezone.utc)
            _date_label = f"{_ran_dt.strftime('%b')} {_ran_dt.day}"
        except Exception:  # noqa: BLE001
            _date_label = ran_at[:10]
        _top_count = int((payload.get("summary") or {}).get("top_candidate_count", 0))
        _count_label = f"{_top_count} candidate{'s' if _top_count != 1 else ''}"
        subject = f"MacMarket \u00b7 {schedule.name} \u00b7 {_date_label} \u00b7 {_count_label}"

        email_html = render_strategy_report_html(
            schedule_name=schedule.name,
            ran_at=ran_at,
            source=str(payload.get("source") or "fallback"),
            top_candidates=list(payload.get("top_candidates") or []),
            watchlist_only=list(payload.get("watchlist_only") or []),
            no_trade=list(payload.get("no_trade") or []),
            summary=dict(payload.get("summary") or {}),
        )
        email_text = render_strategy_report_text(
            schedule_name=schedule.name,
            ran_at=ran_at,
            source=str(payload.get("source") or "fallback"),
            top_candidates=list(payload.get("top_candidates") or []),
            watchlist_only=list(payload.get("watchlist_only") or []),
            no_trade=list(payload.get("no_trade") or []),
            summary=dict(payload.get("summary") or {}),
        )
        message_id = self.email_provider.send(
            EmailMessage(
                to_email=target_email,
                subject=subject,
                body=email_text,
                template_name="strategy_report",
                html=email_html,
            )
        )
        self.email_log_repo.create(schedule.app_user_id, "strategy_report", target_email, "sent", message_id)

        now = datetime.now(timezone.utc)
        next_run = self._next_run_at(
            now=now,
            frequency=schedule.frequency,
            run_time=schedule.run_time,
            timezone_name=schedule.timezone,
        )
        self.report_repo.mark_schedule_run(
            schedule_id=schedule.id,
            status="sent",
            next_run_at=next_run,
            latest_run_id=run_row.id,
        )
        return payload

    def run_due_schedules(self, *, now: datetime | None = None) -> list[dict[str, object]]:
        current = now or datetime.now(timezone.utc)
        schedules = self.report_repo.list_due_schedules(now=current)
        output: list[dict[str, object]] = []
        for schedule in schedules:
            output.append(self.run_schedule(schedule.id, trigger="scheduler"))
        return output
