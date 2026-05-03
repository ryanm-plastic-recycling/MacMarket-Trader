# Active Paper Position Management Design

Status: started for open equity paper positions.

Implementation note, 2026-05-02:
`GET /user/paper-positions/review` now returns one deterministic review object
per open equity paper position, and the Next.js proxy
`GET /api/user/paper-positions/review` feeds the Orders page Active Position
Review section. This first implementation remains review-only and does not
create, close, stage, route, or scale any position automatically.

Follow-up implementation note, 2026-05-02:
Recommendations and ranked queue payloads now include already-open awareness
for current-user open equity paper positions. Ranked queue candidates,
persisted recommendation list/detail rows, queue promotion responses, and
generation responses attach `already_open`, `open_position_id`,
`open_position_quantity`, `open_position_average_entry`, optional
`active_review_action_classification`, optional `active_review_summary`, and
`open_position_review_path` when the symbol is already open. This is response
decoration only; ranking, entry/stop/target/sizing math, approval, replay, and
paper-order creation are unchanged.

This design covers the gap between manual paper position close/reopen support
and a full operator-grade review loop for open paper equity positions. The
current system can stage/fill paper orders, create open paper positions, close
them manually, record realized gross/net P&L, and reopen closed positions during
the undo window. It does not yet re-evaluate open positions against current
market data, current recommendation rank, stop/target distance, time stop, or
updated thesis validity.

This must remain paper-only. It must not imply live trading, broker routing,
real brokerage execution, or automated exits. The goal is an operator review
surface and read-only recommendation context for open paper positions.

## Product Goal

Open paper positions should be reviewed as active managed positions, not treated
as disconnected prior artifacts or fresh duplicate setups. If the operator owns
10 paper shares of `GOOG` and `GOOG` appears again as a top-ranked
recommendation, the workflow should recognize the existing open position and
show `Already open` / `Active position review` state by default.

The operator should see whether the current mark and current ranking support
holding, trailing, taking profit, stopping out, respecting a time stop, marking
the thesis invalid, or considering a scale-in only when explicit risk rules
allow it.

## Paper-Only Boundaries

- No live trading support.
- No brokerage routing or real broker execution.
- No automated close orders.
- No silent average-in behavior.
- No changes to equity recommendation generation by default.
- No schema changes are required by this design checkpoint.
- Broker integration should not be promoted until open-position review exists,
  because external paper brokerage plumbing would otherwise automate around an
  incomplete lifecycle.

## Mark-To-Market Review Model

The future review read model should return one object per open paper equity
position. Each review object should include:

- `position_id`
- `symbol`
- `side`
- `opened_qty`
- `remaining_qty`
- `avg_entry_price`
- `opened_at`
- `days_held`
- `max_holding_days`
- `current_mark_price`
- `mark_source`
- `mark_as_of`
- `fallback_mode`
- `unrealized_pnl`
- `unrealized_return_pct`
- `stop_price`
- `target_1`
- `target_2`
- `distance_to_stop`
- `distance_to_stop_pct`
- `distance_to_target_1`
- `distance_to_target_1_pct`
- `distance_to_target_2`
- `distance_to_target_2_pct`
- `current_recommendation_id`
- `current_recommendation_rank`
- `current_recommendation_score`
- `current_recommendation_status`
- `already_open`
- `action_status`
- `action_reason`
- `risk_blockers`
- `reviewed_at`

Distances should be signed in a way the UI can explain clearly. For a long
position, a negative stop distance means the current mark has crossed below the
stop. For a short position, the inverse convention should be defined before
short paper position management is expanded.

## Position Review Statuses

`hold_valid`
: The position remains inside the thesis, above stop for a long, within holding
period, and current recommendation/rank context is still supportive.

`target_reached_hold`
: Target 1 or target 2 has been reached, but current ranking/thesis context
still supports holding or trailing rather than immediate profit-taking.

`target_reached_take_profit`
: Target has been reached and rank/thesis/holding-period context no longer
supports additional exposure. This is a review recommendation only, not an
automated paper close.

`stop_triggered`
: Current mark has crossed the active invalidation/stop level. The operator
should be prompted to review and manually close or document an override.

