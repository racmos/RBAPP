import { describe, expect, it } from 'vitest';
import {
  BG_BLUR_PX,
  BG_OVERLAYS,
  BG_OVERLAY_CSS,
  applyBackground,
  bgVars,
  overlayCss,
} from './background';

const PERCENTS = Array.from({ length: 101 }, (_, p) => p);

/** Numeric argument of a CSS filter function, e.g. brightness(0.85) -> 0.85. */
function filterArg(filter: string, name: string): number | undefined {
  const match = new RegExp(`${name}\\(([\\d.]+)(px)?\\)`).exec(filter);
  return match ? Number(match[1]) : undefined;
}

describe('bgVars invariants (DS-5), every integer 0..100', () => {
  it.each(PERCENTS)(
    'p=%i: blurred, never brightened, never oversaturated, opacity in range',
    (p) => {
      const { vars } = bgVars(p);
      const filter = vars['--bg-image-filter'];
      expect(filterArg(filter, 'blur')).toBeGreaterThan(0);
      expect(filterArg(filter, 'brightness')).toBeLessThanOrEqual(1);
      expect(filterArg(filter, 'brightness')).toBeGreaterThan(0);
      expect(filterArg(filter, 'saturate')).toBeLessThanOrEqual(1);
      expect(filterArg(filter, 'saturate')).toBeGreaterThan(0);
      expect(filter).not.toContain('contrast(');
      const opacity = Number(vars['--bg-image-opacity']);
      expect(opacity).toBeGreaterThanOrEqual(0);
      expect(opacity).toBeLessThanOrEqual(1);
    },
  );

  it('never decreases the opacity as the value grows', () => {
    const opacities = PERCENTS.map((p) => Number(bgVars(p).vars['--bg-image-opacity']));
    for (let p = 1; p <= 100; p++) {
      expect(opacities[p]).toBeGreaterThanOrEqual(opacities[p - 1]);
    }
    expect(opacities[100]).toBeGreaterThan(opacities[0]);
  });

  it('hides the image only at 0', () => {
    expect(bgVars(0).bg).toBe('off');
    expect(PERCENTS.slice(1).every((p) => bgVars(p).bg === 'on')).toBe(true);
  });

  it('has opacity 0 at 0 and 1 at 100, still blurred at 100', () => {
    expect(bgVars(0).vars['--bg-image-opacity']).toBe('0');
    expect(bgVars(100).vars['--bg-image-opacity']).toBe('1');
    expect(filterArg(bgVars(100).vars['--bg-image-filter'], 'blur')).toBe(BG_BLUR_PX);
  });

  it('keeps the blur in the slight range tuned for readability (2 to 4 px)', () => {
    expect(BG_BLUR_PX).toBeGreaterThanOrEqual(2);
    expect(BG_BLUR_PX).toBeLessThanOrEqual(4);
  });
});

describe('bgVars input handling', () => {
  it('clamps and rounds', () => {
    expect(bgVars(-10)).toEqual(bgVars(0));
    expect(bgVars(250)).toEqual(bgVars(100));
    expect(bgVars(49.6)).toEqual(bgVars(50));
    expect(bgVars(49.4)).toEqual(bgVars(49));
  });

  it('treats NaN and infinities as the default 100', () => {
    expect(bgVars(Number.NaN)).toEqual(bgVars(100));
    expect(bgVars(Number.POSITIVE_INFINITY)).toEqual(bgVars(100));
  });
});

// Golden table: deliberately updated whenever the constants are tuned (task 1.50).
describe('bgVars golden table', () => {
  it.each([
    [0, 'off', '0', 'blur(3px) brightness(0.700) saturate(0.800)'],
    [50, 'on', '0.5', 'blur(3px) brightness(0.775) saturate(0.875)'],
    [100, 'on', '1', 'blur(3px) brightness(0.850) saturate(0.950)'],
  ])('p=%i', (p, bg, opacity, filter) => {
    expect(bgVars(p)).toEqual({
      bg,
      vars: { '--bg-image-opacity': opacity, '--bg-image-filter': filter },
    });
  });
});

describe('overlay gradients', () => {
  it('serialises a radial and a linear overlay to CSS', () => {
    expect(overlayCss(BG_OVERLAYS[0])).toBe(
      'radial-gradient(120% 90% at 50% -10%, rgba(46, 198, 230, 0.1) 0%, rgba(46, 198, 230, 0) 55%)',
    );
    expect(overlayCss(BG_OVERLAYS[2])).toBe(
      'linear-gradient(180deg, rgba(6, 30, 40, 0.55) 0%, rgba(5, 24, 32, 0.78) 100%)',
    );
  });

  it('joins every overlay, first on top, into the --bg-overlay value', () => {
    expect(BG_OVERLAY_CSS.split(/\), (?=[a-z-]+gradient)/)).toHaveLength(BG_OVERLAYS.length);
    expect(BG_OVERLAY_CSS.startsWith(overlayCss(BG_OVERLAYS[0]))).toBe(true);
    expect(BG_OVERLAY_CSS.endsWith(overlayCss(BG_OVERLAYS[BG_OVERLAYS.length - 1]))).toBe(true);
  });
});

describe('applyBackground', () => {
  it('writes data-bg and the three variables on the element', () => {
    const root = document.createElement('html');
    applyBackground(root, 50);
    expect(root.dataset.bg).toBe('on');
    expect(root.style.getPropertyValue('--bg-image-opacity')).toBe('0.5');
    expect(root.style.getPropertyValue('--bg-image-filter')).toBe(
      bgVars(50).vars['--bg-image-filter'],
    );
    expect(root.style.getPropertyValue('--bg-overlay')).toBe(BG_OVERLAY_CSS);
  });

  it('switches the image off at 0 and back on', () => {
    const root = document.createElement('html');
    applyBackground(root, 0);
    expect(root.dataset.bg).toBe('off');
    expect(root.style.getPropertyValue('--bg-image-opacity')).toBe('0');
    applyBackground(root, 100);
    expect(root.dataset.bg).toBe('on');
    expect(root.style.getPropertyValue('--bg-image-opacity')).toBe('1');
  });
});
