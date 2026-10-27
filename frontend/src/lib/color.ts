const HEX6 = /^#[0-9a-f]{6}$/i;

/**
 * Lighten or darken a 6-digit hex colour by `amount` percent.
 * Each channel is shifted by `amount * 2.55`, clamped to 0..255 and rounded.
 */
export function shadeHex(hex: string, amount: number): string {
  if (!HEX6.test(hex)) throw new Error('Expected #rrggbb');
  const shift = Math.round(amount * 2.55);
  const channel = (offset: number) => {
    const value = parseInt(hex.slice(1 + offset * 2, 3 + offset * 2), 16);
    return Math.min(255, Math.max(0, value + shift));
  };
  const toHex = (value: number) => value.toString(16).padStart(2, '0');
  return `#${toHex(channel(0))}${toHex(channel(1))}${toHex(channel(2))}`;
}
