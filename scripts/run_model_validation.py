"""Generate local model validation and performance evidence without live providers."""

from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_EVIDENCE_DIR = Path(".tmp") / "evidence"
DEFAULT_DATABASE = Path("macmarket_trader.db")
BASELINE_SYMBOLS = ("SPY", "QQQ")
SECRET_PATTERNS = [
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bsk_(?:test|live)_[A-Za-z0-9]{12,}\b"),
    re.compile(r"\bre_[A-Za-z0-9]{12,}\b"),
    re.compile(r"\b(?:postgres|postgresql|mysql)://[^:\s]+:[^@\s]+@[^ \n\r\t]+"),
]


def timestamp() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")


def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def redact_text(value: str) -> str:
    redacted = value
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def redact_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: redact_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_payload(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def safe_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "approved"}:
            return True
        if lowered in {"false", "0", "no", "rejected"}:
            return False
    return None


def parse_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def dig(payload: dict[str, Any], *path: str) -> Any:
    current: Any = payload
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def distribution(values: list[str | None]) -> dict[str, int]:
    normalized = [str(value) if value not in {None, ""} else "unknown" for value in values]
    return dict(sorted(Counter(normalized).items()))


def numeric_summary(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"count": 0, "average": None, "min": None, "max": None}
    return {
        "count": len(values),
        "average": round(sum(values) / len(values), 6),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
    }


def table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {str(row["name"]) for row in rows}


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    return {str(row["name"]) for row in rows}


def fetch_table(conn: sqlite3.Connection, table: str, *, limit: int | None = None) -> list[dict[str, Any]]:
    sql = f'SELECT * FROM "{table}"'
    if limit is not None:
        sql += f" LIMIT {int(limit)}"
    rows = conn.execute(sql).fetchall()
    return [dict(row) for row in rows]


def recommendation_dimensions(row: dict[str, Any]) -> dict[str, Any]:
    payload = parse_json(row.get("payload"))
    approved = safe_bool(payload.get("approved"))
    outcome = str(payload.get("outcome") or "").lower()
    if approved is None and outcome:
        approved = outcome in {"approved", "paper_ready"}
    workflow = parse_json(payload.get("workflow"))
    return {
        "recommendation_id": row.get("recommendation_id"),
        "symbol": row.get("symbol") or payload.get("symbol"),
        "approved": approved,
        "outcome": payload.get("outcome") or "unknown",
        "setup": dig(payload, "entry", "setup_type")
        or payload.get("setup_type")
        or workflow.get("source_strategy")
        or workflow.get("strategy"),
        "regime": dig(payload, "regime_context", "market_regime") or dig(payload, "regime", "market_regime"),
        "catalyst_type": dig(payload, "catalyst", "type") or dig(payload, "event", "source_type"),
        "timeframe": workflow.get("timeframe") or workflow.get("source_timeframe") or payload.get("timeframe"),
        "provider_source": workflow.get("market_data_source")
        or payload.get("market_data_source")
        or dig(payload, "provenance", "market_data_source"),
        "risk_calendar_state": dig(payload, "risk_calendar", "decision", "decision_state")
        or dig(payload, "risk_calendar", "state")
        or ("blocked" if "calendar" in outcome else None),
        "already_open": bool(payload.get("already_open") or workflow.get("already_open")),
        "expected_rr": safe_float(dig(payload, "quality", "expected_rr") or payload.get("expected_rr")),
        "created_at": row.get("created_at"),
    }


