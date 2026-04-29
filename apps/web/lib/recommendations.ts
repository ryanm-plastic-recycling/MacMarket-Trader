export type QueueCandidate = {
  rank: number;
  symbol: string;
  strategy: string;
  strategy_id?: string;
  strategy_status?: string;
  market_mode?: string;
  source?: string;
  workflow_source: string;
  timeframe: string;
  status: string;
  score: number;
  score_breakdown?: Record<string, number>;
  expected_rr: number;
  confidence: number;
  reason_text: string;
  thesis: string;
  trigger?: string;
  entry_zone?: Record<string, unknown>;
  invalidation?: Record<string, unknown>;
  targets?: unknown[];
};

export type StoredRecommendation = {
  id: number;
  created_at: string;
  symbol: string;
  recommendation_id: string;
  // Pass 4 — operator-readable label, e.g. "AAPL-EVCONT-20260429-0830".
  // Backend always populates either the generated value or a "Rec #shortid"
  // fallback for legacy rows; the frontend should prefer this over the raw
  // canonical recommendation_id whenever it is shown to the operator.
  display_id?: string;
  payload: Record<string, unknown>;
  market_data_source?: string;
  fallback_mode?: boolean;
};

export type RecommendationSearchPrefill = {
  symbols: string[];
  recommendationId: string | null;
};

export type OptionsResearchLeg = {
  action?: string | null;
  right?: string | null;
  strike?: number | null;
  label?: string | null;
};

export type OptionsResearchStructure = {
  type?: string | null;
  expiration?: string | null;
  legs?: OptionsResearchLeg[] | null;
  net_credit?: number | null;
  net_debit?: number | null;
  max_profit?: number | null;
  max_loss?: number | null;
  breakeven_low?: number | null;
  breakeven_high?: number | null;
  dte?: number | null;
  iv_snapshot?: number | null;
  event_blockers?: string[] | null;
};

export type OptionsExpectedRange = {
  status: "computed" | "blocked" | "omitted";
  method?: string | null;
  absolute_move?: number | null;
  lower_bound?: number | null;
  upper_bound?: number | null;
  horizon_value?: number | null;
  horizon_unit?: string | null;
  reason?: string | null;
};

export type OptionsChainPreviewRow = {
  strike?: number | null;
  expiry?: string | null;
  last_price?: number | null;
  volume?: number | null;
};

export type OptionsChainPreview = {
  underlying?: string | null;
  expiry?: string | null;
  calls?: OptionsChainPreviewRow[] | null;
  puts?: OptionsChainPreviewRow[] | null;
  data_as_of?: string | null;
  source?: string | null;
  reason?: string | null;
};

export type OptionsResearchSetup = {
  symbol: string;
  market_mode: string;
  timeframe?: string | null;
  workflow_source: string;
  strategy: string;
  operator_disclaimer?: string | null;
  option_structure?: OptionsResearchStructure | null;
  expected_range?: OptionsExpectedRange | null;
  options_chain_preview?: OptionsChainPreview | null;
};

export function parseRecommendationSearchParams(params: URLSearchParams): RecommendationSearchPrefill {
  const rawSymbols = [params.get("symbols") ?? "", params.get("symbol") ?? ""]
    .join(",")
    .split(",")
    .map((value) => value.trim().toUpperCase())
    .filter(Boolean);

  const seen = new Set<string>();
  const symbols = rawSymbols.filter((value) => {
    if (seen.has(value)) {
      return false;
    }
    seen.add(value);
    return true;
  });

  const recommendationId = (params.get("recommendation") ?? "").trim() || null;
  return { symbols, recommendationId };
}

export function getRankingProvenance(payload: Record<string, unknown> | null | undefined): Record<string, unknown> | null {
  const workflow = payload?.workflow;
  if (!workflow || typeof workflow !== "object") {
    return null;
  }
  const ranking = (workflow as Record<string, unknown>).ranking_provenance;
  return ranking && typeof ranking === "object" ? (ranking as Record<string, unknown>) : null;
}

export function isFallbackWorkflow(candidate: QueueCandidate | null, recommendation: StoredRecommendation | null): boolean {
  if (recommendation) {
    if (typeof recommendation.fallback_mode === "boolean") {
      return recommendation.fallback_mode;
    }
    const workflow = (recommendation.payload?.workflow ?? null) as Record<string, unknown> | null;
    return Boolean(workflow?.fallback_mode);
  }
  if (!candidate) {
    return false;
  }
  return candidate.workflow_source.toLowerCase().includes("fallback") || candidate.source?.toLowerCase().includes("fallback") === true;
}

export function isOptionsResearchMode(mode: string | null | undefined): boolean {
  return String(mode ?? "").trim().toLowerCase() === "options";
}

export function isReadOnlyResearchMode(mode: string | null | undefined): boolean {
  const normalized = String(mode ?? "").trim().toLowerCase();
  return normalized === "options" || normalized === "crypto";
}

export function formatResearchValue(value: unknown, fallback = "Unavailable"): string {
  if (value == null) return fallback;
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return fallback;
    return value.toLocaleString("en-US", {
      minimumFractionDigits: Number.isInteger(value) ? 0 : 2,
      maximumFractionDigits: 2,
    });
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed ? trimmed : fallback;
  }
  return String(value);
}

export function formatResearchCell(value: unknown): string {
  return formatResearchValue(value, "—");
}

export function formatOptionsLegLabel(leg: OptionsResearchLeg): string {
  const action = typeof leg.action === "string" && leg.action.trim() ? leg.action.trim() : null;
  const right = typeof leg.right === "string" && leg.right.trim() ? leg.right.trim().toUpperCase() : null;
  const strike = typeof leg.strike === "number" && Number.isFinite(leg.strike) ? formatResearchValue(leg.strike) : null;
  const label = typeof leg.label === "string" && leg.label.trim() ? leg.label.trim() : null;
  const summary = [action, right, strike].filter(Boolean).join(" ");
  if (summary && label) return `${summary} — ${label}`;
  return summary || label || "Unavailable";
}

export function getOptionsPremiumLabel(structure: OptionsResearchStructure | null | undefined): "Net credit" | "Net debit" | "Net premium" {
  if (structure?.net_credit != null) return "Net credit";
  if (structure?.net_debit != null) return "Net debit";
  return "Net premium";
}

export function getOptionsPremiumValue(structure: OptionsResearchStructure | null | undefined): number | null {
  if (structure?.net_credit != null && Number.isFinite(structure.net_credit)) return structure.net_credit;
  if (structure?.net_debit != null && Number.isFinite(structure.net_debit)) return structure.net_debit;
  return null;
}

/**
 * Returns a Set of queue-row keys (same format as the page's selectedQueueKey:
 * "${symbol}-${strategy}-${rank}") for every stored recommendation that has
 * ranking_provenance, so the queue table can badge already-promoted rows.
 */
export function getPromotedQueueKeys(rows: StoredRecommendation[]): Set<string> {
  const keys = new Set<string>();
  for (const row of rows) {
    const provenance = getRankingProvenance(row.payload);
    if (!provenance) continue;
    const symbol = typeof provenance.symbol === "string" ? provenance.symbol : null;
    const strategy = typeof provenance.strategy === "string" ? provenance.strategy : null;
    const rank = provenance.rank != null ? Number(provenance.rank) : null;
    if (symbol && strategy && rank != null && !Number.isNaN(rank)) {
      keys.add(`${symbol}-${strategy}-${rank}`);
    }
  }
  return keys;
}
