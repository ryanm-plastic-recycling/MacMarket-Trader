from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import mean

from macmarket_trader.domain.enums import MarketMode
from macmarket_trader.domain.schemas import Bar
from macmarket_trader.strategy_registry import StrategyRegistryEntry, list_strategies


@dataclass
class RankedCandidate:
    rank: int
    symbol: str
    strategy: str
    strategy_id: str
    strategy_status: str
    source: str
    workflow_source: str
    market_mode: str
    timeframe: str
    status: str
    conviction_tier: str
    score: float
    score_breakdown: dict[str, float]
    expected_rr: float
    confidence: float
    thesis: str
    trigger: str
    entry_zone: str
    invalidation: str
    targets: str
    reason_text: str


def _regime_alignment_bonus(bars: list[Bar], strategy: str) -> float:
    """Return a deterministic bonus [0.0, 0.08] based on simple trend/momentum alignment."""
    if len(bars) < 5:
        return 0.0
    recent = bars[-5:]
    closes = [b.close for b in recent]
    # Uptrend: each close >= previous
    up_count = sum(1 for i in range(1, len(closes)) if closes[i] >= closes[i - 1])
    trend_ratio = up_count / (len(closes) - 1)
    # Momentum strategies align with trend; mean-reversion aligns with counter-trend
    if "Mean Reversion" in strategy:
        alignment = 1.0 - trend_ratio
    elif "Pullback" in strategy:
        alignment = trend_ratio * 0.8
    else:
        alignment = trend_ratio
    return round(alignment * 0.08, 4)


def _recency_weight(bars: list[Bar]) -> float:
    """Return a recency bonus [0.0, 0.06] — higher when latest close is near the recent high."""
    if len(bars) < 10:
        return 0.0
    recent = bars[-10:]
    high = max(b.high for b in recent)
    low = min(b.low for b in recent)
    rng = high - low or 0.01
    last_close = recent[-1].close
    position = (last_close - low) / rng  # 0 = at recent low, 1 = at recent high
    return round(position * 0.06, 4)


def _conviction_tier(score: float) -> str:
    if score >= 0.72:
        return "HIGH"
    if score >= 0.62:
        return "MEDIUM"
    return "LOW"


def _score_symbol(bars: list[Bar], strategy: str) -> dict[str, float]:
    last = bars[-1]
    avg_volume = mean([bar.volume for bar in bars[-20:]]) if bars else float(last.volume)
    daily_ranges = [max(bar.high - bar.low, 0.01) for bar in bars[-14:]]
    atr = mean(daily_ranges) if daily_ranges else 1.0
    close = max(last.close, 0.01)
    rel_volatility = min(2.0, atr / close * 100)
    liquidity = min(1.0, avg_volume / 4_000_000)
    strategy_fit = 0.75 if strategy == "Event Continuation" else 0.68
    regime_fit = 0.65 + min(0.2, rel_volatility / 10)
    catalyst_quality = 0.55
    volatility_fit = min(1.0, rel_volatility / 1.5)
    spread_penalty = 0.05 if liquidity > 0.5 else 0.18
    regime_bonus = _regime_alignment_bonus(bars, strategy)
    recency_bonus = _recency_weight(bars)
    expected_rr = round(1.2 + (strategy_fit * 1.1) + (volatility_fit * 0.35) - spread_penalty, 2)
    confidence = max(0.2, min(0.95, (strategy_fit + regime_fit + liquidity) / 3))
    score = (
        strategy_fit * 0.22
        + regime_fit * 0.17
        + catalyst_quality * 0.11
        + liquidity * 0.13
        + volatility_fit * 0.13
        + confidence * 0.10
        + min(1.0, expected_rr / 3) * 0.10
        - spread_penalty * 0.14
        + regime_bonus
        + recency_bonus
    )
    return {
        "strategy_fit_score": round(strategy_fit, 3),
        "regime_fit_score": round(regime_fit, 3),
        "catalyst_quality_score": round(catalyst_quality, 3),
        "liquidity_score": round(liquidity, 3),
        "volatility_suitability_score": round(volatility_fit, 3),
        "spread_slippage_penalty": round(spread_penalty, 3),
        "regime_alignment_bonus": round(regime_bonus, 4),
        "recency_weight": round(recency_bonus, 4),
        "expected_rr": expected_rr,
        "confidence": round(confidence, 3),
        "total_score": round(score, 3),
    }


