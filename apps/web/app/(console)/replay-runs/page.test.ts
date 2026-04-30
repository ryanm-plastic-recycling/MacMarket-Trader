import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { GLOSSARY_TERMS } from "@/lib/glossary";

const source = readFileSync(new URL("./page.tsx", import.meta.url), "utf8");

describe("replay metric help labels", () => {
  it("wires compact glossary help into Replay score, confidence, P&L, and fee labels", () => {
    expect(source).toContain('import { MetricLabel } from "@/components/ui/metric-help";');
    expect(source).toContain('<MetricLabel label="Fees" term="equity_commission_per_trade" />');
    expect(source).toContain('<MetricLabel label="Projected net outcome" term="net_pnl" />');
    expect(source).toContain('<MetricLabel label="Projected net" term="net_pnl" />');
    expect(source).toContain('<MetricLabel label="Gross P&L" term="gross_pnl" />');
    expect(source).toContain('<MetricLabel label="Score" term="score" />');
    expect(source).toContain('<MetricLabel label="Confidence" term="confidence" />');
    expect(source).not.toContain("stage real order");
    expect(source).not.toContain("broker execution");
    expect(source).not.toContain("broker routing");
    expect(source).not.toContain("live trading");
  });

  it("keeps Replay glossary help from implying probability or broker simulation", () => {
    expect(GLOSSARY_TERMS.confidence.caveat).not.toMatch(/probability of profit/i);
    expect(GLOSSARY_TERMS.score.caveat).not.toMatch(/probability of profit/i);
    expect(GLOSSARY_TERMS.replay_payoff_preview.definition).toMatch(/read-only/i);
    expect(GLOSSARY_TERMS.replay_payoff_preview.caveat).not.toMatch(/broker mark-to-market|broker simulation|live trading|broker routing/i);
    expect(GLOSSARY_TERMS.net_pnl.definition).toMatch(/after modeled commissions/i);
    expect(GLOSSARY_TERMS.gross_pnl.definition).toMatch(/before commissions/i);
  });
});
