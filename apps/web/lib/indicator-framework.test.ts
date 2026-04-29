import { describe, expect, it } from 'vitest';

import { calculateIndicatorSnapshot, normalizeSelection } from '@/lib/indicator-framework';

describe('indicator framework', () => {
  it('normalizes unknown indicators to defaults', () => {
    const selected = normalizeSelection(['nope', 'ema20']);
    expect(selected.includes('ema20')).toBe(true);
  });

  it('produces deterministic snapshot shape', () => {
    const bars = Array.from({ length: 30 }).map((_, idx) => ({
      time: `2026-01-${String(idx + 1).padStart(2, '0')}`,
      open: 100 + idx,
      high: 101 + idx,
      low: 99 + idx,
      close: 100.5 + idx,
      volume: 1_000_000,
    }));
    const snapshot = calculateIndicatorSnapshot(bars);
    expect(snapshot).toHaveProperty('sma20');
    expect(snapshot).toHaveProperty('sma50');
    expect(snapshot).toHaveProperty('ema20');
    expect(snapshot).toHaveProperty('relativeVolume');
  });
});
