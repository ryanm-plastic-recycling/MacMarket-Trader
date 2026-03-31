"""Domain enums for deterministic trading pipeline."""

from enum import Enum


class EventSourceType(str, Enum):
    NEWS = "news"
    MACRO = "macro"
    CORPORATE = "corporate"


class SetupType(str, Enum):
    EVENT_CONTINUATION = "event_continuation"
    PULLBACK_CONTINUATION = "pullback_continuation"
    FAILED_EVENT_FADE = "failed_event_fade"


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"


class RegimeType(str, Enum):
    RISK_ON_TREND = "risk_on_trend"
    RANGE_BALANCED = "range_balanced"
    RISK_OFF = "risk_off"


class OrderStatus(str, Enum):
    CREATED = "created"
    SUBMITTED = "submitted"
    FILLED = "filled"
    CANCELLED = "cancelled"
