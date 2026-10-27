import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { contrast } from './contrast';
import { DOMAIN_COLORS, domainColor, RARITY_COLORS, rarityColor } from './domains';

function cssTokenValues(): Record<string, string> {
  const css = readFileSync(resolve(import.meta.dirname, '../styles/tokens.css'), 'utf8');
  const values: Record<string, string> = {};
  for (const match of css.matchAll(
    /--(domain-[a-z]+|rarity-[a-z]+|green-text):\s*(#[0-9a-f]{6})/gi,
  )) {
    values[match[1]] = match[2].toLowerCase();
  }
  return values;
}

describe('domain and rarity colours', () => {
  it('matches the CSS token values exactly', () => {
    const css = cssTokenValues();
    for (const [domain, hex] of Object.entries(DOMAIN_COLORS)) {
      expect(hex.toLowerCase(), `domain ${domain}`).toBe(css[`domain-${domain.toLowerCase()}`]);
    }
    for (const [rarity, hex] of Object.entries(RARITY_COLORS)) {
      expect(hex.toLowerCase(), `rarity ${rarity}`).toBe(css[`rarity-${rarity.toLowerCase()}`]);
    }
    expect(css['green-text']).toBe('#5fe0a8');
  });

  it('falls back to colorless for unknown domains', () => {
    expect(domainColor('Void')).toBe(DOMAIN_COLORS.Colorless);
  });

  it('falls back to common for unknown rarities', () => {
    expect(rarityColor('Promo')).toBe(RARITY_COLORS.Common);
  });

  it('has at least 3:1 glyph contrast on every domain pip', () => {
    const inks = ['#ffffff', '#06222c'];
    for (const [domain, hex] of Object.entries(DOMAIN_COLORS)) {
      const best = Math.max(...inks.map((ink) => contrast(ink, hex)));
      expect(best, `glyph contrast on ${domain}`).toBeGreaterThanOrEqual(3);
    }
  });
});
