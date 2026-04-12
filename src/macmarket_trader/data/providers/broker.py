"""Broker provider adapters — Alpaca paper trading."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from macmarket_trader.config import settings
from macmarket_trader.data.providers.base import BrokerProvider


class AlpacaBrokerProvider(BrokerProvider):
    """Places paper orders via Alpaca paper trading API."""

    def __init__(self) -> None:
        self.base_url = settings.alpaca_paper_base_url.rstrip("/")
        self.api_key = settings.alpaca_api_key_id.strip()
        self.api_secret = settings.alpaca_api_secret_key.strip()
        self.timeout_seconds = settings.market_data_request_timeout_seconds

    def _headers(self) -> dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _post_json(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8")
        request = Request(url=url, headers=self._headers(), data=data, method="POST")
        with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))

    def place_paper_order(self, symbol: str, side: str, shares: int, limit_price: float) -> dict[str, object]:
        payload = self._post_json(
            "/v2/orders",
            {
                "symbol": symbol.upper(),
                "side": side.lower(),
                "type": "limit",
                "qty": str(shares),
                "limit_price": str(round(limit_price, 2)),
                "time_in_force": "day",
            },
        )
        return {
            "order_id": str(payload.get("id") or ""),
            "symbol": str(payload.get("symbol") or symbol.upper()),
            "side": str(payload.get("side") or side.lower()),
            "shares": int(float(payload.get("qty") or shares)),
            "limit_price": float(payload.get("limit_price") or limit_price),
            "status": str(payload.get("status") or "unknown"),
            "submitted_at": str(payload.get("submitted_at") or datetime.now(tz=UTC).isoformat()),
            "provider": "alpaca_paper",
        }