class DeterministicRankingEngine:
    def rank_candidates(
        self,
        *,
        bars_by_symbol: dict[str, tuple[list[Bar], str, bool]],
        strategies: list[str],
        market_mode: MarketMode,
        timeframe: str,
        top_n: int = 5,
    ) -> dict[str, object]:
        if market_mode != MarketMode.EQUITIES:
            raise ValueError(
                f"Ranking queue market_mode '{market_mode.value}' is planned research preview only and not runnable for live workflows."
            )

        allowed = {entry.display_name: entry for entry in list_strategies(MarketMode.EQUITIES)}
        selected: list[StrategyRegistryEntry] = [allowed[name] for name in strategies if name in allowed]
        if not selected:
            selected = [allowed["Event Continuation"]]

        output: list[RankedCandidate] = []
        for symbol, (bars, source, fallback_mode) in bars_by_symbol.items():
            if not bars:
                continue
            latest = bars[-1]
            prior = bars[-2] if len(bars) > 1 else latest
            workflow_source = f"fallback ({source})" if fallback_mode else source
            for entry in selected:
                metrics = _score_symbol(bars, entry.display_name)
                total = metrics["total_score"]
                status = "top_candidate" if total >= 0.62 else "watchlist"
                if metrics["confidence"] < 0.45:
                    status = "no_trade"
                tier = _conviction_tier(total)
                reason_text = (
                    f"{entry.display_name}: fit {metrics['strategy_fit_score']}, liquidity {metrics['liquidity_score']}, "
                    f"volatility {metrics['volatility_suitability_score']}, confidence {metrics['confidence']}, "
                    f"regime bonus {metrics['regime_alignment_bonus']}, recency {metrics['recency_weight']}."
                )
                output.append(
                    RankedCandidate(
                        rank=0,
                        symbol=symbol,
                        strategy=entry.display_name,
                        strategy_id=entry.strategy_id,
                        strategy_status=entry.status,
                        source=source,
                        workflow_source=workflow_source,
                        market_mode=market_mode.value,
                        timeframe=timeframe,
                        status=status,
                        conviction_tier=tier,
                        score=total,
                        score_breakdown={k: v for k, v in metrics.items() if k not in {"expected_rr", "confidence", "total_score"}},
                        expected_rr=metrics["expected_rr"],
                        confidence=metrics["confidence"],
                        thesis=f"{entry.display_name} alignment with deterministic regime and liquidity filters.",
                        trigger="Hold above opening range high with RVOL confirmation.",
                        entry_zone=f"{latest.close * 0.995:.2f} - {latest.close * 1.005:.2f}",
                        invalidation=f"{prior.low * 0.995:.2f}",
                        targets=f"{latest.close * 1.02:.2f} / {latest.close * 1.04:.2f}",
                        reason_text=reason_text,
                    )
                )

        output.sort(key=lambda item: item.score, reverse=True)
        for idx, item in enumerate(output, start=1):
            item.rank = idx

        top_candidates = [asdict(item) for item in output if item.status == "top_candidate"][:top_n]
        watchlist = [asdict(item) for item in output if item.status == "watchlist"]
        no_trade = [asdict(item) for item in output if item.status == "no_trade"]

        return {
            "queue": [asdict(item) for item in output],
            "top_candidates": top_candidates,
            "watchlist_only": watchlist,
            "no_trade": no_trade,
            "summary": {
                "total": len(output),
                "top_candidate_count": len(top_candidates),
                "watchlist_count": len(watchlist),
                "no_trade_count": len(no_trade),
            },
        }
