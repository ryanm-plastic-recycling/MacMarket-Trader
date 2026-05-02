import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const source = readFileSync(new URL("./page.tsx", import.meta.url), "utf8");

describe("orders metric help rollout", () => {
  it("adds compact help to equity Orders P&L and fee labels without new actions", () => {
    expect(source).toContain('import { MetricLabel } from "@/components/ui/metric-help";');
    expect(source).toContain('<MetricLabel label="Realized net P&L" term="net_pnl" />');
    expect(source).toContain('<MetricLabel label="Fees" term="equity_commission_per_trade" />');
    expect(source).toContain('<MetricLabel label="Projected net outcome" term="net_pnl" />');
    expect(source).toContain('<MetricLabel label="Total fees" term="equity_commission_per_trade" />');
    expect(source).toContain('<MetricLabel label="gross P&L" term="gross_pnl" />');
    expect(source).toContain('<MetricLabel label="fees" term="equity_commission_per_trade" />');
    expect(source).toContain('<MetricLabel label="net P&L" term="net_pnl" />');
    expect(source).toContain("Recommended shares");
    expect(source).toContain("Order shares");
    expect(source).toContain("Estimated notional");
    expect(source).toContain("Max paper order value");
    expect(source).toContain("Max paper order value reduced");
    expect(source).toContain("Reset my paper portfolio");
    expect(source).toContain("Type RESET");
    expect(source).toContain("Calendar risk");
    expect(source).toContain("risk_calendar_confirmed");
    expect(source).toContain("risk_calendar_override_reason");
    expect(source).toContain("Confirmation reason");
    expect(source).toContain("Sit this one out");
    expect(source).toContain("Close position");
    expect(source).not.toContain("live trading");
    expect(source).not.toContain("broker execution");
    expect(source).not.toContain("broker routing");
  });
});