`time_stop_warning`
: Days held are near max holding days while thesis is not invalidated. The UI
should warn that the expected event window is aging.

`time_stop_exit`
: Days held exceed max holding days or the time-stop condition is otherwise
met. This is a review recommendation only, not automated execution.

`scale_in_candidate`
: Same-symbol current recommendation remains highly ranked, the existing
position is profitable or thesis-valid, and explicit portfolio risk rules allow
additional exposure. Scale-in must require clear UI messaging and must never
silently average into an open position.

`invalidated`
: Current market/recommendation context contradicts the original thesis even if
the stop has not yet triggered. Examples include a catalyst reversal, no-trade
ranking, degraded provider/workflow source, or recommendation status that no
longer supports the setup.

## Recommendation Handling For Already-Held Symbols

Ranked recommendations should be open-position aware. If a symbol already has
an open paper position for the operator, the recommendation row/card should show
an `Already open` or `Active position review` state instead of presenting the
setup as a totally new trade by default.

The operator can still inspect the setup, but the primary action should route
to position review. A new order or scale-in path should require explicit
confirmation and risk-rule approval.

Current implementation:

- `GET /user/recommendations`, `GET /user/recommendations/{id}`,
  `POST /user/recommendations/queue`,
  `POST /user/recommendations/queue/promote`, and
  `POST /user/recommendations/generate` attach already-open fields for matching
  open equity paper position symbols.
- The ranked queue and persisted recommendation rows show an `Already open`
  badge plus `Review position` link to `/orders#active-position-review`.
- Queue and persisted detail panels describe the candidate as an existing paper
  position review context when already open.
- The guided Orders paper ticket warns that additional paper order staging would
  increase exposure and shows existing/new/combined quantity and combined
  estimated notional when available.
- No automatic scale-in, automatic close, broker routing, live trading,
  recommendation scoring change, or paper-order sizing change is introduced.

Options parity note, 2026-05-03:
Options paper structures now have a separate review-only endpoint and Orders
section:

```http
GET /user/options/paper-structures/review
GET /api/user/options/paper-structures/review
```

This does not reuse the equity position review shape because options require a
structure/legs contract. The options review is paper-only, excludes closed
structures by default, owner-scopes data to the current user, reports persisted
opening debit/credit, commissions, payoff bounds, expiration status,
risk-calendar context, and leg detail, and returns `mark_unavailable` when
provider-backed option marks are unavailable. It does not auto-close, auto-roll,
auto-adjust, auto-scale, route to a broker, or imply live trading.

## Scale-In Guardrails

Scale-in is allowed only when deterministic risk rules explicitly approve it.
At minimum, the review logic should account for:

- remaining per-trade risk budget
- max position size
- max portfolio heat
- sector/factor concentration
- daily loss/risk lockouts
- whether the existing position is already at or beyond intended exposure

If risk limits are exceeded, the review object should block scale-in and list
operator-readable blockers. The UI must clearly say that averaging into a
position is not automatic.

## Proposed Endpoint Contract

Frontend route:

```http
GET /api/user/paper-positions/review
```

Backend route maps to the existing protected user API namespace:

```http
GET /user/paper-positions/review
```

Example response:

```json
[
  {
    "position_id": 42,
    "symbol": "GOOG",
    "side": "long",
    "opened_qty": 10,
    "remaining_qty": 10,
    "avg_entry_price": 172.5,
    "opened_at": "2026-05-01T14:30:00Z",
    "days_held": 1,
    "max_holding_days": 5,
    "current_mark_price": 178.2,
    "mark_source": "provider",
    "mark_as_of": "2026-05-02T15:59:00Z",
    "fallback_mode": false,
    "unrealized_pnl": 57.0,
    "unrealized_return_pct": 3.3,
    "stop_price": 168.4,
    "target_1": 177.5,
    "target_2": 184.0,
    "distance_to_stop": 9.8,
    "distance_to_stop_pct": 5.5,
    "distance_to_target_1": -0.7,
    "distance_to_target_1_pct": -0.39,
    "distance_to_target_2": 5.8,
    "distance_to_target_2_pct": 3.25,
    "current_recommendation_id": "GOOG-EVCONT-20260502-0830",
    "current_recommendation_rank": 1,
    "current_recommendation_score": 0.91,
    "current_recommendation_status": "ranked_active",
    "already_open": true,
    "action_status": "target_reached_hold",
    "action_reason": "Target 1 is reached, but GOOG remains top-ranked and thesis-valid.",
    "risk_blockers": [],
    "reviewed_at": "2026-05-02T16:00:00Z"
  }
]
```

