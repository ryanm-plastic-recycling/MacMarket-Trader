import { expect, test } from "@playwright/test";

// Phase 6 close-trade lifecycle e2e coverage:
//   1. Open positions list renders after fill (full lineage).
//   2. Open positions empty state.
//   3. Close ticket opens inline below row.
//   4. Cancel dismisses without POST.
//   5. Close success refetches positions / trades / portfolio summary.
//   6. Closed trade row appears in blotter after close.
//   7. Realized PnL color coding (green positive / red negative).
//   8. Workflow lineage card extension shows open-position / closed-trade lines.
//   9. Close error surfaces InlineFeedback and does not refetch lists.

// ---------------------------------------------------------------------------
// Catch-all + /me mock so the console layout and any unmocked routes resolve
// without proxying to the (absent) Python backend.
// ---------------------------------------------------------------------------
test.beforeEach(async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    await route.fulfill({ status: 404, json: { detail: "not mocked in e2e" } });
  });
  await page.route("**/api/user/me", async (route) => {
    await route.fulfill({ json: { app_role: null, approval_status: "approved" } });
  });
});

// ---------------------------------------------------------------------------
// Reusable mock builders
// ---------------------------------------------------------------------------
type PositionMock = {
  id: number;
  symbol?: string;
  side?: string;
  opened_qty?: number;
  remaining_qty?: number;
  avg_entry_price?: number;
  open_notional?: number;
  status?: string;
  opened_at?: string | null;
  closed_at?: string | null;
  recommendation_id?: string | null;
  replay_run_id?: number | null;
  order_id?: string | null;
};

function buildPosition(overrides: PositionMock): Required<PositionMock> {
  const remaining = overrides.remaining_qty ?? overrides.opened_qty ?? 10;
  const avg = overrides.avg_entry_price ?? 121;
  return {
    id: overrides.id,
    symbol: overrides.symbol ?? "AAPL",
    side: overrides.side ?? "long",
    opened_qty: overrides.opened_qty ?? remaining,
    remaining_qty: remaining,
    avg_entry_price: avg,
    open_notional: overrides.open_notional ?? remaining * avg,
    status: overrides.status ?? "open",
    opened_at: overrides.opened_at ?? "2026-04-28T10:00:00Z",
    closed_at: overrides.closed_at ?? null,
    recommendation_id: overrides.recommendation_id ?? "rec-phase6-e2e",
    replay_run_id: overrides.replay_run_id ?? 22,
    order_id: overrides.order_id ?? "ord-phase6-e2e",
  };
}

type TradeMock = {
  id: number;
  symbol?: string;
  side?: string;
  qty?: number;
  entry_price?: number;
  exit_price?: number | null;
  realized_pnl?: number;
  opened_at?: string | null;
  closed_at?: string | null;
  hold_seconds?: number | null;
  position_id?: number | null;
  recommendation_id?: string | null;
  replay_run_id?: number | null;
  order_id?: string | null;
  close_reason?: string | null;
};

function buildTrade(overrides: TradeMock): Required<TradeMock> {
  return {
    id: overrides.id,
    symbol: overrides.symbol ?? "AAPL",
    side: overrides.side ?? "long",
    qty: overrides.qty ?? 10,
    entry_price: overrides.entry_price ?? 121,
    exit_price: overrides.exit_price ?? 135,
    realized_pnl: overrides.realized_pnl ?? 140,
    opened_at: overrides.opened_at ?? "2026-04-27T10:00:00Z",
    closed_at: overrides.closed_at ?? "2026-04-28T11:00:00Z",
    hold_seconds: overrides.hold_seconds ?? 25 * 3600,
    position_id: overrides.position_id ?? 1,
    recommendation_id: overrides.recommendation_id ?? "rec-phase6-e2e",
    replay_run_id: overrides.replay_run_id ?? 22,
    order_id: overrides.order_id ?? "ord-phase6-e2e",
    close_reason: overrides.close_reason ?? "Target hit",
  };
}

