"""Deterministic mock event extractor."""

from datetime import datetime, timezone

from macmarket_trader.domain.enums import EventSourceType
from macmarket_trader.domain.schemas import (
    BetterElsewhereCandidate,
    CorporateEvent,
    LLMEventFields,
    LLMRecommendationExplanation,
    MacroEvent,
    NewsEvent,
    OpportunityCandidateSummary,
    OpportunityComparisonMemo,
    TradeRecommendation,
)
from macmarket_trader.llm.base import EventExtractor, LLMClient, LLM_PROMPT_VERSION


class MockEventExtractor(EventExtractor):
    """Keyword classifier with deterministic sentiment calibration."""

    def extract(self, symbol: str, text: str) -> NewsEvent | MacroEvent | CorporateEvent:
        lower = text.lower()
        now = datetime.now(timezone.utc)
        summary = text[:240]

        if any(token in lower for token in ("fed", "cpi", "rates", "jobs")):
            return MacroEvent(
                symbol=symbol,
                source_type=EventSourceType.MACRO,
                source_timestamp=now,
                headline="Macro event extracted",
                summary=summary,
                sentiment_score=0.0,
                tags=["macro"],
            )

        positive_tokens = ("beat", "strong guidance", "raised", "upgrade", "breakout")
        negative_tokens = ("miss", "downgrade", "cuts", "weak guidance", "probe")
        pos_hits = sum(1 for token in positive_tokens if token in lower)
        neg_hits = sum(1 for token in negative_tokens if token in lower)
        sentiment = max(-0.85, min(0.85, 0.2 + (0.18 * pos_hits) - (0.22 * neg_hits)))

        if any(token in lower for token in ("merger", "buyback", "restructure", "guidance", "earnings")):
            return CorporateEvent(
                symbol=symbol,
                source_type=EventSourceType.CORPORATE,
                source_timestamp=now,
                headline="Corporate event extracted",
                summary=summary,
                sentiment_score=sentiment,
                tags=["corporate"],
            )

        return NewsEvent(
            symbol=symbol,
            source_type=EventSourceType.NEWS,
            source_timestamp=now,
            headline="News event extracted",
            summary=summary,
            sentiment_score=sentiment,
            tags=["news"],
        )


