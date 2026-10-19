import type { Overlay, Rgba } from '@/lib/background';

/** Samples the CSS background overlays analytically (no browser), for contrast tests. */
type Pixel = readonly [r: number, g: number, b: number];

/** Colour of a gradient at `t` along its stops, interpolated premultiplied like CSS. */
function colorAt(stops: Overlay['stops'], t: number): Rgba {
  const first = stops[0];
  const last = stops[stops.length - 1];
  if (t <= first.at) return first.color;
  if (t >= last.at) return last.color;
  const index = stops.findIndex((stop) => stop.at >= t);
  const [from, to] = [stops[index - 1], stops[index]];
  const k = (t - from.at) / (to.at - from.at);
  const alpha = from.color[3] + (to.color[3] - from.color[3]) * k;
  if (alpha === 0) return [0, 0, 0, 0];
  const channel = (i: 0 | 1 | 2) =>
    (from.color[i] * from.color[3] * (1 - k) + to.color[i] * to.color[3] * k) / alpha;
  return [channel(0), channel(1), channel(2), alpha];
}

function gradientColor(
  overlay: Overlay,
  x: number,
  y: number,
  width: number,
  height: number,
): Rgba {
  if (overlay.kind === 'linear') return colorAt(overlay.stops, y / height);
  const dx = (x - overlay.center[0] * width) / (overlay.radius[0] * width);
  const dy = (y - overlay.center[1] * height) / (overlay.radius[1] * height);
  return colorAt(overlay.stops, Math.hypot(dx, dy));
}

/** `base` with every overlay painted over it (the first overlay is the topmost). */
export function overlayOver(
  base: Pixel,
  overlays: readonly Overlay[],
  point: { x: number; y: number; width: number; height: number },
): Pixel {
  return [...overlays].reverse().reduce<Pixel>((below, overlay) => {
    const [r, g, b, a] = gradientColor(overlay, point.x, point.y, point.width, point.height);
    return [r * a + below[0] * (1 - a), g * a + below[1] * (1 - a), b * a + below[2] * (1 - a)];
  }, base);
}
