"use client";

import { createChart, LineStyle, type CandlestickData, type IChartApi, type Time } from "lightweight-charts";
import { useAuth } from "@clerk/nextjs";
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import { Card, EmptyState, ErrorState, InlineFeedback, PageHeader, StatusBadge } from "@/components/operator-ui";
import { IndicatorSelector } from "@/components/charts/indicator-selector";
import { normalizeSelection, type IndicatorId } from "@/lib/indicator-framework";
import { fetchWorkflowApi } from "@/lib/api-client";
import { fetchHacoChart } from "@/lib/haco-api";
import { applyIndicatorsToChart, FIRST_CLASS_WORKFLOW_INDICATORS } from "@/lib/chart-indicators";

type Rec = { id: number; created_at: string; symbol: string; payload: any; recommendation_id: string; market_data_source?: string; fallback_mode?: boolean };
const SORTABLE_COLUMNS = ["created_at", "symbol", "side", "setup", "approved", "expected_rr", "confidence", "catalyst"] as const;
type SortColumn = (typeof SORTABLE_COLUMNS)[number];
const STORAGE_KEY = "macmarket-indicators-recommendations";
const PROVIDER_BLOCKED_HINT = "Configured provider unavailable. Recommendations/Replay/Orders are blocked from silently falling back. For local demo only, enable WORKFLOW_DEMO_FALLBACK=true in backend env.";

