export type ReplayRunSelectionInput = {
  guided: boolean;
  requestedRunId?: string | null;
  requestedRecommendationId?: string | null;
  requestedSymbol?: string | null;
  runs: Array<{ id: number; source_recommendation_id?: string | null; symbol: string }>;
};

export function pickReplayRunSelection(input: ReplayRunSelectionInput): number | null {
  const { guided, requestedRunId, requestedRecommendationId, requestedSymbol, runs } = input;
  if (guided) {
    return (
      runs.find((run) => String(run.id) === requestedRunId)?.id
      ?? runs.find((run) => run.source_recommendation_id === requestedRecommendationId)?.id
      ?? null
    );
  }
  return (
    runs.find((run) => String(run.id) === requestedRunId)?.id
    ?? runs.find((run) => run.source_recommendation_id === requestedRecommendationId)?.id
    ?? runs.find((run) => run.symbol === requestedSymbol)?.id
    ?? runs[0]?.id
    ?? null
  );
}

export type OrderSelectionInput = {
  guided: boolean;
  requestedOrderId?: string | null;
  requestedReplayRunId?: string | null;
  requestedRecommendationId?: string | null;
  orders: Array<{ order_id: string; replay_run_id?: number | null; recommendation_id: string }>;
};

export function pickOrderSelection(input: OrderSelectionInput): string | null {
  const { guided, requestedOrderId, requestedReplayRunId, requestedRecommendationId, orders } = input;
  if (guided) {
    return (
      orders.find((order) => order.order_id === requestedOrderId)?.order_id
      ?? orders.find((order) => String(order.replay_run_id ?? "") === requestedReplayRunId)?.order_id
      ?? orders.find((order) => order.recommendation_id === requestedRecommendationId)?.order_id
      ?? null
    );
  }
  return (
    orders.find((order) => order.order_id === requestedOrderId)?.order_id
    ?? orders.find((order) => String(order.replay_run_id ?? "") === requestedReplayRunId)?.order_id
    ?? orders.find((order) => order.recommendation_id === requestedRecommendationId)?.order_id
    ?? orders[0]?.order_id
    ?? null
  );
}
