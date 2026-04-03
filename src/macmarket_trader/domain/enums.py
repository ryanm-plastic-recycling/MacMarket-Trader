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
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"




class MarketMode(str, Enum):
    EQUITIES = "equities"
    OPTIONS = "options"
    CRYPTO = "crypto"


class InstrumentType(str, Enum):
    EQUITY = "equity"
    ETF = "etf"
    FUND = "fund"
    OPTION_CONTRACT = "option_contract"
    CRYPTO_SPOT = "crypto_spot"
    CRYPTO_PERPETUAL = "crypto_perpetual"
    CRYPTO_FUTURE = "crypto_future"


class TradingSessionModel(str, Enum):
    US_EQUITIES_REGULAR_HOURS = "us_equities_regular_hours"
    US_OPTIONS_REGULAR_HOURS = "us_options_regular_hours"
    CRYPTO_24_7 = "crypto_24_7"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


class AppRole(str, Enum):
    USER = "user"
    ANALYST = "analyst"
    ADMIN = "admin"
