"use client";

import { createChart, CrosshairMode, LineStyle, type CandlestickData, type Time } from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";

import { EmptyState, StatusBadge } from "@/components/operator-ui";
import { IndicatorSelector } from "@/components/charts/indicator-selector";
import { applyIndicatorsToChart, FIRST_CLASS_WORKFLOW_INDICATORS, type IndicatorLegendEntry } from "@/lib/chart-indicators";
import type { HacoChartPayload } from "@/lib/haco-api";
import type { IndicatorId } from "@/lib/indicator-framework";
import {
  WORKFLOW_INDICATOR_PRESETS,
  detectWorkflowIndicatorPreset,
  getWorkflowPresetIndicators,
  sanitizeWorkflowIndicatorSelection,
} from "@/lib/workflow-chart";

type WorkflowChartOverlay = {
  label: string;
  value: number | null | undefined;
  color: string;
  lineStyle?: LineStyle;
  lineWidth?: number;
};

function timeKey(time: Time): string {
  if (typeof time === "number" || typeof time === "string") return String(time);
  return `${time.year}-${String(time.month).padStart(2, "0")}-${String(time.day).padStart(2, "0")}`;
}

function formatTimestamp(raw: string | null | undefined): string {
  if (!raw) return "Unavailable";
  const timestamp = new Date(raw);
  if (Number.isNaN(timestamp.getTime())) return raw;
  return timestamp.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatNumber(value: number | null | undefined, kind: "price" | "volume" | "momentum" = "price"): string {
  if (value == null || Number.isNaN(value)) return "Unavailable";
  if (kind === "volume") {
    return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 2 }).format(value);
  }
  if (kind === "momentum") {
    return value.toFixed(2);
  }
  return value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function legendValueKind(entry: IndicatorLegendEntry): "price" | "volume" | "momentum" {
  if (entry.pane === "volume") return "volume";
  if (entry.pane === "momentum") return "momentum";
  return "price";
}