function buildOrder(overrides: { order_id: string; symbol?: string; recommendation_id?: string; replay_run_id?: number }) {
  return {
    order_id: overrides.order_id,
    recommendation_id: overrides.recommendation_id ?? "rec-phase6-e2e",
    replay_run_id: overrides.replay_run_id ?? 22,
    symbol: overrides.symbol ?? "AAPL",
    status: "filled",
    side: "buy",
    shares: 10,
    limit_price: 121,
    created_at: "2026-04-28T09:30:00Z",
    market_data_source: "polygon",
    fallback_mode: false,
    fills: [{ fill_price: 121, filled_shares: 10, timestamp: "2026-04-28T09:31:00Z" }],
  };
}

// ---------------------------------------------------------------------------
// Test 1 — Open positions list renders after fill
// ---------------------------------------------------------------------------
test("open positions card renders row with lineage + closed trades empty state", async ({ page }) => {
  const position = buildPosition({ id: 1, symbol: "AAPL", side: "long", opened_qty: 10, avg_entry_price: 121.00, recommendation_id: "rec-lineage-e2e", order_id: "ord-1" });

  await page.route("**/api/user/orders", async (route) => route.fulfill({ json: { items: [] } }));
  await page.route("**/api/user/orders/portfolio-summary", async (route) => route.fulfill({ status: 404, json: { detail: "not found" } }));
  await page.route("**/api/user/paper-positions**", async (route) => route.fulfill({ json: [position] }));
  await page.route("**/api/user/paper-trades**", async (route) => route.fulfill({ json: [] }));

  await page.goto("/orders?guided=1");

  // Open positions card heading
  await expect(page.getByRole("heading", { name: "Open paper positions" })).toBeVisible();

  // Row data: symbol, side badge, remaining qty, avg entry, recommendation link, Close button
  const positionsCard = page.locator("section.op-card").filter({ has: page.getByRole("heading", { name: "Open paper positions" }) });
  await expect(positionsCard.getByRole("cell", { name: "AAPL" })).toBeVisible();
  await expect(positionsCard.locator(".op-side-badge.is-long")).toBeVisible();
  await expect(positionsCard.getByRole("cell", { name: "10", exact: true })).toBeVisible();
  await expect(positionsCard.getByRole("cell", { name: "121.00" })).toBeVisible();
  await expect(positionsCard.getByRole("link", { name: "rec-lineage-e2e" })).toBeVisible();
  await expect(positionsCard.getByRole("button", { name: "Close position" })).toBeVisible();

  // Closed trades empty state
  const closedCard = page.locator("section.op-card").filter({ has: page.getByRole("heading", { name: "Closed trades (last 50)" }) });
  await expect(closedCard.getByText("No closed trades yet.")).toBeVisible();
});

// ---------------------------------------------------------------------------
// Test 2 — Open positions empty state
// ---------------------------------------------------------------------------
test("open positions card empty state renders when no positions", async ({ page }) => {
  await page.route("**/api/user/orders", async (route) => route.fulfill({ json: { items: [] } }));
  await page.route("**/api/user/orders/portfolio-summary", async (route) => route.fulfill({ status: 404, json: { detail: "not found" } }));
  await page.route("**/api/user/paper-positions**", async (route) => route.fulfill({ json: [] }));
  await page.route("**/api/user/paper-trades**", async (route) => route.fulfill({ json: [] }));

  await page.goto("/orders?guided=1");

  await expect(page.getByText("No open paper positions")).toBeVisible();

  // No Close buttons inside the Open positions card.
  const positionsCard = page.locator("section.op-card").filter({ has: page.getByRole("heading", { name: "Open paper positions" }) });
  await expect(positionsCard.getByRole("button", { name: "Close position" })).toHaveCount(0);
});

