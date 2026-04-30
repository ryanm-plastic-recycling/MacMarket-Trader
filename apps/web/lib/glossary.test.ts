import { describe, expect, it } from "vitest";

import { GLOSSARY_TERMS, getGlossaryTerm, type GlossaryTermKey } from "@/lib/glossary";

const REQUIRED_TERMS: GlossaryTermKey[] = [
  "rr",
  "confidence",
  "score",
  "expected_range",
  "dte",
  "iv",
  "open_interest",
  "breakeven",
  "max_profit",
  "max_loss",
  "gross_pnl",
  "net_pnl",
  "equity_commission_per_trade",
  "options_commission_per_contract",
  "provider_readiness",
  "paper_lifecycle",
  "replay_payoff_preview",
];

describe("glossary registry", () => {
  it("contains the required initial explainable metric terms", () => {
    expect(Object.keys(GLOSSARY_TERMS).sort()).toEqual([...REQUIRED_TERMS].sort());
    for (const term of REQUIRED_TERMS) {
      expect(GLOSSARY_TERMS[term].label).toBeTruthy();
      expect(GLOSSARY_TERMS[term].title).toBeTruthy();
      expect(GLOSSARY_TERMS[term].definition).toBeTruthy();
    }
  });

  it("keeps options commission per-contract math explicit", () => {
    const term = getGlossaryTerm("options_commission_per_contract");

    expect(term?.definition).toContain("per contract");
    expect(term?.definition).toContain("per leg");
    expect(term?.definition).toContain("per open or close event");
    expect(term?.formula).toContain("commission per contract × contracts × legs × events");
    expect(term?.example).toContain("$0.65 × 1 contract × 4 legs × 2 events = $5.20");
    expect(term?.caveat).toContain("Not per share");
    expect(term?.caveat).toContain("not multiplied by 100");
  });

  it("keeps Expected Range and score language inside safety boundaries", () => {
    const expectedRange = getGlossaryTerm("expected_range");
    const confidence = getGlossaryTerm("confidence");
    const score = getGlossaryTerm("score");

    expect(expectedRange?.caveat).toContain("does not change payoff math");
    expect(expectedRange?.caveat).toContain("probability of profit");
    expect(`${confidence?.definition} ${confidence?.caveat}`.toLowerCase()).not.toContain("probability of profit");
    expect(`${score?.definition} ${score?.caveat}`.toLowerCase()).not.toContain("probability of profit");
  });

  it("keeps provider readiness from implying execution plumbing", () => {
    const providerReadiness = getGlossaryTerm("provider_readiness");
    const copy = `${providerReadiness?.definition} ${providerReadiness?.caveat}`.toLowerCase();

    expect(copy).toContain("workflow-trust context");
    expect(copy).toContain("not live routing, broker execution");
    expect(copy).not.toContain("broker routing");
    expect(copy).not.toContain("live trading");
  });

  it("keeps replay payoff preview from implying broker simulation", () => {
    const replayPayoffPreview = getGlossaryTerm("replay_payoff_preview");
    const copy = `${replayPayoffPreview?.definition} ${replayPayoffPreview?.caveat}`.toLowerCase();

    expect(copy).toContain("read-only");
    expect(copy).toContain("broker mark-to-market simulation");
    expect(copy).not.toContain("live trading");
    expect(copy).not.toContain("broker routing");
  });
});
