# Symbol Discovery and Watchlist Design

Last updated: 2026-04-30

## Purpose

This document is a design checkpoint for better user-scoped symbol discovery,
watchlist management, and recommendation-universe selection.

It is documentation-only. It does not implement symbol search, change
recommendation generation, add provider probes, change schemas, or imply live
trading / brokerage routing.

## Current-state Inventory

Current symbol entry is intentionally simple:

- Analysis / Strategy Workbench:
  a single free-text symbol input drives one setup at a time.
- Symbol Analyze:
  a single free-text symbol input drives an ad-hoc symbol snapshot.
- Recommendations:
  the queue form stores a manual text field in the frontend, accepts comma,
  space, or new-line separated symbols, shows a normalized uppercase parsed
  preview plus duplicate feedback, and posts those symbols to
  `/user/recommendations/queue`.
- Scheduled Strategy Reports:
  the schedule form stores a manual text field in the frontend, accepts comma,
  space, or new-line separated symbols, shows a normalized uppercase parsed
  preview plus duplicate feedback, and persists those symbols inside the
  schedule payload.
- Watchlists:
  the backend has a user-scoped `watchlists` table with `app_user_id`, `name`,
  `symbols` JSON, and `created_at`. The current repository supports list,
  upsert, update, and delete by current user.
- Schedules page:
  shows a basic Watchlists card where users enter a watchlist name plus a
  manual symbol list, review the same parsed preview, then apply the saved list
  back into the schedule symbol field.
- Scheduled runs:
  `StrategyReportService.run_schedule()` reads `symbols` from the schedule
  payload, fetches bars per symbol, and passes a `bars_by_symbol` map into
  `DeterministicRankingEngine.rank_candidates(...)`.
- Recommendation queue:
  `/user/recommendations/queue` reads `symbols` directly from the request,
  fetches bars per symbol, and passes them into the same ranking engine.

Current scoping:

- Watchlist rows and schedule rows are user-scoped by `app_user_id`.
- Schedule payload symbols are copied into each schedule payload rather than
  linked to a watchlist row.
- Recommendation queue requests are transient and are not currently linked to a
  persisted watchlist.
- Provider/source metadata for symbols is not persisted in watchlists.
- There is no current provider-backed symbol search endpoint or symbol metadata
  table.

Current limitations:

- Users must already know symbols.
- Names, asset types, exchanges, provider support, options eligibility, and
  index/ETF substitution guidance are not first-class watchlist fields.
- Duplicate handling is mostly whatever the caller provides.
- There is no active/inactive symbol status.
- There are no tags/groups, notes, import audit, or per-symbol update
  timestamps.
- Recommendation and schedule workflows still depend on raw symbol arrays.

## 10W2 Current Manual-entry Cleanup

Status: complete for the current frontend-only scope.

Current manual-entry surfaces now provide clearer operator guidance without
changing backend behavior, storage, provider access, schedule execution, or
recommendation generation:

- Recommendations labels the queue input as `Symbols to evaluate`, explains
  comma/space/new-line separators, shows an example list, shows SPX/NDX versus
  SPY/QQQ substitute guidance, and labels the list as a temporary manual
  universe until richer watchlist management exists.
- Recommendations shows a read-only parsed preview with normalized uppercase
  symbols, symbol count, and duplicate feedback.
- Schedules and the current Watchlists card use the same manual-entry helper
  copy and parsed preview while continuing to save resolved symbol arrays.
- Analysis keeps its single-symbol behavior and adds a small provider-access
  hint for ticker symbols and index symbols.

Still deferred after `10W2`:

- provider-backed symbol search
- schema or migration work
- normalized `user_symbol_universe` / `watchlist_symbols` records
- replacing existing watchlist storage
- recommendation/schedule universe selector behavior
- provider metadata enrichment
- any live routing, brokerage execution, or execution approval semantics

## Symbol Discovery Design

Future symbol discovery should provide a research-universe search flow:

- search by ticker
- search by company/security name
- show ticker, display name, asset type, and exchange/venue when available
- distinguish equities, ETFs, indexes, option-eligible underlyings, and future
  crypto where practical
- show provider/source metadata when already available or later explicitly
  added
- show options/index caveats such as:
  - SPX/NDX may require index-data access
  - SPY/QQQ can be practical ETF substitutes
  - options chains, IV, Greeks, and open interest depend on provider coverage
- keep missing metadata non-blocking so manual entry still works