// ---------------------------------------------------------------------------
// Test 3 — Close ticket opens inline below row
// ---------------------------------------------------------------------------
test("close ticket opens inline with mark-price default, 5-option reason select, Confirm + Cancel", async ({ page }) => {
  const position = buildPosition({ id: 7, symbol: "AAPL", avg_entry_price: 121.00 });

  await page.route("**/api/user/orders", async (route) => route.fulfill({ json: { items: [] } }));
  await page.route("**/api/user/orders/portfolio-summary", async (route) => route.fulfill({ status: 404, json: { detail: "not found" } }));
  await page.route("**/api/user/paper-positions**", async (route) => route.fulfill({ json: [position] }));
  await page.route("**/api/user/paper-trades**", async (route) => route.fulfill({ json: [] }));

  await page.goto("/orders?guided=1");

  const positionsCard = page.locator("section.op-card").filter({ has: page.getByRole("heading", { name: "Open paper positions" }) });
  await positionsCard.getByRole("button", { name: "Close position" }).click();

  // Inline ticket — table-scoped (not a modal). The ticket sits in a sibling <tr>.
  const markInput = positionsCard.locator('input[type="number"]');
  await expect(markInput).toBeVisible();
  await expect(markInput).toHaveValue("121.00");

  const reasonSelect = positionsCard.locator("select");
  await expect(reasonSelect).toBeVisible();
  const optionTexts = await reasonSelect.locator("option").allTextContents();
  expect(optionTexts).toEqual(["Target hit", "Stop hit", "Manual exit", "Time exit", "Other"]);

  await expect(positionsCard.getByRole("button", { name: "Confirm close" })).toBeVisible();
  await expect(positionsCard.getByRole("button", { name: "Cancel" })).toBeVisible();
});

// ---------------------------------------------------------------------------
// Test 4 — Close ticket Cancel dismisses without POST
// ---------------------------------------------------------------------------
test("close ticket Cancel dismisses without firing POST close", async ({ page }) => {
  const position = buildPosition({ id: 9, symbol: "AAPL" });
  let closePostCount = 0;

  await page.route("**/api/user/orders", async (route) => route.fulfill({ json: { items: [] } }));
  await page.route("**/api/user/orders/portfolio-summary", async (route) => route.fulfill({ status: 404, json: { detail: "not found" } }));
  await page.route("**/api/user/paper-positions**", async (route, request) => {
    if (request.method() === "POST" && request.url().includes("/close")) {
      closePostCount++;
      await route.fulfill({ json: buildTrade({ id: 1 }) });
      return;
    }
    await route.fulfill({ json: [position] });
  });
  await page.route("**/api/user/paper-trades**", async (route) => route.fulfill({ json: [] }));

  await page.goto("/orders?guided=1");

  const positionsCard = page.locator("section.op-card").filter({ has: page.getByRole("heading", { name: "Open paper positions" }) });
  await positionsCard.getByRole("button", { name: "Close position" }).click();
  await expect(positionsCard.locator('input[type="number"]')).toBeVisible();

  await positionsCard.getByRole("button", { name: "Cancel" }).click();

  // Ticket gone, no POST hit.
  await expect(positionsCard.locator('input[type="number"]')).toHaveCount(0);
  expect(closePostCount).toBe(0);
});

// ---------------------------------------------------------------------------
// Test 5 — Close success refetches positions / trades / portfolio summary
// ---------------------------------------------------------------------------
test("close success refetches positions, trades, and portfolio summary; surfaces realized PnL", async ({ page }) => {
  const position = buildPosition({ id: 11, symbol: "AAPL", avg_entry_price: 121.00 });

  let positionsCalls = 0;
  let tradesCalls = 0;
  let summaryCalls = 0;

  await page.route("**/api/user/orders", async (route) => route.fulfill({ json: { items: [] } }));
  await page.route("**/api/user/orders/portfolio-summary", async (route) => {
    summaryCalls++;
    await route.fulfill({ json: { open_positions: 0, total_open_notional: 0, unrealized_pnl: null, realized_pnl: 142.50, closed_trade_count: 1, win_rate: 1.0 } });
  });
  await page.route("**/api/user/paper-positions**", async (route, request) => {
    if (request.method() === "POST" && request.url().includes("/close")) {
      await route.fulfill({ json: buildTrade({ id: 99, symbol: "AAPL", realized_pnl: 142.50, close_reason: "Target hit" }) });
      return;
    }
    positionsCalls++;
    // After close, return empty; before close, return the open position.
    await route.fulfill({ json: positionsCalls === 1 ? [position] : [] });
  });
  await page.route("**/api/user/paper-trades**", async (route) => {
    tradesCalls++;
    await route.fulfill({ json: tradesCalls === 1 ? [] : [buildTrade({ id: 99, realized_pnl: 142.50 })] });
  });

  await page.goto("/orders?guided=1");

  const positionsCard = page.locator("section.op-card").filter({ has: page.getByRole("heading", { name: "Open paper positions" }) });
  await positionsCard.getByRole("button", { name: "Close position" }).click();
  await positionsCard.getByRole("button", { name: "Confirm close" }).click();

  await expect(page.getByText(/realized P&L \+?142\.50/)).toBeVisible();

  expect(positionsCalls, "paper-positions GET should have been called twice (mount + post-close)").toBeGreaterThanOrEqual(2);
  expect(tradesCalls, "paper-trades GET should have been called twice (mount + post-close)").toBeGreaterThanOrEqual(2);
  expect(summaryCalls, "portfolio-summary GET should have been called twice (mount + post-close)").toBeGreaterThanOrEqual(2);
});

