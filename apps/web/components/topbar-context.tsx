"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";

function TopbarContextInner() {
  const searchParams = useSearchParams();
  const guided = searchParams.get("guided") === "1";
  const symbol = searchParams.get("symbol");
  const strategy = searchParams.get("strategy");

  if (!guided) return <span>Explorer mode</span>;
  if (!symbol) return <span>Guided workflow — start at Analyze</span>;
  const parts: string[] = [symbol.toUpperCase()];
  if (strategy) parts.push(strategy);
  return <span>{parts.join(" · ")}</span>;
}

export function TopbarContext() {
  return (
    <Suspense fallback={<span>Workflow: Analyze → Recommendation → Replay → Paper Order</span>}>
      <TopbarContextInner />
    </Suspense>
  );
}
