"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { fetchWorkflowApi } from "@/lib/api-client";
import { parseGuidedFlowState, type GuidedFlowState } from "@/lib/guided-workflow";

function lineageStatus(state: GuidedFlowState): string {
  if (state.orderId) return "Order staged";
  if (state.replayRunId) return `Replay run #${state.replayRunId} complete`;
  if (state.recommendationId) return "Recommendation created";
  return "";
}

type RecListItem = { recommendation_id?: string; display_id?: string };

export function ActiveTradeBanner({ state }: { state?: GuidedFlowState }) {
  const searchParams = useSearchParams();
  const resolvedState = useMemo<GuidedFlowState>(
    () => state ?? parseGuidedFlowState(searchParams),
    [state, searchParams],
  );
  const [displayId, setDisplayId] = useState<string | null>(null);

  // Pass 4 — fetch display_id for the active recommendation so the banner
  // can show the operator-readable label alongside the symbol/strategy chips.
  // Single GET; if it fails, just suppress the chip — never break the banner.
  useEffect(() => {
    if (!resolvedState.guided || !resolvedState.recommendationId) {
      setDisplayId(null);
      return;
    }
    let cancelled = false;
    void fetchWorkflowApi<RecListItem>("/api/user/recommendations").then((result) => {
      if (cancelled || !result.ok) return;
      const match = result.items.find((row) => row.recommendation_id === resolvedState.recommendationId);
      if (match?.display_id) setDisplayId(match.display_id);
      else setDisplayId(null);
    });
    return () => { cancelled = true; };
  }, [resolvedState.guided, resolvedState.recommendationId]);

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
      {displayId ? (
        <span
          style={{
            color: "#21c06e",
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
            fontSize: 12,
            background: "rgba(33, 192, 110, 0.12)",
            border: "1px solid rgba(33, 192, 110, 0.4)",
            borderRadius: 4,
            padding: "1px 8px",
          }}
          title="Operator-readable recommendation ID"
        >
          {displayId}
        </span>
      ) : null}
      <span style={{ flex: 1 }} />
      {status ? <span style={{ color: "#7a8999", fontSize: 13 }}>{status}</span> : null}
    </div>
  );
}
