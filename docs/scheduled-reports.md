# Scheduled strategy reports

MacMarket-Trader supports production-minded recurring strategy scans without embedding a brittle always-on scheduler inside web requests.

## Core model

- **Watchlists** store reusable symbol lists.
- **Strategy report schedules** define frequency (`daily`, `weekdays`, `weekly`), run time, timezone, enabled strategies, ranking preferences, top-N, and email target.
- **Strategy report runs** store ranked payloads and delivery audit history.

## Local-safe execution

Run due schedules from CLI:

```bash
python -m macmarket_trader.cli run-due-strategy-schedules
```

This command calls the same service layer as the API "run now" action and is designed to be wired to cron, Windows Task Scheduler, or a future worker process.

## Email provider behavior

With `EMAIL_PROVIDER=console`, report payloads are printed to stdout, including:

- Top trade candidates
- Watchlist-only monitor names
- No-trade rejected names
- Deterministic scoring fields and rank metadata

No external provider is required in local/dev mode.
