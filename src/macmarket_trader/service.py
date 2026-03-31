"""Unified recommendation service used by API and replay."""

from macmarket_trader.audit.engine import AuditEngine
from macmarket_trader.config import settings
from macmarket_trader.data.providers.mock import MockMarketDataProvider
from macmarket_trader.domain.schemas import (
    CorporateEvent,
    EvidenceBundle,
    MacroEvent,
    NewsEvent,
    OrderIntent,
    PortfolioSnapshot,
    TradeRecommendation,
)
from macmarket_trader.llm.mock_extractor import MockEventExtractor
from macmarket_trader.regime.engine import RegimeEngine
from macmarket_trader.risk.engine import RiskEngine
from macmarket_trader.setups.engine import SetupEngine


class RecommendationService:
    """Deterministic recommendation pipeline orchestration."""

    def __init__(self) -> None:
        self.provider = MockMarketDataProvider()
        self.extractor = MockEventExtractor()
        self.regime_engine = RegimeEngine()
        self.setup_engine = SetupEngine()
        self.risk_engine = RiskEngine()
        self.audit_engine = AuditEngine()

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
        shares, stop_distance, approved, rejection_reason = self.risk_engine.size_position(
            setup=setup,
            risk_dollars=settings.risk_dollars_per_trade,
            portfolio=portfolio_state,
            max_portfolio_heat=settings.max_portfolio_heat,
            max_position_notional=settings.max_position_notional,
        )
        notes = [
            "LLM constrained to extraction/summarization/explanation only.",
            f"Setup selected: {setup.setup_type.value}",
            f"Regime classified as: {regime.regime.value}",
        ]
        evidence = EvidenceBundle(
            event_id=structured_event.event_id,
            source_type=structured_event.source_type,
            source_timestamp=structured_event.source_timestamp,
            regime_version=regime.version,
            setup_engine_version=setup.setup_engine_version,
            risk_engine_version=self.risk_engine.version,
            explanatory_notes=notes,
        )
        rec = TradeRecommendation(
            symbol=symbol,
            event=structured_event,
            regime=regime,
            technical_context=technical_context,
            setup=setup,
            stop_distance=stop_distance,
            risk_dollars=settings.risk_dollars_per_trade,
            shares=shares,
            approved=approved,
            rejection_reason=rejection_reason,
            evidence=evidence,
        )
        self.audit_engine.record(rec)
        return rec

    def to_order_intent(self, rec: TradeRecommendation) -> OrderIntent:
        limit_price = (rec.setup.entry_zone_low + rec.setup.entry_zone_high) / 2
        return OrderIntent(
            recommendation_id=rec.recommendation_id,
            symbol=rec.symbol,
            side=rec.setup.direction,
            shares=rec.shares,
            limit_price=limit_price,
        )
