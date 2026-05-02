"use client";

import {
  createChart,
  CrosshairMode,
  LineStyle,
  type CandlestickData,
  type IChartApi,
  type Time,
} from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";

import { EmptyState, StatusBadge } from "@/components/operator-ui";
import { IndicatorSelector } from "@/components/charts/indicator-selector";
import {
  buildWorkflowIndicatorModel,
  FIRST_CLASS_WORKFLOW_INDICATORS,
  type IndicatorGuideDescriptor,
  type IndicatorHistogramDescriptor,
  type IndicatorLegendEntry,
  type IndicatorLineDescriptor,
  type IndicatorPanelDescriptor,
  type IndicatorPane,
} from "@/lib/chart-indicators";
import type { HacoChartPayload } from "@/lib/haco-api";
import type { IndicatorId } from "@/lib/indicator-framework";
import {
  WORKFLOW_INDICATOR_PRESETS,
  detectWorkflowIndicatorPreset,
  extractWorkflowHoverLegendValues,
  formatChartTimestamp,
  getWorkflowPanelState,
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

type VisibleTimeRange = { from: Time; to: Time };

function timeKey(time: Time): string {
  if (typeof time === "number" || typeof time === "string") return String(time);
  return `${time.year}-${String(time.month).padStart(2, "0")}-${String(time.day).padStart(2, "0")}`;
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

function legendValueKind(pane: IndicatorPane): "price" | "volume" | "momentum" {
  if (pane === "volume") return "volume";
  if (pane === "momentum") return "momentum";
  return "price";
}

function formatSessionPolicy(value: string | null | undefined): string | null {
  if (!value) return null;
  if (value === "regular_hours") return "Regular hours";
  return value.replaceAll("_", " ");
}

const PRICE_PANEL_HEIGHT = 288;
const LOWER_PANEL_HEIGHT = 74;

function createBaseChart(container: HTMLDivElement, height: number): IChartApi {
  return createChart(container, {
    autoSize: true,
    height,
    crosshair: { mode: CrosshairMode.Normal },
    layout: {
      background: { color: "#0b1219" },
      textColor: "#d9e2ef",
    },
    grid: {
      vertLines: { color: "rgba(115, 138, 163, 0.12)" },
      horzLines: { color: "rgba(115, 138, 163, 0.12)" },
    },
    rightPriceScale: {
      borderColor: "rgba(115, 138, 163, 0.24)",
    },
    timeScale: {
      borderColor: "rgba(115, 138, 163, 0.24)",
      timeVisible: true,
      secondsVisible: false,
    },
  });
}

function renderLineSeries(chart: IChartApi, line: IndicatorLineDescriptor) {
  chart
    .addLineSeries({
      color: line.color,
      lineWidth: (line.lineWidth ?? 2) as 1 | 2 | 3 | 4,
      lineStyle: line.lineStyle,
      priceScaleId: line.priceScaleId,
      lastValueVisible: line.lastValueVisible,
      priceLineVisible: line.priceLineVisible,
      autoscaleInfoProvider: line.fixedRange
        ? () => ({ priceRange: line.fixedRange })
        : undefined,
    })
    .setData(line.points);
}

function renderGuides(chart: IChartApi, candles: CandlestickData<Time>[], scaleId: string, guides: IndicatorGuideDescriptor[] = []) {
  for (const guide of guides) {
    chart
      .addLineSeries({
        color: guide.color,
        lineWidth: 1,
        lineStyle: guide.lineStyle,
        priceScaleId: scaleId,
        lastValueVisible: false,
        priceLineVisible: false,
      })
      .setData(candles.map((candle) => ({ time: candle.time, value: guide.value })));
  }
}

function renderVolumePanel(chart: IChartApi, descriptor: IndicatorHistogramDescriptor) {
  chart.priceScale("volume").applyOptions({
    scaleMargins: { top: 0.12, bottom: 0.08 },
    borderVisible: false,
  });
  chart.addHistogramSeries({
    priceScaleId: "volume",
    priceFormat: { type: "volume" },
    color: descriptor.color,
    lastValueVisible: false,
    priceLineVisible: false,
  }).setData(descriptor.data);
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
  const priceChartRef = useRef<HTMLDivElement | null>(null);
  const volumeChartRef = useRef<HTMLDivElement | null>(null);
  const momentumChartRef = useRef<HTMLDivElement | null>(null);
  const syncGuardRef = useRef(false);

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
  const indicatorModel = useMemo(
    () => buildWorkflowIndicatorModel(candles, selectedIndicators),
    [candles, selectedIndicators],
  );
  const panelState = useMemo(() => getWorkflowPanelState(selectedIndicators), [selectedIndicators]);

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
    setLegendEntries(indicatorModel.legendEntries);
  }, [indicatorModel.legendEntries]);

  useEffect(() => {
    if (!priceChartRef.current || candles.length === 0) {
      setHoveredTimeKey(null);
      return;
    }

    const priceChart = createBaseChart(priceChartRef.current, PRICE_PANEL_HEIGHT);
    const priceSeries = priceChart.addCandlestickSeries({
      upColor: "#2c9f5d",
      downColor: "#b24f4f",
      borderVisible: false,
      wickUpColor: "#5bc47c",
      wickDownColor: "#d66d6d",
    });
    priceSeries.setData(candles);
    for (const overlay of indicatorModel.priceOverlays) {
      renderLineSeries(priceChart, overlay);
    }
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

    const linkedCharts: Array<IChartApi | null> = [priceChart];
    let volumeChart: IChartApi | null = null;
    let momentumChart: IChartApi | null = null;

    if (indicatorModel.volumePanel && volumeChartRef.current) {
      volumeChart = createBaseChart(volumeChartRef.current, LOWER_PANEL_HEIGHT);
      renderVolumePanel(volumeChart, indicatorModel.volumePanel);
      linkedCharts.push(volumeChart);
    }

    const rsiPanel = indicatorModel.momentumPanels[0] ?? null;
    if (rsiPanel && momentumChartRef.current) {
      momentumChart = createBaseChart(momentumChartRef.current, LOWER_PANEL_HEIGHT);
      momentumChart.priceScale(rsiPanel.scaleId).applyOptions({
        scaleMargins: { top: 0.08, bottom: 0.08 },
        autoScale: true,
        borderVisible: false,
        mode: 0,
      });
      for (const line of rsiPanel.lines) {
        renderLineSeries(momentumChart, line);
      }
      renderGuides(momentumChart, candles, rsiPanel.scaleId, rsiPanel.guides);
      linkedCharts.push(momentumChart);
    }

    const syncVisibleRange = (source: IChartApi, targets: IChartApi[]) => {
      const handler = (range: VisibleTimeRange | null) => {
        if (!range || syncGuardRef.current) return;
        syncGuardRef.current = true;
        for (const target of targets) {
          target.timeScale().setVisibleRange(range);
        }
        syncGuardRef.current = false;
      };
      source.timeScale().subscribeVisibleTimeRangeChange(handler);
      return () => source.timeScale().unsubscribeVisibleTimeRangeChange(handler);
    };

    const hoverHandler = (param: { time?: Time }) => {
      if (!param.time) {
        setHoveredTimeKey(timeKey(candles[candles.length - 1].time));
        return;
      }
      setHoveredTimeKey(timeKey(param.time));
    };

    const cleanups: Array<() => void> = [];
    for (const chart of linkedCharts) {
      if (!chart) continue;
      chart.subscribeCrosshairMove(hoverHandler);
      cleanups.push(() => chart.unsubscribeCrosshairMove(hoverHandler));
    }
    if (volumeChart) cleanups.push(syncVisibleRange(priceChart, [volumeChart]));
    if (momentumChart) cleanups.push(syncVisibleRange(priceChart, [momentumChart]));
    if (volumeChart && momentumChart) cleanups.push(syncVisibleRange(volumeChart, [priceChart, momentumChart]));
    if (momentumChart && volumeChart) cleanups.push(syncVisibleRange(momentumChart, [priceChart, volumeChart]));
    if (momentumChart && !volumeChart) cleanups.push(syncVisibleRange(momentumChart, [priceChart]));
    if (volumeChart && !momentumChart) cleanups.push(syncVisibleRange(volumeChart, [priceChart]));

    setHoveredTimeKey(timeKey(candles[candles.length - 1].time));
    priceChart.timeScale().fitContent();
    const initialRange = priceChart.timeScale().getVisibleRange();
    if (initialRange) {
      volumeChart?.timeScale().setVisibleRange(initialRange);
      momentumChart?.timeScale().setVisibleRange(initialRange);
    }

    return () => {
      for (const cleanup of cleanups) cleanup();
      priceChart.remove();
      volumeChart?.remove();
      momentumChart?.remove();
    };
  }, [candles, indicatorModel, overlayLevels]);

  const hoverLegendEntries = useMemo(
    () => extractWorkflowHoverLegendValues(legendEntries, activeTimeKey),
    [activeTimeKey, legendEntries],
  );
  const priceLegendEntries = hoverLegendEntries.filter((entry) => entry.pane === "price");
  const lowerLegendEntries = hoverLegendEntries.filter((entry) => entry.pane !== "price");
  const latestBarTime = candles.length > 0 ? candles[candles.length - 1].time : null;

  if (!chartPayload || candles.length === 0) {
    return <EmptyState title={emptyTitle} hint={emptyHint} />;
  }

  return (
    <div className="op-stack" style={{ gap: 10 }}>
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
        {formatSessionPolicy(chartPayload.session_policy) ? (
          <StatusBadge tone="neutral">Session: {formatSessionPolicy(chartPayload.session_policy)}</StatusBadge>
        ) : null}
        <StatusBadge tone="neutral">As of: {formatChartTimestamp(latestBarTime)}</StatusBadge>
      </div>

      {unsupportedIndicators.length > 0 ? (
        <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.82rem", lineHeight: 1.5 }}>
          Stored indicators not available on this workflow chart were hidden: {unsupportedIndicators.join(", ")}.
        </div>
      ) : null}

      {showControls ? <IndicatorSelector selected={selectedIndicators} onChange={setSelectedIndicators} enabledIds={supportedIndicators} /> : null}

      <div className="op-grid-2" style={{ gap: 10, alignItems: "start" }}>
        <div style={{ minWidth: 0, border: "1px solid var(--op-border, #1e2d3d)", borderRadius: 10, padding: "10px 12px", background: "rgba(10, 18, 25, 0.72)" }}>
          <div style={{ fontSize: "0.8rem", fontWeight: 600, marginBottom: 6 }}>Hover snapshot</div>
          <div style={{ display: "grid", gap: 4, fontSize: "0.86rem" }}>
            <div><strong>Time:</strong> {formatChartTimestamp(activeCandle?.time ?? null)}</div>
            <div><strong>Close:</strong> {formatNumber(activeCandle?.close ?? null)}</div>
            {panelState.showVolume ? <div><strong>Volume:</strong> {formatNumber(activeCandle?.volume ?? null, "volume")}</div> : null}
          </div>
        </div>
        <div style={{ minWidth: 0, border: "1px solid var(--op-border, #1e2d3d)", borderRadius: 10, padding: "10px 12px", background: "rgba(10, 18, 25, 0.72)" }}>
          <div style={{ fontSize: "0.8rem", fontWeight: 600, marginBottom: 6 }}>Visible indicators</div>
          {hoverLegendEntries.length === 0 ? (
            <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.82rem" }}>
              No indicators enabled. Use a preset or custom toggles to add chart context.
            </div>
          ) : (
            <div className="op-stack" style={{ gap: 8, maxHeight: 220, overflowY: "auto", paddingRight: 2 }}>
              {priceLegendEntries.length > 0 ? (
                <div className="op-stack" style={{ gap: 6 }}>
                  <div style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--op-muted, #7a8999)" }}>Price overlays</div>
                  <div style={{ display: "grid", gap: 6 }}>
                    {priceLegendEntries.map((entry) => (
                      <button
                        key={`${entry.label}-${entry.color}`}
                        type="button"
                        onClick={() => setSelectedIndicators((prev) => prev.filter((item) => item !== legendEntries.find((source) => source.label === entry.label)?.id))}
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
                        <span style={{ display: "inline-flex", alignItems: "center", gap: 8, minWidth: 0 }}>
                          <span style={{ width: 10, height: 10, borderRadius: 999, background: entry.color, display: "inline-block" }} />
                          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{entry.label}</span>
                        </span>
                        <span style={{ flexShrink: 0, fontVariantNumeric: "tabular-nums" }}>{formatNumber(entry.value, legendValueKind(entry.pane))}</span>
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}
              {lowerLegendEntries.length > 0 ? (
                <div className="op-stack" style={{ gap: 6 }}>
                  <div style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--op-muted, #7a8999)" }}>Lower panels</div>
                  <div style={{ display: "grid", gap: 6 }}>
                    {lowerLegendEntries.map((entry) => (
                      <div
                        key={`${entry.label}-${entry.color}`}
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          gap: 12,
                          padding: "6px 8px",
                          borderRadius: 8,
                          border: "1px solid rgba(115, 138, 163, 0.24)",
                          background: "rgba(15, 24, 34, 0.72)",
                        }}
                      >
                        <span style={{ display: "inline-flex", alignItems: "center", gap: 8, minWidth: 0 }}>
                          <span style={{ width: 10, height: 10, borderRadius: 999, background: entry.color, display: "inline-block" }} />
                          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{entry.label}</span>
                        </span>
                        <span style={{ flexShrink: 0, fontVariantNumeric: "tabular-nums" }}>{formatNumber(entry.value, legendValueKind(entry.pane))}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          )}
        </div>
      </div>

      <div className="op-stack" style={{ gap: 6 }}>
        <div className="op-row" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontSize: "0.8rem", fontWeight: 600 }}>Price</div>
          <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.76rem" }}>Primary panel</div>
        </div>
        <div ref={priceChartRef} />
        {indicatorModel.volumePanel ? (
          <>
            <div className="op-row" style={{ justifyContent: "space-between", alignItems: "center", marginTop: 2 }}>
              <div style={{ fontSize: "0.78rem", fontWeight: 600 }}>Volume</div>
              <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.76rem" }}>Compact bars</div>
            </div>
            <div ref={volumeChartRef} />
          </>
        ) : null}
        {indicatorModel.momentumPanels[0] ? (
          <>
            <div className="op-row" style={{ justifyContent: "space-between", alignItems: "center", marginTop: 2 }}>
              <div style={{ fontSize: "0.78rem", fontWeight: 600 }}>{indicatorModel.momentumPanels[0].label}</div>
              <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.76rem" }}>0 / 30 / 50 / 70 / 100</div>
            </div>
            <div ref={momentumChartRef} />
          </>
        ) : null}
      </div>

      <div style={{ color: "var(--op-muted, #7a8999)", fontSize: "0.8rem", lineHeight: 1.5 }}>
        Hover any panel to inspect one synchronized bar context across price, volume, and momentum. Values without enough history remain Unavailable. MACD, ATR, HACO parity, and richer interactive coverage remain deferred for a later chart pass.
      </div>
    </div>
  );
}