// ---------------------------------------------------------------------------
// Test 6 — Closed trade row appears after close
// ---------------------------------------------------------------------------
test("closed trades card shows the new trade row after a successful close", async ({ page }) => {
  const position = buildPosition({ id: 13, symbol: "MSFT", avg_entry_price: 400, opened_qty: 5 });
  const tradeAfter = buildTrade({ id: 200, symbol: "MSFT", qty: 5, entry_price: 400, exit_price: 410, realized_pnl: 50, hold_seconds: 2 * 3600 + 14 * 60, close_reason: "Target hit" });

  let tradesCalls = 0;

  await page.route("**/api/user/orders", async (route) => route.fulfill({ json: { items: [] } }));
  await page.route("**/api/user/orders/portfolio-summary", async (route) => route.fulfill({ status: 404, json: { detail: "not found" } }));
  await page.route("**/api/user/paper-positions**", async (route, request) => {
    if (request.method() === "POST" && request.url().includes("/close")) {
      await route.fulfill({ json: tradeAfter });
      return;
    }
    await route.fulfill({ json: [position] });
  });
  await page.route("**/api/user/paper-trades**", async (route) => {
    tradesCalls++;
    await route.fulfill({ json: tradesCalls === 1 ? [] : [tradeAfter] });
  });

  await page.goto("/orders?guided=1");

  const positionsCard = page.locator("section.op-card").filter({ has: page.getByRole("heading", { name: "Open paper positions" }) });
  await positionsCard.getByRole("button", { name: "Close position" }).click();
  await positionsCard.getByRole("button", { name: "Confirm close" }).click();

  const closedCard = page.locator("section.op-card").filter({ has: page.getByRole("heading", { name: "Closed trades (last 50)" }) });
  await expect(closedCard.getByRole("cell", { name: "MSFT" })).toBeVisible();
  await expect(closedCard.getByRole("cell", { name: "5", exact: true })).toBeVisible();
  await expect(closedCard.getByRole("cell", { name: "400.00 → 410.00" })).toBeVisible();
  await expect(closedCard.getByRole("cell", { name: /\+50\.00/ })).toBeVisible();
  await expect(closedCard.getByRole("cell", { name: "2h 14m" })).toBeVisible();
  await expect(closedCard.getByRole("cell", { name: "Target hit" })).toBeVisible();
});

// ---------------------------------------------------------------------------
// Test 7 — Realized PnL color coding
// ---------------------------------------------------------------------------
test("closed trades realized PnL uses green for positive and red for negative", async ({ page }) => {
  const positiveTrade = buildTrade({ id: 301, symbol: "AAPL", realized_pnl: 220 });
  const negativeTrade = buildTrade({ id: 302, symbol: "MSFT", realized_pnl: -85 });

  await page.route("**/api/user/orders", async (route) => route.fulfill({ json: { items: [] } }));
  await page.route("**/api/user/orders/portfolio-summary", async (route) => route.fulfill({ status: 404, json: { detail: "not found" } }));
  await page.route("**/api/user/paper-positions**", async (route) => route.fulfill({ json: [] }));
  await page.route("**/api/user/paper-trades**", async (route) => route.fulfill({ json: [positiveTrade, negativeTrade] }));

  await page.goto("/orders?guided=1");

  const closedCard = page.locator("section.op-card").filter({ has: page.getByRole("heading", { name: "Closed trades (last 50)" }) });

  const posCell = closedCard.getByRole("cell", { name: /\+220\.00/ });
  await expect(posCell).toBeVisible();
  // pnlColor positive → "#21c06e" → rgb(33, 192, 110)
  await expect(posCell).toHaveCSS("color", "rgb(33, 192, 110)");

  const negCell = closedCard.getByRole("cell", { name: /-85\.00/ });
  await expect(negCell).toBeVisible();
  // pnlColor negative → "#e07a7a" → rgb(224, 122, 122)
  await expect(negCell).toHaveCSS("color", "rgb(224, 122, 122)");
});