Discovery copy must say provider support and options eligibility are research
context only. They are not execution approval, routing support, or broker
account capability.

## Watchlist Management Design

The future watchlist UI should replace comma-only editing with an operator
table:

- searchable / sortable symbols table
- add one symbol at a time
- delete one symbol at a time
- bulk add/import from pasted text or CSV-like input
- duplicate detection and merge/skip feedback
- active/inactive status per symbol
- optional notes
- optional tags/groups such as `Core`, `ETFs`, `Tech`, `Options Candidates`,
  and `Watch Only`
- created/updated timestamps
- source indicator such as `manual`, `imported`, or `provider-discovered`
- metadata fallback states such as `Metadata unavailable`

The first implementation should keep actions small and reversible. A user
should be able to disable a symbol without deleting its notes/tags, then later
remove it entirely if desired.

## Recommendation-universe Selection

Recommendation and schedule workflows should eventually select their universe
from:

- all active symbols for the current user
- one selected watchlist
- one or more selected tags/groups
- manually entered temporary symbols
- explicit exclusions
- pinned/priority symbols

This should feed the existing recommendation/ranking path as a resolved symbol
list. The universe resolver should be separate from
`RecommendationService.generate()` and from deterministic scoring.

Do not change recommendation generation in the design checkpoint. Future
implementation should translate watchlist/group choices into the same kind of
symbol list the queue and schedule paths already accept.

## Data-model Options

### Option A: Extend Existing Watchlist Records

Extend the current `watchlists` row and `symbols` JSON payload to carry objects
instead of strings.

Potential shape:

```json
{
  "symbol": "AAPL",
  "name": "Apple Inc.",
  "asset_type": "equity",
  "exchange": "NASDAQ",
  "active": true,
  "tags": ["Core", "Tech"],
  "notes": "Primary large-cap watch",
  "source": "manual",
  "updated_at": "2026-04-30T00:00:00Z"
}
```

Pros:

- lowest migration pressure if implemented as payload-compatible JSON
- keeps current watchlist routes conceptually intact
- easy rollback to old symbol arrays if new UI is hidden

Cons:

- harder to query, filter, dedupe, and sort at the database layer
- harder to enforce uniqueness per user/watchlist/symbol
- less suitable for tags, active filters, provider metadata, or auditability
- schedule payloads may keep diverging from watchlist truth

### Option B: Dedicated User Symbol Universe / Watchlist Symbol Tables

Add normalized tables later, for example:

- `user_symbol_universe`
  - `id`
  - `app_user_id`
  - `symbol`
  - `display_name`
  - `asset_type`
  - `exchange`
  - `provider_source`
  - `metadata_status`
  - `active`
  - `notes`
  - `created_at`
  - `updated_at`
- `watchlist_symbols`
  - `watchlist_id`
  - `user_symbol_id`
  - `sort_order`
  - `tags` or a separate tag join table
  - `created_at`
  - `updated_at`

Pros:

- best user scoping and duplicate handling
- supports per-symbol active/inactive state across watchlists
- supports searchable/sortable tables without parsing JSON
- better foundation for schedule/recommendation universe selection
- easier to test uniqueness, permissions, and metadata fallbacks

Cons:

- requires schema/migration design and backfill from existing JSON watchlists
- needs compatibility logic for old watchlist payloads and schedule payloads
- higher rollback planning burden

### Option C: Hybrid Compatibility Layer

Keep current `watchlists.symbols` JSON for compatibility while adding a
dedicated universe table and a resolver layer. The UI reads/writes the new
normalized model, but schedules and recommendation queue requests continue to
receive resolved symbol arrays until a later persistence migration is complete.

Pros:

- lets new UI and resolver land without immediately changing ranking/scoring
- supports gradual migration and fallback to old watchlist rows
- keeps schedule and recommendation paths stable in early slices
- can backfill normalized rows from existing JSON watchlists

Cons:

- temporary dual-write/read complexity
- requires clear source-of-truth rules during migration
- needs tests to prevent drift between JSON rows and normalized rows

## Recommended Approach

Use the hybrid approach.

Reasoning:

- The current repo already has user-scoped watchlists and schedule payloads, so
  throwing them away would create unnecessary risk.
- Normalized per-symbol rows are the right long-term model for duplicate
  handling, active/inactive status, tags, notes, source labels, and provider
  metadata.
- The safest early implementation can resolve normalized universe selections
  into the same symbol arrays already used by Recommendations and Schedules.
