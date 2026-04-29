"use client";

import { INDICATOR_REGISTRY, type IndicatorCategory, type IndicatorId } from "@/lib/indicator-framework";

const BUCKETS: Array<{
  key: "price" | "lower" | "context";
  label: string;
  hint: string;
  categories: IndicatorCategory[];
}> = [
  { key: "price", label: "Price overlays", hint: "Overlays that share the main price pane.", categories: ["trend", "volatility", "structure"] },
  { key: "lower", label: "Lower panels", hint: "Separate scales for compact volume and RSI context.", categories: ["momentum", "volume"] },
  { key: "context", label: "HACO context", hint: "Dedicated HACO/HACOLT context strips.", categories: ["haco"] },
];

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
  const visibleIndicators = INDICATOR_REGISTRY.filter((item) => enabledSet.has(item.id));
  return (
    <div className="op-stack" style={{ gap: 6 }}>
      <strong>Indicators</strong>
      {BUCKETS.map((bucket) => {
        const bucketIndicators = visibleIndicators.filter((indicator) => bucket.categories.includes(indicator.category));
        if (bucketIndicators.length === 0) return null;
        return (
          <div key={bucket.key} className="op-stack" style={{ gap: 6 }}>
            <div>
              <div style={{ fontSize: "0.86rem", fontWeight: 600 }}>{bucket.label}</div>
              <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.78rem" }}>{bucket.hint}</div>
            </div>
            <div className="op-row" style={{ rowGap: 6 }}>
              {bucketIndicators.map((indicator) => (
                <label
                  key={indicator.id}
                  className="op-badge op-badge-neutral"
                  style={{ display: "inline-flex", gap: 6 }}
                >
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
      })}
    </div>
  );
}
