export const GUIDED_FLOW_LABEL = "Start guided paper trade";
export const GUIDED_ENTRY_PATH = "/analysis?guided=1";
export const GUIDED_STEPS = ["Analyze", "Recommendation", "Replay", "Paper Order"] as const;
export type GuidedStep = (typeof GUIDED_STEPS)[number];

export type GuidedFlowState = {
  guided: boolean;
  symbol?: string;
  strategy?: string;
  marketMode?: string;
  source?: string;
  recommendationId?: string;
  replayRunId?: string;
  orderId?: string;
};

export function parseGuidedFlowState(params: URLSearchParams): GuidedFlowState {
  return {
    guided: params.get("guided") === "1",
    symbol: params.get("symbol") ?? undefined,
    strategy: params.get("strategy") ?? undefined,
    marketMode: params.get("market_mode") ?? undefined,
    source: params.get("source") ?? undefined,
    recommendationId: params.get("recommendation") ?? undefined,
    replayRunId: params.get("replay_run") ?? undefined,
    orderId: params.get("order") ?? undefined,
  };
}

export function buildGuidedQuery(state: GuidedFlowState): string {
  const params = new URLSearchParams();
  if (state.guided) params.set("guided", "1");
  if (state.symbol) params.set("symbol", state.symbol);
  if (state.strategy) params.set("strategy", state.strategy);
  if (state.marketMode) params.set("market_mode", state.marketMode);
  if (state.source) params.set("source", state.source);
  if (state.recommendationId) params.set("recommendation", state.recommendationId);
  if (state.replayRunId) params.set("replay_run", state.replayRunId);
  if (state.orderId) params.set("order", state.orderId);
  return params.toString();
}
