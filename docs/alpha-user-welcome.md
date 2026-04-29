# Welcome to MacMarket-Trader (Private Alpha)

You're one of the first people outside the build team to use this. Thanks for being early.

This doc is the only orientation you need. Read it once, then start clicking. It takes about 5 minutes.

---

## What this is

MacMarket-Trader is an **operator-grade trading intelligence console**. It's not a charting tool, not a robo-advisor, not a backtest playground. It's a disciplined workflow for taking one trade idea from analysis to a paper-traded position with full audit lineage.

**The whole product is one workflow:**

```
Analyze → Recommendation → Replay → Paper Order → Position → Close
```

Every action you take is logged. Every recommendation has explicit entry, stop, and target levels. Every replay run validates the idea against historical data before you stage a paper order. Every position can be closed with a reason; recent closes can be undone within 5 minutes.

**It is paper-only.** No real money moves. No live broker integration. This is for testing the discipline, not the trades.

---

## What it is NOT

- It does not pick trades for you. You pick the symbol and strategy; it scores the setup.
- It does not predict the future. The "scores" are deterministic functions of regime, technicals, and event context — no ML, no opinions.
- It is not a chat interface. There is no AI assistant inside the app. LLMs only explain context; the engines decide.
- It is not a brokerage. You cannot place a real order. Ever.

---

## Getting in

You should have received an email with a sign-in link to **https://macmarket.io**.

When you visit, you'll hit **two auth gates**:

1. **Cloudflare Access** — you'll see a screen asking for your email. Enter the email I invited, click send, check inbox for a 6-digit PIN, paste it. This proves you're on the allowlist.
2. **Clerk sign-in** — after the PIN, you'll see the MacMarket sign-in page. Use the email I invited (same one). If it's your first time, you'll create a password.

After both, you land on the **Dashboard**. If your account isn't approved yet, you'll see "Pending approval" — message me and I'll approve you in the admin panel.

Sessions last 24 hours. After that you'll re-do the PIN step but Clerk will remember you.

---

## Your first 5 minutes — do this exact walkthrough

This proves the workflow works for you. Do it once, then you'll never need this section again.

### 1. Click "Start guided paper trade" on the dashboard

This drops you into **guided mode**. You'll see a green sticky banner at the top showing your active trade context — symbol, strategy, market mode. It updates as you move through the workflow.

### 2. On the Analyze page

- **Symbol**: type `AAPL` (or anything liquid — MSFT, NVDA, SPY)
- **Market mode**: equities (options/crypto are research preview only — they will block when you try to advance)
- **Timeframe**: 1D
- **Strategy**: pick any. "Event Continuation" is the easiest to interpret.
- Click **Refresh analysis**

You'll see the chart, the strategy rationale, and the entry/stop/target levels. Read them. The system has just done the work that would normally take you 10 minutes of manual chart inspection.

If anything looks off, that's real signal. Tell me.

### 3. Click "Create recommendation"

This persists the setup as a recommendation with a unique ID. You're auto-advanced to the **Recommendations** page after the create succeeds.

### 4. On Recommendations

You'll see your active recommendation in the hero card with the same symbol/strategy you just picked. Click **Make active →** (the big green button in the Next action card).

The system auto-advances to **Replay** after ~600ms.

### 5. On Replay

Click **Run replay now →** (big green button, may pulse).

The replay engine walks the recommendation through historical bars and shows you what would have happened. Each step is labeled `✓ Bar #N` or `✗ Bar #N` — green checks are bars where the strategy logic would have triggered, red X's are bars that didn't meet the gate.

