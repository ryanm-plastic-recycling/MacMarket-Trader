# Symbol Discovery and Watchlist Design

Last updated: 2026-04-30

## Purpose

This document started as a design checkpoint for better user-scoped symbol
discovery, watchlist management, and recommendation-universe selection. It now
also tracks the completed additive schema, internal repository/resolver
foundation, and current watchlist UI polish slices.

It does not implement symbol search, change recommendation generation, add
provider probes, change current schedule execution, or imply live trading /
brokerage routing.

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
  shows a Watchlists card where users enter a watchlist name plus a manual
  symbol list, review the same parsed preview, search/sort saved lists, inspect
  normalized symbol chips/counts, filter symbols inside a list, remove an
  individual chip through the existing update route, then apply the saved list
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
- `watchlists` currently has `id`, `app_user_id`, `name`, `symbols` JSON, and
  `created_at`.
- `WatchlistRepository` lists by `app_user_id`, upserts by
  `(app_user_id, name)`, updates by `(id, app_user_id)`, and deletes by
  `(id, app_user_id)`.
- Watchlist API responses currently expose `id`, `name`, `symbols`, and
  `created_at`; they do not expose per-symbol metadata, active state, tags, or
  notes.
- The current frontend Watchlists card edits one name plus one manual symbol
  field, then saves the parsed `symbols` array, can apply a saved list back into
  the schedule form, and now has a small management table around the same
  compatibility data.
- Schedule payload symbols are copied into each schedule payload rather than
  linked to a watchlist row.
- `strategy_report_schedules.payload.symbols` is the execution-time symbol
  snapshot used by `StrategyReportService.run_schedule()`.
- Recommendation queue requests are transient and are not currently linked to a
  persisted watchlist.
- `/user/recommendations/queue` receives a `symbols` array in the request,
  uppercases entries, fetches bars per symbol, and passes a `bars_by_symbol`
  map into `DeterministicRankingEngine.rank_candidates(...)`.
- Provider/source metadata for symbols is not persisted in watchlists.
- There is no current provider-backed symbol search endpoint or symbol metadata
  table.

Current limitations:

- Users must already know symbols.
- Names, asset types, exchanges, provider support, options eligibility, and
  index/ETF substitution guidance are not first-class watchlist fields.
- Duplicate handling has a parser-preview warning in current manual-entry and
  watchlist editing flows; richer bulk import and audit remain deferred.
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

## 10W3 Schema / Read-model Checkpoint

Status: complete as a documentation-only design checkpoint.

No schema, migration, backend, frontend, provider, schedule, or
recommendation-generation behavior is implemented by this section. It defines
the future read model and compatibility plan only.

## 10W4 Schema / Migration Foundation

Status: complete for the current additive schema foundation.

Implemented now:

- `user_symbol_universe` ORM model and Alembic table for per-user canonical
  symbol rows
- `watchlist_symbols` ORM model and Alembic table for future normalized
  watchlist membership rows
- nullable provider metadata fields so manual symbols do not require provider
  lookup
- `active` defaults, timestamp fields, symbol snapshots, uniqueness
  constraints, and indexes for later user-scoped reads
- focused schema/migration tests for upgrade, downgrade, defaults, nullable
  provider metadata, duplicate constraints, and snapshot-only watchlist
  membership

Still unchanged by `10W4`:

- existing `watchlists.symbols` JSON/list behavior
- existing `strategy_report_schedules.payload.symbols` behavior
- recommendation queue symbol handling
- schedule execution behavior
- frontend UI
- provider-backed symbol search or metadata enrichment
- live routing or brokerage execution

## 10W5 Repository / Read-model and Resolver Foundation

Status: complete for the current backend-only repository/read-model scope.

Implemented now:

- `SymbolUniverseRepository` internal helpers to upsert/get/list user-symbol
  rows, mark them active/inactive, add/list/deactivate/remove normalized
  watchlist membership rows, and create snapshot-only membership rows without
  provider metadata
- `SymbolUniverseResolver` pure helper to normalize, uppercase, trim, ignore
  blanks, dedupe, apply exclusions, and combine pinned, manual, watchlist, and
  active user-universe symbols in deterministic order