## Data Source Rules

The review must use the same workflow-source discipline as recommendations,
replay, and orders:

- Prefer provider-backed marks when provider-backed market data is configured.
- Label fallback data explicitly.
- Do not silently mix provider chart context with fallback position-review
  logic.
- Include `mark_source`, `mark_as_of`, and `fallback_mode` in the contract.
- If current recommendation/ranking context is stale or unavailable, surface
  that as a review limitation instead of forcing a confident action.

## Current Implementation Details

- Scope is open equity paper positions from `paper_positions` only. Closed
  positions are excluded by default, and options-paper lifecycle rows remain
  deferred to a later options-specific contract.
- Current marks use the existing market-data service latest snapshot path.
  If provider-backed market data is configured and the service can only return
  fallback data outside explicit local/demo fallback policy, the review object
  is marked `review_unavailable` instead of silently using a fake mark.
- Stop, target 1, target 2, and max holding days are recovered from the linked
  recommendation payload when the paper position carries recommendation/order
  lineage. Missing levels are returned in `missing_data`; they are not
  fabricated.
- Current recommendation status is derived from recent persisted
  recommendations and ranking provenance for the same symbol:
  `top_candidate`, `still_ranked`, `weakened`, `not_currently_ranked`, or
  `unavailable`.
- Market Risk Calendar is evaluated for each position. Restricted/no-trade
  states warn against new additions/scale-ins but do not become automatic close
  recommendations solely because new entries are blocked.
- Scale-in is only classified when the symbol is already open, ranking context
  is strong, the open position is profitable/thesis-valid, the risk calendar
  allows additions, and max paper notional/risk-at-stop checks leave room. If
  those checks block an otherwise attractive addition, the review returns a
  warning and uses the next lower deterministic action.

Classification precedence is:

1. `review_unavailable`
2. `stop_triggered`
3. `invalidated`
4. `time_stop_exit`
5. `target_reached_take_profit`
6. `target_reached_hold`
7. `scale_in_candidate`
8. `time_stop_warning`
9. `hold_valid`

## Remaining Limitations

- Equity-only.
- No automated exits, no automatic close, no automatic scale-in, no broker
  routing, and no live trading.
- Stop/target/time-stop recovery depends on available recommendation lineage
  and provenance.
- Current ranking context uses recent persisted recommendation/ranking
  provenance; a richer durable "current queue" snapshot remains future work.
- Already-open awareness uses current open equity paper positions by symbol and
  does not alter ranking, approval, sizing, promotion, or staging behavior.
- LLM position-review copy is deferred. Deterministic logic owns the action
  classification.
- Options position review is deferred to a separate options-aware shape.

## Test Expectations

- An open `GOOG` long paper position returns current mark price and unrealized
  P&L dollars.
- The same response returns unrealized return percent.
- A position near or through the stop returns `stop_triggered` or a warning
  status according to the final threshold rules.
- A position above target while still highly ranked returns
  `target_reached_hold`.
- An existing open symbol appearing in ranked recommendations is flagged as
  `already_open`.
- A scale-in candidate is blocked when portfolio risk limits are exceeded and
  returns operator-readable risk blockers.
- Fallback market data is explicitly labeled in position review.
- No review endpoint creates orders, trades, replay runs, recommendations, or
  broker-side artifacts.

## Suggested Implementation Slices

1. Docs/design checkpoint and roadmap placement before Alpaca paper integration.
2. Backend read-model helper for open paper positions plus current mark
   enrichment using existing provider/fallback workflow rules.
3. Deterministic action classifier with focused tests for the statuses above.
4. Protected read-only review endpoint returning one object per open position.
5. Recommendation list/read model flag for already-held symbols.
6. Operator UI integration that routes already-open symbols to active position
   review before any new paper order/scale-in action.
7. Closure audit confirming no live trading, no broker routing, no schema drift
   unless a later explicit persistence pass is approved.
