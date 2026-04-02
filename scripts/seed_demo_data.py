"""Seed local deterministic demo data for operator console panes."""

from __future__ import annotations

import json

from macmarket_trader.dev.seed_demo import seed_demo_data


if __name__ == "__main__":
    print(json.dumps(seed_demo_data(), indent=2, sort_keys=True))