- resolver fallback that can read legacy `watchlists.symbols` snapshots when a
  watchlist has not been represented in normalized membership rows yet
- focused backend tests for duplicate/upsert behavior, nullable provider
  metadata, active filtering, snapshot-only membership, user scoping, resolver
  dedupe/order, and legacy watchlist compatibility

Still unchanged by `10W5`:

- existing `watchlists.symbols` JSON/list behavior
- existing `strategy_report_schedules.payload.symbols` behavior
- recommendation queue symbol handling
- schedule execution behavior
- frontend UI
- provider-backed symbol search or metadata enrichment
- live routing or brokerage execution

## 10W6 Current Watchlist Table UI Polish

Status: complete for the current frontend-only compatibility scope.

Implemented now:

- the Schedules Watchlists card remains on existing user-scoped
  `watchlists.symbols` JSON/list data and existing watchlist create/update/delete
  routes
- saved watchlists can be searched by name or symbol and sorted by name or
  symbol count
- rows show clear symbol counts, created date when available, normalized symbol
  chips, and per-list symbol filtering
- current manual edit fields reuse the shared parser preview for uppercase
  normalization, counts, and duplicate feedback
- individual symbol removal is available from a chip when at least one symbol
  remains; it uses the existing watchlist `PUT` route with the remaining
  symbols array
- operator copy labels current lists as research-universe management, notes that
  provider metadata may be unavailable, keeps SPX/NDX versus SPY/QQQ guidance
  visible, and explains that normalized watchlist management remains future work

Still unchanged by `10W6`:

- existing `watchlists.symbols` JSON/list persistence
- normalized `user_symbol_universe` / `watchlist_symbols` production UI usage
- existing `strategy_report_schedules.payload.symbols` behavior
- recommendation queue symbol handling
- schedule execution behavior
- provider-backed symbol search or metadata enrichment
- bulk import / import audit
- active/inactive symbol state, tags/groups, and notes in production UI
- live routing or brokerage execution

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

### Option A: Keep Existing Watchlist JSON/List Model and Add UI Only

Keep `watchlists.symbols` as a JSON `list[str]` and build richer frontend
editing around the current API.

Evaluation:

- Migration complexity:
  lowest; no migration required.
- Compatibility with schedules/recommendations:
  strongest short-term compatibility because schedules and queue requests
  already accept symbol arrays.
- User scoping:
  already adequate at the watchlist row level through `app_user_id`.
- Duplicate handling:
  can be handled in frontend/backend parsing, but cannot be enforced cleanly
  across all watchlists or a user-wide universe.
- Active/inactive support:
  weak; would require JSON objects or sidecar state.
- Tags/groups support:
  weak; tags inside JSON would be hard to query and sort.
- Notes/source metadata:
  possible only as JSON object expansion, with poor queryability.
- Provider metadata enrichment:
  poor fit; nullable metadata inside JSON is difficult to index and refresh.
- Rollback risk:
  lowest if strings remain strings; rises if the JSON payload changes from
  strings to objects.
- Test complexity:
  low for current behavior, but grows quickly for metadata, filtering, and
  duplicate rules.

Verdict:

- Safe for short-term copy/UX polish only.
- Not sufficient as the long-term read model for searchable/sortable
  watchlists, active filters, tags, notes, or metadata.

### Option B: Add Normalized Watchlist Membership Records, Preserve Existing Compatibility

Keep `watchlists` as the named collection table, preserve `watchlists.symbols`
as a compatibility snapshot, and add a normalized membership table such as
`watchlist_symbols`.

Evaluation:

- Migration complexity:
  moderate; requires a table migration and optional backfill from existing
  `watchlists.symbols`.
- Compatibility with schedules/recommendations:
  good if resolver functions continue to emit symbol arrays and legacy
  `watchlists.symbols` remains readable.
- User scoping:
  inherited through `watchlists.app_user_id`; direct `app_user_id` on the
  membership table could be redundant but useful for query/index simplicity.
- Duplicate handling:
  good within a watchlist via unique `(watchlist_id, normalized_symbol)` or
  `(watchlist_id, user_symbol_id)`.
- Active/inactive support:
  good per watchlist membership.
- Tags/groups support:
  possible per membership, but user-wide tags across watchlists remain
  awkward unless tags are normalized separately.
