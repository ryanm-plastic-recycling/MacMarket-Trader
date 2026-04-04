# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: phase1-closeout.spec.ts >> analysis -> recommendations -> replay -> orders click path with stale-banner recovery
- Location: tests\e2e\phase1-closeout.spec.ts:15:5

# Error details

```
Test timeout of 60000ms exceeded.
```

```
Error: locator.click: Test timeout of 60000ms exceeded.
Call log:
  - waiting for getByTestId('analysis-refresh-button')

```

# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - main [ref=e2]:
    - img "MacMarket Trader" [ref=e3]
    - paragraph [ref=e4]: Operator sign-in · Strategy Workbench → Recommendations → Replay → Paper Orders
    - generic [ref=e6]:
      - generic [ref=e7]:
        - generic [ref=e8]:
          - link "MacMarket" [ref=e10] [cursor=pointer]:
            - /url: http://127.0.0.1:9500/
            - img "MacMarket" [ref=e11]
          - generic [ref=e12]:
            - heading "Sign in to MacMarket" [level=1] [ref=e13]
            - paragraph [ref=e14]: Welcome back! Please sign in to continue
        - generic [ref=e15]:
          - generic [ref=e17]:
            - button "Sign in with Apple" [ref=e18] [cursor=pointer]:
              - img "Sign in with Apple" [ref=e19]
            - button "Sign in with Google" [ref=e20] [cursor=pointer]:
              - img "Sign in with Google" [ref=e21]
            - button "Sign in with Microsoft" [ref=e22] [cursor=pointer]:
              - img "Sign in with Microsoft" [ref=e23]
          - paragraph [ref=e26]: or
          - generic [ref=e28]:
            - generic [ref=e29]:
              - generic [ref=e32]:
                - generic [ref=e34]: Email address
                - textbox "Email address" [ref=e35]:
                  - /placeholder: Enter your email address
              - generic:
                - generic:
                  - generic:
                    - generic:
                      - generic: Password
                    - generic:
                      - textbox "Password":
                        - /placeholder: Enter your password
                      - button "Show password":
                        - img
            - button "Continue" [ref=e38] [cursor=pointer]:
              - generic [ref=e39]:
                - text: Continue
                - img [ref=e40]
      - generic [ref=e42]:
        - generic [ref=e43]:
          - generic [ref=e44]: Don’t have an account?
          - link "Sign up" [ref=e45] [cursor=pointer]:
            - /url: http://127.0.0.1:9500/sign-up#/?redirect_url=http%3A%2F%2F127.0.0.1%3A9500%2Fanalysis
        - generic [ref=e47]:
          - generic [ref=e49]:
            - paragraph [ref=e50]: Secured by
            - link "Clerk logo" [ref=e51] [cursor=pointer]:
              - /url: https://go.clerk.com/components
              - img [ref=e52]
          - paragraph [ref=e57]: Development mode
  - button "Open Next.js Dev Tools" [ref=e63] [cursor=pointer]:
    - img [ref=e64]
  - alert [ref=e67]
