"""
Professional HTML email templates for MacMarket Trader.

Rules:
- Inline CSS only (no <style> tags — stripped by most clients)
- Table-based layout (no flexbox/grid — widest email-client support)
- All user-supplied strings HTML-escaped before insertion
- Returns both HTML and plain-text so callers can populate both fields
"""

from __future__ import annotations

import base64
import html as _html
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Colour palette (referenced inline throughout)
# ---------------------------------------------------------------------------
_BG_PAGE = "#060d13"
_BG_CARD = "#0f1923"
_BG_CARD_ALT = "#0b1720"
_BG_DARK = "#0a1520"
_BORDER = "#1e2d3d"
_GREEN = "#21c06e"
_GREEN_BG = "#07200f"
_GREEN_BORDER = "#164f30"
_RED = "#e05555"
_RED_BG = "#200a0a"
_RED_BORDER = "#7a2222"
_YELLOW = "#f0c040"
_TEXT_PRIMARY = "#f0f4f8"
_TEXT_SECONDARY = "#8892a4"
_TEXT_MUTED = "#4a5568"


# ---------------------------------------------------------------------------
# Logo loader
# ---------------------------------------------------------------------------

def _load_logo_base64() -> str | None:
    """Return a data URI for the brand lockup PNG, or None if the file is not found.

    Resolves relative to this module's location:
        <repo-root>/apps/web/public/brand/square_console_ticks_lockup_light.png
    """
    try:
        logo_path = (
            Path(__file__).resolve().parent.parent.parent
            / "apps" / "web" / "public" / "brand"
            / "square_console_ticks_lockup_light.png"
        )
        data = logo_path.read_bytes()
        encoded = base64.b64encode(data).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    except Exception:  # noqa: BLE001
        return None


# Module-level cache — encode once per process start.
_LOGO_DATA_URI: str | None = _load_logo_base64()


def _logo_img(width: int = 200) -> str:
    """Return an <img> tag using the logo, or the CSS text lockup fallback.

    Priority:
    1. BRAND_LOGO_URL env var (URL-based — works for hosted deployments)
    2. Embedded base64 data URI (embedded — works without external access)
    3. CSS text lockup fallback (no broken image ever rendered)
    """
    brand_logo_url = os.environ.get("BRAND_LOGO_URL", "").strip()
    if brand_logo_url:
        return (
            f'<img src="{_html.escape(brand_logo_url)}" alt="MacMarket Trader" width="{width}" '
            f'style="display:block;max-width:{width}px;height:auto;border:0;" />'
        )
    if _LOGO_DATA_URI:
        return (
            f'<img src="{_LOGO_DATA_URI}" alt="MacMarket Trader" width="{width}" '
            f'style="display:block;max-width:{width}px;height:auto;border:0;" />'
        )
    # CSS fallback: table-based monogram + name lockup
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0">'
        f'<tr>'
        f'<td align="center" valign="middle" width="46" '
        f'style="width:46px;height:46px;line-height:46px;background-color:{_BG_DARK};'
        f'border:2px solid {_GREEN};border-radius:50%;'
        f'font-family:Georgia,serif;font-size:22px;font-weight:700;color:{_TEXT_PRIMARY};">M</td>'
        f'<td width="12" style="width:12px;">&nbsp;</td>'
        f'<td valign="middle">'
        f'<p style="margin:0;font-family:Arial,sans-serif;font-size:28px;font-weight:700;'
        f'color:{_TEXT_PRIMARY};line-height:1;">MacMarket</p>'
        f'<p style="margin:2px 0 0 1px;font-family:Arial,sans-serif;font-size:12px;'
        f'font-weight:700;letter-spacing:3px;color:{_GREEN};text-transform:uppercase;'
        f'line-height:1;">TRADER</p>'
        f'</td>'
        f'</tr>'
        f'</table>'
    )


# ---------------------------------------------------------------------------
# Tiny helpers
# ---------------------------------------------------------------------------

def _e(value: object) -> str:
    """HTML-escape a value for safe inline insertion."""
    return _html.escape(str(value))


