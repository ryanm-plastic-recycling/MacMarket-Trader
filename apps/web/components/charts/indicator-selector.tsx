"use client";

import { INDICATOR_REGISTRY, type IndicatorId } from "@/lib/indicator-framework";

export function IndicatorSelector({ selected, onChange }: { selected: IndicatorId[]; onChange: (next: IndicatorId[]) => void }) {
  const selectedSet = new Set(selected);
  return (
    <div className="op-stack" style={{ gap: 6 }}>
      <strong>Indicators</strong>
      <div className="op-row">
        {INDICATOR_REGISTRY.map((indicator) => (
          <label key={indicator.id} className="op-badge op-badge-neutral" style={{ display: "inline-flex", gap: 6 }}>
            <input
              type="checkbox"
              checked={selectedSet.has(indicator.id)}
              onChange={(event) => {
                if (event.target.checked) {
                  onChange([...selected, indicator.id]);
                  return;
                }
                onChange(selected.filter((item) => item !== indicator.id));
              }}
            />
            {indicator.label}
          </label>
        ))}
      </div>
    </div>
  );
}