def analyze_recommendations(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    dims = [recommendation_dimensions(row) for row in rows]
    by_id = {
        str(item["recommendation_id"]): item
        for item in dims
        if item.get("recommendation_id") not in {None, ""}
    }
    approved = sum(1 for item in dims if item["approved"] is True)
    rejected = sum(1 for item in dims if item["approved"] is False)
    unknown = len(dims) - approved - rejected
    expected_rr_values = [value for value in (item.get("expected_rr") for item in dims) if isinstance(value, float)]
    risk_block_count = sum(
        1
        for item in dims
        if str(item.get("outcome") or "").lower() in {"calendar_blocked", "no_trade"}
        or str(item.get("risk_calendar_state") or "").lower() in {"no_trade", "restricted", "blocked"}
    )
    report = {
        "count": len(dims),
        "approved_count": approved,
        "rejected_count": rejected,
        "approval_unknown_count": unknown,
        "setup_type_distribution": distribution([item.get("setup") for item in dims]),
        "symbol_distribution": distribution([item.get("symbol") for item in dims]),
        "regime_distribution": distribution([item.get("regime") for item in dims]),
        "catalyst_type_distribution": distribution([item.get("catalyst_type") for item in dims]),
        "timeframe_distribution": distribution([item.get("timeframe") for item in dims]),
        "provider_source_distribution": distribution([item.get("provider_source") for item in dims]),
        "already_open_distribution": distribution(
            ["already_open" if item.get("already_open") else "fresh_or_unknown" for item in dims]
        ),
        "average_expected_rr": (
            round(sum(expected_rr_values) / len(expected_rr_values), 6) if expected_rr_values else None
        ),
        "expected_rr_summary": numeric_summary(expected_rr_values),
        "no_trade_or_risk_calendar_block_count": risk_block_count,
    }
    return report, by_id


def trade_net_pnl(row: dict[str, Any]) -> float:
    for key in ("net_pnl", "realized_pnl", "gross_pnl"):
        parsed = safe_float(row.get(key))
        if parsed is not None:
            return parsed
    return 0.0


def trade_gross_pnl(row: dict[str, Any]) -> float:
    return safe_float(row.get("gross_pnl")) or trade_net_pnl(row)


def trade_return_pct(row: dict[str, Any]) -> float | None:
    entry = safe_float(row.get("entry_price"))
    qty = safe_float(row.get("quantity"))
    if entry is None or qty is None or entry <= 0 or qty <= 0:
        return None
    return (trade_net_pnl(row) / (entry * qty)) * 100


def max_drawdown(values: list[float]) -> float | None:
    if not values:
        return None
    cumulative = 0.0
    peak = 0.0
    worst = 0.0
    for value in values:
        cumulative += value
        peak = max(peak, cumulative)
        worst = max(worst, peak - cumulative)
    return round(worst, 6)


def analyze_trades(rows: list[dict[str, Any]]) -> dict[str, Any]:
    closed = [row for row in rows if row.get("closed_at")]
    pnl_values = [trade_net_pnl(row) for row in closed]
    gross_values = [trade_gross_pnl(row) for row in closed]
    wins = [value for value in pnl_values if value > 0]
    losses = [value for value in pnl_values if value < 0]
    hold_seconds = [safe_float(row.get("hold_seconds")) for row in closed]
    hold_values = [value for value in hold_seconds if value is not None]
    returns = [value for value in (trade_return_pct(row) for row in closed) if value is not None]
    sorted_closed = sorted(closed, key=lambda row: str(row.get("closed_at") or row.get("opened_at") or ""))
    sorted_pnl = [trade_net_pnl(row) for row in sorted_closed]
    return {
        "count": len(rows),
        "closed_count": len(closed),
        "linked_to_recommendation_count": sum(1 for row in closed if row.get("recommendation_id")),
        "total_gross_pnl": round(sum(gross_values), 6),
        "total_net_pnl": round(sum(pnl_values), 6),
        "realized_paper_trade_pnl": round(sum(pnl_values), 6),
        "win_count": len(wins),
        "loss_count": len(losses),
        "win_rate": round(len(wins) / len(closed), 6) if closed else None,
        "average_win": round(sum(wins) / len(wins), 6) if wins else None,
        "average_loss": round(sum(losses) / len(losses), 6) if losses else None,
        "max_drawdown": max_drawdown(sorted_pnl),
        "holding_period_seconds": numeric_summary(hold_values),
        "holding_period_days": numeric_summary([value / 86400 for value in hold_values]),
        "paper_trade_return_pct": numeric_summary(returns),
    }


def empty_attribution_group() -> dict[str, Any]:
    return {"recommendation_count": 0, "closed_trade_count": 0, "total_net_pnl": 0.0, "wins": 0}


def finalize_attribution_group(group: dict[str, Any]) -> dict[str, Any]:
    trades = int(group["closed_trade_count"])
    wins = int(group.pop("wins"))
    total = float(group["total_net_pnl"])
    group["total_net_pnl"] = round(total, 6)
    group["win_rate"] = round(wins / trades, 6) if trades else None
    return group


def build_attribution(
    recommendations_by_id: dict[str, dict[str, Any]],
    trade_rows: list[dict[str, Any]],
) -> dict[str, dict[str, dict[str, Any]]]:
    dimensions = {
        "by_setup": "setup",
        "by_regime": "regime",
        "by_catalyst_type": "catalyst_type",
        "by_timeframe": "timeframe",
        "by_risk_calendar_state": "risk_calendar_state",
        "by_provider_source": "provider_source",
        "by_already_open_vs_fresh": "already_open_group",
    }
    groups: dict[str, dict[str, dict[str, Any]]] = {
        name: defaultdict(empty_attribution_group) for name in dimensions
    }
    for rec in recommendations_by_id.values():
        rec = dict(rec)
        rec["already_open_group"] = "already_open" if rec.get("already_open") else "fresh_or_unknown"
        for output_name, key in dimensions.items():
            label = str(rec.get(key) or "unknown")
            groups[output_name][label]["recommendation_count"] += 1

    for row in trade_rows:
        if not row.get("closed_at"):
            continue
        rec = recommendations_by_id.get(str(row.get("recommendation_id") or ""))
        if rec is None:
            rec = {"already_open_group": "unlinked", "setup": "unlinked", "regime": "unlinked", "catalyst_type": "unlinked", "timeframe": "unlinked", "risk_calendar_state": "unlinked", "provider_source": "unlinked"}
        else:
            rec = dict(rec)
            rec["already_open_group"] = "already_open" if rec.get("already_open") else "fresh_or_unknown"
        pnl = trade_net_pnl(row)
        for output_name, key in dimensions.items():
            label = str(rec.get(key) or "unknown")
            group = groups[output_name][label]
            group["closed_trade_count"] += 1
            group["total_net_pnl"] += pnl
            if pnl > 0:
                group["wins"] += 1

    return {
        name: {label: finalize_attribution_group(dict(group)) for label, group in sorted(values.items())}
        for name, values in groups.items()
    }


def fetch_baseline_rows(conn: sqlite3.Connection, symbol: str) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in conn.execute(
            """
            SELECT symbol, bar_date, close
            FROM daily_bars
            WHERE UPPER(symbol) = ?
            ORDER BY bar_date ASC
            """,
            (symbol.upper(),),
        ).fetchall()
    ]


