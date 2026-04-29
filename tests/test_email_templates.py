"""Pass 4 root-cause fix verification — email logo must inline as base64.

Gmail (and most webmail) proxy remote `<img src=…>` URLs through their own
fetcher. When that proxy fails to load the URL — for any reason — the email
shows a broken-image icon. The fix promotes the embedded base64 data URI
from "fallback" to "primary" so the logo renders without depending on any
remote fetch by the email client.

These tests assert that rule for every render path that emits a logo, and
specifically that setting BRAND_LOGO_URL no longer wins over the inlined
asset.
"""

from __future__ import annotations

import re

import pytest

from macmarket_trader import email_templates
from macmarket_trader.email_templates import (
    render_approval_html,
    render_invite_html,
    render_rejection_html,
)


_DATA_URI_RE = re.compile(r'src="data:image/png;base64,[A-Za-z0-9+/=]+"')


@pytest.fixture(autouse=True)
def _set_brand_logo_url_env(monkeypatch):
    # Simulate the production state where BRAND_LOGO_URL is set in .env.
    # The fix must still emit the base64 data URI, not the remote URL.
    monkeypatch.setenv("BRAND_LOGO_URL", "https://logos.macmarket.io/square_console_ticks_lockup_dark.png")


def test_logo_data_uri_is_loaded_at_module_init() -> None:
    """The on-disk PNG must be encoded into _LOGO_DATA_URI at import time."""
    assert email_templates._LOGO_DATA_URI is not None
    assert email_templates._LOGO_DATA_URI.startswith("data:image/png;base64,")


def test_logo_img_emits_base64_even_when_brand_logo_url_is_set() -> None:
    """Regression guard for the Pass 4 root cause.

    Pre-fix behaviour: BRAND_LOGO_URL was first in the priority chain, so
    `_logo_img` rendered <img src="https://logos.macmarket.io/..."> and
    Gmail's proxy occasionally failed to fetch it.
    Post-fix: the on-disk base64 wins, regardless of BRAND_LOGO_URL.
    """
    html = email_templates._logo_img(width=200)
    assert _DATA_URI_RE.search(html), html
    assert "logos.macmarket.io" not in html


def test_logo_img_falls_back_to_brand_logo_url_when_data_uri_missing(monkeypatch) -> None:
    """If the on-disk asset somehow disappears, the env URL is used as a deeper
    fallback before the CSS lockup. Operator-recoverable mode."""
    monkeypatch.setattr(email_templates, "_LOGO_DATA_URI", None)
    html = email_templates._logo_img(width=200)
    assert 'src="https://logos.macmarket.io/square_console_ticks_lockup_dark.png"' in html


def test_logo_img_falls_back_to_css_lockup_when_neither_available(monkeypatch) -> None:
    """No data URI and no env URL — the CSS table lockup must render so the
    email is never broken by a missing image."""
    monkeypatch.setattr(email_templates, "_LOGO_DATA_URI", None)
    monkeypatch.delenv("BRAND_LOGO_URL", raising=False)
    html = email_templates._logo_img(width=200)
    assert "<img" not in html
    assert "MacMarket" in html
    assert "TRADER" in html


def test_render_invite_html_inlines_logo() -> None:
    html = render_invite_html(
        to_email="op@example.com",
        invite_url="https://macmarket.io/sign-up?token=abc",
        display_name="Operator",
        invited_by="admin@example.com",
    )
    assert _DATA_URI_RE.search(html), "invite email must inline the logo as base64"
    assert "logos.macmarket.io" not in html


def test_render_approval_html_inlines_logo() -> None:
    html = render_approval_html(
        to_email="op@example.com",
        display_name="Operator",
        console_url="https://macmarket.io",
    )
    assert _DATA_URI_RE.search(html), "approval email must inline the logo as base64"


def test_render_rejection_html_inlines_logo() -> None:
    html = render_rejection_html(
        to_email="op@example.com",
        display_name="Operator",
    )
    assert _DATA_URI_RE.search(html), "rejection email must inline the logo as base64"


def test_render_invite_html_links_welcome_and_signin() -> None:
    """Pass 5 — Track B: the invite email must surface both the welcome guide
    URL and the sign-in URL, each as its own primary CTA. The HTML body is
    asserted directly so any future template refactor that drops one of the
    two links will fail this gate."""
    welcome_url = "https://macmarket.io/welcome"
    invite_url = "https://macmarket.io/sign-up?invite_token=abc&email=op@example.com"
    html = render_invite_html(
        to_email="op@example.com",
        invite_url=invite_url,
        display_name="Operator",
        invited_by="admin@example.com",
        welcome_url=welcome_url,
    )
    # Both URLs appear as href targets (HTML entity-escaped form for the
    # ampersand-bearing invite URL — _e() escapes & into &amp;).
    escaped_invite_url = "https://macmarket.io/sign-up?invite_token=abc&amp;email=op@example.com"
    assert f'href="{welcome_url}"' in html, "invite must link to the welcome guide"
    assert f'href="{escaped_invite_url}"' in html, "invite must link to the sign-in URL"
    # Welcome CTA copy is present
    assert "Read the welcome guide" in html
    # Sign-in CTA copy is present
    assert "Sign in" in html
    # Auth-gate orientation paragraph is preserved
    assert "Cloudflare Access PIN" in html
    assert "Clerk sign-in" in html