- Notes/source metadata:
  possible per membership; provider metadata remains duplicated if the same
  symbol appears in many watchlists.
- Provider metadata enrichment:
  only moderate; without a canonical user symbol row, enrichment is repeated
  per membership or kept in JSON.
- Rollback risk:
  moderate; the compatibility `symbols` snapshot lets old routes keep working
  while new membership UI can be disabled.
- Test complexity:
  moderate; must prove membership scoping, compatibility snapshots, and
  duplicate handling.

Verdict:

- Useful intermediate model if the product only needs richer watchlist rows.
- Less ideal if the product needs a user-wide active universe, tags, notes, or
  provider/source metadata independent of watchlist membership.

### Option C: Add User Symbol Universe plus Watchlist Membership Records

Add a canonical per-user symbol table such as `user_symbol_universe`, and add a
membership/join table such as `watchlist_symbols` that links watchlists to
those canonical rows. Preserve current `watchlists.symbols` as a compatibility
snapshot until migration closure.

Evaluation:

- Migration complexity:
  highest, but can be staged safely: add nullable tables first, backfill later,
  then route new UI through the read model.
- Compatibility with schedules/recommendations:
  strong if a resolver emits the same `list[str]` arrays already consumed by
  schedules and recommendation queues.
- User scoping:
  strongest; `user_symbol_universe.app_user_id` makes each symbol row
  explicitly user-scoped, and watchlists still remain user-scoped.
- Duplicate handling:
  strongest; unique `(app_user_id, normalized_symbol)` prevents duplicate
  canonical rows, and unique `(watchlist_id, user_symbol_id)` prevents
  duplicate membership.
- Active/inactive support:
  strongest; can support user-wide active state plus optional
  membership-specific active state.
- Tags/groups support:
  strongest; tags can start as JSON on the user symbol row and later normalize
  if needed.
- Notes/source metadata:
  strongest; user notes and source/import metadata can live once on the
  canonical row, with optional watchlist-specific notes on membership.
- Provider metadata enrichment:
  best fit; provider metadata can be nullable, non-blocking, and refreshed
  independently of watchlist membership.
- Rollback risk:
  manageable if current `watchlists.symbols` and schedule payload snapshots are
  preserved until all read paths are migrated.
- Test complexity:
  highest, but the tests map cleanly to user scoping, uniqueness, resolver
  behavior, metadata fallback, and compatibility guarantees.

Verdict:

- Best long-term model.
- Requires explicit migration/backfill and resolver phases, but keeps current
  ranking and schedule execution contracts stable.

## Recommended Approach

Use Option C with a compatibility-first rollout.

Reasoning:

- The current repo already has user-scoped watchlists and schedule payloads, so
  throwing them away would create unnecessary risk.
- Normalized per-symbol rows are the right long-term model for duplicate
  handling, active/inactive status, tags, notes, source labels, and provider
  metadata.
- The safest implementation can preserve current `watchlists.symbols` as a
  compatibility snapshot while new resolver functions emit the same symbol
  arrays already used by Recommendations and Schedules.
- `RecommendationService.generate()` and deterministic ranking can stay
  unchanged while the operator universe improves around them.

Recommended source-of-truth rule for later implementation:

- `user_symbol_universe` is the long-term per-user symbol truth.
- `watchlists` remain named collections and legacy compatibility snapshots.
- `watchlist_symbols` links named watchlists to canonical user symbol rows.
- schedules should eventually store a universe selector snapshot plus a
  resolved symbol snapshot for auditability.
- recommendation queue requests should accept a resolved list plus optional
  provenance such as `watchlist_id`, `tags`, `exclusions`, and `manual_symbols`.

## Proposed Future Fields

These began as `10W3` design fields. `10W4` implements the additive schema
foundation for the core symbol-universe and watchlist-membership fields while
leaving repository/read-model behavior, backfill, resolver wiring, UI, and
provider enrichment deferred.

### `user_symbol_universe`

- `id`: integer primary key
- `app_user_id`: foreign key to `app_users.id`, indexed
- `symbol`: operator-facing symbol as entered or displayed, for example `BRK.B`
- `normalized_symbol`: canonical uppercase lookup key used for uniqueness and
  resolver dedupe, for example `BRK.B`