export function WorkflowChart({
  chartPayload,
  storageKey,
  overlayLevels = [],
  supportedIndicators = FIRST_CLASS_WORKFLOW_INDICATORS,
  emptyTitle,
  emptyHint,
  sourceLabel,
}: {
  chartPayload: HacoChartPayload | null;
  storageKey: string;
  overlayLevels?: WorkflowChartOverlay[];
  supportedIndicators?: IndicatorId[];
  emptyTitle: string;
  emptyHint: string;
  sourceLabel?: string;
}) {
  const chartRef = useRef<HTMLDivElement | null>(null);
  const [legendEntries, setLegendEntries] = useState<IndicatorLegendEntry[]>([]);
  const [selectedIndicators, setSelectedIndicators] = useState<IndicatorId[]>([]);
  const [unsupportedIndicators, setUnsupportedIndicators] = useState<IndicatorId[]>([]);
  const [hoveredTimeKey, setHoveredTimeKey] = useState<string | null>(null);
  const [showControls, setShowControls] = useState(false);

  const candles = useMemo<Array<CandlestickData<Time> & { volume: number }>>(
    () =>
      (chartPayload?.candles ?? []).slice(-180).map((candle) => ({
        time: candle.time as Time,
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
        volume: candle.volume,
      })),
    [chartPayload],
  );

  const candleMap = useMemo(() => new Map(candles.map((candle) => [timeKey(candle.time), candle])), [candles]);
  const latestTimeKey = candles.length > 0 ? timeKey(candles[candles.length - 1].time) : null;
  const activeTimeKey = hoveredTimeKey ?? latestTimeKey;
  const activeCandle = activeTimeKey ? candleMap.get(activeTimeKey) ?? candles[candles.length - 1] ?? null : null;
  const activePreset = useMemo(
    () => detectWorkflowIndicatorPreset(selectedIndicators, supportedIndicators),
    [selectedIndicators, supportedIndicators],
  );

  useEffect(() => {
    if (typeof window === "undefined") return;
    const raw = window.localStorage.getItem(storageKey);
    try {
      const parsed = raw ? (JSON.parse(raw) as string[]) : [];
      const next = sanitizeWorkflowIndicatorSelection(parsed, supportedIndicators);
      setSelectedIndicators(next.selected);
      setUnsupportedIndicators(next.unsupported);
    } catch {
      const next = sanitizeWorkflowIndicatorSelection([], supportedIndicators);
      setSelectedIndicators(next.selected);
      setUnsupportedIndicators([]);
    }
  }, [storageKey, supportedIndicators]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(storageKey, JSON.stringify(selectedIndicators));
  }, [selectedIndicators, storageKey]);

  useEffect(() => {
    if (!chartRef.current || candles.length === 0) {
      setLegendEntries([]);
      setHoveredTimeKey(null);
      return;
    }
    const chart = createChart(chartRef.current, {
      autoSize: true,
      height: 380,
      crosshair: { mode: CrosshairMode.Normal },
      layout: {
        background: { color: "#0b1219" },
        textColor: "#d9e2ef",
      },
      grid: {
        vertLines: { color: "rgba(115, 138, 163, 0.14)" },
        horzLines: { color: "rgba(115, 138, 163, 0.14)" },
      },
      rightPriceScale: {
        borderColor: "rgba(115, 138, 163, 0.24)",
      },
      timeScale: {
        borderColor: "rgba(115, 138, 163, 0.24)",
      },
    });
    const priceSeries = chart.addCandlestickSeries({
      upColor: "#2c9f5d",
      downColor: "#b24f4f",
      borderVisible: false,
      wickUpColor: "#5bc47c",
      wickDownColor: "#d66d6d",
    });
    priceSeries.setData(candles);

    const renderResult = applyIndicatorsToChart(chart, candles, selectedIndicators);
    setLegendEntries(renderResult.legendEntries);
    setHoveredTimeKey(timeKey(candles[candles.length - 1].time));

    for (const overlay of overlayLevels) {
      if (overlay.value == null || Number.isNaN(overlay.value)) continue;
      priceSeries.createPriceLine({
        price: overlay.value,
        color: overlay.color,
        lineStyle: overlay.lineStyle ?? LineStyle.Solid,
        lineWidth: (overlay.lineWidth ?? 1) as 1 | 2 | 3 | 4,
        axisLabelVisible: true,
        title: overlay.label,
      });
    }

    const handleCrosshairMove = (param: { time?: Time }) => {
      if (!param.time) {
        setHoveredTimeKey(timeKey(candles[candles.length - 1].time));
        return;
      }
      setHoveredTimeKey(timeKey(param.time));
    };

    chart.subscribeCrosshairMove(handleCrosshairMove);
    chart.timeScale().fitContent();

    return () => {
      chart.unsubscribeCrosshairMove(handleCrosshairMove);
      chart.remove();
    };
  }, [candles, overlayLevels, selectedIndicators]);

  const hoverLegendEntries = useMemo(
    () =>
      legendEntries.map((entry) => ({
        ...entry,
        activeValue: activeTimeKey ? entry.valuesByTime.get(activeTimeKey) ?? null : null,
      })),
    [activeTimeKey, legendEntries],
  );

  const latestBarTime = candles.length > 0 ? String(candles[candles.length - 1].time) : null;

  if (!chartPayload || candles.length === 0) {
    return <EmptyState title={emptyTitle} hint={emptyHint} />;
  }

  return (
    <div className="op-stack" style={{ gap: 12 }}>
      <div className="op-row" style={{ justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
        <div className="op-row" style={{ flexWrap: "wrap", gap: 8 }}>
          {WORKFLOW_INDICATOR_PRESETS.map((preset) => {
            const isActive = activePreset === preset.id;
            return (
              <button
                key={preset.id}
                type="button"
                className={isActive ? "op-btn op-btn-primary" : "op-btn op-btn-ghost"}
                title={preset.description}
                onClick={() => setSelectedIndicators(getWorkflowPresetIndicators(preset.id, supportedIndicators))}
              >
                {preset.label}
              </button>
            );
          })}
          <StatusBadge tone={activePreset === "custom" ? "warn" : "neutral"}>
            {activePreset === "custom" ? "Custom" : `${activePreset} preset`}
          </StatusBadge>
        </div>
        <button type="button" className="op-btn op-btn-ghost" onClick={() => setShowControls((prev) => !prev)}>
          {showControls ? "Hide indicator controls" : "Show indicator controls"}
        </button>
      </div>

      <div className="op-row" style={{ flexWrap: "wrap", gap: 8 }}>
        <StatusBadge tone={chartPayload.fallback_mode ? "warn" : "good"}>
          {chartPayload.fallback_mode ? "Fallback bars" : "Provider-backed bars"}
        </StatusBadge>
        <StatusBadge tone="neutral">Source: {sourceLabel ?? chartPayload.data_source}</StatusBadge>
        <StatusBadge tone="neutral">As of: {formatTimestamp(latestBarTime)}</StatusBadge>
      </div>

      {unsupportedIndicators.length > 0 ? (
        <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.82rem", lineHeight: 1.5 }}>
          Stored indicators not available on this workflow chart were hidden: {unsupportedIndicators.join(", ")}.
        </div>
      ) : null}

      {showControls ? <IndicatorSelector selected={selectedIndicators} onChange={setSelectedIndicators} enabledIds={supportedIndicators} /> : null}

      <div className="op-grid-2" style={{ gap: 12 }}>
        <div style={{ border: "1px solid var(--op-border, #1e2d3d)", borderRadius: 10, padding: 12, background: "rgba(10, 18, 25, 0.72)" }}>
          <div style={{ fontSize: "0.8rem", fontWeight: 600, marginBottom: 8 }}>Hover snapshot</div>
          <div style={{ display: "grid", gap: 4 }}>
            <div><strong>Time:</strong> {formatTimestamp(activeCandle ? String(activeCandle.time) : null)}</div>
            <div><strong>Close:</strong> {formatNumber(activeCandle?.close ?? null)}</div>
            <div><strong>Volume:</strong> {formatNumber(activeCandle?.volume ?? null, "volume")}</div>
          </div>
        </div>
        <div style={{ border: "1px solid var(--op-border, #1e2d3d)", borderRadius: 10, padding: 12, background: "rgba(10, 18, 25, 0.72)" }}>
          <div style={{ fontSize: "0.8rem", fontWeight: 600, marginBottom: 8 }}>Visible indicator values</div>
          {hoverLegendEntries.length === 0 ? (
            <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.82rem" }}>
              No indicators enabled. Use a preset or custom toggles to add chart context.
            </div>
          ) : (
            <div style={{ display: "grid", gap: 6 }}>
              {hoverLegendEntries.map((entry) => (
                <button
                  key={`${entry.id}-${entry.label}`}
                  type="button"
                  onClick={() => setSelectedIndicators((prev) => prev.filter((item) => item !== entry.id))}
                  title={`Hide ${entry.label}`}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 12,
                    padding: "6px 8px",
                    borderRadius: 8,
                    border: "1px solid rgba(115, 138, 163, 0.24)",
                    background: "rgba(15, 24, 34, 0.72)",
                    color: "inherit",
                    cursor: "pointer",
                    textAlign: "left",
                  }}
                >
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                    <span style={{ width: 10, height: 10, borderRadius: 999, background: entry.color, display: "inline-block" }} />
                    <span>{entry.label}</span>
                  </span>
                  <span>{formatNumber(entry.activeValue, legendValueKind(entry))}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div ref={chartRef} />

      <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.8rem", lineHeight: 1.5 }}>
        Hover the crosshair to inspect the displayed bar and currently visible indicators only. Values without enough chart history render as Unavailable.
      </div>
    </div>
  );
}
