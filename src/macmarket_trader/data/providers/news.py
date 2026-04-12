"""News provider adapters."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from macmarket_trader.config import settings
from macmarket_trader.data.providers.base import NewsProvider


class PolygonNewsProvider(NewsProvider):
    """Fetches company news via Polygon /v2/reference/news."""

    def __init__(self) -> None:
        self.base_url = settings.polygon_base_url.rstrip("/")
        self.api_key = settings.polygon_api_key.strip()
        self.timeout_seconds = settings.polygon_timeout_seconds
        self.max_articles = settings.news_polygon_max_articles

    def _request_json(self, path: str, query: dict[str, str]) -> dict[str, Any]:
        effective_query = {**query, "apiKey": self.api_key}
        url = f"{self.base_url}{path}?{urlencode(effective_query)}"
        request = Request(url=url, headers={"Accept": "application/json"}, method="GET")
        with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))

    def _normalize_article(self, article: dict[str, Any], symbol: str) -> dict[str, object]:
        publisher = article.get("publisher") or {}
        return {
            "id": str(article.get("id") or ""),
            "symbol": symbol.upper(),
            "headline": str(article.get("title") or ""),
            "published_utc": str(article.get("published_utc") or ""),
            "source": str(publisher.get("name") or ""),
            "url": str(article.get("article_url") or ""),
            "description": str(article.get("description") or ""),
            "keywords": list(article.get("keywords") or []),
        }

    def fetch_latest(self, symbol: str, since: datetime | None = None) -> list[dict[str, object]]:
        query: dict[str, str] = {
            "ticker": symbol.upper(),
            "limit": str(self.max_articles),
            "order": "desc",
            "sort": "published_utc",
        }
        if since is not None:
            query["published_utc.gte"] = since.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            payload = self._request_json("/v2/reference/news", query)
        except (HTTPError, URLError, TimeoutError, OSError):
            return []

        results = payload.get("results") or []
        return [self._normalize_article(item, symbol) for item in results]