```

# Test source

```ts
  1   | import { expect, test } from "@playwright/test";
  2   | 
  3   | function chartPayload() {
  4   |   const candles = Array.from({ length: 40 }, (_, idx) => ({
  5   |     time: `2026-01-${String((idx % 28) + 1).padStart(2, "0")}`,
  6   |     open: 100 + idx,
  7   |     high: 101 + idx,
  8   |     low: 99 + idx,
  9   |     close: 100.5 + idx,
  10  |     volume: 1_000_000 + idx * 1_000,
  11  |   }));
  12  |   return { symbol: "AAPL", timeframe: "1D", data_source: "polygon", fallback_mode: false, candles, heikin_ashi_candles: candles };
  13  | }
  14  | 
  15  | test("analysis -> recommendations -> replay -> orders click path with stale-banner recovery", async ({ page }) => {
  16  |   let recommendationListCalls = 0;
  17  | 
  18  |   await page.route("**/api/user/strategy-registry", async (route) => {
  19  |     await route.fulfill({ json: [{ strategy_id: "event_continuation", display_name: "Event Continuation", market_modes: ["equities"] }] });
  20  |   });
  21  |   await page.route("**/api/user/analysis/setup**", async (route) => {
  22  |     await route.fulfill({
  23  |       json: {
  24  |         market_mode: "equities",
  25  |         workflow_source: "provider",
  26  |         strategy: "Event Continuation",
  27  |         active: true,
  28  |         active_reason: "phase1 e2e",
  29  |         trigger: "above prior-day high",
  30  |         entry_zone: { low: 120, high: 122 },
  31  |         invalidation: { price: 118, reason: "breakdown" },
  32  |         targets: [126, 129],
  33  |         confidence: 0.66,
  34  |         filters: ["trend"],
  35  |       },
  36  |     });
  37  |   });
  38  |   await page.route("**/api/charts/haco**", async (route) => route.fulfill({ json: chartPayload() }));
  39  |   await page.route("**/api/user/recommendations/generate", async (route) => {
  40  |     await route.fulfill({ json: { recommendation_id: "rec-phase1-e2e", market_data_source: "polygon", fallback_mode: false } });
  41  |   });
  42  |   await page.route("**/api/user/recommendations**", async (route) => {
  43  |     recommendationListCalls += 1;
  44  |     if (recommendationListCalls === 1) {
  45  |       await route.fulfill({ status: 401, json: { detail: "Invalid token" } });
  46  |       return;
  47  |     }
  48  |     await route.fulfill({
  49  |       json: {
  50  |         items: [{
  51  |           id: 1,
  52  |           created_at: "2026-04-04T00:00:00Z",
  53  |           symbol: "AAPL",
  54  |           recommendation_id: "rec-phase1-e2e",
  55  |           market_data_source: "polygon",
  56  |           fallback_mode: false,
  57  |           payload: {
  58  |             thesis: "Deterministic setup",
  59  |             catalyst: { type: "earnings" },
  60  |             entry: { setup_type: "Event Continuation", zone_low: 120, zone_high: 122, trigger_text: "breakout hold" },
  61  |             invalidation: { price: 118, reason: "failed hold" },
  62  |             targets: { target_1: 126, target_2: 129 },
  63  |             quality: { expected_rr: 1.8, confidence: 0.67 },
  64  |             workflow: { timeframe: "1D", market_data_source: "polygon", fallback_mode: false },
  65  |           },
  66  |         }],
  67  |       },
  68  |     });
  69  |   });
  70  |   await page.route("**/api/user/replay-runs", async (route) => {
  71  |     if (route.request().method() === "POST") {
  72  |       await route.fulfill({ json: { id: 22, market_data_source: "polygon", fallback_mode: false } });
  73  |       return;
  74  |     }
  75  |     await route.fulfill({ json: { items: [{ id: 22, symbol: "AAPL", created_at: "2026-04-04", recommendation_count: 1, approved_count: 1, fill_count: 1, ending_heat: 0.2, ending_open_notional: 1000, market_data_source: "polygon", fallback_mode: false }] } });
  76  |   });
  77  |   await page.route("**/api/user/replay-runs/22/steps", async (route) => {
  78  |     await route.fulfill({ json: { items: [{ id: 1, step_index: 1, recommendation_id: "rec-phase1-e2e", approved: true, pre_step_snapshot: { current_heat: 0, open_positions_notional: 0, equity: 10000 }, post_step_snapshot: { current_heat: 0.2, open_positions_notional: 1000, equity: 10050 } }] } });
  79  |   });
  80  |   await page.route("**/api/user/orders", async (route) => {
  81  |     if (route.request().method() === "POST") {
  82  |       await route.fulfill({ json: { order_id: "ord-1", market_data_source: "polygon", fallback_mode: false } });
  83  |       return;
  84  |     }
  85  |     await route.fulfill({ json: { items: [{ order_id: "ord-1", recommendation_id: "rec-phase1-e2e", symbol: "AAPL", status: "filled", side: "buy", shares: 10, limit_price: 121, created_at: "2026-04-04", market_data_source: "polygon", fallback_mode: false, fills: [{ fill_price: 121, filled_shares: 10, timestamp: "2026-04-04T00:00:01Z" }] }] } });
  86  |   });
  87  | 
  88  |   await page.goto("/analysis");
> 89  |   await page.getByTestId("analysis-refresh-button").click();
      |                                                     ^ Error: locator.click: Test timeout of 60000ms exceeded.
  90  |   await page.getByTestId("analysis-create-recommendation-button").click();
  91  | 
  92  |   await expect(page).toHaveURL(/\/recommendations\?recommendation=rec-phase1-e2e/);
  93  |   await expect(page.getByText("Recommendations unavailable")).toBeVisible();
  94  |   await page.getByRole("button", { name: "Refresh" }).click();
  95  |   await expect(page.getByText("Recommendations unavailable")).toHaveCount(0);
  96  | 
  97  |   await page.getByRole("button", { name: "Run replay with context" }).click();
  98  |   await expect(page).toHaveURL(/\/replay-runs\?symbol=AAPL&recommendation=rec-phase1-e2e/);
  99  |   await page.getByRole("button", { name: "Run replay" }).click();
  100 |   await expect(page.getByText("replay complete")).toBeVisible();
  101 | 
  102 |   await page.goto("/recommendations?recommendation=rec-phase1-e2e");
  103 |   await page.getByRole("button", { name: "Stage paper order" }).click();
  104 |   await expect(page).toHaveURL(/\/orders\?recommendation=rec-phase1-e2e/);
  105 |   await page.getByRole("button", { name: "Stage paper order" }).click();
  106 |   await expect(page.getByText("Order id:")).toBeVisible();
  107 | });
  108 | 
  109 | test("dashboard and provider-health show matching provider truth chips/messages in healthy provider mode", async ({ page }) => {
  110 |   await page.route("**/api/user/dashboard", async (route) => {
  111 |     await route.fulfill({
  112 |       json: {
  113 |         market_regime: "risk_on",
  114 |         last_refresh: "2026-04-04T00:00:00Z",
  115 |         account: { app_role: "admin", approval_status: "approved" },
  116 |         provider_health: {
  117 |           summary: "ok",
  118 |           auth: "ok",
  119 |           email: "ok",
  120 |           market_data: "polygon",
  121 |           configured_provider: "polygon",
  122 |           effective_read_mode: "provider",
  123 |           workflow_execution_mode: "provider",
  124 |           failure_reason: null,
  125 |         },
  126 |         active_recommendations: [],
  127 |         recent_replay_runs: [],
  128 |         recent_orders: [],
  129 |         pending_admin_actions: [],
  130 |         alerts: [],
  131 |         workflow_guide: ["check provider truth"],
  132 |       },
  133 |     });
  134 |   });
  135 |   await page.route("**/api/admin/provider-health", async (route) => {
  136 |     await route.fulfill({
  137 |       json: {
  138 |         checked_at: "2026-04-04T00:00:00Z",
  139 |         providers: [
  140 |           { provider: "market_data", mode: "configured", status: "ok", details: "polygon healthy", configured_provider: "polygon", effective_read_mode: "provider", workflow_execution_mode: "provider", operational_impact: "workflows on provider-backed bars", failure_reason: null },
  141 |         ],
  142 |       },
  143 |     });
  144 |   });
  145 | 
  146 |   await page.goto("/dashboard");
  147 |   await expect(page.getByText("provider")).toBeVisible();
  148 |   await expect(page.getByText(/configured: polygon · reads: provider/i)).toBeVisible();
  149 | 
  150 |   await page.goto("/admin/provider-health");
  151 |   await expect(page.getByText(/workflow mode: provider/i)).toBeVisible();
  152 |   await expect(page.getByText(/configured provider: polygon/i)).toBeVisible();
  153 |   await expect(page.getByText(/effective read mode: provider/i)).toBeVisible();
  154 |   await expect(page.getByText(/provider-backed bars/i)).toBeVisible();
  155 | });
  156 | 
  157 | test("dashboard and provider-health show matching provider truth chips/messages in demo fallback mode", async ({ page }) => {
  158 |   await page.route("**/api/user/dashboard", async (route) => {
  159 |     await route.fulfill({
  160 |       json: {
  161 |         market_regime: "risk_on",
  162 |         last_refresh: "2026-04-04T00:00:00Z",
  163 |         account: { app_role: "admin", approval_status: "approved" },
  164 |         provider_health: {
  165 |           summary: "degraded",
  166 |           auth: "ok",
  167 |           email: "ok",
  168 |           market_data: "degraded",
  169 |           configured_provider: "polygon",
  170 |           effective_read_mode: "fallback",
  171 |           workflow_execution_mode: "demo_fallback",
  172 |           failure_reason: "quota",
  173 |         },
  174 |         active_recommendations: [],
  175 |         recent_replay_runs: [],
  176 |         recent_orders: [],
  177 |         pending_admin_actions: [],
  178 |         alerts: [],
  179 |         workflow_guide: ["check provider truth"],
  180 |       },
  181 |     });
  182 |   });
  183 |   await page.route("**/api/admin/provider-health", async (route) => {
  184 |     await route.fulfill({
  185 |       json: {
  186 |         checked_at: "2026-04-04T00:00:00Z",
  187 |         providers: [
  188 |           { provider: "market_data", mode: "configured", status: "degraded", details: "quota", configured_provider: "polygon", effective_read_mode: "fallback", workflow_execution_mode: "demo_fallback", operational_impact: "workflows on explicit deterministic demo fallback bars", failure_reason: "quota" },
  189 |         ],
```