import { describe, expect, it } from 'vitest';
import { contrast } from '@/lib/contrast';
import { DOMAIN_COLORS, RARITY_COLORS } from '@/lib/domains';

describe('tokens', () => {
  it('has enough contrast for --green-text on --panel', () => {
    expect(contrast('#5fe0a8', 'rgba(13, 58, 73, 0.66)', '#06222c')).toBeGreaterThanOrEqual(4.5);
  });

  it('exposes a colour for every known domain', () => {
    const domains = ['Fury', 'Calm', 'Mind', 'Body', 'Chaos', 'Order', 'Colorless'];
    for (const domain of domains) {
      expect(DOMAIN_COLORS[domain as keyof typeof DOMAIN_COLORS]).toMatch(/^#[0-9a-f]{6}$/i);
    }
  });

  it('exposes a colour for every known rarity', () => {
    const rarities = ['Common', 'Uncommon', 'Rare', 'Epic', 'Showcase'];
    for (const rarity of rarities) {
      expect(RARITY_COLORS[rarity as keyof typeof RARITY_COLORS]).toMatch(/^#[0-9a-f]{6}$/i);
    }
  });
});
