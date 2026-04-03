"use client";

import { INDICATOR_REGISTRY, type IndicatorId } from "@/lib/indicator-framework";

export function IndicatorSelector({
  selected,
  onChange,
  enabledIds,
}: {
  selected: IndicatorId[];
  onChange: (next: IndicatorId[]) => void;
  enabledIds?: IndicatorId[];
}) {
  const selectedSet = new Set(selected);
  const enabledSet = new Set(enabledIds ?? INDICATOR_REGISTRY.map((item) => item.id));
  return (
    <div className="op-stack" style={{ gap: 6 }}>
      <strong>Indicators</strong>
      <div className="op-row">
        {INDICATOR_REGISTRY.map((indicator) => {
          const isEnabled = enabledSet.has(indicator.id);
          return (
            <label
              key={indicator.id}
              className="op-badge op-badge-neutral"
              style={{ display: "inline-flex", gap: 6, opacity: isEnabled ? 1 : 0.5 }}
              title={isEnabled ? "" : "Not available on this chart yet"}
            >
              <input
                type="checkbox"
                checked={selectedSet.has(indicator.id)}
                disabled={!isEnabled}
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
          );
        })}
      </div>
    </div>
  );
}
