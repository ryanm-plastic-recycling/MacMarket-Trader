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
  payload: Record<string, unknown>;
  market_data_source?: string;
  fallback_mode?: boolean;
};

export type RecommendationSearchPrefill = {
  symbols: string[];
  recommendationId: string | null;
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