def analyze_baseline(
    conn: sqlite3.Connection | None,
    tables: set[str],
    trade_summary: dict[str, Any],
) -> dict[str, Any]:
    missing: list[str] = []
    if conn is None or "daily_bars" not in tables:
        return {
            "status": "missing_data",
            "baselines": {},
            "missing_data": ["daily_bars table not available; SPY/QQQ baseline not computed."],
        }
    baselines: dict[str, dict[str, Any]] = {}
    for symbol in BASELINE_SYMBOLS:
        rows = fetch_baseline_rows(conn, symbol)
        if len(rows) < 2:
            missing.append(f"{symbol} has fewer than two daily bars.")
            continue
        first = rows[0]
        last = rows[-1]
        first_close = safe_float(first.get("close"))
        last_close = safe_float(last.get("close"))
        if first_close is None or last_close is None or first_close <= 0:
            missing.append(f"{symbol} baseline bars have invalid close values.")
            continue
        baselines[symbol] = {
            "start_date": first.get("bar_date"),
            "end_date": last.get("bar_date"),
            "start_close": first_close,
            "end_close": last_close,
            "return_pct": round(((last_close - first_close) / first_close) * 100, 6),
            "bar_count": len(rows),
        }
    return {
        "status": "available" if baselines else "missing_data",
        "comparison_basis": "baseline close-to-close return; paper results remain paper-only and are not live performance",
        "paper_trade_return_pct": trade_summary.get("paper_trade_return_pct"),
        "baselines": baselines,
        "missing_data": missing,
    }


def load_database(database: Path) -> tuple[sqlite3.Connection | None, set[str], list[str]]:
    resolved = database.resolve()
    if not resolved.exists():
        return None, set(), [f"database not found: {resolved}"]
    uri = f"file:{resolved.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn, table_names(conn), []