- `display_name`: nullable company/security name
- `asset_type`: nullable enum/string such as `equity`, `etf`, `index`,
  `option_underlying`, `crypto`, or `unknown`
- `exchange`: nullable exchange/venue label
- `provider_source`: nullable provider/source label, for example `polygon`
- `provider_symbol`: nullable provider-specific symbol if it differs from the
  app normalized symbol
- `metadata_status`: nullable status such as `manual`, `metadata_unavailable`,
  `provider_discovered`, or `provider_verified`
- `notes`: nullable operator notes
- `active`: boolean user-wide active flag, default `true`
- `tags`: JSON list of strings for early tags/groups such as `Core`, `ETFs`,
  `Tech`, `Options Candidates`, or `Watch Only`
- `created_at`: timezone-aware timestamp, indexed
- `updated_at`: timezone-aware timestamp

Suggested constraints/indexes:

- unique `(app_user_id, normalized_symbol)`
- index `(app_user_id, active)`
- index `(app_user_id, asset_type)` if asset filters land

### `watchlist_symbols`

- `id`: integer primary key
- `watchlist_id`: foreign key to `watchlists.id`, indexed
- `user_symbol_id`: foreign key to `user_symbol_universe.id`, indexed
- `active`: boolean membership-level active flag, default `true`
- `sort_order`: nullable integer for user ordering
- `added_at`: timezone-aware timestamp
- `notes`: nullable watchlist-specific notes

Suggested constraints/indexes:

- unique `(watchlist_id, user_symbol_id)`
- index `(watchlist_id, active, sort_order)`

Compatibility notes:

- Keep `watchlists.symbols` as a string-array snapshot while old UI/API flows
  still depend on it.
- Backfill `user_symbol_universe` from `watchlists.symbols`, but do not require
  provider metadata during backfill.
- Do not remove or change `strategy_report_schedules.payload.symbols`; keep it
  as the audit/execution snapshot even after selectors exist.

## Resolver Design

Future workflows should call a resolver that returns a deterministic resolved
symbol list and a provenance summary. It should not call
`RecommendationService.generate()` and should not change deterministic ranking
logic.

Inputs:

- `manual_symbols`: temporary parsed symbols from the current text field
- `all_active`: boolean to include all active user universe rows
- `watchlist_ids`: selected user-scoped watchlists
- `tags`: selected user-scoped tags/groups
- `include_inactive`: normally false
- `exclusions`: symbols to omit after inclusion
- `pinned_symbols`: symbols to put first without duplicating

Resolution rules:

1. Normalize every incoming symbol to the same uppercase `normalized_symbol`
   format used by 10W2 parsing.
2. Load only rows owned by the current `app_user_id`.
3. Include active user-universe rows, selected watchlist memberships, selected
   tags, and manual temporary symbols according to the selector.
4. Apply exclusions after inclusion.
5. Dedupe by `normalized_symbol`, preserving deterministic order:
   pinned symbols, manual symbols, watchlist order, tag/group order, then
   alphabetical fallback.
6. Return:
   - `symbols`: resolved `list[str]`
   - `source`: `manual`, `watchlist`, `tags`, `all_active`, or `mixed`
   - `provenance`: selected watchlist IDs, tags, exclusions, duplicate count,
     and metadata fallback count

Schedules should eventually persist both:

- `universe_selector`: the operator's selector, for example watchlist IDs,
  tags, exclusions, pinned symbols, and manual symbols
- `symbols`: the resolved snapshot used by a run

Recommendations should eventually send the resolved `symbols` array plus
optional provenance to the queue endpoint, while the endpoint and ranking engine
continue to treat symbols as an input array.

## Migration / Compatibility Strategy

Recommended staged implementation after this design checkpoint:

1. `10W4` schema/migration foundation:
   complete for the current additive table/model/migration slice. It added the
   new normalized tables, indexes, uniqueness constraints, nullable provider
   metadata, and schema tests without changing current routes, recommendation
   generation, or schedule execution.
2. Backfill helper:
   deferred. Create an optional, idempotent backfill from existing
   `watchlists.symbols` into user universe rows and watchlist memberships only
   in a later explicitly scoped pass. Manual symbols should use
   `metadata_status=manual` or `metadata_unavailable` if that field is added
   later.
