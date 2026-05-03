"""Defensive API security helpers."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from time import monotonic
from urllib.parse import urlparse

from fastapi import HTTPException, Request
from starlette.responses import JSONResponse

from macmarket_trader.config import settings


MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
DEFAULT_ALLOWED_ORIGINS = {
    "https://macmarket.io",
    "https://www.macmarket.io",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:9500",
    "http://127.0.0.1:9500",
}

SYMBOL_PATTERN = re.compile(r"^[A-Z][A-Z0-9.:-]{0,14}$")
MAX_BULK_SYMBOLS = 25
MAX_WATCHLIST_SYMBOLS = 100
MAX_SELECTED_STRATEGIES = 12
MAX_QUEUE_TOP_N = 25
MAX_TEXT_FIELD_LENGTH = 4_000


@dataclass(frozen=True)
class RateLimit:
    limit: int
    window_seconds: int


HIGH_COST_ROUTE_LIMITS: dict[str, RateLimit] = {
    "/admin/provider-health": RateLimit(limit=30, window_seconds=60),
    "/charts/haco": RateLimit(limit=240, window_seconds=60),
    "/recommendations/generate": RateLimit(limit=120, window_seconds=60),
    "/replay/run": RateLimit(limit=120, window_seconds=60),
    "/user/recommendations/opportunity-intelligence": RateLimit(limit=30, window_seconds=60),
    "/user/recommendations/queue/promote": RateLimit(limit=120, window_seconds=60),
    "/user/recommendations/queue": RateLimit(limit=120, window_seconds=60),
    "/user/recommendations/generate": RateLimit(limit=120, window_seconds=60),
    "/user/replay-runs": RateLimit(limit=120, window_seconds=60),
    "/user/options/replay-preview": RateLimit(limit=120, window_seconds=60),
    "/user/options/paper-structures/open": RateLimit(limit=120, window_seconds=60),
}


def _normalize_origin(value: str) -> str | None:
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}".lower()


def allowed_origins() -> set[str]:
    origins = set(DEFAULT_ALLOWED_ORIGINS)
    origins.update(
        origin
        for origin in (_normalize_origin(item) for item in settings.cors_allowed_origins)
        if origin
    )
    origins.update(
        origin
        for origin in (_normalize_origin(item) for item in settings.security_allowed_origins)
        if origin
    )
    app_origin = _normalize_origin(settings.app_base_url)
    if app_origin:
        origins.add(app_origin)
    return origins


def request_origin(request: Request) -> str | None:
    origin = request.headers.get("origin")
    if origin:
        return _normalize_origin(origin)
    referer = request.headers.get("referer")
    if referer:
        return _normalize_origin(referer)
    return None


def validate_mutation_origin(request: Request) -> None:
    if not settings.security_origin_check_enabled:
        return
    if request.method.upper() not in MUTATING_METHODS:
        return
    origin = request_origin(request)
    if origin is None:
        # Server-to-server calls, local tests, and Next proxy calls do not always
        # carry Origin/Referer. Browser-originated mutations do, and are checked.
        return
    if origin not in allowed_origins():
        raise HTTPException(status_code=403, detail="Request origin is not allowed.")


def normalize_symbol(value: object, *, field_name: str = "symbol") -> str:
    symbol = str(value or "").strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail=f"{field_name} is required.")
    if len(symbol) > 15 or not SYMBOL_PATTERN.fullmatch(symbol):
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must be 1-15 characters using letters, numbers, '.', ':', or '-'.",
        )
    return symbol


def normalize_symbol_list(
    values: object,
    *,
    max_items: int,
    field_name: str = "symbols",
) -> list[str]:
    if not isinstance(values, list):
        raise HTTPException(status_code=400, detail=f"{field_name} must be a list.")
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        symbol = normalize_symbol(value, field_name=field_name)
        if symbol in seen:
            continue
        seen.add(symbol)
        output.append(symbol)
        if len(output) > max_items:
            raise HTTPException(status_code=400, detail=f"{field_name} may include at most {max_items} symbols.")
    if not output:
        raise HTTPException(status_code=400, detail=f"{field_name} requires at least one symbol.")
    return output


def capped_int(value: object, *, default: int, minimum: int, maximum: int, field_name: str) -> int:
    raw = default if value is None or value == "" else value
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"{field_name} must be an integer.") from None
    if parsed < minimum or parsed > maximum:
        raise HTTPException(status_code=400, detail=f"{field_name} must be between {minimum} and {maximum}.")
    return parsed


def capped_text(value: object, *, field_name: str, max_length: int = MAX_TEXT_FIELD_LENGTH) -> str:
    text = str(value or "").strip()
    if len(text) > max_length:
        raise HTTPException(status_code=400, detail=f"{field_name} may be at most {max_length} characters.")
    return text


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._events: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def reset(self) -> None:
        self._events.clear()

    def check(self, *, bucket: str, identity: str, limit: RateLimit) -> tuple[bool, int]:
        now = monotonic()
        window_start = now - limit.window_seconds
        key = (bucket, identity)
        events = self._events[key]
        while events and events[0] <= window_start:
            events.popleft()
        if len(events) >= limit.limit:
            retry_after = max(1, int(limit.window_seconds - (now - events[0])) + 1)
            return False, retry_after
        events.append(now)
        return True, 0


rate_limiter = InMemoryRateLimiter()


def _route_limit(path: str) -> tuple[str, RateLimit] | None:
    for prefix in sorted(HIGH_COST_ROUTE_LIMITS, key=len, reverse=True):
        if path == prefix or path.startswith(f"{prefix}/"):
            return prefix, HIGH_COST_ROUTE_LIMITS[prefix]
    return None


def _request_identity(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        digest = hashlib.sha256(authorization.encode("utf-8")).hexdigest()
        return f"token:{digest}"
    forwarded_for = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    host = forwarded_for or (request.client.host if request.client else "unknown")
    return f"ip:{host}"


def validate_rate_limit(request: Request) -> JSONResponse | None:
    if not settings.security_rate_limit_enabled:
        return None
    if request.method.upper() not in MUTATING_METHODS and request.url.path != "/admin/provider-health":
        return None
    match = _route_limit(request.url.path)
    if match is None:
        return None
    bucket, limit = match
    allowed, retry_after = rate_limiter.check(bucket=bucket, identity=_request_identity(request), limit=limit)
    if allowed:
        return None
    return JSONResponse(
        {
            "detail": "Rate limit exceeded.",
            "retry_after_seconds": retry_after,
        },
        status_code=429,
        headers={"Retry-After": str(retry_after)},
    )
