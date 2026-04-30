export type GlossaryTermKey =
  | "rr"
  | "confidence"
  | "score"
  | "expected_range"
  | "dte"
  | "iv"
  | "open_interest"
  | "breakeven"
  | "max_profit"
  | "max_loss"
  | "gross_pnl"
  | "net_pnl"
  | "equity_commission_per_trade"
  | "options_commission_per_contract"
  | "provider_readiness"
  | "paper_lifecycle"
  | "replay_payoff_preview";

export type GlossaryTerm = {
  label: string;
  title: string;
  definition: string;
  formula?: string;
  example?: string;
  caveat?: string;
  relatedTerms?: GlossaryTermKey[];
};

export const GLOSSARY_TERMS: Record<GlossaryTermKey, GlossaryTerm> = {
  rr: {
    label: "RR",
    title: "Risk-reward ratio",
    definition: "A deterministic comparison of planned reward versus planned risk for a setup.",
    formula: "expected reward / planned risk",
    example: "A setup risking $1 to target $2 has RR 2.0.",
    caveat: "It does not say the setup is likely to win.",
    relatedTerms: ["score", "confidence"],
  },
  confidence: {
    label: "CONF",
    title: "Confidence",
    definition: "A model/rules quality signal for how well the setup evidence aligns with the strategy.",
    caveat: "It is not a win-rate, guarantee, or permission to trade.",
    relatedTerms: ["score", "rr"],
  },
  score: {
    label: "Score",
    title: "Recommendation score",
    definition: "A deterministic ranking value used to compare candidates within the current workflow.",
    caveat: "It is not a broker signal, win-rate, or execution approval.",
    relatedTerms: ["confidence", "rr"],
  },
  expected_range: {
    label: "Expected Range",
    title: "Expected Range / Expected Move",
    definition: "Research context estimating an upper and lower underlying-price range from available provider data and assumptions.",
    formula: "method-dependent, such as IV-derived one-sigma move when available",
    caveat: "It does not change payoff math, approve execution, or represent probability of profit.",
    relatedTerms: ["iv", "dte", "breakeven"],
  },
  dte: {
    label: "DTE",
    title: "Days to expiration",
    definition: "The number of days remaining until an option contract expires.",
    caveat: "DTE is timing context only; it does not model assignment, exercise, or settlement.",
    relatedTerms: ["expected_range", "iv"],
  },
  iv: {
    label: "IV",
    title: "Implied volatility",
    definition: "An options-market volatility input from provider data when available.",
    caveat: "Provider plan coverage may omit IV. Missing IV should render as unavailable, not as zero.",
    relatedTerms: ["expected_range", "open_interest"],
  },
  open_interest: {
    label: "Open interest",
    title: "Open interest",
    definition: "The number of outstanding option contracts reported by the data provider when available.",
    caveat: "It is liquidity context, not execution approval.",
    relatedTerms: ["iv"],
  },
  breakeven: {
    label: "Breakeven",
    title: "Breakeven",
    definition: "Underlying price where the structure's modeled payoff crosses approximately zero before commissions.",
    caveat: "It is payoff context, not a target or recommendation.",
    relatedTerms: ["max_profit", "max_loss", "expected_range"],
  },
  max_profit: {
    label: "Max profit",
    title: "Max profit",
    definition: "The largest modeled gain for the structure under the current deterministic payoff assumptions.",
    caveat: "It is not a forecast and may exclude future lifecycle states that are not modeled.",
    relatedTerms: ["max_loss", "breakeven", "gross_pnl"],
  },
  max_loss: {
    label: "Max loss",
    title: "Max loss",
    definition: "The largest modeled loss for the structure under the current deterministic payoff assumptions.",
    caveat: "It is not margin modeling and does not add assignment/exercise automation.",
    relatedTerms: ["max_profit", "breakeven"],
  },
  gross_pnl: {
    label: "Gross P&L",
    title: "Gross P&L",
    definition: "Paper profit or loss before commissions are subtracted.",
    formula: "proceeds or close value - entry cost, before commission adjustments",
    caveat: "Gross P&L is not the final fee-aware result.",
    relatedTerms: ["net_pnl", "equity_commission_per_trade", "options_commission_per_contract"],
  },
  net_pnl: {
    label: "Net P&L",
    title: "Net P&L",
    definition: "Paper profit or loss after modeled commissions are subtracted.",
    formula: "gross P&L - total commissions",
    caveat: "Net P&L is still paper-result accounting, not live account reconciliation.",
    relatedTerms: ["gross_pnl", "equity_commission_per_trade", "options_commission_per_contract"],
  },
  equity_commission_per_trade: {
    label: "Equity commission / trade",
    title: "Equity commission per trade",
    definition: "The paper fee applied to each equity paper-trade event.",
    formula: "commission per trade x trade events",
    example: "$1.00 entry + $1.00 close = $2.00 modeled round-trip equity commission.",
    caveat: "This setting is separate from options commission per contract.",
    relatedTerms: ["options_commission_per_contract", "net_pnl"],
  },
  options_commission_per_contract: {
    label: "Options commission / contract",
    title: "Options commission per contract",
    definition: "The paper options fee applied per contract, per leg, per open or close event.",
    formula: "commission per contract × contracts × legs × events",
    example: "$0.65 × 1 contract × 4 legs × 2 events = $5.20 total options commission.",
    caveat: "Not per share and not multiplied by 100. The 100 multiplier applies to premium and P&L math, not commission.",
    relatedTerms: ["equity_commission_per_trade", "net_pnl"],
  },
  provider_readiness: {
    label: "Provider readiness",
    title: "Provider readiness",
    definition: "Operator visibility into configured data providers, fallback/blocking mode, and whether safe checks are available.",
    caveat: "Readiness is workflow-trust context. It is not live routing, broker execution, trade approval, or account connectivity.",
    relatedTerms: ["expected_range", "iv", "open_interest"],
  },
  paper_lifecycle: {
    label: "Paper lifecycle",
    title: "Paper lifecycle",
    definition: "A persisted simulated record for paper-only opens, closes, and resulting paper P&L.",
    caveat: "Paper lifecycle records do not mean external orders were sent.",
    relatedTerms: ["gross_pnl", "net_pnl", "replay_payoff_preview"],
  },
  replay_payoff_preview: {
    label: "Replay payoff preview",
    title: "Replay payoff preview",
    definition: "A read-only options payoff inspection using deterministic expiration-payoff assumptions.",
    caveat: "It does not create replay runs, orders, positions, trades, broker mark-to-market simulation, or execution approval.",
    relatedTerms: ["expected_range", "breakeven", "paper_lifecycle"],
  },
};

export function getGlossaryTerm(term: GlossaryTermKey | string): GlossaryTerm | null {
  return Object.prototype.hasOwnProperty.call(GLOSSARY_TERMS, term)
    ? GLOSSARY_TERMS[term as GlossaryTermKey]
    : null;
}
