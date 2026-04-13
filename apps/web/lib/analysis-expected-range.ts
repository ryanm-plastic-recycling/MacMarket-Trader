export type ExpectedRangeView = {
  status: "computed" | "blocked" | "omitted";
  method?: string | null;
  absolute_move?: number | null;
  lower_bound?: number | null;
  upper_bound?: number | null;
  horizon_value?: number | null;
  horizon_unit?: string | null;
  reason?: string | null;
};

export function formatExpectedMoveSummary(range: ExpectedRangeView | null | undefined): string {
  if (!range) return "Expected move preview unavailable for this setup.";
  if (range.status !== "computed") return `Expected move ${range.status}: ${range.reason ?? "reason unavailable"}`;
  const method = range.method ?? "iv_1sigma";
  return `${method} (current preview method) · ±${range.absolute_move ?? "-"} (${range.lower_bound ?? "-"} to ${range.upper_bound ?? "-"}) over ${range.horizon_value ?? "-"} ${range.horizon_unit ?? ""}`.trim();
}
