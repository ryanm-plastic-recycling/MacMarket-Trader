"""Deterministic mock event extractor."""

from datetime import datetime, timezone

from macmarket_trader.domain.enums import EventSourceType
from macmarket_trader.domain.schemas import CorporateEvent, MacroEvent, NewsEvent
from macmarket_trader.llm.base import EventExtractor


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
