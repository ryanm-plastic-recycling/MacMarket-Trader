"""Deterministic mock event extractor."""

from datetime import datetime, timezone

from macmarket_trader.domain.enums import EventSourceType
from macmarket_trader.domain.schemas import CorporateEvent, MacroEvent, NewsEvent
from macmarket_trader.llm.base import EventExtractor


class MockEventExtractor(EventExtractor):
    """Simple keyword classifier with deterministic summary generation."""

    def extract(self, symbol: str, text: str) -> NewsEvent | MacroEvent | CorporateEvent:
        lower = text.lower()
        now = datetime.now(timezone.utc)
        summary = text[:240]
        sentiment = 0.25

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
        if any(token in lower for token in ("merger", "buyback", "restructure")):
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