3. Repository read model:
   complete for the current internal helper scope. `SymbolUniverseRepository`
   can list, upsert, deactivate, and resolve user symbols by current user while
   `WatchlistRepository` compatibility methods remain intact.
4. Compatibility bridge:
   keep writing or deriving `watchlists.symbols` string arrays until old
   Schedules UI/API paths are retired.
5. UI table:
   introduce a table view for user symbols and watchlist memberships after the
   repository read model exists.
6. Selector integration:
   add recommendation/schedule universe selectors that resolve to the current
   `symbols` array. Keep schedule payload snapshots.
7. Provider-backed discovery:
   only after explicit provider-design approval, enrich nullable metadata from
   provider search. Missing metadata must not block manual symbols.
8. Closure:
   audit old compatibility paths before considering removal of
   `watchlists.symbols` reliance.

Original `10W4` target:

   add `user_symbol_universe` and `watchlist_symbols` tables with nullable
   provider metadata, indexes, and uniqueness constraints. Do not change
   current routes yet.

Rollback posture:

- If the new UI is disabled, old `watchlists.symbols`,
  `strategy_report_schedules.payload.symbols`, and direct queue symbol arrays
  should still work.
- If provider metadata enrichment fails, manual symbols remain usable.
- If backfill is incomplete, resolver code should fall back to current
  watchlist snapshots rather than blocking scheduled reports.

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

- migration creates `user_symbol_universe` and `watchlist_symbols`
- manual add creates a user-scoped symbol row
- manual symbols can exist without provider metadata
- duplicate add returns deterministic skip/merge feedback
- duplicate normalized symbols are prevented within a user universe
- delete or deactivate affects only the current user
- active/inactive filtering affects universe resolution
- tags/groups filter the resolved universe correctly
- watchlist membership is user-scoped
- watchlist membership prevents duplicate `(watchlist_id, user_symbol_id)`
- existing `watchlists.symbols` compatibility rows remain readable
- schedule creation can store universe selectors and resolved symbol snapshots
- recommendation queue can receive a resolved universe without changing
  recommendation generation
- resolver returns deduped symbols with deterministic ordering
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
  complete with this section; design normalized universe tables, backfill,
  compatibility, resolver behavior, and rollback before any migration.
- `10W4` schema/migration foundation:
  complete; adds normalized tables, indexes, uniqueness constraints, nullable
  provider metadata, and focused schema tests while keeping old
  `watchlists.symbols` and schedule payload symbol snapshots untouched. No
  backfill was run in this slice.
- `10W5` repository/read-model and resolver:
  complete; adds user-symbol repository methods plus resolver functions that
  emit current symbol arrays and provenance without changing ranking/scoring,
  recommendation generation, schedule execution, current watchlist JSON
  behavior, or frontend UI.
- `10W6` user-scoped watchlist table UI:
  complete for current compatibility UI; adds search, sort, symbol counts,
  normalized chips, per-list symbol filtering, duplicate feedback, and
  per-symbol removal while keeping existing `watchlists.symbols` JSON behavior.
- `10W7` bulk import and duplicate handling:
  paste/import workflow with deterministic duplicate feedback.
- `10W8` recommendation/schedule universe selection:
  resolve watchlists, tags/groups, exclusions, pinned symbols, and temporary
  manual symbols into current symbol arrays.
- `10W9` provider-backed symbol discovery:
  add provider-backed search only after explicit provider-design approval.
- `10W10` closure:
  docs/tests audit proving user scoping, fallback metadata, no execution
  implication, and no recommendation-generation drift.

## Suggested Next Implementation Slice

Next after `10W6`: bulk import and duplicate handling, if explicitly
authorized.

Why:

- current manual entry and saved-list management are easier to inspect
- bulk paste/import can build on the existing parser preview without provider
  search or recommendation/schedule selector behavior
- it keeps provider-backed search, storage replacement, normalized table
  production UI, and ranking/schedule behavior changes deferred

Do not start the next slice with provider-backed symbol search,
recommendation/schedule selector behavior, storage replacement, normalized
symbol-universe production UI, or ranking changes. The next implementation
should be a small import/dedupe UX slice around the current manual parser.
