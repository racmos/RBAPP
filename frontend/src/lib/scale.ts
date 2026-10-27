export type Scale = ((value: number) => number) & { invert: (value: number) => number };

/**
 * Linear scale from `domain` to `range`. When the domain is a single value every input is
 * mapped to the middle of the range; the inverse still returns that single value.
 */
export function linearScale(
  domain: readonly [number, number],
  range: readonly [number, number],
): Scale {
  const [d0, d1] = domain;
  const [r0, r1] = range;

  if (d0 === d1) {
    const mid = (r0 + r1) / 2;
    const scale = () => mid;
    scale.invert = () => d0;
    return scale as Scale;
  }

  const slope = (r1 - r0) / (d1 - d0);
  const scale = (value: number) => r0 + slope * (value - d0);
  scale.invert = (value: number) => d0 + (value - r0) / slope;
  return scale as Scale;
}

const NICE_FACTORS = [1, 2, 2.5, 5];

function stepPrecision(step: number): number {
  if (step === 0) return 0;
  const text = step.toString();
  if (text.includes('e-')) return Number(text.split('e-')[1]);
  const decimals = text.split('.')[1];
  return decimals ? decimals.length : 0;
}

function round(value: number, precision: number): number {
  const factor = 10 ** precision;
  return Math.round(value * factor) / factor;
}

/**
 * Round tick values that cover `[min, max]`. The returned array has 2–6 entries and uses
 * steps of the form 1, 2, 2.5 or 5 × 10^n.
 */
export function niceTicks(min: number, max: number, count: number): number[] {
  if (min === max) return [min];

  const span = max - min;
  const rawStep = span / Math.max(1, count);
  const exponent = Math.floor(Math.log10(rawStep));
  const base = 10 ** exponent;
  const mantissa = rawStep / base;

  let bestFactor = NICE_FACTORS[0];
  let bestDistance = Infinity;
  for (const factor of NICE_FACTORS) {
    const distance = Math.abs(factor - mantissa);
    if (distance < bestDistance) {
      bestDistance = distance;
      bestFactor = factor;
    }
  }

  const step = bestFactor * base;
  const start = Math.floor(min / step) * step;
  const end = Math.ceil(max / step) * step;

  const precision = stepPrecision(step);
  const ticks: number[] = [];
  // Guard against infinite loops on unexpected floating point results.
  const maxTicks = Math.max(2, Math.ceil((end - start) / step) + 2);
  for (let i = 0; i <= maxTicks; i++) {
    const value = round(start + i * step, precision);
    if (value > end + step * 1e-9) break;
    if (ticks.length === 0 || value > ticks[ticks.length - 1] + step * 1e-9) {
      ticks.push(value);
    }
  }

  return ticks;
}