- `RecommendationService.generate()` and deterministic ranking can stay
  unchanged while the operator universe improves around them.

Recommended source-of-truth rule for later implementation:

- `user_symbol_universe` is the long-term per-user symbol truth.
- `watchlists` remain named collections.
- schedules should eventually store a universe selector snapshot plus a
  resolved symbol snapshot for auditability.
- recommendation queue requests should accept a resolved list plus optional
  provenance such as `watchlist_id`, `tags`, `exclusions`, and `manual_symbols`.

## Provider Assumptions

No provider behavior is added by this plan.

Future provider-backed search is a separate implementation slice. Until then:

- manual symbol entry must remain available
- missing provider metadata should render as `Metadata unavailable`
- provider/source labels must not imply live trading, brokerage routing, or
  order support
- options eligibility is research context only
- index/options coverage depends on provider plan/access
- SPX/NDX caveats and SPY/QQQ substitutes should be visible where useful

## UX Flow

Future operator flow:

1. Search for a symbol by ticker or name.
2. Inspect available metadata and caveats.
3. Add the symbol to the user universe.
4. Add it to one or more watchlists.
5. Assign tags/groups and optional notes.
6. Mark it active or inactive.
7. Select a watchlist, tag/group, all active symbols, or temporary manual
   symbols in Recommendations or Schedules.
8. Resolve the selected universe into a symbol list for ranking.
9. Review provider/source labels and fallback states.
10. Remove or deactivate symbols later without touching historical runs.

## Future Test Plan

Backend / API tests:

- manual add creates a user-scoped symbol row
- duplicate add returns deterministic skip/merge feedback
- delete or deactivate affects only the current user
- active/inactive filtering affects universe resolution
- tags/groups filter the resolved universe correctly
- watchlist membership is user-scoped
- schedule creation can store universe selectors and resolved symbol snapshots
- recommendation queue can receive a resolved universe without changing
  recommendation generation
- provider metadata unavailable fallback does not block manual symbols
- SPX/NDX caveat metadata can be represented without implying execution
- no live routing, broker execution, or order support language appears

Frontend tests:

- search/filter/sort table behavior
- add/delete individual symbol
- bulk import duplicate handling
- active/inactive toggle
- tags/groups selection
- schedule universe selector renders watchlist/tag/manual choices
- recommendation universe selector renders watchlist/tag/manual choices
- missing metadata renders `Metadata unavailable`
- SPX/NDX versus SPY/QQQ guidance appears where intended
- provider support labels stay research-only

Regression tests:

- existing `/user/watchlists` behavior remains compatible during migration
- existing schedule payload symbol arrays still run
- existing recommendation queue payload symbol arrays still run
- `RecommendationService.generate()` behavior does not change

## Implementation Slices

Numbering note: the existing roadmap already reserves `10D` for expiration
settlement design. To preserve that structure, this symbol/watchlist work
should be tracked as a Phase 10 workflow-polish lane unless the roadmap is
explicitly renumbered later.

Recommended slices:

- `10W1` symbol/watchlist design checkpoint:
  complete with this document and roadmap alignment; docs-only.
- `10W2` current-state cleanup / copy polish:
  complete; clarifies current comma-entry limitations on Recommendations,
  Schedules, current watchlist editing, and Analysis single-symbol entry, with
  no schema or backend behavior changes.
- `10W3` schema/read-model checkpoint:
  design normalized universe tables, backfill, compatibility, and rollback
  before any migration.
- `10W4` user-scoped watchlist table UI:
  frontend table around existing or new read model, starting with manual add,
  delete, search, sort, and active/inactive display.
- `10W5` bulk import and duplicate handling:
  paste/import workflow with deterministic duplicate feedback.
- `10W6` recommendation/schedule universe selection:
  resolve watchlists, tags/groups, exclusions, pinned symbols, and temporary
  manual symbols into current symbol arrays.
- `10W7` provider-backed symbol discovery:
  add provider-backed search only after explicit provider-design approval.
- `10W8` closure:
  docs/tests audit proving user scoping, fallback metadata, no execution
  implication, and no recommendation-generation drift.

## Suggested First Implementation Slice

Start with `10W2`: current-state cleanup / UI copy for existing comma entry.

Why:

- frontend-only
- no schema or provider behavior
- improves operator understanding immediately
- can label watchlists as recommendation-universe management only
- can keep manual entry as the fallback path

Do not start with provider-backed symbol search, schema migration, or
recommendation/schedule resolver changes until the read-model checkpoint is
approved.
