/**
 * App background (DS-5): the Summoner's Rift map on a fixed layer, slightly blurred and
 * darkened so text on top stays readable. It is never brightened or oversaturated; the
 * slider only changes how much of it shows. Constants are tuned visually; the tests assert
 * the invariants plus a golden table (background.test.ts) and the contrast of text over the
 * worst case (background-contrast.test.ts).
 */
export const BG_BLUR_PX = 3;

/** Percent used when a value is missing or not finite (the product default, DS-5). */
export const BG_DEFAULT_PERCENT = 100;

export type BackgroundVars = {
  bg: 'on' | 'off';
  vars: { '--bg-image-opacity': string; '--bg-image-filter': string };
};

/** CSS variables for the image layer at `input` percent (clamped to 0..100 and rounded). */
export function bgVars(input: number): BackgroundVars {
  const p = Math.min(
    100,
    Math.max(0, Math.round(Number.isFinite(input) ? input : BG_DEFAULT_PERCENT)),
  );
  const t = p / 100;
  return {
    bg: p === 0 ? 'off' : 'on',
    vars: {
      '--bg-image-opacity': String(t),
      '--bg-image-filter': `blur(${BG_BLUR_PX}px) brightness(${(0.7 + 0.15 * t).toFixed(3)}) saturate(${(0.8 + 0.15 * t).toFixed(3)})`,
    },
  };
}

export type Rgba = readonly [r: number, g: number, b: number, a: number];
export type Stop = { color: Rgba; at: number };
export type Overlay =
  | {
      kind: 'radial';
      /** Radii as fractions of the layer width and height. */
      radius: readonly [number, number];
      /** Centre as fractions of the layer width and height. */
      center: readonly [number, number];
      stops: readonly Stop[];
    }
  | { kind: 'linear'; stops: readonly Stop[] }; // 180deg, top to bottom

/**
 * Overlay gradients of the handoff (riftbound.css `.app-bg::after`), first entry on top.
 * They are data so the contrast test and the CSS share one source.
 */
export const BG_OVERLAYS: readonly Overlay[] = [
  {
    kind: 'radial',
    radius: [1.2, 0.9],
    center: [0.5, -0.1],
    stops: [
      { color: [46, 198, 230, 0.1], at: 0 },
      { color: [46, 198, 230, 0], at: 0.55 },
    ],
  },
  {
    kind: 'radial',
    radius: [1.4, 1.2],
    center: [0.5, 1.1],
    stops: [
      { color: [6, 28, 36, 0.85], at: 0 },
      { color: [6, 28, 36, 0.45], at: 0.4 },
      { color: [6, 28, 36, 0.92], at: 1 },
    ],
  },
  {
    kind: 'linear',
    stops: [
      { color: [6, 30, 40, 0.55], at: 0 },
      { color: [5, 24, 32, 0.78], at: 1 },
    ],
  },
];

const pct = (fraction: number) => `${+(fraction * 100).toFixed(2)}%`;
const stopCss = ({ color: [r, g, b, a], at }: Stop) => `rgba(${r}, ${g}, ${b}, ${a}) ${pct(at)}`;

export function overlayCss(overlay: Overlay): string {
  const stops = overlay.stops.map(stopCss).join(', ');
  return overlay.kind === 'linear'
    ? `linear-gradient(180deg, ${stops})`
    : `radial-gradient(${pct(overlay.radius[0])} ${pct(overlay.radius[1])} at ${pct(overlay.center[0])} ${pct(overlay.center[1])}, ${stops})`;
}

/** Value of `--bg-overlay`: all overlay gradients as one CSS `background` image list. */
export const BG_OVERLAY_CSS = BG_OVERLAYS.map(overlayCss).join(', ');

/** Apply the background state to `<html>` (D18/D19): data-bg plus the three variables. */
export function applyBackground(root: HTMLElement, percent: number): void {
  const { bg, vars } = bgVars(percent);
  root.dataset.bg = bg;
  root.style.setProperty('--bg-overlay', BG_OVERLAY_CSS);
  for (const [name, value] of Object.entries(vars)) root.style.setProperty(name, value);
}
