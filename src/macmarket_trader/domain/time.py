"""Timezone-safe datetime helpers."""

from __future__ import annotations

from datetime import date, datetime, timezone


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def _coerce_calendar_date(value: date | datetime | str | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return aware.astimezone(timezone.utc).date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        try:
            if len(normalized) == 10:
                return date.fromisoformat(normalized)
            parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        except ValueError:
            return None
        aware = parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
        return aware.astimezone(timezone.utc).date()
    return None


def calendar_days_to_expiration(
    expiration_date: date | datetime | str | None,
    *,
    as_of: date | datetime | str | None = None,
    allow_expired_negative: bool = False,
) -> int | None:
    """Return UTC-calendar DTE for an option expiration.

    The default clamps expired contracts to zero for display/research horizons.
    Review flows that need to distinguish expired-open structures can opt into
    negative values and map that state to a separate expiration status.
    """

    expiration = _coerce_calendar_date(expiration_date)
    assessed_at = _coerce_calendar_date(as_of) or utc_now().date()
    if expiration is None:
        return None
    days = (expiration - assessed_at).days
    if days < 0 and not allow_expired_negative:
        return 0
    return days
