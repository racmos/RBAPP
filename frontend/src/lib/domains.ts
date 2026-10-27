/**
 * Domain and rarity colours shared by CSS tokens and TS code (DS-2).
 * The values are mirrored in `src/styles/tokens.css` and are kept equal by a test.
 */
export const DOMAIN_COLORS = {
  Fury: '#e7504a',
  Calm: '#33b27b',
  Mind: '#4f86e6',
  Body: '#e08a36',
  Chaos: '#a45cc8',
  Order: '#d8b84a',
  Colorless: '#8aa3ad',
} as const;

export const RARITY_COLORS = {
  Common: '#9fb6bf',
  Uncommon: '#4fb6a5',
  Rare: '#4f86e6',
  Epic: '#a45cc8',
  Showcase: '#e0a93a',
} as const;

export function domainColor(domain: string): string {
  return DOMAIN_COLORS[domain as keyof typeof DOMAIN_COLORS] ?? DOMAIN_COLORS.Colorless;
}

export function rarityColor(rarity: string): string {
  return RARITY_COLORS[rarity as keyof typeof RARITY_COLORS] ?? RARITY_COLORS.Common;
}
