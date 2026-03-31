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
        # SDK call intentionally deferred so local dev and tests remain dependency-light.
        return f"resend-placeholder-{message.template_name}"
