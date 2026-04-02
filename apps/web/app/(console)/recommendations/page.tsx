"use client";

import { createChart, type CandlestickData, LineStyle, type Time } from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "@clerk/nextjs";

import { Card, EmptyState, ErrorState, PageHeader, StatusBadge } from "@/components/operator-ui";
import { fetchNormalizedAuthed } from "@/lib/api-client";
import { fetchHacoChart } from "@/lib/haco-api";

type Rec = { id: number; created_at: string; symbol: string; payload: any; recommendation_id: string; market_data_source?: string; fallback_mode?: boolean };

const SORTABLE_COLUMNS = ["created_at", "symbol", "side", "setup", "approved", "expected_rr", "confidence", "catalyst"] as const;
type SortColumn = (typeof SORTABLE_COLUMNS)[number];

export default function Page() {
  const { getToken } = useAuth();
  const chartRef = useRef<HTMLDivElement | null>(null);
  const [rows, setRows] = useState<Rec[]>([]);
  const [selected, setSelected] = useState<Rec | null>(null);
  const [status, setStatus] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [symbolInput, setSymbolInput] = useState("AAPL");
  const [eventText, setEventText] = useState("Operator catalyst review.");
  const [sortCol, setSortCol] = useState<SortColumn>("created_at");
  const [showHaco, setShowHaco] = useState(false);
  const [chartSource, setChartSource] = useState("unknown");
  const [chartError, setChartError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    const result = await fetchNormalizedAuthed<Rec>("/api/user/recommendations", undefined, getToken);
    if (!result.ok) {
      setError(result.error ?? "Could not load recommendations.");
      setRows([]);
      setSelected(null);
      setLoading(false);
      return;
    }
    const normalized = result.items.filter((item) => item && typeof item === "object" && "id" in item) as Rec[];
    setError(null);
    setRows(normalized);
    setSelected((prev) => normalized.find((item) => item.id === prev?.id) ?? normalized[0] ?? null);
    setLoading(false);
  }

  useEffect(() => {
    void load();
  }, []);

  async function generate() {
    setStatus("Generating deterministic recommendation...");
    const result = await fetchNormalizedAuthed<{ market_data_source?: string; fallback_mode?: boolean }>("/api/user/recommendations/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol: symbolInput.trim().toUpperCase(), event_text: eventText.trim() }),
    }, getToken);
    if (!result.ok) {
      setError(result.error ?? `Generation failed (${result.status}).`);
      return;
    }
    setError(null);
    const fallbackMode = result.data?.fallback_mode ?? false;
    const sourceName = result.data?.market_data_source ?? "provider";
    setChartSource(fallbackMode ? `fallback (${sourceName})` : sourceName);
    setStatus("Recommendation generated.");
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
    async function renderChart() {
      if (!chartRef.current || !selected) return;
      const selectedFallback = Boolean(selected.fallback_mode ?? selected.payload?.workflow?.fallback_mode);
      const selectedSource = String(selected.market_data_source ?? selected.payload?.workflow?.market_data_source ?? "unknown");
      setChartSource(selectedFallback ? `fallback (${selectedSource})` : selectedSource);
      if (selectedFallback) {
        setChartError("Selected recommendation was generated from fallback bars; provider chart overlay is disabled to avoid mixed-source context.");
        return;
      }
      setChartError(null);
      const payload = await fetchHacoChart({ symbol: selected.symbol, timeframe: "1D", include_heikin_ashi: showHaco });
      setChartSource(payload.fallback_mode ? `fallback (${payload.data_source})` : payload.data_source);
      const chart = createChart(chartRef.current, { height: 280, layout: { background: { color: "#0b1219" }, textColor: "#d9e2ef" } });
      const candles: CandlestickData<Time>[] = payload.candles.slice(-90).map((c) => ({ time: c.time as Time, open: c.open, high: c.high, low: c.low, close: c.close }));
      chart.addCandlestickSeries().setData(candles);
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
      let hacoSeries;
      if (showHaco) {
        hacoSeries = chart.addLineSeries({ color: "#f7b267", lineWidth: 1 });
        hacoSeries.setData(payload.heikin_ashi_candles.slice(-90).map((c) => ({ time: c.time as Time, value: c.close })));
      }
      return () => chart.remove();
    }
    let cleanup: (() => void) | undefined;
    renderChart().then((c) => {
      cleanup = c;
    }).catch(() => {
      setChartError("Unable to render chart overlay for selected recommendation. Workflow detail remains available.");
    });
    return () => cleanup?.();
  }, [selected, showHaco]);

  return (
    <section className="op-stack">
      <PageHeader title="Recommendations" subtitle="Flagship operator workspace for deterministic trade plans." actions={<StatusBadge tone="neutral">{status || "idle"}</StatusBadge>} />
      <Card title="Workflow guidance">
        Generate a recommendation from current market mode, review setup detail, then move to replay or paper orders. Chart/context source: <strong>{chartSource}</strong>.
      </Card>
      <Card>
        <div className="op-row">
          <input value={symbolInput} onChange={(e) => setSymbolInput(e.target.value.toUpperCase())} placeholder="Symbol" />
          <input value={eventText} onChange={(e) => setEventText(e.target.value)} placeholder="Catalyst summary" style={{ minWidth: 260 }} />
          <button onClick={() => void generate()}>Generate recommendations</button>
          <button onClick={() => void load()} disabled={loading}>{loading ? "Refreshing..." : "Refresh"}</button>
          <button onClick={() => setError(null)}>Clear error</button>
        </div>
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
            <div><strong>Regime context:</strong> {selected.payload?.regime_context?.market_regime ?? "-"}</div>
            <div><strong>Entry zone:</strong> {selected.payload?.entry?.zone_low} - {selected.payload?.entry?.zone_high}</div>
            <div><strong>Trigger:</strong> {selected.payload?.entry?.trigger_text}</div>
            <div><strong>Invalidation:</strong> {selected.payload?.invalidation?.price} ({selected.payload?.invalidation?.reason})</div>
            <div><strong>Targets:</strong> {selected.payload?.targets?.target_1} / {selected.payload?.targets?.target_2}</div>
            <div><strong>Time stop:</strong> {selected.payload?.time_stop?.max_holding_days} days</div>
            <div><strong>Expected R/R:</strong> {selected.payload?.quality?.expected_rr}</div>
            <div><strong>Confidence:</strong> {selected.payload?.quality?.confidence}</div>
            <div><strong>No-trade reason:</strong> {selected.payload?.rejection_reason || "n/a"}</div>
            <div><strong>Evidence notes:</strong> {(selected.payload?.evidence?.explanatory_notes ?? []).join(" | ") || "none"}</div>
            <div><strong>Provenance summary:</strong> {selected.payload?.evidence?.source_type} @ {selected.payload?.evidence?.source_timestamp}</div>
            <div><strong>Visible chart symbol:</strong> {selected.symbol} ({chartSource})</div>
            <div className="op-row" style={{ marginTop: 8 }}>
              <button onClick={() => void load()}>Rerun / refresh</button>
              <button onClick={() => window.location.assign(`/replay-runs?symbol=${selected.symbol}`)}>Run replay with context</button>
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
        <div ref={chartRef} />
      </Card>
    </section>
  );
}
