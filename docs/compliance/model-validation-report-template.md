# Model Validation Report Template

This template is for internal validation evidence. It must not be presented as
live trading performance, public investment advice, or a guarantee of future
performance.

## Objective

- Validation objective:
- Model/engine version:
- Change or release under review:
- Reviewer:

## Data Period

- Start date:
- End date:
- Data completeness notes:

## Symbols / Universe

- Universe definition:
- Inclusion/exclusion criteria:
- Symbol snapshot source:

## Timeframes

- Timeframes tested:
- Holding period assumption:

## Provider / Source

- Market data provider:
- Fallback mode:
- Provider-health evidence:
- Data quality exclusions:

## Session Policy

- Session:
- RTH normalization policy:
- Timezone:

## Baseline Comparison

- Baselines: SPY, QQQ, simple no-trade, and any strategy-specific baseline.
- Capital assumptions:
- Benchmark return method:
- Missing baseline data:

## Walk-Forward Method

- Train/selection window:
- Validation window:
- Rebalance/re-rank cadence:
- Lookahead-bias controls:

## Replay Method

- Replay engine:
- Replay input source:
- Paper fill assumptions:
- Slippage/fees/commission assumptions:
- Replay/live parity caveats:

## Metrics

- Number of recommendations.
- Approved vs rejected.
- Setup type distribution.
- Symbol distribution.
- Regime distribution.
- Average expected RR.
- Realized paper trade P&L where linked.
- Win rate where available.
- Average win/loss where available.
- Max drawdown where available.
- Holding period stats.
- SPY/QQQ baseline comparison where available.
- No-trade/risk-calendar block count.

## Attribution

- By setup.
- By regime.
- By catalyst type.
- By timeframe.
- By risk-calendar state.
- By provider source.
- By already-open vs fresh setup.

## Limitations

- Paper-only results are not live trading performance.
- No guarantee of future performance.
- No slippage/live execution modeled unless explicitly included in stored
  paper records.
- Provider data limitations:
- No public investment-advice claim.

## Approval / Signoff Placeholder

- Prepared by:
- Reviewed by:
- Approval decision:
- Exceptions:
- Follow-up owner:
- Follow-up due date:
