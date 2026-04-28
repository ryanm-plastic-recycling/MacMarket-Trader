"use client";

import { useSearchParams } from "next/navigation";
import { useMemo } from "react";

import { parseGuidedFlowState, type GuidedFlowState } from "@/lib/guided-workflow";

function lineageStatus(state: GuidedFlowState): string {
  if (state.orderId) return "Order staged";
  if (state.replayRunId) return `Replay run #${state.replayRunId} complete`;
  if (state.recommendationId) return "Recommendation created";
  return "";
}

export function ActiveTradeBanner({ state }: { state?: GuidedFlowState }) {
  const searchParams = useSearchParams();
  const resolvedState = useMemo<GuidedFlowState>(
    () => state ?? parseGuidedFlowState(searchParams),
    [state, searchParams],
  );

  if (!resolvedState.guided || !resolvedState.recommendationId) return null;

  const status = lineageStatus(resolvedState);
  return (
    <div
      role="status"
      aria-label="Active trade"
      style={{
        position: "sticky",
        top: 0,
        zIndex: 5,
        background: "#1a2e1f",
        borderBottom: "2px solid #21c06e",
        padding: "10px 16px",
        display: "flex",
        alignItems: "center",
        gap: 16,
        fontSize: 14,
      }}
    >
      <span style={{ color: "#21c06e", fontWeight: 700, letterSpacing: "0.04em" }}>ACTIVE TRADE:</span>
      <span style={{ color: "#fff", fontWeight: 700, fontSize: 16 }}>{resolvedState.symbol ?? "—"}</span>
      <span style={{ color: "#fff" }}>{resolvedState.strategy ?? "—"}</span>
      <span style={{ color: "#7a8999" }}>{resolvedState.marketMode ?? "equities"}</span>
      <span style={{ flex: 1 }} />
      {status ? <span style={{ color: "#7a8999", fontSize: 13 }}>{status}</span> : null}
    </div>
  );
}