export default function Page() {
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const searchParams = useSearchParams();
  const searchKey = searchParams.toString();
  const chartRef = useRef<HTMLDivElement | null>(null);
  const chartApiRef = useRef<IChartApi | null>(null);
  const [rows, setRows] = useState<Rec[]>([]);
  const [selected, setSelected] = useState<Rec | null>(null);
  const [status, setStatus] = useState<string>("idle");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [symbolInput, setSymbolInput] = useState("AAPL");
  const [eventText, setEventText] = useState("Operator catalyst review.");
  const [sortCol, setSortCol] = useState<SortColumn>("created_at");
  const [showHaco, setShowHaco] = useState(false);
  const [chartSource, setChartSource] = useState("workflow pending");
  const [chartError, setChartError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ state: "idle" | "loading" | "success" | "error"; message: string }>({ state: "idle", message: "" });
  const [selectedIndicators, setSelectedIndicators] = useState<IndicatorId[]>([]);

  async function load() {
    if (!isLoaded || !isSignedIn) {
      setFeedback({ state: "loading", message: "Initializing authenticated workflow…" });
      return;
    }
    setLoading(true);
    setError(null);
    setFeedback({ state: "loading", message: "Loading recommendations…" });
    const result = await fetchWorkflowApi<Rec>("/api/user/recommendations", undefined, { authMode: "token", getToken });
    if (!result.ok) {
      if (result.authPending) {
        setError(null);
        setFeedback({ state: "loading", message: "Authentication initializing. Retrying shortly…" });
        setLoading(false);
        return;
      }
      setError(result.status === 503 ? PROVIDER_BLOCKED_HINT : (result.error ?? "Could not load recommendations."));
      setFeedback({ state: "error", message: result.status === 503 ? PROVIDER_BLOCKED_HINT : (result.error ?? "Could not load recommendations.") });
      setRows([]);
      setSelected(null);
      setLoading(false);
      return;
    }
    const normalized = result.items.filter((item) => item && typeof item === "object" && "id" in item) as Rec[];
    setError(null);
    setRows(normalized);
    const requestedRecommendation = new URLSearchParams(searchKey).get("recommendation");
    setSelected((prev) =>
      normalized.find((item) => item.recommendation_id === requestedRecommendation)
      ?? normalized.find((item) => item.id === prev?.id)
      ?? normalized[0]
      ?? null,
    );
    setFeedback({ state: "success", message: "Recommendations updated." });
    setLoading(false);
  }

  useEffect(() => {
    if (!isLoaded || !isSignedIn) return;
    void load();
  }, [searchKey, isLoaded, isSignedIn]);
  useEffect(() => {
    if (feedback.state !== "success") return;
    const timer = window.setTimeout(() => setFeedback({ state: "idle", message: "" }), 2800);
    return () => window.clearTimeout(timer);
  }, [feedback.state, feedback.message]);

  async function generate() {
    if (!isLoaded || !isSignedIn) {
      setFeedback({ state: "loading", message: "Authentication still initializing." });
      return;
    }
    setStatus("Generating deterministic recommendation...");
    setFeedback({ state: "loading", message: "Generating recommendation…" });
    const result = await fetchWorkflowApi<{ market_data_source?: string; fallback_mode?: boolean }>(
      "/api/user/recommendations/generate",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: symbolInput.trim().toUpperCase(), event_text: eventText.trim() }),
      },
      { authMode: "token", getToken },
    );
    if (!result.ok) {
      if (result.authPending) {
        setFeedback({ state: "loading", message: "Authentication initializing. Please retry in a moment." });
        return;
      }
      const msg = result.status === 503 ? PROVIDER_BLOCKED_HINT : (result.error ?? `Generation failed (${result.status}).`);
      setError(msg);
      setFeedback({ state: "error", message: msg });
      return;
    }
    setError(null);
    const fallbackMode = result.data?.fallback_mode ?? false;
    const sourceName = result.data?.market_data_source ?? "provider";
    setChartSource(fallbackMode ? `fallback (${sourceName})` : sourceName);
    setStatus("Recommendation generated.");
    setFeedback({ state: "success", message: "Recommendation generated." });
    await load();
  }

  const sortedRows = useMemo(() => {
    const clone = [...rows];
    clone.sort((a, b) => {
      const pa = a.payload ?? {};
      const pb = b.payload ?? {};
      const map: Record<SortColumn, string | number> = {
        created_at: a.created_at,
        symbol: a.symbol,
        side: pa.side ?? "",
        setup: pa.entry?.setup_type ?? "",
        approved: pa.approved ? 1 : 0,
        expected_rr: Number(pa.quality?.expected_rr ?? 0),
        confidence: Number(pa.quality?.confidence ?? 0),
        catalyst: pa.catalyst?.type ?? "",
      };
      const bmap: Record<SortColumn, string | number> = {
        ...map,
        created_at: b.created_at,
        symbol: b.symbol,
        side: pb.side ?? "",
        setup: pb.entry?.setup_type ?? "",
        approved: pb.approved ? 1 : 0,
        expected_rr: Number(pb.quality?.expected_rr ?? 0),
        confidence: Number(pb.quality?.confidence ?? 0),
        catalyst: pb.catalyst?.type ?? "",
      };
      return String(bmap[sortCol]).localeCompare(String(map[sortCol]), undefined, { numeric: true });
    });
    return clone;
  }, [rows, sortCol]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const raw = window.localStorage.getItem(STORAGE_KEY);
    try {
      setSelectedIndicators(normalizeSelection(raw ? (JSON.parse(raw) as string[]) : []).filter((item) => FIRST_CLASS_WORKFLOW_INDICATORS.includes(item)));
    } catch {
      setSelectedIndicators(normalizeSelection([]).filter((item) => FIRST_CLASS_WORKFLOW_INDICATORS.includes(item)));
    }
  }, []);

  function handleIndicatorChange(next: IndicatorId[]) {
    const normalized = normalizeSelection(next).filter((item) => FIRST_CLASS_WORKFLOW_INDICATORS.includes(item));
    setSelectedIndicators(normalized);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(normalized));
    }
  }

  useEffect(() => {
    async function renderChart() {
      if (!chartRef.current || !selected) return;
      const selectedFallback = Boolean(selected.fallback_mode ?? selected.payload?.workflow?.fallback_mode);
      const selectedSource = String(selected.market_data_source ?? selected.payload?.workflow?.market_data_source ?? "provider");
      setChartSource(selectedFallback ? `fallback (${selectedSource})` : selectedSource);
      if (selectedFallback) {
        setChartError("Selected recommendation was generated from fallback bars; provider chart overlay is disabled to avoid mixed-source context.");
        return;
      }
      setChartError(null);
      const timeframe = String(selected.payload?.workflow?.timeframe ?? "1D");
      const payload = await fetchHacoChart({ symbol: selected.symbol, timeframe, include_heikin_ashi: showHaco });
      setChartSource(payload.fallback_mode ? `fallback (${payload.data_source})` : payload.data_source);
      if (chartApiRef.current) chartApiRef.current.remove();
      const chart = createChart(chartRef.current, { height: 300, layout: { background: { color: "#0b1219" }, textColor: "#d9e2ef" } });
      chartApiRef.current = chart;
      const candles: Array<CandlestickData<Time> & { volume: number }> = payload.candles.slice(-120).map((c) => ({ time: c.time as Time, open: c.open, high: c.high, low: c.low, close: c.close, volume: c.volume }));
      chart.addCandlestickSeries().setData(candles);
      applyIndicatorsToChart(chart, candles, selectedIndicators);

      const invalidation = chart.addLineSeries({ color: "#ff8b8b", lineStyle: LineStyle.Dashed, lineWidth: 2 });
      const target = chart.addLineSeries({ color: "#7ee787", lineStyle: LineStyle.Dotted, lineWidth: 2 });
      const entry = chart.addLineSeries({ color: "#6ea8fe", lineWidth: 2 });
      const inv = selected.payload?.invalidation?.price;
      const t1 = selected.payload?.targets?.target_1;
      const mid = Number(selected.payload?.entry?.zone_low ?? 0) + Number(selected.payload?.entry?.zone_high ?? 0);
      const entryMid = mid > 0 ? mid / 2 : undefined;
      if (inv) invalidation.setData(candles.map((c) => ({ time: c.time, value: inv })));
      if (t1) target.setData(candles.map((c) => ({ time: c.time, value: t1 })));
      if (entryMid) entry.setData(candles.map((c) => ({ time: c.time, value: entryMid })));
      if (showHaco) {
        chart.addLineSeries({ color: "#f7b267", lineWidth: 1 }).setData(payload.heikin_ashi_candles.slice(-120).map((c) => ({ time: c.time as Time, value: c.close })));
      }
    }
    void renderChart().catch((err) => {
      const message = err instanceof Error && err.message === "AUTH_NOT_READY"
        ? "Auth is still initializing for chart context. Retry in a moment."
        : "Unable to render chart overlay for selected recommendation. Workflow detail remains available.";
      setChartError(message);
    });
    return () => chartApiRef.current?.remove();
  }, [selected, showHaco, selectedIndicators]);

  return (
    <section className="op-stack">
      <PageHeader title="Recommendations" subtitle="Flagship operator workspace for deterministic trade plans." actions={<StatusBadge tone="neutral">{status || "idle"}</StatusBadge>} />
      <Card title="Workflow breadcrumbs">
        Strategy Workbench → Recommendations review → Replay validation → Paper Orders staging.
      </Card>
      <Card title="Workflow guidance">
        Generate from Strategy Workbench setup, validate strategy/risk context, then move to replay and paper orders. HACO is supporting context only. Chart/context source: <strong>{chartSource}</strong>.
      </Card>
      {!isLoaded ? <Card title="Auth status">Initializing authenticated session before protected workflow API requests.</Card> : null}
      <Card>
        <div className="op-row">
          <input value={symbolInput} onChange={(e) => setSymbolInput(e.target.value.toUpperCase())} placeholder="Symbol" />
          <input value={eventText} onChange={(e) => setEventText(e.target.value)} placeholder="Catalyst summary" style={{ minWidth: 260 }} />
          <button onClick={() => void generate()}>Generate recommendations</button>
          <button onClick={() => void load()} disabled={loading}>{loading ? "Refreshing..." : "Refresh"}</button>
          <button onClick={() => setError(null)}>Clear error</button>
        </div>
        <InlineFeedback state={feedback.state} message={feedback.message} onRetry={() => void load()} />
      </Card>

      {error ? <ErrorState title="Recommendations unavailable" hint={error} /> : null}
      {chartError ? <ErrorState title="Chart context notice" hint={chartError} /> : null}
      {!loading && !error && rows.length === 0 ? <EmptyState title="No recommendations yet" hint="Generate a deterministic recommendation to seed the workspace." /> : null}

      <div className="op-grid-2">
        <Card title="Recommendation queue">
          <div className="op-row" style={{ marginBottom: 8 }}>{SORTABLE_COLUMNS.map((col) => <button key={col} onClick={() => setSortCol(col)}>{col}</button>)}</div>
          <table className="op-table">
            <thead><tr><th>created_at</th><th>symbol</th><th>side</th><th>setup</th><th>approved/no_trade</th><th>expected_rr</th><th>confidence</th><th>catalyst</th></tr></thead>
            <tbody>{sortedRows.map((r) => <tr key={r.id} onClick={() => setSelected(r)} className={`is-selectable ${selected?.id === r.id ? "is-active" : ""}`}><td>{r.created_at}</td><td>{r.symbol}</td><td>{r.payload?.side}</td><td>{r.payload?.entry?.setup_type}</td><td>{r.payload?.approved ? "approved" : "no_trade"}</td><td>{r.payload?.quality?.expected_rr}</td><td>{r.payload?.quality?.confidence}</td><td>{r.payload?.catalyst?.type}</td></tr>)}</tbody>
          </table>
        </Card>
        <Card title="Selected recommendation detail">
          {!selected ? <EmptyState title="Select a recommendation" hint="Choose a row to review thesis, risk controls, and provenance." /> : <div className="op-detail-list">
            <div><strong>Thesis:</strong> {selected.payload?.thesis ?? "-"}</div>
            <div><strong>Catalyst:</strong> {selected.payload?.catalyst?.type ?? "-"}</div>
            <div><strong>Strategy:</strong> {selected.payload?.entry?.setup_type ?? "Event Continuation"}</div>
            <div><strong>Regime context:</strong> {selected.payload?.regime_context?.market_regime ?? "-"}</div>
            <div><strong>Symbol / timeframe:</strong> {selected.symbol} / {selected.payload?.workflow?.timeframe ?? "1D"}</div>
            <div><strong>Workflow data source:</strong> {selected.payload?.workflow?.fallback_mode ? `fallback (${selected.payload?.workflow?.market_data_source ?? selected.market_data_source ?? "provider"})` : (selected.payload?.workflow?.market_data_source ?? selected.market_data_source ?? "provider")}</div>
            <div><strong>HACO role:</strong> Supporting technical context, not sole approval engine.</div>
            <div><strong>Entry zone:</strong> {selected.payload?.entry?.zone_low} - {selected.payload?.entry?.zone_high}</div>
            <div><strong>Trigger:</strong> {selected.payload?.entry?.trigger_text}</div>
            <div><strong>Invalidation:</strong> {selected.payload?.invalidation?.price} ({selected.payload?.invalidation?.reason})</div>
            <div><strong>Targets:</strong> {selected.payload?.targets?.target_1} / {selected.payload?.targets?.target_2}</div>
            <div><strong>Time stop:</strong> {selected.payload?.time_stop?.max_holding_days} days</div>
            <div><strong>Expected R/R:</strong> {selected.payload?.quality?.expected_rr}</div>
            <div><strong>Confidence:</strong> {selected.payload?.quality?.confidence}</div>
            <div><strong>No-trade reason:</strong> {selected.payload?.rejection_reason || "n/a"}</div>
            <div><strong>Provenance summary:</strong> {selected.payload?.evidence?.source_type} @ {selected.payload?.evidence?.source_timestamp}</div>
            <div className="op-row" style={{ marginTop: 8 }}>
              <button onClick={() => void load()}>Rerun / refresh</button>
              <button onClick={() => window.location.assign(`/replay-runs?symbol=${selected.symbol}&recommendation=${selected.recommendation_id}`)}>Run replay with context</button>
              <button onClick={() => window.location.assign(`/orders?recommendation=${selected.recommendation_id}`)}>Stage paper order</button>
            </div>
          </div>}
        </Card>
      </div>

      <Card title="Recommendation chart context">
        <div className="op-row" style={{ marginBottom: 8 }}>
          <label><input type="checkbox" checked={showHaco} onChange={(e) => setShowHaco(e.target.checked)} /> show HACO overlay</label>
          <StatusBadge tone="neutral">{chartSource}</StatusBadge>
        </div>
        <IndicatorSelector selected={selectedIndicators} onChange={handleIndicatorChange} enabledIds={FIRST_CLASS_WORKFLOW_INDICATORS} />
        <div className="op-row">{selectedIndicators.map((item) => <StatusBadge key={item} tone="neutral">{item}</StatusBadge>)}</div>
        <div ref={chartRef} />
      </Card>
    </section>
  );
}
