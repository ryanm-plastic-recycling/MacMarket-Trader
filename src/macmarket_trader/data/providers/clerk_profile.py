"""Clerk backend profile hydration helper."""

from __future__ import annotations

from dataclasses import dataclass
from json import loads
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass
class ClerkHydratedIdentity:
    email: str
    display_name: str


class ClerkProfileProvider:
    """Fetches Clerk user profile details from backend API using secret key auth."""

    def __init__(self, *, secret_key: str, api_base_url: str = "https://api.clerk.com") -> None:
        self.secret_key = secret_key.strip()
        self.api_base_url = api_base_url.rstrip("/")

    def fetch_identity(self, external_auth_user_id: str) -> ClerkHydratedIdentity | None:
        if not self.secret_key or not external_auth_user_id:
            return None
        request = Request(
            f"{self.api_base_url}/v1/users/{external_auth_user_id}",
            headers={
                "Authorization": f"Bearer {self.secret_key}",
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=4) as response:
                payload = loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, ValueError):
            return None

        if not isinstance(payload, dict):
            return None

        email = self._extract_email(payload)
        display_name = self._extract_name(payload)
        return ClerkHydratedIdentity(email=email, display_name=display_name)

    @staticmethod
    def _extract_email(payload: dict[str, Any]) -> str:
        email_addresses = payload.get("email_addresses")
        if isinstance(email_addresses, list):
            for candidate in email_addresses:
                if isinstance(candidate, dict):
                    value = candidate.get("email_address")
                    if isinstance(value, str) and value.strip():
                        return value.strip().lower()
        primary = payload.get("primary_email_address")
        if isinstance(primary, dict):
            value = primary.get("email_address")
            if isinstance(value, str) and value.strip():
                return value.strip().lower()
        return ""

    @staticmethod
    def _extract_name(payload: dict[str, Any]) -> str:
        first_name = payload.get("first_name")
        last_name = payload.get("last_name")
        if isinstance(first_name, str) and isinstance(last_name, str):
            full = f"{first_name.strip()} {last_name.strip()}".strip()
            if full:
                return full
        username = payload.get("username")
        if isinstance(username, str) and username.strip():
            return username.strip()
        return ""
