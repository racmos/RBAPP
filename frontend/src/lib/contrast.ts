/** WCAG 2.2 contrast helpers (DS-7). Pure; used by the token and background tests. */
export type Rgba = { r: number; g: number; b: number; a: number };

const HEX = /^#([\da-f]{3}|[\da-f]{6}|[\da-f]{8})$/i;
const RGB = /^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)$/i;

export function parseColor(input: string): Rgba {
  const text = input.trim();
  const hex = HEX.exec(text);
  if (hex) {
    const digits =
      hex[1].length === 3 ? [...hex[1]].map((digit) => digit + digit).join('') : hex[1];
    const byte = (index: number) => parseInt(digits.slice(index * 2, index * 2 + 2), 16);
    return { r: byte(0), g: byte(1), b: byte(2), a: digits.length === 8 ? byte(3) / 255 : 1 };
  }
  const rgb = RGB.exec(text);
  if (rgb) {
    return {
      r: Number(rgb[1]),
      g: Number(rgb[2]),
      b: Number(rgb[3]),
      a: rgb[4] ? Number(rgb[4]) : 1,
    };
  }
  throw new Error(`Cannot parse the colour "${input}"`);
}

/** `color` painted over an opaque `base`. */
export function composite(color: Rgba, base: Rgba): Rgba {
  const mix = (top: number, bottom: number) => top * color.a + bottom * (1 - color.a);
  return { r: mix(color.r, base.r), g: mix(color.g, base.g), b: mix(color.b, base.b), a: 1 };
}

const linear = (channel: number) => {
  const value = channel / 255;
  return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
};

export const relativeLuminance = ({ r, g, b }: Rgba): number =>
  0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b);

/** Contrast ratio of text `fg` on `bg`; translucent colours are composed over `base`. */
export function contrast(fg: string, bg: string, base = '#000000'): number {
  const background = composite(parseColor(bg), parseColor(base));
  const text = composite(parseColor(fg), background);
  const [lighter, darker] = [relativeLuminance(text), relativeLuminance(background)].sort(
    (a, b) => b - a,
  );
  return (lighter + 0.05) / (darker + 0.05);
}
