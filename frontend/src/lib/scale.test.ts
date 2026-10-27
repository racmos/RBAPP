import { describe, expect, it } from 'vitest';
import { linearScale, niceTicks } from './scale';

describe('linearScale (F2-g S2)', () => {
  it('maps a domain to a range', () => {
    const s = linearScale([0, 10], [0, 100]);
    expect(s(0)).toBe(0);
    expect(s(5)).toBe(50);
    expect(s(10)).toBe(100);
  });

  it('supports inverted ranges', () => {
    const s = linearScale([0, 10], [100, 0]);
    expect(s(0)).toBe(100);
    expect(s(10)).toBe(0);
    expect(s(5)).toBe(50);
  });

  it('exposes an inverse', () => {
    const s = linearScale([0, 10], [0, 100]);
    expect(s.invert(0)).toBe(0);
    expect(s.invert(50)).toBe(5);
    expect(s.invert(100)).toBe(10);
  });

  it('maps every value to the middle when the domain is flat', () => {
    const s = linearScale([5, 5], [0, 100]);
    expect(s(0)).toBe(50);
    expect(s(5)).toBe(50);
    expect(s(10)).toBe(50);
    expect(s.invert(50)).toBe(5);
  });
});

describe('niceTicks (F2-g S2)', () => {
  it('returns the spec example for 0.83 .. 1.27', () => {
    expect(niceTicks(0.83, 1.27, 4)).toEqual([0.8, 0.9, 1, 1.1, 1.2, 1.3]);
  });

  it('returns a single tick when min equals max', () => {
    expect(niceTicks(5, 5, 4)).toEqual([5]);
  });

  it('covers the requested range', () => {
    const ticks = niceTicks(0.83, 1.27, 4);
    expect(ticks[0]).toBeLessThanOrEqual(0.83);
    expect(ticks[ticks.length - 1]).toBeGreaterThanOrEqual(1.27);
  });

  it('produces 2 to 6 ticks for common ranges', () => {
    expect(niceTicks(0, 10, 5).length).toBeGreaterThanOrEqual(2);
    expect(niceTicks(0, 10, 5).length).toBeLessThanOrEqual(6);
  });

  it('uses round step values', () => {
    const ticks = niceTicks(0, 100, 5);
    expect(ticks).toEqual([0, 20, 40, 60, 80, 100]);
  });
});
