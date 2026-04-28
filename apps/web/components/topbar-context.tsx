"use client";

import { Suspense } from "react";
import { usePathname, useSearchParams } from "next/navigation";

import { parseGuidedFlowState } from "@/lib/guided-workflow";

function TopbarContextInner() {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const state = parseGuidedFlowState(searchParams as unknown as URLSearchParams);

  if (!state.guided) return <span key={pathname}>Explorer mode</span>;
  if (!state.symbol) return <span key={pathname}>Guided workflow — start at Analyze</span>;

  const parts: string[] = [state.symbol.toUpperCase()];
  if (state.strategy) parts.push(state.strategy);
  return <span key={pathname}>{parts.join(" · ")}</span>;
}

export function TopbarContext() {
  return (
    <Suspense fallback={<span>Explorer mode</span>}>
      <TopbarContextInner />
    </Suspense>
  );
}
