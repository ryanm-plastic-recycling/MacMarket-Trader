"""Unified recommendation service used by API and replay."""

from __future__ import annotations

from macmarket_trader.audit.engine import AuditEngine
from macmarket_trader.config import settings
from macmarket_trader.data.providers.mock import MockMarketDataProvider
from macmarket_trader.domain.enums import EventSourceType
from macmarket_trader.domain.schemas import (
    CatalystMetadata,
    CorporateEvent,
    EntryMetadata,
    EvidenceBundle,
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
from macmarket_trader.regime.engine import RegimeEngine
from macmarket_trader.risk.engine import RiskEngine
from macmarket_trader.setups.engine import SetupEngine
from macmarket_trader.storage.db import SessionLocal
from macmarket_trader.storage.repositories import OrderRepository, RecommendationRepository


class RecommendationService:
    """Deterministic recommendation pipeline orchestration."""

    def __init__(
        self,
        persist_audit: bool | None = None,
        recommendation_repository: RecommendationRepository | None = None,
        order_repository: OrderRepository | None = None,
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

    def generate(
        self,
        symbol: str,
        bars: list,
        event_text: str | None,
        event: NewsEvent | MacroEvent | CorporateEvent | None,
        portfolio: PortfolioSnapshot | None,
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

        expected_rr = abs(setup.target_1 - ((setup.entry_zone_low + setup.entry_zone_high) / 2)) / max(
            stop_distance, 0.01
        )
        confidence = min(max(0.45 + (structured_event.sentiment_score * 0.2), 0.05), 0.95)
        risk_score = min(1.0, max(0.0, 1.0 / max(expected_rr, 0.01)))
        notes = [
            "LLM constrained to extraction/summarization/explanation only.",
            f"Setup selected: {setup.setup_type.value}",
            f"Regime classified as: {regime.regime.value}",
        ]

        rec = TradeRecommendation(
            symbol=symbol,
            side=setup.direction,
            thesis=self._build_thesis(structured_event.summary, setup.setup_type.value, regime.regime.value),
            event=structured_event,
            catalyst=CatalystMetadata(
                type=structured_event.source_type.value,
                novelty="medium",
                source_quality="primary" if structured_event.source_type != EventSourceType.NEWS else "secondary",
                event_timestamp=structured_event.source_timestamp,
            ),
            regime_context=RegimeContext(
                market_regime=regime.regime,
                volatility_regime="moderate" if regime.volatility_score < 0.035 else "elevated",
                breadth_state="supportive" if regime.participation_score >= 1 else "fragile",
            ),
            technical_context=technical_context,
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
                shares=shares,
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
            self.recommendation_repository.create(rec)
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

    def persist_order(self, order: OrderRecord, notes: str = "") -> None:
        if self.persist_audit:
            self.order_repository.create(order, notes=notes)

    @staticmethod
    def _build_thesis(summary: str, setup_type: str, regime: str) -> str:
        clipped = summary.strip()[:120] or "Event-driven setup"
        return f"{clipped}; setup={setup_type}; regime={regime}"
