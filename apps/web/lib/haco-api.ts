export type HacoChartRequest = {
  symbol: string;
  timeframe: string;
  include_heikin_ashi: boolean;
  bars: Array<{
    date: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
    rel_volume?: number;
  }>;
};

export type HacoChartPayload = {
  symbol: string;
  timeframe: string;
  candles: Array<{ time: string; open: number; high: number; low: number; close: number; volume: number }>;
  heikin_ashi_candles: Array<{ time: string; open: number; high: number; low: number; close: number; volume: number }>;
  markers: Array<{ time: string; marker_type: string; direction: string; price: number; text: string }>;
  haco_strip: Array<{ time: string; value: number; state: string }>;
  hacolt_strip: Array<{ time: string; value: number; direction: string }>;
  explanation: {
    current_haco_state: string;
    latest_flip: string;
    latest_flip_bars_ago: number | null;
    current_hacolt_direction: string;
  };
};

export async function fetchHacoChart(request: HacoChartRequest): Promise<HacoChartPayload> {
  const response = await fetch("/api/charts/haco", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Failed to load HACO chart: ${response.status}`);
  }
  return (await response.json()) as HacoChartPayload;
}
