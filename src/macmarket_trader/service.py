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
    LLMProvenance,
    LLMRecommendationExplanation,
    MacroEvent,
    NewsEvent,
    OrderIntent,
    OrderRecord,
    BetterElsewhereCandidate,
    OpportunityCandidateSummary,
    OpportunityComparisonMemo,
    OpportunityIntelligenceProvenance,
    PortfolioSnapshot,
    QualityMetadata,
    RegimeContext,
    SizingMetadata,
    TargetsMetadata,
    TimeStopMetadata,
    TradeRecommendation,
)
from macmarket_trader.domain.time import utc_now
from macmarket_trader.llm.base import LLMClient, LLMProviderUnavailable, LLMValidationError
from macmarket_trader.llm.mock_extractor import MockEventExtractor, MockLLMClient
from macmarket_trader.llm.registry import build_llm_client
from macmarket_trader.indicators import compute_haco_states, compute_hacolt_direction
from macmarket_trader.regime.engine import RegimeEngine
from macmarket_trader.risk.engine import RiskEngine
from macmarket_trader.risk_calendar.registry import build_risk_calendar_service
from macmarket_trader.risk_calendar.service import MarketRiskCalendarService
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
        llm_client: LLMClient | None = None,
        risk_calendar_service: MarketRiskCalendarService | None = None,
    ) -> None:
        self.provider = MockMarketDataProvider()
        self.extractor = MockEventExtractor()
        self._explicit_llm_client = llm_client is not None
        self.llm_client = llm_client or build_llm_client()
        self.risk_calendar_service = risk_calendar_service or build_risk_calendar_service()
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
        risk_dollars: float | None = None,
        timeframe: str = "1D",
    ) -> TradeRecommendation:
        # Pass 4 — `risk_dollars` overrides settings.risk_dollars_per_trade
        # when the caller (route handler) has resolved the per-user override.
        effective_risk_dollars = (
            float(risk_dollars) if risk_dollars is not None else settings.risk_dollars_per_trade
        )
        portfolio_state = portfolio or PortfolioSnapshot()
        structured_event = event or self.extractor.extract(symbol=symbol, text=event_text or "")
        technical_context = self.provider.build_technical_context(bars)
        regime = self.regime_engine.classify(bars)
        setup = self.setup_engine.generate(structured_event, regime, technical_context)
        shares, stop_distance, approved, rejection_reason, constraint_report = self.risk_engine.size_position(
            setup=setup,
            risk_dollars=effective_risk_dollars,
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
            "Deterministic setup, risk, approval, and order-intent engines own trade decisions.",
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
                risk_dollars=effective_risk_dollars,
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
        rec = self._apply_risk_calendar(rec, bars=bars, timeframe=timeframe)
        rec.ai_explanation, rec.llm_provenance = self._build_ai_explanation(rec)
        self.audit_engine.record(rec)
        if self.persist_audit:
            self.recommendation_repository.create(rec, app_user_id=app_user_id)
        return rec

    def _apply_risk_calendar(self, rec: TradeRecommendation, *, bars: list, timeframe: str = "1D") -> TradeRecommendation:
        assessment = self.risk_calendar_service.assess(
            symbol=rec.symbol,
            timeframe=timeframe,
            bars=bars,
        )
        decision = assessment.decision
        if decision.decision_state in {"no_trade", "requires_event_evidence", "data_quality_block"}:
            rejection = decision.block_reason or decision.warning_summary
            return TradeRecommendation.model_validate(
                rec.model_copy(
                    update={
                        "approved": False,
                        "outcome": "calendar_blocked",
                        "rejection_reason": rejection,
                        "risk_calendar": assessment,
                    }
                )
            )
        return TradeRecommendation.model_validate(
            rec.model_copy(update={"risk_calendar": assessment})
        )

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

    def _active_llm_client(self) -> LLMClient:
        if self._explicit_llm_client:
            return self.llm_client
        self.llm_client = build_llm_client()
        return self.llm_client

    def _build_ai_explanation(self, rec: TradeRecommendation) -> tuple[LLMRecommendationExplanation, LLMProvenance]:
        validation_errors: list[str] = []
        llm_client = self._active_llm_client()
        provider = getattr(llm_client, "provider_name", "mock")
        model = getattr(llm_client, "model", None)
        prompt_version = getattr(llm_client, "prompt_version", "llm-explanation-v1")
        fallback_used = (
            not settings.llm_enabled
            or (settings.llm_provider.strip().lower() != "mock" and provider == "mock")
        )

        try:
            raw_explanation = llm_client.explain_recommendation(recommendation=rec)
            explanation = LLMRecommendationExplanation.model_validate(raw_explanation)
            if not explanation.counter_thesis:
                counter_thesis = llm_client.generate_counter_thesis(recommendation=rec)
                explanation = explanation.model_copy(update={"counter_thesis": counter_thesis[:8]})
            explanation = LLMRecommendationExplanation.model_validate(explanation)
        except (LLMProviderUnavailable, LLMValidationError, ValueError, TypeError) as exc:
            validation_errors.append(str(exc))
            fallback_client = MockLLMClient()
            provider = fallback_client.provider_name
            model = fallback_client.model
            prompt_version = fallback_client.prompt_version
            explanation = fallback_client.explain_recommendation(recommendation=rec)
            fallback_used = True

        provenance = LLMProvenance(
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            generated_at=utc_now(),
            fallback_used=fallback_used,
            validation_errors=validation_errors,
        )
        return explanation, provenance

    def generate_opportunity_intelligence(
        self,
        *,
        candidates: list[OpportunityCandidateSummary],
        better_elsewhere: list[BetterElsewhereCandidate] | None = None,
        index_context: dict[str, object] | None = None,
    ) -> OpportunityComparisonMemo:
        supplied_better_elsewhere = better_elsewhere or []
        validation_errors: list[str] = []
        llm_client = self._active_llm_client()
        provider = getattr(llm_client, "provider_name", "mock")
        model = getattr(llm_client, "model", None)
        prompt_version = getattr(llm_client, "prompt_version", "llm-explanation-v1")
        fallback_used = (
            not settings.llm_enabled
            or (settings.llm_provider.strip().lower() != "mock" and provider == "mock")
        )

        try:
            raw_memo = llm_client.compare_candidates(
                candidates=candidates,
                better_elsewhere=supplied_better_elsewhere,
                index_context=index_context,
            )
            memo = OpportunityComparisonMemo.model_validate(raw_memo)
            self._validate_opportunity_memo(
                memo=memo,
                candidates=candidates,
                better_elsewhere=supplied_better_elsewhere,
            )
        except (LLMProviderUnavailable, LLMValidationError, ValueError, TypeError) as exc:
            validation_errors.append(str(exc))
            fallback_client = MockLLMClient()
            provider = fallback_client.provider_name
            model = fallback_client.model
            prompt_version = fallback_client.prompt_version
            memo = fallback_client.compare_candidates(
                candidates=candidates,
                better_elsewhere=supplied_better_elsewhere,
                index_context=index_context,
            )
            fallback_used = True

        provenance = OpportunityIntelligenceProvenance(
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            generated_at=utc_now(),
            fallback_used=fallback_used,
            validation_errors=validation_errors,
            candidate_ids=[candidate.recommendation_id for candidate in candidates],
            scanned_symbols=sorted(
                {
                    candidate.symbol
                    for candidate in candidates
                }
                | {
                    candidate.symbol
                    for candidate in supplied_better_elsewhere
                    if candidate.source == "deterministic_scan"
                }
            ),
            better_elsewhere_source="deterministic_scan" if supplied_better_elsewhere else "omitted",
            index_context=index_context,
        )
        return OpportunityComparisonMemo.model_validate(
            memo.model_copy(
                update={
                    "candidates": candidates,
                    "better_elsewhere": supplied_better_elsewhere,
                    "provenance": provenance,
                }
            )
        )

    @staticmethod
    def _validate_opportunity_memo(
        *,
        memo: OpportunityComparisonMemo,
        candidates: list[OpportunityCandidateSummary],
        better_elsewhere: list[BetterElsewhereCandidate],
    ) -> None:
        candidate_ids = {candidate.recommendation_id for candidate in candidates}
        selected_symbols = {candidate.symbol for candidate in candidates}
        better_symbols = {candidate.symbol for candidate in better_elsewhere}
        allowed_symbols = selected_symbols | better_symbols
        if memo.best_deterministic_candidate_id and memo.best_deterministic_candidate_id not in candidate_ids:
            raise LLMValidationError("best deterministic candidate was not supplied by backend")
        if memo.best_deterministic_symbol and memo.best_deterministic_symbol not in selected_symbols:
            raise LLMValidationError("best deterministic symbol was not supplied by backend")
        for row in memo.comparison_rows:
            candidate_id = row.get("candidate_id")
            symbol = row.get("symbol")
            if candidate_id is not None and str(candidate_id) not in candidate_ids:
                raise LLMValidationError("comparison row referenced unsupplied candidate")
            if symbol is not None and str(symbol).upper() not in selected_symbols:
                raise LLMValidationError("comparison row referenced unsupplied symbol")
        for candidate_id in memo.counter_thesis_by_candidate:
            if candidate_id not in candidate_ids:
                raise LLMValidationError("counter-thesis referenced unsupplied candidate")
        for item in memo.better_elsewhere:
            if item.source == "deterministic_scan" and item.symbol not in better_symbols:
                raise LLMValidationError("better-elsewhere candidate was not supplied by deterministic scan")
            if item.source == "research_only_unverified" and item.symbol not in allowed_symbols:
                raise LLMValidationError("research-only better-elsewhere symbol was not supplied by backend")

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
