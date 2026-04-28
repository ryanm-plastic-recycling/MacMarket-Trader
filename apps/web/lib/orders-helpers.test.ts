import { describe, expect, it } from "vitest";

import { formatHoldDuration, formatRelativeTime, pnlColor } from "./orders-helpers";

describe("pnlColor", () => {
  it("returns green for positive PnL", () => {
    expect(pnlColor(125.5)).toBe("#21c06e");
  });

  it("returns red for negative PnL", () => {
    expect(pnlColor(-42)).toBe("#e07a7a");
  });

  it("returns inherit for zero", () => {
    expect(pnlColor(0)).toBe("inherit");
  });
});

describe("formatHoldDuration", () => {
  it("returns em-dash for null/undefined/negative input", () => {
    expect(formatHoldDuration(null)).toBe("—");
    expect(formatHoldDuration(undefined)).toBe("—");
    expect(formatHoldDuration(-5)).toBe("—");
  });

  it("renders sub-minute as <1m", () => {
    expect(formatHoldDuration(0)).toBe("<1m");
    expect(formatHoldDuration(45)).toBe("<1m");
  });

  it("renders sub-hour minutes only", () => {
    expect(formatHoldDuration(60)).toBe("1m");
    expect(formatHoldDuration(45 * 60)).toBe("45m");
  });

  it("renders sub-day with hours and minutes", () => {
    expect(formatHoldDuration(2 * 3600 + 14 * 60)).toBe("2h 14m");
    expect(formatHoldDuration(3 * 3600)).toBe("3h");
  });

  it("renders multi-day with days and hours", () => {
    expect(formatHoldDuration(3 * 86400 + 5 * 3600)).toBe("3d 5h");
    expect(formatHoldDuration(7 * 86400)).toBe("7d");
  });
});

describe("formatRelativeTime", () => {
  const NOW = Date.parse("2026-04-28T12:00:00Z");

  it("returns em-dash for null/undefined", () => {
    expect(formatRelativeTime(null, NOW)).toBe("—");
    expect(formatRelativeTime(undefined, NOW)).toBe("—");
  });

  it("returns 'just now' for sub-minute deltas", () => {
    expect(formatRelativeTime("2026-04-28T11:59:30Z", NOW)).toBe("just now");
  });

  it("renders minutes-ago for sub-hour deltas", () => {
    expect(formatRelativeTime("2026-04-28T11:55:00Z", NOW)).toBe("5m ago");
  });

  it("renders hours-ago for sub-day deltas", () => {
    expect(formatRelativeTime("2026-04-28T09:00:00Z", NOW)).toBe("3h ago");
  });

  it("renders days-ago for multi-day deltas", () => {
    expect(formatRelativeTime("2026-04-25T12:00:00Z", NOW)).toBe("3d ago");
  });

  it("returns the original ISO for future-dated input", () => {
    expect(formatRelativeTime("2026-04-29T12:00:00Z", NOW)).toBe("2026-04-29T12:00:00Z");
  });

  it("returns the input string when not a parseable date", () => {
    expect(formatRelativeTime("not-a-date", NOW)).toBe("not-a-date");
  });
});