// ---------------------------------------------------------------------------
// Test 8 — Workflow lineage card extension
// ---------------------------------------------------------------------------
test("workflow lineage card appends open-position and closed-trade lines based on selected order", async ({ page }) => {
  const orderOpen = buildOrder({ order_id: "ord-open", symbol: "AAPL" });
  const orderClosed = buildOrder({ order_id: "ord-closed", symbol: "MSFT" });

  const openPosition = buildPosition({ id: 31, symbol: "AAPL", order_id: "ord-open" });
  const closedTrade = buildTrade({ id: 41, symbol: "MSFT", order_id: "ord-closed", realized_pnl: 75.25 });

  await page.route("**/api/user/orders", async (route) => route.fulfill({ json: { items: [orderOpen, orderClosed] } }));
  await page.route("**/api/user/orders/portfolio-summary", async (route) => route.fulfill({ status: 404, json: { detail: "not found" } }));
  await page.route("**/api/user/paper-positions**", async (route) => route.fulfill({ json: [openPosition] }));
  await page.route("**/api/user/paper-trades**", async (route) => route.fulfill({ json: [closedTrade] }));

  await page.goto("/orders?guided=1");

  const lineageCard = page.locator("section.op-card").filter({ has: page.getByRole("heading", { name: "Workflow lineage" }) });

  // Click the AAPL row in the order history table to select ord-open.
  const orderHistoryCard = page.locator("section.op-card").filter({ has: page.getByRole("heading", { name: /Order history/ }) });
  await orderHistoryCard.getByRole("row").filter({ hasText: "AAPL" }).click();
  await expect(lineageCard.getByText(/↳ open position #31/)).toBeVisible();

  // Switch to the MSFT row → closed trade lineage line.
  await orderHistoryCard.getByRole("row").filter({ hasText: "MSFT" }).click();
  await expect(lineageCard.getByText(/↳ closed trade #41 · realized/)).toBeVisible();
  await expect(lineageCard.getByText(/\+75\.25/)).toBeVisible();
});

// ---------------------------------------------------------------------------
// Test 9 — Close error surfaces InlineFeedback and does not refetch
// ---------------------------------------------------------------------------
test("close error renders feedback message, leaves ticket open, does not refetch lists", async ({ page }) => {
  const position = buildPosition({ id: 51, symbol: "AAPL" });

  let positionsGetCount = 0;
  let tradesGetCount = 0;

  await page.route("**/api/user/orders", async (route) => route.fulfill({ json: { items: [] } }));
  await page.route("**/api/user/orders/portfolio-summary", async (route) => route.fulfill({ status: 404, json: { detail: "not found" } }));
  await page.route("**/api/user/paper-positions**", async (route, request) => {
    if (request.method() === "POST" && request.url().includes("/close")) {
      await route.fulfill({ status: 400, json: { detail: "Position already closed" } });
      return;
    }
    positionsGetCount++;
    await route.fulfill({ json: [position] });
  });
  await page.route("**/api/user/paper-trades**", async (route) => {
    tradesGetCount++;
    await route.fulfill({ json: [] });
  });

  await page.goto("/orders?guided=1");

  const positionsCard = page.locator("section.op-card").filter({ has: page.getByRole("heading", { name: "Open paper positions" }) });
  await positionsCard.getByRole("button", { name: "Close position" }).click();

  const initialPositionsCount = positionsGetCount;
  const initialTradesCount = tradesGetCount;

  await positionsCard.getByRole("button", { name: "Confirm close" }).click();

  await expect(page.getByText("Position already closed")).toBeVisible();

  // Ticket remains open
  await expect(positionsCard.locator('input[type="number"]')).toBeVisible();
  await expect(positionsCard.getByRole("button", { name: "Confirm close" })).toBeVisible();

  // Lists were NOT refetched on error
  expect(positionsGetCount, "paper-positions GET should NOT be refetched on close error").toBe(initialPositionsCount);
  expect(tradesGetCount, "paper-trades GET should NOT be refetched on close error").toBe(initialTradesCount);
});
