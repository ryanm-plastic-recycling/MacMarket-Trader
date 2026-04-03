export type HacoChartRequest = {
  symbol: string;
  timeframe: string;
  include_heikin_ashi: boolean;
  bars?: Array<{
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
  candles: Array<{ index: number; time: string; open: number; high: number; low: number; close: number; volume: number }>;
  heikin_ashi_candles: Array<{ index: number; time: string; open: number; high: number; low: number; close: number; volume: number }>;
  markers: Array<{ index: number; time: string; marker_type: string; direction: string; price: number; text: string }>;
  haco_strip: Array<{ index: number; time: string; value: number; state: string }>;
  hacolt_strip: Array<{ index: number; time: string; value: number; direction: string }>;
  explanation: {
    current_haco_state: string;
    latest_flip: string;
    latest_flip_bars_ago: number | null;
    current_hacolt_direction: string;
  };
  data_source: string;
  fallback_mode: boolean;
};

export async function fetchHacoChart(request: HacoChartRequest): Promise<HacoChartPayload> {
  const response = await fetch("/api/charts/haco", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
    cache: "no-store",
    credentials: "include",
  });
  if (!response.ok) {
    if (response.status === 425) {
      throw new Error("AUTH_NOT_READY");
    }
    throw new Error(`Failed to load HACO chart: ${response.status}`);
  }
  return (await response.json()) as HacoChartPayload;
}