If the replay produces no fills (sometimes the case — strategy doesn't trigger in the historical window), you'll see a styled warning block. **That's not a bug**. It means the system is honestly telling you the setup wouldn't have worked. Don't stage a paper order if this happens.

If the replay does produce fills, the system auto-advances to **Paper Orders**.

### 6. On Paper Orders

Click **Stage paper order now →**.

The order appears in your order history, and an open paper position appears in the **Open paper positions** card above.

### 7. Close the position

Click **Close position** on the open position row. An inline ticket appears below the row:
- **Mark price** defaults to your average entry price — change it to a higher number to simulate a profitable close, or lower for a loss
- **Reason** — pick "Target hit" or "Manual exit"
- Click **Confirm**

The position closes. A row appears in the **Closed trades** card showing your realized P&L (green if positive, red if negative), hold duration, and close reason.

### 8. (Optional) Undo the close

Closed within the last 5 minutes? You'll see a **Reopen position** button on that closed trade row with a countdown. Click it, confirm, and the position is restored as if the close never happened.

After 5 minutes, the button disappears. Closes become permanent.

---

## What the workflow rules actually enforce

These aren't preferences — they're hard gates the backend enforces. Knowing them prevents confusion:

- **Equities only for execution prep.** Options and crypto stop at research preview. You can analyze them, but you can't promote to replay or stage paper orders.
- **No replay without a recommendation.** You can't run a replay against a symbol; it must be against a persisted recommendation. The "Make active" step is what creates that lineage.
- **No paper order without a stageable replay.** If the replay produces no fills or no approval, the order staging is blocked.
- **No silent fallbacks.** If a data provider is down, the system tells you. It doesn't pretend.
- **Cancel only before fills.** A staged order with no fills can be canceled. Once it fills, it becomes a position; cancel is no longer an option (close is).

---

## Two modes to know about

**Guided mode** — what you used in the walkthrough. Sticky active-trade banner, big green CTAs, auto-advance between steps, one trade idea at a time. This is the primary way to use the app.

**Explorer mode** — when you visit any workflow page without `guided=1` in the URL. You see the full history tables, no auto-advance, all data exposed. Use this when you want to browse past recommendations, replay runs, or orders without progressing a new trade.

You can switch any time by adding/removing `?guided=1` from the URL, or by starting from the dashboard's **Start guided paper trade** button (always launches guided).

---

## What's intentionally rough in alpha

I'd rather you know these are gaps, not bugs:

- **Recommendation IDs look like `rec_a65757eb8d23`** — not human-readable. A schema upgrade to friendly IDs (`AAPL-EVCONT-20260428-1430`) is on the roadmap but not done. For now, copy the hex when you need to reference a specific rec.
- **Trade dollar size is fixed at $1000.** Per-user configurable risk is on the roadmap. If you have strong opinions about what your risk per trade should default to, tell me — that's useful signal.
- **Strategy descriptions are sparse.** The selector shows a hint per strategy but it's not a full guide. If you don't recognize a strategy name, ask before using it.
- **The analysis chart sometimes feels visually busy.** I know. Indicator selection works but the default state has more on it than I'd like.
- **Email rendering is now base64-inline** — should be reliable, but if you get a strategy report email and the logo is broken, screenshot it and send it to me.

---

## Scheduled strategy reports

If your account has scheduled reports enabled, you'll get an email at the times you set. The email shows ranked candidates with entry/stop/target/score for each. The email subject leads with the top candidate, e.g., `MacMarket · Apr 28 · Top: NVDA (0.93) + 4 more`.

To create a schedule: visit **/schedules** in the app. Set the time, timezone, watchlist, and strategy set. The runner checks every 5 minutes for due schedules.

If a scheduled time passes and you don't get the email within 10 minutes, tell me.

---

## What I want from you

This is a private alpha because feedback at this stage is more valuable than scale. Specifically:

**Tell me when:**
- Any step felt confusing or you didn't know what to do next
- A button label was misleading
- A page loaded with stale data or a broken state
- You hit an error and the message wasn't useful
- A workflow rule blocked you and you couldn't tell why
- The numbers looked wrong (entry/stop/target make no sense for a setup)

**You don't need to format these as bug reports.** A one-line text or email is fine: "I clicked Make active and nothing happened" is more useful than a 5-paragraph reproduction. I'll dig in.

**You also don't need to be polite.** "This is dumb" is a useful signal. I'd rather hear it now than after I've shipped this to 100 people.

---

## What you should NOT do

- **Don't share the URL.** The Cloudflare Access allowlist only includes specific emails. Sharing the link doesn't help anyone — they'll just be blocked at the PIN screen. If you want to recommend someone, send me their email and I'll evaluate adding them.
- **Don't expect uptime guarantees.** This runs on hardware that's healthy but not enterprise. If you can't reach it, try again in 5 minutes. If still down, tell me.
- **Don't trust the numbers as financial advice.** This is a paper trading research tool. The recommendations are deterministic outputs from rules I wrote, not validated alpha signals. Use it to test the workflow, not to inform real money decisions.

---

## How to reach me

- Text or email — fastest
- For bugs: include the URL you were on, what you clicked, what happened
- For "this is confusing": just say what you expected vs. what you got

---

## What's coming next

Roughly in this order:

- Human-readable recommendation IDs
- Per-user trade dollar size (Settings page)
- Polish on strategy descriptions and regime hints
- More robust scheduled report controls
- Eventually: real broker paper-trading integration (Alpaca paper API)

If something on this list matters more or less to you than I'm ranking it, say so.

---

Thanks for being early. Let's see what breaks.

— Ryan