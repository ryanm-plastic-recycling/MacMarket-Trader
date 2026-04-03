from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import mean
from zoneinfo import ZoneInfo

from macmarket_trader.data.providers.base import EmailMessage, EmailProvider
from macmarket_trader.data.providers.registry import build_market_data_service
from macmarket_trader.domain.schemas import Bar
from macmarket_trader.storage.repositories import (
    EmailLogRepository,
    StrategyReportRepository,
)


@dataclass
class RankedCandidate:
    symbol: str
    strategy: str
    source: str
    thesis: str
    trigger: str
    entry_zone: str
    invalidation: str
    targets: str
    expected_rr: float
    confidence: float
    rank: int
    quick_note: str
    status: str
    score: float


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

    @staticmethod
    def _score_symbol(symbol: str, bars: list[Bar], strategy: str) -> dict[str, float]:
        last = bars[-1]
        avg_volume = mean([bar.volume for bar in bars[-20:]]) if bars else float(last.volume)
        daily_ranges = [max(bar.high - bar.low, 0.01) for bar in bars[-14:]]
        atr = mean(daily_ranges) if daily_ranges else 1.0
        close = max(last.close, 0.01)
        rel_volatility = min(2.0, atr / close * 100)
        liquidity = min(1.0, avg_volume / 4_000_000)
        strategy_fit = 0.75 if strategy == "Event Continuation" else 0.68
        regime_fit = 0.65 + min(0.2, rel_volatility / 10)
        catalyst_quality = 0.55
        volatility_fit = min(1.0, rel_volatility / 1.5)
        spread_penalty = 0.05 if liquidity > 0.5 else 0.18
        expected_rr = round(1.2 + (strategy_fit * 1.1) + (volatility_fit * 0.35) - spread_penalty, 2)
        confidence = max(0.2, min(0.95, (strategy_fit + regime_fit + liquidity) / 3))
        score = (
            strategy_fit * 0.24
            + regime_fit * 0.18
            + catalyst_quality * 0.12
            + liquidity * 0.14
            + volatility_fit * 0.14
            + confidence * 0.10
            + min(1.0, expected_rr / 3) * 0.12
            - spread_penalty * 0.16
        )
        return {
            "strategy_fit_score": round(strategy_fit, 3),
            "regime_fit_score": round(regime_fit, 3),
            "catalyst_quality_score": round(catalyst_quality, 3),
            "liquidity_score": round(liquidity, 3),
            "volatility_suitability_score": round(volatility_fit, 3),
            "spread_slippage_penalty": round(spread_penalty, 3),
            "expected_rr": expected_rr,
            "confidence": round(confidence, 3),
            "total_score": round(score, 3),
        }

    def run_schedule(self, schedule_id: int, *, trigger: str = "manual") -> dict[str, object]:
        schedule = self.report_repo.get_schedule(schedule_id)
        if schedule is None:
            raise ValueError("schedule not found")
        settings = dict(schedule.payload or {})
        symbols = [str(item).upper() for item in settings.get("symbols", []) if str(item).strip()]
        strategies = [str(item) for item in settings.get("enabled_strategies", []) if str(item).strip()]
        top_n = int(settings.get("top_n", 5))
        if not symbols:
            raise ValueError("schedule requires at least one symbol")
        if not strategies:
            strategies = ["Event Continuation"]

        source = "provider"
        fallback = False
        candidates: list[RankedCandidate] = []
        for symbol in symbols:
            bars, data_source, fallback_mode = self.market_data_service.historical_bars(symbol=symbol, timeframe="1D", limit=60)
            if not bars:
                continue
            source = data_source
            fallback = fallback_mode
            for strategy in strategies:
                metrics = self._score_symbol(symbol, bars, strategy)
                signal_status = "top_candidate" if metrics["total_score"] >= 0.62 else "watchlist"
                if metrics["confidence"] < 0.45:
                    signal_status = "no_trade"
                candidates.append(
                    RankedCandidate(
                        symbol=symbol,
                        strategy=strategy,
                        source=(f"fallback ({data_source})" if fallback_mode else data_source),
                        thesis=f"{strategy} alignment with deterministic regime and liquidity filters.",
                        trigger="Hold above opening range high with RVOL confirmation.",
                        entry_zone=f"{bars[-1].close * 0.995:.2f} - {bars[-1].close * 1.005:.2f}",
                        invalidation=f"{bars[-1].low * 0.995:.2f}",
                        targets=f"{bars[-1].close * 1.02:.2f} / {bars[-1].close * 1.04:.2f}",
                        expected_rr=metrics["expected_rr"],
                        confidence=metrics["confidence"],
                        rank=0,
                        quick_note=f"fit={metrics['strategy_fit_score']}, liquidity={metrics['liquidity_score']}, vol={metrics['volatility_suitability_score']}",
                        status=signal_status,
                        score=metrics["total_score"],
                    )
                )

        candidates.sort(key=lambda item: item.score, reverse=True)
        for idx, item in enumerate(candidates, start=1):
            item.rank = idx

        top_candidates = [item for item in candidates if item.status == "top_candidate"][:top_n]
        watchlist = [item for item in candidates if item.status == "watchlist"]
        no_trade = [item for item in candidates if item.status == "no_trade"]

        payload = {
            "schedule_id": schedule.id,
            "trigger": trigger,
            "ran_at": datetime.now(timezone.utc).isoformat(),
            "source": f"fallback ({source})" if fallback else source,
            "top_candidates": [item.__dict__ for item in top_candidates],
            "watchlist_only": [item.__dict__ for item in watchlist],
            "no_trade": [item.__dict__ for item in no_trade],
        }
        run_row = self.report_repo.create_run(
            schedule_id=schedule.id,
            status="sent",
            payload=payload,
            delivered_to=str(settings.get("email_delivery_target") or schedule.email_target),
        )

        body = json.dumps(payload, indent=2)
        target_email = str(settings.get("email_delivery_target") or schedule.email_target)
        message_id = self.email_provider.send(
            EmailMessage(
                to_email=target_email,
                subject=f"MacMarket strategy report · {schedule.name}",
                body=body,
                template_name="strategy_report",
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