def _fmt_dt(iso_str: str) -> str:
    """Return a human-readable UTC timestamp from an ISO-8601 string."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).strftime("%B %d, %Y &nbsp;&middot;&nbsp; %H:%M UTC")
    except Exception:  # noqa: BLE001
        return _e(iso_str)


def _conviction_badge(tier: str) -> str:
    tier = (tier or "LOW").upper()
    styles: dict[str, tuple[str, str, str]] = {
        "HIGH": (_GREEN_BG, _GREEN, _GREEN_BORDER),
        "MEDIUM": ("#2a2000", _YELLOW, "#7a5e00"),
        "LOW": ("#1a2433", _TEXT_SECONDARY, "#2a3a4d"),
    }
    bg, fg, bd = styles.get(tier, styles["LOW"])
    return (
        f'<span style="display:inline-block;background-color:{bg};color:{fg};'
        f'border:1px solid {bd};font-family:Arial,sans-serif;font-size:9px;'
        f'font-weight:700;letter-spacing:1px;text-transform:uppercase;'
        f'padding:2px 7px;border-radius:3px;vertical-align:middle;">{_e(tier)}</span>'
    )


def _source_badge(source: str) -> str:
    label = source.split("(")[-1].rstrip(")").strip() if "(" in source else source
    is_live = "fallback" not in source.lower()
    if is_live:
        bg, fg, bd = _GREEN_BG, _GREEN, _GREEN_BORDER
    else:
        bg, fg, bd = "#1a2433", _TEXT_SECONDARY, "#2a3a4d"
    return (
        f'<span style="display:inline-block;background-color:{bg};color:{fg};'
        f'border:1px solid {bd};font-family:Arial,sans-serif;font-size:9px;'
        f'font-weight:700;letter-spacing:1px;text-transform:uppercase;'
        f'padding:2px 7px;border-radius:3px;vertical-align:middle;">{_e(label)}</span>'
    )


def _level_box(label: str, value: str, fg: str, bg: str, border: str) -> str:
    """Return a mini level-pill table cell (label over value)."""
    return (
        f'<td style="padding:0 5px 0 0;">'
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0">'
        f'<tr><td style="background-color:{bg};border:1px solid {border};'
        f'border-radius:4px;padding:5px 9px;">'
        f'<p style="margin:0 0 2px 0;font-family:Arial,sans-serif;font-size:9px;'
        f'font-weight:600;color:{_TEXT_SECONDARY};text-transform:uppercase;'
        f'letter-spacing:0.5px;">{_e(label)}</p>'
        f'<p style="margin:0;font-family:Arial,sans-serif;font-size:12px;'
        f'font-weight:700;color:{fg};white-space:nowrap;">{_e(value)}</p>'
        f'</td></tr></table>'
        f'</td>'
    )


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _header(schedule_name: str, ran_at: str, source: str) -> str:
    date_str = _fmt_dt(ran_at)
    return (
        f'<tr><td style="background-color:{_BG_CARD};padding:28px 28px 22px 28px;">'
        # Logo
        f'<div style="margin:0 0 12px 0;">{_logo_img(200)}</div>'
        # Subtitle
        f'<p style="margin:0 0 16px 0;font-family:Arial,sans-serif;font-size:10px;'
        f'font-weight:600;letter-spacing:2px;color:{_TEXT_SECONDARY};text-transform:uppercase;">'
        f'Morning Strategy Intelligence</p>'
        # Schedule name + meta
        f'<h1 style="margin:0 0 12px 0;font-family:Arial,sans-serif;font-size:23px;'
        f'font-weight:700;color:{_TEXT_PRIMARY};line-height:1.2;">{_e(schedule_name)}</h1>'
        f'<p style="margin:0;font-family:Arial,sans-serif;font-size:12px;color:{_TEXT_SECONDARY};">'
        f'{date_str} &nbsp;&nbsp; {_source_badge(source)}'
        f'</p>'
        f'</td></tr>'
    )


def _accent_line() -> str:
    return (
        f'<tr><td style="background-color:{_GREEN};height:2px;'
        f'font-size:0;line-height:0;">&nbsp;</td></tr>'
    )


def _summary_bar(
    top_n: int,
    watchlist_n: int,
    no_trade_n: int,
    high_n: int,
    med_n: int,
    low_n: int,
) -> str:
    def _stat(value: str, label: str, color: str, border_left: bool = False) -> str:
        border = f'border-left:1px solid {_BORDER};' if border_left else ''
        return (
            f'<td align="center" style="{border}padding:12px 8px;">'
            f'<p style="margin:0;font-family:Arial,sans-serif;font-size:26px;'
            f'font-weight:700;color:{color};">{_e(value)}</p>'
            f'<p style="margin:4px 0 0 0;font-family:Arial,sans-serif;font-size:9px;'
            f'font-weight:600;color:{_TEXT_SECONDARY};text-transform:uppercase;'
            f'letter-spacing:1px;">{_e(label)}</p>'
            f'</td>'
        )

    conviction_html = (
        f'<td align="center" style="border-left:1px solid {_BORDER};padding:12px 8px;">'
        f'<p style="margin:0;font-family:Arial,sans-serif;font-size:13px;font-weight:700;">'
        f'<span style="color:{_GREEN};">H&nbsp;{high_n}</span>'
        f'&nbsp;<span style="color:{_YELLOW};">M&nbsp;{med_n}</span>'
        f'&nbsp;<span style="color:{_TEXT_SECONDARY};">L&nbsp;{low_n}</span>'
        f'</p>'
        f'<p style="margin:4px 0 0 0;font-family:Arial,sans-serif;font-size:9px;'
        f'font-weight:600;color:{_TEXT_SECONDARY};text-transform:uppercase;'
        f'letter-spacing:1px;">Conviction</p>'
        f'</td>'
    )

    return (
        f'<tr><td style="background-color:{_BG_DARK};padding:4px 28px 4px 28px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        f'<tr>'
        + _stat(str(top_n), "Top Candidates", _GREEN)
        + _stat(str(watchlist_n), "Watchlist", _YELLOW, border_left=True)
        + _stat(str(no_trade_n), "No Trade", _TEXT_SECONDARY, border_left=True)
        + conviction_html
        + f'</tr></table>'
        f'</td></tr>'
    )


def _section_label(text: str) -> str:
    return (
        f'<tr><td style="background-color:{_BG_PAGE};'
        f'padding:20px 28px 8px 28px;">'
        f'<p style="margin:0;font-family:Arial,sans-serif;font-size:10px;'
        f'font-weight:700;color:{_GREEN};text-transform:uppercase;'
        f'letter-spacing:2px;">{_e(text)}</p>'
        f'</td></tr>'
    )


def _candidate_row(candidate: dict, idx: int) -> str:
    bg = _BG_CARD if idx % 2 == 0 else _BG_CARD_ALT
    rank = int(candidate.get("rank") or (idx + 1))
    symbol = str(candidate.get("symbol") or "")
    strategy = str(candidate.get("strategy") or "")
    tier = str(candidate.get("conviction_tier") or "LOW").upper()
    entry_zone = str(candidate.get("entry_zone") or "—").replace(" - ", " \u2013 ")
    invalidation = str(candidate.get("invalidation") or "—")
    targets = str(candidate.get("targets") or "—")
    expected_rr = candidate.get("expected_rr")
    rr_str = f"{expected_rr:.1f}\u00d7" if isinstance(expected_rr, (int, float)) else "—"
    score = candidate.get("score")
    score_str = f"{score:.3f}" if isinstance(score, (int, float)) else "—"
    thesis = str(candidate.get("thesis") or "")
    trigger = str(candidate.get("trigger") or "")

    level_row = (
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0">'
        f'<tr>'
        + _level_box("Entry", entry_zone, _GREEN, _GREEN_BG, _GREEN_BORDER)
        + _level_box("Stop", invalidation, _RED, _RED_BG, _RED_BORDER)
        + _level_box("T1 / T2", targets, _GREEN, _GREEN_BG, _GREEN_BORDER)
        + _level_box("R:R", rr_str, _TEXT_PRIMARY, _BG_CARD, _BORDER)
        + _level_box("Score", score_str, _TEXT_PRIMARY, _BG_CARD, _BORDER)
        + f'</tr></table>'
    )

    trigger_html = (
        f'<p style="margin:6px 0 0 0;font-family:Arial,sans-serif;font-size:10px;'
        f'color:{_TEXT_MUTED};">'
        f'<strong style="color:{_TEXT_SECONDARY};">Trigger:</strong>&nbsp;{_e(trigger)}</p>'
    ) if trigger else ""

    return (
        f'<tr>'
        f'<td style="background-color:{bg};padding:16px 28px;'
        f'border-bottom:1px solid {_BORDER};">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        f'<tr>'
        # Rank badge
        f'<td width="36" style="vertical-align:top;">'
        f'<p style="margin:0;width:28px;height:28px;line-height:28px;text-align:center;'
        f'background-color:{_BORDER};border-radius:4px;font-family:Arial,sans-serif;'
        f'font-size:11px;font-weight:700;color:{_TEXT_SECONDARY};">#{_e(rank)}</p>'
        f'</td>'
        # Content
        f'<td style="vertical-align:top;padding-left:12px;">'
        f'<p style="margin:0 0 8px 0;">'
        f'<span style="font-family:Arial,sans-serif;font-size:22px;font-weight:700;'
        f'color:{_TEXT_PRIMARY};">{_e(symbol)}</span>'
        f'&nbsp;&nbsp;'
        + _conviction_badge(tier)
        + f'&nbsp;&nbsp;'
        f'<span style="font-family:Arial,sans-serif;font-size:11px;'
        f'color:{_TEXT_SECONDARY};">{_e(strategy)}</span>'
        f'</p>'
        + level_row
        + f'<p style="margin:8px 0 0 0;font-family:Arial,sans-serif;font-size:11px;'
        f'font-style:italic;color:{_TEXT_SECONDARY};line-height:1.5;">{_e(thesis)}</p>'
        + trigger_html
        + f'</td>'
        f'</tr></table>'
        f'</td></tr>'
    )


def _watchlist_section(watchlist_only: list[dict]) -> str:
    if not watchlist_only:
        return ""
    rows = []
    for item in watchlist_only:
        symbol = str(item.get("symbol") or "")
        strategy = str(item.get("strategy") or "")
        score = item.get("score")
        score_str = f"{score:.3f}" if isinstance(score, (int, float)) else "—"
        rows.append(
            f'<tr>'
            f'<td style="padding:6px 0;border-bottom:1px solid {_BORDER};">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
            f'<tr>'
            f'<td><span style="font-family:Arial,sans-serif;font-size:13px;font-weight:700;'
            f'color:{_TEXT_PRIMARY};">{_e(symbol)}</span>'
            f'&nbsp;&nbsp;<span style="font-family:Arial,sans-serif;font-size:11px;'
            f'color:{_TEXT_SECONDARY};">{_e(strategy)}</span></td>'
            f'<td align="right"><span style="font-family:Arial,sans-serif;font-size:11px;'
            f'font-weight:600;color:{_YELLOW};">{score_str}</span></td>'
            f'</tr></table>'
            f'</td></tr>'
        )

    return (
        _section_label("Watchlist")
        + f'<tr><td style="background-color:{_BG_DARK};padding:12px 28px 16px 28px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        + "".join(rows)
        + f'</table></td></tr>'
    )


def _no_trade_section(no_trade: list[dict]) -> str:
    if not no_trade:
        return ""
    symbols = ", ".join(str(c.get("symbol") or "") for c in no_trade if c.get("symbol"))
    return (
        _section_label("Screened Out — No Trade")
        + f'<tr><td style="background-color:{_BG_PAGE};padding:8px 28px 20px 28px;">'
        f'<p style="margin:0;font-family:Arial,sans-serif;font-size:11px;'
        f'color:{_TEXT_MUTED};">{_e(symbols)} did not meet minimum conviction or '
        f'liquidity thresholds.</p>'
        f'</td></tr>'
    )


def _empty_state_row(message: str) -> str:
    return (
        f'<tr><td style="background-color:{_BG_PAGE};padding:24px 28px;">'
        f'<p style="margin:0;font-family:Arial,sans-serif;font-size:12px;'
        f'color:{_TEXT_MUTED};font-style:italic;">{_e(message)}</p>'
        f'</td></tr>'
    )


def _footer(ran_at: str) -> str:
    try:
        dt = datetime.fromisoformat(ran_at.replace("Z", "+00:00"))
        ts = dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:  # noqa: BLE001
        ts = ran_at
    return (
        f'<tr><td style="background-color:{_BG_PAGE};border-top:1px solid {_BORDER};'
        f'padding:20px 28px;">'
        f'<p style="margin:0;font-family:Arial,sans-serif;font-size:11px;'
        f'color:{_TEXT_MUTED};text-align:center;">'
        f'Generated by <strong style="color:{_TEXT_SECONDARY};">MacMarket Trader</strong>'
        f'&nbsp;&middot;&nbsp;{_e(ts)}'
        f'</p>'
        f'<p style="margin:8px 0 0 0;font-family:Arial,sans-serif;font-size:10px;'
        f'color:#2d3748;text-align:center;">'
        f'This is not financial advice. For operator review only.'
        f'</p>'
        f'</td></tr>'
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_strategy_report_html(
    *,
    schedule_name: str,
    ran_at: str,
    source: str,
    top_candidates: list[dict],
    watchlist_only: list[dict],
    no_trade: list[dict],
    summary: dict,
) -> str:
    """Return a complete HTML email string for a strategy report run."""
    tier_counts: Counter[str] = Counter(
        str(c.get("conviction_tier") or "LOW").upper() for c in top_candidates
    )
    top_n = summary.get("top_candidate_count", len(top_candidates))
    watchlist_n = summary.get("watchlist_count", len(watchlist_only))
    no_trade_n = summary.get("no_trade_count", len(no_trade))

    candidate_rows = "".join(
        _candidate_row(c, i) for i, c in enumerate(top_candidates)
    )
    if not candidate_rows:
        candidate_rows = _empty_state_row(
            "No candidates met the minimum score threshold for this run."
        )

    body_rows = (
        _header(schedule_name, ran_at, source)
        + _accent_line()
        + _summary_bar(
            top_n,
            watchlist_n,
            no_trade_n,
            tier_counts.get("HIGH", 0),
            tier_counts.get("MEDIUM", 0),
            tier_counts.get("LOW", 0),
        )
        + _section_label("Top Candidates")
        + candidate_rows
        + _watchlist_section(watchlist_only)
        + _no_trade_section(no_trade)
        + _footer(ran_at)
    )

    return (
        "<!DOCTYPE html>"
        '<html lang="en">'
        "<head>"
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1.0">'
        f"<title>{_e(schedule_name)}</title>"
        "</head>"
        f'<body style="margin:0;padding:0;background-color:{_BG_PAGE};">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background-color:{_BG_PAGE};">'
        f'<tr><td align="center" style="padding:20px 12px;">'
        f'<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" '
        f'style="max-width:600px;width:100%;border:1px solid {_BORDER};border-radius:6px;'
        f'overflow:hidden;">'
        + body_rows
        + "</table>"
        "</td></tr>"
        "</table>"
        "</body>"
        "</html>"
    )


def render_strategy_report_text(
    *,
    schedule_name: str,
    ran_at: str,
    source: str,
    top_candidates: list[dict],
    watchlist_only: list[dict],
    no_trade: list[dict],
    summary: dict,
) -> str:
    """Return a plain-text fallback for the strategy report email."""
    try:
        dt = datetime.fromisoformat(ran_at.replace("Z", "+00:00"))
        date_str = dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:  # noqa: BLE001
        date_str = ran_at

    lines: list[str] = [
        "=" * 58,
        "MacMarket Trader — Strategy Report",
        schedule_name,
        f"{date_str}  |  Source: {source}",
        "=" * 58,
        "",
        f"Top Candidates : {summary.get('top_candidate_count', len(top_candidates))}",
        f"Watchlist Only : {summary.get('watchlist_count', len(watchlist_only))}",
        f"No Trade       : {summary.get('no_trade_count', len(no_trade))}",
        "",
    ]

    if top_candidates:
        lines.append("TOP CANDIDATES")
        lines.append("-" * 58)
        for c in top_candidates:
            rank = c.get("rank", "?")
            symbol = c.get("symbol", "")
            strategy = c.get("strategy", "")
            tier = c.get("conviction_tier", "LOW")
            entry = c.get("entry_zone", "—")
            stop = c.get("invalidation", "—")
            targets = c.get("targets", "—")
            rr = c.get("expected_rr")
            rr_str = f"{rr:.1f}x" if isinstance(rr, (int, float)) else "—"
            score = c.get("score")
            score_str = f"{score:.3f}" if isinstance(score, (int, float)) else "—"
            thesis = c.get("thesis", "")
            lines += [
                f"#{rank}  {symbol}  [{tier}]  {strategy}",
                f"    Entry: {entry}  |  Stop: {stop}  |  Targets: {targets}",
                f"    R:R {rr_str}  |  Score {score_str}",
                f"    {thesis}",
                "",
            ]

    if watchlist_only:
        lines.append("WATCHLIST")
        lines.append("-" * 58)
        for c in watchlist_only:
            score = c.get("score")
            score_str = f"{score:.3f}" if isinstance(score, (int, float)) else "—"
            lines.append(f"  {c.get('symbol', '')}  {c.get('strategy', '')}  {score_str}")
        lines.append("")

    if no_trade:
        syms = ", ".join(str(c.get("symbol", "")) for c in no_trade if c.get("symbol"))
        lines += ["NO TRADE", f"  {syms}", ""]

    lines += [
        "=" * 58,
        f"Generated by MacMarket Trader  |  {date_str}",
        "This is not financial advice. For operator review only.",
    ]

    return "\n".join(lines)


def render_approval_html(
    *,
    to_email: str,
    display_name: str = "",
    console_url: str = "http://localhost:9500",
) -> str:
    """Return a branded dark-theme HTML approval notification email."""
    greeting = f"Hi {_e(display_name)}," if display_name else "Hi,"
    safe_console_url = _e(console_url.rstrip("/"))
    body_rows = (
        # header
        f'<tr><td style="background-color:{_BG_CARD};padding:28px 28px 22px 28px;">'
        f'<div style="margin:0 0 14px 0;">{_logo_img(180)}</div>'
        f'<h1 style="margin:0 0 8px 0;font-family:Arial,sans-serif;font-size:22px;'
        f'font-weight:700;color:{_TEXT_PRIMARY};line-height:1.2;">'
        f'You&rsquo;ve been approved &mdash; welcome to MacMarket</h1>'
        f'<p style="margin:0;font-family:Arial,sans-serif;font-size:12px;color:{_TEXT_SECONDARY};">'
        f'Invite-only &middot; Operator console &middot; Private alpha'
        f'</p>'
        f'</td></tr>'
        # accent line
        f'<tr><td style="background-color:{_GREEN};height:2px;font-size:0;line-height:0;">&nbsp;</td></tr>'
        # body
        f'<tr><td style="background-color:{_BG_CARD};padding:28px;">'
        f'<p style="margin:0 0 16px 0;font-family:Arial,sans-serif;font-size:14px;color:{_TEXT_PRIMARY};">{greeting}</p>'
        f'<p style="margin:0 0 20px 0;font-family:Arial,sans-serif;font-size:14px;color:{_TEXT_SECONDARY};line-height:1.7;">'
        f'Your operator account is approved and ready. Sign in to access the console and '
        f'start your first guided paper trade: '
        f'<strong style="color:{_TEXT_PRIMARY};">Analyze &rarr; Recommendation &rarr; Replay &rarr; Paper Order</strong>.'
        f'</p>'
        # CTA button
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:8px 0 0 0;">'
        f'<tr><td style="background-color:{_GREEN};border-radius:4px;text-align:center;">'
        f'<a href="{safe_console_url}" '
        f'style="display:inline-block;font-family:Arial,sans-serif;font-size:14px;font-weight:700;'
        f'color:#000000;text-decoration:none;padding:12px 28px;border-radius:4px;">'
        f'Open the console</a>'
        f'</td></tr></table>'
        f'</td></tr>'
        # footer
        f'<tr><td style="background-color:{_BG_DARK};padding:16px 28px;border-top:1px solid {_BORDER};">'
        f'<p style="margin:0;font-family:Arial,sans-serif;font-size:10px;color:{_TEXT_MUTED};text-align:center;">'
        f'MacMarket &nbsp;&middot;&nbsp; Invite-only private alpha'
        f'&nbsp;&middot;&nbsp; Questions? Reply to this email.'
        f'</p>'
        f'</td></tr>'
    )
    return (
        "<!DOCTYPE html>"
        '<html lang="en">'
        "<head>"
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1.0">'
        "<title>MacMarket Trader — Account approved</title>"
        "</head>"
        f'<body style="margin:0;padding:0;background-color:{_BG_PAGE};">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background-color:{_BG_PAGE};">'
        f'<tr><td align="center" style="padding:20px 12px;">'
        f'<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" '
        f'style="max-width:600px;width:100%;border:1px solid {_BORDER};border-radius:6px;overflow:hidden;">'
        + body_rows
        + "</table>"
        "</td></tr>"
        "</table>"
        "</body>"
        "</html>"
    )


def render_rejection_html(
    *,
    to_email: str,
    display_name: str = "",
) -> str:
    """Return a branded dark-theme HTML rejection / access-denied notification email."""
    greeting = f"Hi {_e(display_name)}," if display_name else "Hi,"
    body_rows = (
        # header
        f'<tr><td style="background-color:{_BG_CARD};padding:28px 28px 22px 28px;">'
        f'<div style="margin:0 0 14px 0;">{_logo_img(180)}</div>'
        f'<h1 style="margin:0 0 8px 0;font-family:Arial,sans-serif;font-size:22px;'
        f'font-weight:700;color:{_TEXT_PRIMARY};line-height:1.2;">'
        f'Account access update</h1>'
        f'<p style="margin:0;font-family:Arial,sans-serif;font-size:12px;color:{_TEXT_SECONDARY};">'
        f'MacMarket &middot; Invite-only private alpha'
        f'</p>'
        f'</td></tr>'
        # accent line (red for rejection)
        f'<tr><td style="background-color:{_RED};height:2px;font-size:0;line-height:0;">&nbsp;</td></tr>'
        # body
        f'<tr><td style="background-color:{_BG_CARD};padding:28px;">'
        f'<p style="margin:0 0 16px 0;font-family:Arial,sans-serif;font-size:14px;color:{_TEXT_PRIMARY};">{greeting}</p>'
        f'<p style="margin:0 0 16px 0;font-family:Arial,sans-serif;font-size:14px;color:{_TEXT_SECONDARY};line-height:1.7;">'
        f'Your account request has not been approved at this time. '
        f'If you believe this is an error, please reply to this email or contact your administrator.'
        f'</p>'
        f'</td></tr>'
        # footer
        f'<tr><td style="background-color:{_BG_DARK};padding:16px 28px;border-top:1px solid {_BORDER};">'
        f'<p style="margin:0;font-family:Arial,sans-serif;font-size:10px;color:{_TEXT_MUTED};text-align:center;">'
        f'MacMarket &nbsp;&middot;&nbsp; Invite-only private alpha'
        f'&nbsp;&middot;&nbsp; Questions? Reply to this email.'
        f'</p>'
        f'</td></tr>'
    )
    return (
        "<!DOCTYPE html>"
        '<html lang="en">'
        "<head>"
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1.0">'
        "<title>MacMarket Trader — Account access update</title>"
        "</head>"
        f'<body style="margin:0;padding:0;background-color:{_BG_PAGE};">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background-color:{_BG_PAGE};">'
        f'<tr><td align="center" style="padding:20px 12px;">'
        f'<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" '
        f'style="max-width:600px;width:100%;border:1px solid {_BORDER};border-radius:6px;overflow:hidden;">'
        + body_rows
        + "</table>"
        "</td></tr>"
        "</table>"
        "</body>"
        "</html>"
    )


def render_invite_html(
    *,
    to_email: str,
    invite_url: str,
    display_name: str = "",
    invited_by: str = "",
) -> str:
    """Return a branded dark-theme HTML invite email."""
    greeting = f"Hi {_e(display_name)}," if display_name else "Hi,"
    sender_line = (
        f'<p style="margin:12px 0 0 0;font-family:Arial,sans-serif;font-size:13px;'
        f'color:{_TEXT_SECONDARY};">Invited by: {_e(invited_by)}</p>'
        if invited_by
        else ""
    )
    body_rows = (
        # header
        f'<tr><td style="background-color:{_BG_CARD};padding:28px 28px 22px 28px;">'
        f'<div style="margin:0 0 14px 0;">{_logo_img(180)}</div>'
        f'<h1 style="margin:0 0 8px 0;font-family:Arial,sans-serif;font-size:22px;'
        f'font-weight:700;color:{_TEXT_PRIMARY};line-height:1.2;">You&rsquo;re invited to the private alpha</h1>'
        f'<p style="margin:0;font-family:Arial,sans-serif;font-size:12px;color:{_TEXT_SECONDARY};">'
        f'Invite-only · Early access · Operator console'
        f'</p>'
        f'</td></tr>'
        # accent line
        f'<tr><td style="background-color:{_GREEN};height:2px;font-size:0;line-height:0;">&nbsp;</td></tr>'
        # body
        f'<tr><td style="background-color:{_BG_CARD};padding:28px;">'
        f'<p style="margin:0 0 16px 0;font-family:Arial,sans-serif;font-size:14px;color:{_TEXT_PRIMARY};">{greeting}</p>'
        f'<p style="margin:0 0 16px 0;font-family:Arial,sans-serif;font-size:14px;color:{_TEXT_SECONDARY};line-height:1.6;">'
        f'You have been personally invited to <strong style="color:{_TEXT_PRIMARY};">MacMarket Trader</strong>, '
        f'an invite-only private alpha for professional operators. '
        f'Click the button below to accept your invite and complete sign-up via Clerk.'
        f'</p>'
        # CTA button
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:24px 0;">'
        f'<tr><td style="background-color:{_GREEN};border-radius:4px;text-align:center;">'
        f'<a href="{_e(invite_url)}" '
        f'style="display:inline-block;font-family:Arial,sans-serif;font-size:14px;font-weight:700;'
        f'color:#000000;text-decoration:none;padding:12px 28px;border-radius:4px;">'
        f'Accept Invite &amp; Sign Up</a>'
        f'</td></tr></table>'
        f'<p style="margin:16px 0 0 0;font-family:Arial,sans-serif;font-size:11px;color:{_TEXT_MUTED};line-height:1.5;">'
        f'If the button does not work, copy and paste this link into your browser:<br>'
        f'<span style="color:{_TEXT_SECONDARY};word-break:break-all;">{_e(invite_url)}</span>'
        f'</p>'
        f'{sender_line}'
        f'</td></tr>'
        # note
        f'<tr><td style="background-color:{_BG_DARK};padding:16px 28px;border-top:1px solid {_BORDER};">'
        f'<p style="margin:0;font-family:Arial,sans-serif;font-size:11px;color:{_TEXT_MUTED};line-height:1.5;">'
        f'After sign-in your account will be pending admin approval before full access is granted. '
        f'This invite link is single-use and tied to your email address.'
        f'</p>'
        f'</td></tr>'
        # footer
        f'<tr><td style="background-color:{_BG_CARD};padding:16px 28px;border-top:1px solid {_BORDER};">'
        f'<p style="margin:0;font-family:Arial,sans-serif;font-size:10px;color:{_TEXT_MUTED};text-align:center;">'
        f'MacMarket Trader &nbsp;&middot;&nbsp; Invite-only private alpha'
        f'&nbsp;&middot;&nbsp; Not financial advice. Operator use only.'
        f'</p>'
        f'</td></tr>'
    )
    return (
        "<!DOCTYPE html>"
        '<html lang="en">'
        "<head>"
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1.0">'
        "<title>MacMarket Trader — You're invited</title>"
        "</head>"
        f'<body style="margin:0;padding:0;background-color:{_BG_PAGE};">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="background-color:{_BG_PAGE};">'
        f'<tr><td align="center" style="padding:20px 12px;">'
        f'<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" '
        f'style="max-width:600px;width:100%;border:1px solid {_BORDER};border-radius:6px;overflow:hidden;">'
        + body_rows
        + "</table>"
        "</td></tr>"
        "</table>"
        "</body>"
        "</html>"
    )
