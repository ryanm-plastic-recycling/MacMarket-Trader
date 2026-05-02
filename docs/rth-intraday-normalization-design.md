# RTH Intraday Normalization Design

MacMarket v1 equity analysis uses regular trading hours only: 9:30 AM to
4:00 PM America/New_York. Provider intraday aggregates may include premarket or
after-hours bars, so 1H and 4H equity workflows normalize provider data before
charts, Analysis, Recommendations, Opportunity Intelligence inputs, and Market
Risk Calendar data-quality checks consume it.

This is research/paper-only market-data hardening. It does not add day trading,
live trading, broker routing, active paper position management, automated exits,
or LLM-driven trade decisions. LLMs may explain session/data-quality context,
but deterministic services own ranking, approval, entry, invalidation, targets,
sizing, paper-order gating, and risk-calendar state.

## Provider Strategy

Polygon/Massive remains the provider boundary. For 1H and 4H equity output,
MacMarket requests 30-minute source aggregates, sorts by timestamp, filters
source bars to the regular session, and re-aggregates locally.

30-minute source bars are the current base because every canonical 1H and 4H
RTH bucket boundary lands on a 30-minute mark. This keeps provider requests much
smaller than 5-minute data while avoiding provider 1H/4H session ambiguity.

## Canonical Buckets

1H regular-hours buckets:

- 9:30-10:30 ET
- 10:30-11:30 ET
- 11:30-12:30 ET
- 12:30-13:30 ET
- 13:30-14:30 ET
- 14:30-15:30 ET
- 15:30-16:00 ET partial RTH bar

4H regular-hours buckets:

- 9:30-13:30 ET
- 13:30-16:00 ET partial RTH bar

The final buckets are partial because the U.S. equity regular session is 6.5
hours, not evenly divisible into 1H or 4H blocks.

## Aggregation Rules

Bars are converted with America/New_York timezone rules, including DST. UTC
date boundaries are not used as market-session boundaries.

Premarket source bars before 9:30 ET are excluded. Source bars at or after
16:00 ET are excluded. Empty buckets are skipped rather than fabricated.

Local OHLCV aggregation is deterministic:

- open: first source bar open in the bucket
- high: max source high
- low: min source low
- close: last source bar close in the bucket
- volume: sum source volume

Output bars are returned ascending, unique by timestamp, and latest-window
trimmed after RTH aggregation.

## Provenance

Normalized bars and chart payloads expose:

- provider
- source_timeframe
- output_timeframe
- session_policy: regular_hours
- source_session_policy: provider_session
- filtered_extended_hours_count
- rth_bucket_count
- first_bar_timestamp
- last_bar_timestamp

The UI can show this compactly as "Session: Regular hours" without turning the
operator console into a metadata wall.

## Risk Calendar Interaction

Market Risk Calendar treats RTH-normalized 1H/4H equity bars as normal for
session-policy data quality. If provider-session intraday bars are supplied to
an RTH-required equity workflow, the deterministic risk gate returns a data
quality caution by default, or a data_quality_block when configured to block.

Opportunity Intelligence may include and explain that data-quality state, but it
cannot override it or alter deterministic trade fields.

## Remaining Limitations

The current base timeframe is 30 minutes. If future indicators require finer
session detail, the provider base can move to 15-minute or 5-minute bars without
changing the canonical output contract. Holiday and half-day bucket truncation
still depends on broader exchange-calendar integration.
