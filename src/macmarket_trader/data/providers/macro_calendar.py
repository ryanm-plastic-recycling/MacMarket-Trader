"""Macro economic calendar provider adapters."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from macmarket_trader.config import settings
from macmarket_trader.data.providers.base import MacroCalendarProvider


class FredMacroCalendarProvider(MacroCalendarProvider):
    """Fetches upcoming economic release dates via FRED /releases/dates."""

    def __init__(self) -> None:
        self.base_url = settings.fred_base_url.rstrip("/")
        self.api_key = settings.fred_api_key.strip()
        self.timeout_seconds = settings.fred_timeout_seconds

    def _request_json(self, path: str, query: dict[str, str]) -> dict[str, Any]:
        effective_query = {**query, "api_key": self.api_key, "file_type": "json"}
        url = f"{self.base_url}{path}?{urlencode(effective_query)}"
        request = Request(url=url, headers={"Accept": "application/json"}, method="GET")
        with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))

    def upcoming_events(self, from_ts: datetime, to_ts: datetime) -> list[dict[str, object]]:
        query = {
            "realtime_start": from_ts.date().isoformat(),
            "realtime_end": to_ts.date().isoformat(),
            "sort_order": "asc",
        }
        try:
            payload = self._request_json("/releases/dates", query)
        except (HTTPError, URLError, TimeoutError, OSError):
            return []

        release_dates = payload.get("release_dates") or []
        return [
            {
                "event": str(item.get("release_name") or ""),
                "date": str(item.get("date") or ""),
                "release_id": int(item.get("release_id") or 0),
                "from": from_ts.isoformat(),
                "to": to_ts.isoformat(),
            }
            for item in release_dates
        ]
