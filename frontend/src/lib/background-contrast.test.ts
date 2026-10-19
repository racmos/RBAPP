// @vitest-environment node
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { SRC_DIR, declsFor, readCss } from '@/test/css';
import { overlayOver } from '@/test/overlay';
import { BG_OVERLAYS, bgVars } from './background';
import { contrast, parseColor } from './contrast';

const tokens = Object.fromEntries(
  declsFor(readCss(join(SRC_DIR, 'styles', 'tokens.css')), ':root').map((d) => [d.prop, d.value]),
);
const BG0 = parseColor(tokens['--bg-0']);
const GRID = 24;
const VIEWPORTS = [
  { width: 390, height: 844 },
  { width: 1440, height: 900 },
];
const PERCENTS = Array.from({ length: 11 }, (_, i) => i * 10);

const brightnessAt = (p: number) =>
  Number(/brightness\(([\d.]+)\)/.exec(bgVars(p).vars['--bg-image-filter'])?.[1] ?? 1);
const hex = ([r, g, b]: readonly [number, number, number]) => `rgb(${r}, ${g}, ${b})`;

/**
 * Worst case for readability: the map is pure white at the brightest the filter allows, shown
 * at the slider opacity over --bg-0, then covered by the overlay gradients. If text reads on
 * this, it reads over any real image.
 */
function worstCaseBackground(
  p: number,
  point: { x: number; y: number; width: number; height: number },
) {
  const opacity = Number(bgVars(p).vars['--bg-image-opacity']);
  const image = 255 * brightnessAt(p);
  const base = [BG0.r, BG0.g, BG0.b].map(
    (c) => c * (1 - opacity) + image * opacity,
  ) as unknown as readonly [number, number, number];
  return overlayOver(base, BG_OVERLAYS, point);
}

function samples(viewport: { width: number; height: number }) {
  return Array.from({ length: GRID * GRID }, (_, i) => ({
    ...viewport,
    x: ((i % GRID) + 0.5) * (viewport.width / GRID),
    y: (Math.floor(i / GRID) + 0.5) * (viewport.height / GRID),
  }));
}

describe('text contrast over the background (DS-5)', () => {
  it('samples a full grid per viewport', () => {
    expect(samples(VIEWPORTS[0])).toHaveLength(576);
  });

  describe.each(['--text', '--muted'])('%s', (token) => {
    it.each(PERCENTS)('p=%i is at least 4.5:1 at every sample of both viewports', (p) => {
      const worst = Math.min(
        ...VIEWPORTS.flatMap((viewport) =>
          samples(viewport).map((point) =>
            contrast(tokens[token], hex(worstCaseBackground(p, point))),
          ),
        ),
      );
      expect(worst).toBeGreaterThanOrEqual(4.5);
    });
  });

  it('would fail without the overlays (proves the test can fail)', () => {
    const bare = contrast(tokens['--muted'], hex([255 * 0.85, 255 * 0.85, 255 * 0.85]));
    expect(bare).toBeLessThan(4.5);
  });
});
