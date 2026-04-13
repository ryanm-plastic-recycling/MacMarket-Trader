"use client";

import { GUIDED_STEPS } from "@/lib/guided-workflow";

export function GuidedStepRail({ current }: { current: (typeof GUIDED_STEPS)[number] }) {
  return (
    <div className="op-row" style={{ gap: 8, flexWrap: "wrap" }}>
      {GUIDED_STEPS.map((step, index) => (
        <div key={step} style={{ opacity: step === current ? 1 : 0.75 }}>
          <strong>{index + 1}. {step}</strong>
          {index < GUIDED_STEPS.length - 1 ? " → " : ""}
        </div>
      ))}
    </div>
  );
}
