"""Unified recommendation service used by API and replay."""

from __future__ import annotations

from macmarket_trader.audit.engine import AuditEngine
from macmarket_trader.config import settings
from macmarket_trader.data.providers.mock import MockMarketDataProvider
from macmarket_trader.domain.enums import EventSourceType, MarketMode, SetupType
from macmarket_trader.domain.schemas import (
    CatalystMetadata,
    CorporateEvent,
    EntryMetadata,
    EvidenceBundle,
    FillRecord,
    IndicatorContext,
    InvalidationMetadata,
    MacroEvent,
    NewsEvent,
    OrderIntent,
    OrderRecord,
    PortfolioSnapshot,
    QualityMetadata,
    RegimeContext,
    SizingMetadata,
    TargetsMetadata,
    TimeStopMetadata,
    TradeRecommendation,
)
from macmarket_trader.llm.mock_extractor import MockEventExtractor
from macmarket_trader.indicators import compute_haco_states, compute_hacolt_direction
from macmarket_trader.regime.engine import RegimeEngine
from macmarket_trader.risk.engine import RiskEngine
from macmarket_trader.setups.engine import SetupEngine
from macmarket_trader.storage.db import SessionLocal
from macmarket_trader.storage.repositories import FillRepository, OrderRepository, RecommendationRepository


