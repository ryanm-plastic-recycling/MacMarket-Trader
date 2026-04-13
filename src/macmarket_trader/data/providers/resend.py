"""Resend email provider adapter."""

from __future__ import annotations

import os

from macmarket_trader.data.providers.base import EmailMessage, EmailProvider


class ResendEmailProvider(EmailProvider):
    """Thin adapter to keep business logic isolated from SDK specifics."""

    def __init__(self, api_key: str | None = None, from_email: str | None = None) -> None:
        self.api_key = api_key or os.getenv("RESEND_API_KEY", "")
        self.from_email = from_email or os.getenv("RESEND_FROM_EMAIL", "noreply@macmarket-trader.local")

    def send(self, message: EmailMessage) -> str:
        if not self.api_key:
            raise ValueError("RESEND_API_KEY is not configured")
        try:
            import httpx  # available via test/runtime deps; kept as lazy import to avoid hard dep in non-resend mode
            payload: dict[str, object] = {
                "from": self.from_email,
                "to": [message.to_email],
                "subject": message.subject,
                "text": message.body,
            }
            if message.html:
                payload["html"] = message.html
            resp = httpx.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=10.0,
            )
            resp.raise_for_status()
            return str(resp.json().get("id") or f"resend-{message.template_name}")
        except Exception as exc:
            raise RuntimeError(f"Resend delivery failed: {exc}") from exc