def generate_model_validation(
    *,
    database: Path = DEFAULT_DATABASE,
    evidence_dir: Path = DEFAULT_EVIDENCE_DIR,
) -> dict[str, Any]:
    stamp = timestamp()
    conn, tables, load_missing = load_database(database)
    missing_data: list[str] = list(load_missing)
    recommendation_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    replay_rows: list[dict[str, Any]] = []
    try:
        if conn is not None:
            if "recommendations" in tables:
                recommendation_rows = fetch_table(conn, "recommendations")
            else:
                missing_data.append("recommendations table not available.")
            if "paper_trades" in tables:
                trade_rows = fetch_table(conn, "paper_trades")
            else:
                missing_data.append("paper_trades table not available.")
            if "replay_runs" in tables:
                replay_rows = fetch_table(conn, "replay_runs")
            else:
                missing_data.append("replay_runs table not available.")

            for required in ("daily_bars",):
                if required not in tables:
                    missing_data.append(f"{required} table not available for benchmark comparison.")

        recommendation_summary, recommendations_by_id = analyze_recommendations(recommendation_rows)
        trade_summary = analyze_trades(trade_rows)
        attribution = build_attribution(recommendations_by_id, trade_rows)
        baseline = analyze_baseline(conn, tables, trade_summary)
    finally:
        if conn is not None:
            conn.close()

    report: dict[str, Any] = {
        "timestamp": now_iso(),
        "report_type": "model_validation_foundation",
        "database": str(database.resolve()),
        "paper_only": True,
        "llm_used_for_metrics": False,
        "live_trading_performance": False,
        "broker_routing_evaluated": False,
        "scope": {
            "description": "Read-only model validation evidence scaffold using stored deterministic recommendations, replay rows, daily bars, and paper trades when available.",
            "no_strategy_math_changes": True,
            "no_ranking_changes": True,
            "no_live_trading": True,
            "no_broker_routing": True,
            "no_automated_exits": True,
        },
        "limitations": [
            "Paper-only results are not live trading performance.",
            "No guarantee of future performance is implied.",
            "No slippage or live execution modeling is included unless already represented in stored paper records.",
            "Provider data coverage depends on locally retained daily_bars and recommendation provenance.",
            "This report is internal research evidence, not public investment advice.",
        ],
        "tables_present": sorted(tables),
        "recommendations": recommendation_summary,
        "replay": {
            "run_count": len(replay_rows),
            "stageable_run_count": sum(1 for row in replay_rows if safe_bool(row.get("has_stageable_candidate"))),
        },
        "paper_trades": trade_summary,
        "baseline_comparison": baseline,
        "attribution": attribution,
        "missing_data": sorted(set(missing_data + baseline.get("missing_data", []))),
        "validation_inputs_needed": [
            "point-in-time historical validation dataset",
            "walk-forward split definitions",
            "symbol universe snapshot by date",
            "provider/source coverage report",
            "baseline capital assumptions",
            "slippage/live execution model if moving beyond paper evidence",
        ],
    }
    report = redact_payload(report)

    evidence_dir.mkdir(parents=True, exist_ok=True)
    json_path = evidence_dir / f"model-validation-{stamp}.json"
    md_path = evidence_dir / f"model-validation-{stamp}.md"
    report["evidence_json"] = str(json_path)
    report["evidence_markdown"] = str(md_path)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def render_markdown(report: dict[str, Any]) -> str:
    recs = report["recommendations"]
    trades = report["paper_trades"]
    baseline = report["baseline_comparison"]
    lines = [
        f"# Model Validation Evidence {report['timestamp']}",
        "",
        "This is paper/research-only validation evidence. It is not live trading performance, broker routing evidence, public investment advice, or a guarantee of future performance.",
        "",
        "## Summary",
        "",
        f"- Recommendations: `{recs['count']}`",
        f"- Approved / rejected / unknown: `{recs['approved_count']} / {recs['rejected_count']} / {recs['approval_unknown_count']}`",
        f"- Average expected RR: `{recs['average_expected_rr']}`",
        f"- Closed paper trades: `{trades['closed_count']}`",
        f"- Total net paper P&L: `{trades['total_net_pnl']}`",
        f"- Win rate: `{trades['win_rate']}`",
        f"- Max drawdown: `{trades['max_drawdown']}`",
        f"- Baseline comparison status: `{baseline['status']}`",
        f"- LLM used for metrics: `{report['llm_used_for_metrics']}`",
        "",
        "## Attribution Sections",
        "",
        "- by setup",
        "- by regime",
        "- by catalyst type",
        "- by timeframe",
        "- by risk-calendar state",
        "- by provider source",
        "- by already-open vs fresh setup",
        "",
        "## Missing Data",
        "",
    ]
    if report["missing_data"]:
        lines.extend([f"- {item}" for item in report["missing_data"]])
    else:
        lines.append("- None reported by this scaffold.")
    lines.extend(
        [
            "",
            "## Buyer-Facing Limitations",
            "",
            "- Paper-only results are not live trading performance.",
            "- No guarantee of future performance is implied.",
            "- No slippage/live execution model is included unless already present in stored paper records.",
            "- Provider data limitations are reported as missing data.",
            "- This is not a public investment-advice claim.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate read-only model validation evidence.")
    parser.add_argument("--database", default=str(DEFAULT_DATABASE), help="SQLite database path")
    parser.add_argument("--evidence-dir", default=str(DEFAULT_EVIDENCE_DIR), help="Evidence output directory")
    args = parser.parse_args()
    report = generate_model_validation(database=Path(args.database), evidence_dir=Path(args.evidence_dir))
    print(json.dumps({"status": "ok", "evidence_json": report["evidence_json"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