class RecommendationService:
    """Deterministic recommendation pipeline orchestration."""

    def __init__(
        self,
        persist_audit: bool | None = None,
        recommendation_repository: RecommendationRepository | None = None,
        order_repository: OrderRepository | None = None,
        fill_repository: FillRepository | None = None,
    ) -> None:
        self.provider = MockMarketDataProvider()
        self.extractor = MockEventExtractor()
        self.regime_engine = RegimeEngine()
        self.setup_engine = SetupEngine()
        self.risk_engine = RiskEngine()
        self.audit_engine = AuditEngine()
        self.persist_audit = settings.audit_persistence_enabled if persist_audit is None else persist_audit
        self.recommendation_repository = recommendation_repository or RecommendationRepository(SessionLocal)
        self.order_repository = order_repository or OrderRepository(SessionLocal)
        self.fill_repository = fill_repository or FillRepository(SessionLocal)

    def generate(
        self,
        symbol: str,
        bars: list,
        event_text: str | None,
        event: NewsEvent | MacroEvent | CorporateEvent | None,
        portfolio: PortfolioSnapshot | None,
        market_mode: MarketMode = MarketMode.EQUITIES,
        user_is_approved: bool = False,
        app_user_id: int | None = None,
    ) -> TradeRecommendation:
        portfolio_state = portfolio or PortfolioSnapshot()
        structured_event = event or self.extractor.extract(symbol=symbol, text=event_text or "")
        technical_context = self.provider.build_technical_context(bars)
        regime = self.regime_engine.classify(bars)
        setup = self.setup_engine.generate(structured_event, regime, technical_context)
        shares, stop_distance, approved, rejection_reason, constraint_report = self.risk_engine.size_position(
            setup=setup,
            risk_dollars=settings.risk_dollars_per_trade,
            portfolio=portfolio_state,
            max_portfolio_heat=settings.max_portfolio_heat,
            max_position_notional=settings.max_position_notional,
        )

        entry_mid = (setup.entry_zone_low + setup.entry_zone_high) / 2
        target_1_rr = abs(setup.target_1 - entry_mid) / max(stop_distance, 0.01)
        target_2_rr = abs(setup.target_2 - entry_mid) / max(stop_distance, 0.01)
        expected_rr = (0.6 * target_1_rr) + (0.4 * target_2_rr)
        confidence = min(max(0.45 + (structured_event.sentiment_score * 0.2), 0.05), 0.95)
        risk_score = min(1.0, max(0.0, 1.0 / max(expected_rr, 0.01)))
        source_quality = "primary" if structured_event.source_type != EventSourceType.NEWS else "secondary"

        quality_passed, quality_reasons = self._evaluate_quality_gates(
            expected_rr=expected_rr,
            volatility_score=regime.volatility_score,
            setup_type=setup.setup_type,
            source_quality=source_quality,
        )
        if not quality_passed:
            approved = False
            rejection_reason = "; ".join(quality_reasons)
        if user_is_approved and not approved:
            approved = True
            rejection_reason = None
            quality_reasons.append(
                "User approval override applied: local approval_status=approved."
            )

        closes = [bar.close for bar in bars]
        haco_states = compute_haco_states(closes)
        hacolt_states = compute_hacolt_direction(closes)
        last_flip_idx = max((idx for idx, point in enumerate(haco_states) if point.flip), default=None)
        flip_recency = (len(haco_states) - last_flip_idx - 1) if last_flip_idx is not None else None
        latest_haco_state = haco_states[-1].state if haco_states else "neutral"
        latest_hacolt_direction = hacolt_states[-1].direction if hacolt_states else "flat"
        agrees_with_side = (latest_haco_state == "green" and setup.direction.value == "long") or (
            latest_haco_state == "red" and setup.direction.value == "short"
        )

        notes = [
            "LLM constrained to extraction/summarization/explanation only.",
            f"Setup selected: {setup.setup_type.value}",
            f"Regime classified as: {regime.regime.value}",
        ]
        notes.extend([f"Quality gate: {reason}" for reason in quality_reasons])

        outcome = "approved" if approved else "no_trade"
        rec = TradeRecommendation(
            outcome=outcome,
            market_mode=market_mode,
            symbol=symbol,
            side=setup.direction,
            thesis=self._build_thesis(structured_event.summary, setup.setup_type.value, regime.regime.value),
            event=structured_event,
            catalyst=CatalystMetadata(
                type=structured_event.source_type.value,
                novelty="medium",
                source_quality=source_quality,
                event_timestamp=structured_event.source_timestamp,
            ),
            regime_context=RegimeContext(
                market_regime=regime.regime,
                volatility_regime="moderate" if regime.volatility_score < 0.035 else "elevated",
                breadth_state="supportive" if regime.participation_score >= 1 else "fragile",
            ),
            technical_context=technical_context,
            indicator_context=IndicatorContext(
                haco_state=latest_haco_state,
                haco_flip_recency_bars=flip_recency,
                hacolt_direction=latest_hacolt_direction,
                agrees_with_recommendation=agrees_with_side,
            ),
            entry=EntryMetadata(
                setup_type=setup.setup_type,
                zone_low=setup.entry_zone_low,
                zone_high=setup.entry_zone_high,
                trigger_text=setup.trigger_text,
            ),
            invalidation=InvalidationMetadata(price=setup.invalidation_price, reason=setup.invalidation_reason),
            targets=TargetsMetadata(
                target_1=setup.target_1,
                target_2=setup.target_2,
                trailing_rule=setup.trailing_rule_text,
            ),
            time_stop=TimeStopMetadata(
                max_holding_days=setup.time_stop_days,
                reason="Event half-life exhausted",
            ),
            sizing=SizingMetadata(
                risk_dollars=settings.risk_dollars_per_trade,
                stop_distance=stop_distance,
                shares=shares if approved else 0,
            ),
            quality=QualityMetadata(
                expected_rr=expected_rr,
                confidence=confidence,
                risk_score=risk_score,
            ),
            approved=approved,
            rejection_reason=rejection_reason,
            constraints=constraint_report,
            evidence=EvidenceBundle(
                event_id=structured_event.event_id,
                source_type=structured_event.source_type,
                source_timestamp=structured_event.source_timestamp,
                regime_version=regime.version,
                setup_engine_version=setup.setup_engine_version,
                risk_engine_version=self.risk_engine.version,
                explanatory_notes=notes,
                headlines=[],
                filings=[],
                technical_context_refs=[],
                historical_analog_refs=[],
            ),
        )
        self.audit_engine.record(rec)
        if self.persist_audit:
            self.recommendation_repository.create(rec, app_user_id=app_user_id)
        return rec

    def to_order_intent(self, rec: TradeRecommendation) -> OrderIntent:
        limit_price = (rec.entry.zone_low + rec.entry.zone_high) / 2
        return OrderIntent(
            recommendation_id=rec.recommendation_id,
            symbol=rec.symbol,
            side=rec.side,
            shares=rec.sizing.shares,
            limit_price=limit_price,
        )

    def persist_order(self, order: OrderRecord, notes: str = "", *, app_user_id: int | None = None) -> None:
        if self.persist_audit:
            self.order_repository.create(order, notes=notes, app_user_id=app_user_id)

    def persist_fill(self, fill: FillRecord) -> None:
        if self.persist_audit:
            self.fill_repository.create(fill)

    @staticmethod
    def _source_quality_score(source_quality: str) -> float:
        return {
            "primary": 1.0,
            "secondary": 0.6,
            "tertiary": 0.3,
        }.get(source_quality, 0.0)

    def _evaluate_quality_gates(
        self,
        *,
        expected_rr: float,
        volatility_score: float,
        setup_type: SetupType,
        source_quality: str,
    ) -> tuple[bool, list[str]]:
        reasons: list[str] = []

        if expected_rr < settings.min_expected_rr:
            reasons.append(
                f"Expected RR {expected_rr:.2f} below threshold {settings.min_expected_rr:.2f}"
            )

        if (
            setup_type == SetupType.EVENT_CONTINUATION
            and volatility_score > settings.max_event_continuation_volatility
        ):
            reasons.append(
                "Volatility regime too elevated for event continuation "
                f"({volatility_score:.4f}>{settings.max_event_continuation_volatility:.4f})"
            )

        source_quality_score = self._source_quality_score(source_quality)
        if source_quality_score < settings.min_catalyst_source_quality_score:
            reasons.append(
                "Catalyst source quality below configured threshold "
                f"({source_quality_score:.2f}<{settings.min_catalyst_source_quality_score:.2f})"
            )

        return len(reasons) == 0, reasons

    @staticmethod
    def _build_thesis(summary: str, setup_type: str, regime: str) -> str:
        clipped = summary.strip()[:120] or "Event-driven setup"
        return f"{clipped}; setup={setup_type}; regime={regime}"
