"""Deterministic market-risk calendar assessment.

The risk gate is deliberately provider-agnostic and paper-only. LLM layers may
explain the output, but these deterministic decisions own warning/block state.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Protocol

from macmarket_trader.config import Settings, settings
from macmarket_trader.domain.schemas import (
    Bar,
    EventEvidenceBundle,
    IndexRiskSignals,
    MarketRiskEvent,
    RiskCalendarAssessment,
    RiskGateDecision,
    SymbolRiskEvent,
)
from macmarket_trader.domain.time import utc_now
from macmarket_trader.index_risk import extract_index_risk_signals


MACRO_EVENT_TYPES = {
    "cpi",
    "pce",
    "fomc_decision",
    "fomc_press_conference",
    "nonfarm_payrolls",
    "gdp",
    "retail_sales",
    "treasury_auction",
}


class RiskCalendarProvider(Protocol):
    """Provider boundary for future macro, earnings, holiday, and news calendars."""

    def list_events(
        self,
        *,
        start: datetime,
        end: datetime,
        symbols: list[str] | None = None,
    ) -> list[MarketRiskEvent | SymbolRiskEvent]:
        ...

    def evidence_for(
        self,
        *,
        symbol: str | None,
        event_type: str,
    ) -> list[EventEvidenceBundle]:
        ...


class StaticRiskCalendarProvider:
    """Credential-free provider used by local dev and tests."""

    def __init__(
        self,
        *,
        events: list[MarketRiskEvent | SymbolRiskEvent] | None = None,
        evidence: list[EventEvidenceBundle] | None = None,
    ) -> None:
        self._events = events or []
        self._evidence = evidence or []

    def list_events(
        self,
        *,
        start: datetime,
        end: datetime,
        symbols: list[str] | None = None,
    ) -> list[MarketRiskEvent | SymbolRiskEvent]:
        requested_symbols = {symbol.upper() for symbol in symbols or []}
        output: list[MarketRiskEvent | SymbolRiskEvent] = []
        for event in self._events:
            event_end = event.ends_at or event.starts_at
            if event_end < start or event.starts_at > end:
                continue
            if isinstance(event, SymbolRiskEvent):
                if requested_symbols and event.symbol.upper() not in requested_symbols:
                    continue
            elif event.symbols and requested_symbols and not requested_symbols.intersection(
                symbol.upper() for symbol in event.symbols
            ):
                continue
            output.append(event)
        return output

    def evidence_for(
        self,
        *,
        symbol: str | None,
        event_type: str,
    ) -> list[EventEvidenceBundle]:
        requested_symbol = symbol.upper() if symbol else None
        return [
            bundle
            for bundle in self._evidence
            if bundle.event_type == event_type
            and (requested_symbol is None or bundle.symbol is None or bundle.symbol.upper() == requested_symbol)
        ]


class MarketRiskCalendarService:
    def __init__(
        self,
        provider: RiskCalendarProvider | None = None,
        cfg: Settings = settings,
    ) -> None:
        self.provider = provider or StaticRiskCalendarProvider()
        self.settings = cfg

    def assess(
        self,
        *,
        symbol: str | None = None,
        timeframe: str = "1D",
        bars: list[Bar] | None = None,
        as_of: datetime | None = None,
        event_evidence: list[EventEvidenceBundle] | None = None,
        index_context: object | None = None,
    ) -> RiskCalendarAssessment:
        now = self._aware(as_of or utc_now())
        normalized_symbol = symbol.upper() if symbol else None
        if not self.settings.risk_calendar_enabled:
            return self._assessment(
                symbol=normalized_symbol,
                timeframe=timeframe,
                decision=RiskGateDecision(
                    decision_state="normal",
                    allow_new_entries=True,
                    recommended_action="trade_normally",
                    risk_level="normal",
                    warning_summary="Risk calendar disabled by configuration.",
                    assessed_at=now,
                ),
            )

        lookback = now - timedelta(days=max(3, self.settings.earnings_block_days_before + 1))
        lookahead = now + timedelta(days=max(3, self.settings.earnings_block_days_after + 1))
        events = self.provider.list_events(
            start=lookback,
            end=lookahead,
            symbols=[normalized_symbol] if normalized_symbol else None,
        )
        market_events = [event for event in events if isinstance(event, MarketRiskEvent)]
        symbol_events = [event for event in events if isinstance(event, SymbolRiskEvent)]
        supplied_evidence = list(event_evidence or [])
        supplied_evidence.extend(
            self.provider.evidence_for(symbol=normalized_symbol, event_type="earnings")
            if normalized_symbol
            else []
        )

        active_events: list[MarketRiskEvent | SymbolRiskEvent] = []
        missing_evidence: list[str] = []
        volatility_flags = self._volatility_flags(bars or [])
        data_quality_flags = self._session_policy_flags(timeframe=timeframe, bars=bars or [])
        index_risk_signals = extract_index_risk_signals(
            index_context,
            cfg=self.settings,
            now=now,
            symbol=normalized_symbol,
        ) if index_context is not None else None
        if index_risk_signals is not None:
            data_quality_flags.extend(
                f"index:{item}" for item in index_risk_signals.data_quality_flags
            )
        decision = self._normal_decision(now)
        if data_quality_flags:
            decision = self._stronger(
                decision,
                self._session_policy_decision(flags=data_quality_flags, now=now),
            )
        if index_risk_signals is not None:
            decision = self._stronger(
                decision,
                self._index_risk_decision(signals=index_risk_signals, now=now),
            )

        for event in market_events:
            if self._event_active(event, now):
                active_events.append(event)
                if event.event_type in MACRO_EVENT_TYPES and event.impact in {"high", "extreme"}:
                    decision = self._stronger(
                        decision,
                        self._macro_decision(event=event, now=now),
                    )
                elif event.event_type in {"market_holiday", "market_half_day"}:
                    decision = self._stronger(
                        decision,
                        RiskGateDecision(
                            decision_state="no_trade" if event.event_type == "market_holiday" else "restricted",
                            allow_new_entries=event.event_type != "market_holiday",
                            requires_confirmation=event.event_type == "market_half_day",
                            recommended_action="sit_out" if event.event_type == "market_holiday" else "wait",
                            risk_level="extreme" if event.event_type == "market_holiday" else "high",
                            block_reason=f"{event.title} is active.",
                            warning_summary=f"Market calendar event active: {event.title}.",
                            active_events=[event],
                            override_allowed=event.event_type == "market_half_day",
                            override_reason_required=event.event_type == "market_half_day",
                            assessed_at=now,
                        ),
                    )
                elif event.event_type == "provider_data_issue":
                    data_quality_flags.append(event.title)
                    decision = self._stronger(
                        decision,
                        RiskGateDecision(
                            decision_state="data_quality_block",
                            allow_new_entries=False,
                            requires_confirmation=False,
                            recommended_action="sit_out",
                            risk_level="extreme",
                            block_reason="provider_data_issue",
                            warning_summary=f"Provider/data quality issue active: {event.title}.",
                            active_events=[event],
                            missing_evidence=["fresh provider-backed market data"],
                            override_allowed=False,
                            assessed_at=now,
                        ),
                    )

        if normalized_symbol and self.settings.earnings_avoidance_enabled:
            for event in symbol_events:
                if event.event_type in {"earnings", "earnings_call"} and self._inside_earnings_window(event, now):
                    active_events.append(event)
                    current_evidence = [
                        bundle
                        for bundle in supplied_evidence
                        if bundle.event_type in {"earnings", "earnings_call"}
                        and (bundle.symbol or normalized_symbol).upper() == normalized_symbol
                        and not bundle.stale
                    ]
                    if current_evidence:
                        decision = self._stronger(
                            decision,
                            RiskGateDecision(
                                decision_state="restricted",
                                allow_new_entries=True,
                                requires_confirmation=True,
                                recommended_action="event_trade_review",
                                risk_level="high",
                                warning_summary=(
                                    f"{normalized_symbol} has an earnings event; event-trade review is required."
                                ),
                                active_events=[event],
                                override_allowed=True,
                                override_reason_required=True,
                                assessed_at=now,
                            ),
                        )
                    else:
                        missing = (
                            f"{normalized_symbol} earnings evidence missing: expected-move, sector, "
                            "earnings-history, and verified context are unavailable."
                        )
                        missing_evidence.append(missing)
                        decision = self._stronger(
                            decision,
                            RiskGateDecision(
                                decision_state="requires_event_evidence",
                                allow_new_entries=False,
                                requires_confirmation=False,
                                recommended_action="event_trade_review",
                                risk_level="high",
                                block_reason="earnings_event_requires_verified_evidence",
                                warning_summary=missing,
                                active_events=[event],
                                missing_evidence=[missing],
                                override_allowed=False,
                                assessed_at=now,
                            ),
                        )

        if self.settings.high_vol_block_enabled and volatility_flags:
            decision = self._stronger(
                decision,
                RiskGateDecision(
                    decision_state="restricted",
                    allow_new_entries=True,
                    requires_confirmation=True,
                    recommended_action="reduce_size",
                    risk_level="high",
                    warning_summary="Measured volatility circuit breaker is active.",
                    active_events=[],
                    missing_evidence=["VIX data unavailable unless supplied by a provider."],
                    override_allowed=True,
                    override_reason_required=True,
                    assessed_at=now,
                ),
            )
            missing_evidence.append("VIX data unavailable unless supplied by a provider.")

        merged_decision = decision.model_copy(
            update={
                "active_events": self._dedupe_events(active_events + decision.active_events),
                "missing_evidence": sorted(set(missing_evidence + decision.missing_evidence)),
            }
        )
        return RiskCalendarAssessment(
            symbol=normalized_symbol,
            timeframe=timeframe,
            decision=RiskGateDecision.model_validate(merged_decision),
            market_events=market_events,
            symbol_events=symbol_events,
            evidence=supplied_evidence,
            volatility_flags=volatility_flags,
            data_quality_flags=sorted(set(data_quality_flags)),
            index_risk_signals=index_risk_signals,
        )

    def assert_order_allowed(
        self,
        assessment: RiskCalendarAssessment,
        *,
        confirmed: bool,
        reason: str | None,
    ) -> None:
        decision = assessment.decision
        if decision.decision_state in {"no_trade", "data_quality_block", "requires_event_evidence"}:
            raise RiskCalendarBlocked(decision.block_reason or decision.warning_summary)
        if decision.requires_confirmation:
            if not confirmed:
                raise RiskCalendarRestricted("risk_calendar_confirmation_required")
            if decision.override_reason_required and not (reason or "").strip():
                raise RiskCalendarRestricted("risk_calendar_override_reason_required")

    def _macro_decision(self, *, event: MarketRiskEvent, now: datetime) -> RiskGateDecision:
        block = (
            self.settings.risk_calendar_mode.strip().lower() == "block"
            or self.settings.risk_calendar_default_block_high_impact
        )
        return RiskGateDecision(
            decision_state="no_trade" if block else "restricted",
            allow_new_entries=not block,
            requires_confirmation=not block,
            recommended_action="sit_out" if block else "wait",
            risk_level="extreme" if event.impact == "extreme" else "high",
            block_reason=f"{event.event_type}_window_active" if block else None,
            warning_summary=f"High-impact macro event active: {event.title}.",
            active_events=[event],
            override_allowed=not block,
            override_reason_required=not block,
            assessed_at=now,
        )

    def _volatility_flags(self, bars: list[Bar]) -> list[str]:
        if len(bars) < 2:
            return []
        previous = bars[-2]
        latest = bars[-1]
        flags: list[str] = []
        if previous.close:
            gap = abs(latest.open - previous.close) / max(abs(previous.close), 0.01)
            if gap >= self.settings.high_vol_gap_threshold:
                flags.append(f"gap_{gap:.2%}_exceeds_threshold")
        if latest.open:
            intraday_range = abs(latest.high - latest.low) / max(abs(latest.open), 0.01)
            if intraday_range >= self.settings.high_vol_intraday_range_threshold:
                flags.append(f"intraday_range_{intraday_range:.2%}_exceeds_threshold")
        return flags

    def _session_policy_flags(self, *, timeframe: str, bars: list[Bar]) -> list[str]:
        if not self.settings.intraday_rth_session_required:
            return []
        if timeframe.upper() not in {"1H", "4H"} or not bars:
            return []
        if all(bar.session_policy == "regular_hours" for bar in bars):
            return []
        return ["intraday_equity_bars_not_regular_hours_normalized"]

    def _session_policy_decision(self, *, flags: list[str], now: datetime) -> RiskGateDecision:
        block = self.settings.intraday_rth_violation_mode.strip().lower() == "block"
        index_only = flags and all(flag.startswith("index:") for flag in flags)
        if index_only:
            return RiskGateDecision(
                decision_state="caution",
                allow_new_entries=True,
                requires_confirmation=False,
                recommended_action="caution",
                risk_level="elevated",
                warning_summary="Index data is stale or missing; risk context is warning-only.",
                missing_evidence=flags,
                override_allowed=False,
                assessed_at=now,
            )
        return RiskGateDecision(
            decision_state="data_quality_block" if block else "caution",
            allow_new_entries=not block,
            requires_confirmation=False,
            recommended_action="sit_out" if block else "caution",
            risk_level="extreme" if block else "elevated",
            block_reason="intraday_session_policy_not_regular_hours" if block else None,
            warning_summary=(
                "Intraday equity workflow is not using regular-hours-normalized bars."
                if flags
                else "Intraday equity session policy is normal."
            ),
            missing_evidence=["regular-hours-normalized intraday bars"],
            override_allowed=False,
            assessed_at=now,
        )

    @staticmethod
    def _index_risk_decision(*, signals: IndexRiskSignals, now: datetime) -> RiskGateDecision:
        if not signals.enabled or signals.decision_effect == "normal":
            return MarketRiskCalendarService._normal_decision(now)
        summary = "; ".join(signals.reasons[:3]) if signals.reasons else "Index risk context is elevated."
        if signals.decision_effect == "restricted":
            return RiskGateDecision(
                decision_state="restricted",
                allow_new_entries=True,
                requires_confirmation=True,
                recommended_action="reduce_size",
                risk_level="high",
                warning_summary=summary,
                missing_evidence=[],
                override_allowed=True,
                override_reason_required=True,
                assessed_at=now,
            )
        return RiskGateDecision(
            decision_state="caution",
            allow_new_entries=True,
            requires_confirmation=False,
            recommended_action="caution",
            risk_level="elevated",
            warning_summary=summary,
            missing_evidence=[],
            override_allowed=False,
            assessed_at=now,
        )

    def _event_active(self, event: MarketRiskEvent | SymbolRiskEvent, now: datetime) -> bool:
        start = self._aware(event.starts_at)
        end = self._aware(event.ends_at or event.starts_at)
        if event.event_type in MACRO_EVENT_TYPES:
            start -= timedelta(minutes=self.settings.macro_event_block_before_minutes)
            end += timedelta(minutes=self.settings.macro_event_block_after_minutes)
        return start <= now <= end

    def _inside_earnings_window(self, event: SymbolRiskEvent, now: datetime) -> bool:
        event_day = self._aware(event.starts_at).date()
        start_day = event_day - timedelta(days=self.settings.earnings_block_days_before)
        end_day = event_day + timedelta(days=self.settings.earnings_block_days_after)
        return start_day <= now.date() <= end_day

    @staticmethod
    def _normal_decision(now: datetime) -> RiskGateDecision:
        return RiskGateDecision(
            decision_state="normal",
            allow_new_entries=True,
            requires_confirmation=False,
            recommended_action="trade_normally",
            risk_level="normal",
            warning_summary="No active market-risk calendar blocks.",
            assessed_at=now,
        )

    @staticmethod
    def _assessment(
        *,
        symbol: str | None,
        timeframe: str,
        decision: RiskGateDecision,
    ) -> RiskCalendarAssessment:
        return RiskCalendarAssessment(symbol=symbol, timeframe=timeframe, decision=decision)

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)

    @staticmethod
    def _severity(decision: RiskGateDecision) -> int:
        return {
            "normal": 0,
            "caution": 1,
            "restricted": 2,
            "requires_event_evidence": 3,
            "no_trade": 4,
            "data_quality_block": 5,
        }.get(decision.decision_state, 0)

    def _stronger(self, current: RiskGateDecision, candidate: RiskGateDecision) -> RiskGateDecision:
        if self._severity(candidate) > self._severity(current):
            return candidate
        return current

    @staticmethod
    def _dedupe_events(
        events: list[MarketRiskEvent | SymbolRiskEvent],
    ) -> list[MarketRiskEvent | SymbolRiskEvent]:
        seen: set[str] = set()
        output: list[MarketRiskEvent | SymbolRiskEvent] = []
        for event in events:
            if event.event_id in seen:
                continue
            seen.add(event.event_id)
            output.append(event)
        return output


class RiskCalendarBlocked(RuntimeError):
    pass


class RiskCalendarRestricted(RuntimeError):
    pass