class MockLLMClient(LLMClient):
    """Deterministic explanation client used for local/test fallback."""

    provider_name = "mock"
    prompt_version = LLM_PROMPT_VERSION

    def __init__(self, *, model: str | None = None) -> None:
        self.model = model or "mock-deterministic"
        self._extractor = MockEventExtractor()

    def summarize_event_text(self, *, symbol: str, text: str) -> str:
        event = self._extractor.extract(symbol=symbol, text=text)
        return event.summary

    def extract_event_fields(self, *, symbol: str, text: str) -> LLMEventFields:
        event = self._extractor.extract(symbol=symbol, text=text)
        return LLMEventFields(
            source_type=event.source_type,
            headline=event.headline,
            summary=event.summary,
            sentiment_score=event.sentiment_score,
            tags=event.tags,
        )

    def explain_recommendation(self, *, recommendation: TradeRecommendation) -> LLMRecommendationExplanation:
        status = "approved" if recommendation.approved else "rejected"
        reason = recommendation.rejection_reason or "deterministic quality and risk checks passed"
        counter_thesis = self.generate_counter_thesis(recommendation=recommendation)
        return LLMRecommendationExplanation(
            summary=(
                f"{recommendation.symbol} is a {status} {recommendation.side.value} setup. "
                f"The deterministic engine selected {recommendation.entry.setup_type.value} "
                f"inside a {recommendation.regime_context.market_regime.value} regime."
            ),
            approval_explanation=(
                f"Approval status is owned by deterministic quality and risk gates: {reason}."
            ),
            counter_thesis=counter_thesis,
        )

    def generate_counter_thesis(self, *, recommendation: TradeRecommendation) -> list[str]:
        bullets = [
            f"Price fails to hold the invalidation level near {recommendation.invalidation.price}.",
            "Catalyst follow-through fades before the expected holding window.",
            "Market regime or breadth weakens against the setup.",
        ]
        if recommendation.targets.target_1:
            bullets.append(f"Move stalls before target 1 near {recommendation.targets.target_1}.")
        return bullets[:4]

    def compare_candidates(
        self,
        *,
        candidates: list[OpportunityCandidateSummary],
        better_elsewhere: list[BetterElsewhereCandidate],
    ) -> OpportunityComparisonMemo:
        ordered = sorted(
            candidates,
            key=lambda item: (
                item.current_recommendation_rank if item.current_recommendation_rank is not None else 999,
                -(item.deterministic_score or 0.0),
                -(item.expected_rr or 0.0),
            ),
        )
        best = ordered[0] if ordered else None
        memo = self.generate_market_context_memo(candidates=candidates)
        if better_elsewhere:
            memo = f"{memo} {self.generate_better_elsewhere_memo(candidates=candidates, better_elsewhere=better_elsewhere)}"
        comparison_rows = [
            {
                "candidate_id": candidate.recommendation_id,
                "symbol": candidate.symbol,
                "rank": candidate.current_recommendation_rank,
                "score": candidate.deterministic_score,
                "expected_rr": candidate.expected_rr,
                "confidence": candidate.confidence,
                "status": candidate.status,
                "desk_read": self._candidate_read(candidate),
            }
            for candidate in ordered
        ]
        counter_thesis = {
            candidate.recommendation_id: [
                candidate.rejection_reason or "Setup quality fades relative to deterministic scan peers.",
                "Market or catalyst context weakens before follow-through.",
            ][:2]
            for candidate in ordered
        }
        not_good_enough = None
        if not any(candidate.approved for candidate in candidates):
            not_good_enough = "No selected candidate is currently approved by deterministic gates."
        elif best and (best.expected_rr or 0.0) < 1.2:
            not_good_enough = "Best selected candidate has weak deterministic reward/risk for risking paper capital today."
        missing_data = []
        if any(not candidate.event_summary for candidate in candidates):
            missing_data.append("fresh event/news summary")
        if any(candidate.deterministic_score is None for candidate in candidates):
            missing_data.append("deterministic queue score")
        return OpportunityComparisonMemo(
            best_deterministic_candidate_id=best.recommendation_id if best else None,
            best_deterministic_symbol=best.symbol if best else None,
            market_desk_memo=memo,
            comparison_rows=comparison_rows,
            counter_thesis_by_candidate=counter_thesis,
            better_elsewhere=better_elsewhere,
            not_good_enough_warning=not_good_enough,
            missing_data=missing_data,
        )

    def generate_market_context_memo(self, *, candidates: list[OpportunityCandidateSummary]) -> str:
        if not candidates:
            return "No deterministic candidates were supplied for Opportunity Intelligence."
        symbols = ", ".join(candidate.symbol for candidate in candidates)
        approved_count = sum(1 for candidate in candidates if candidate.approved)
        regimes = sorted(
            {
                str(candidate.market_regime.get("market_regime"))
                for candidate in candidates
                if isinstance(candidate.market_regime, dict) and candidate.market_regime.get("market_regime")
            }
        )
        regime_text = f" Regime context: {', '.join(regimes)}." if regimes else ""
        return (
            f"Desk memo for {symbols}: compare only the backend-supplied deterministic candidates. "
            f"{approved_count} of {len(candidates)} selected candidates are approved by deterministic gates."
            f"{regime_text}"
        )

    def generate_better_elsewhere_memo(
        self,
        *,
        candidates: list[OpportunityCandidateSummary],
        better_elsewhere: list[BetterElsewhereCandidate],
    ) -> str:
        del candidates
        if not better_elsewhere:
            return "No stronger deterministic scan candidates were supplied."
        symbols = ", ".join(candidate.symbol for candidate in better_elsewhere)
        return f"Deterministic scan also surfaced {symbols}; treat these as scan-verified alternatives, not LLM-created trades."

    @staticmethod
    def _candidate_read(candidate: OpportunityCandidateSummary) -> str:
        if not candidate.approved:
            return candidate.rejection_reason or "No-trade by deterministic gates."
        if (candidate.risk_score or 0.0) > 0.65:
            return "Approved, but risk score is elevated versus selected peers."
        return "Approved candidate; compare score, reward/risk, and thesis durability before paper execution prep."
