import { describe, expect, it } from 'vitest';
import type { DeckCard, DeckContentV2 } from '@/api/types';
import { emptyContent } from '@/test/fixtures/decks';
import { deckStats, ENERGY_TOP, MIGHT_TOP } from './deckStats';
import type { CardBook } from './editor';

let next = 0;
const card = (overrides: Partial<DeckCard> = {}): DeckCard => {
  next += 1;
  const card_id = overrides.card_id ?? `s${next}`;
  return {
    set_id: 'OGN',
    card_id,
    key: `OGN-${card_id}`,
    name: `Card ${card_id}`,
    domains: ['Calm'],
    type: 'Spell',
    supertype: null,
    rarity: 'Common',
    image_src: null,
    image_thumb_src: null,
    is_base: true,
    market: null,
    owned_total: 0,
    tags: [],
    energy: null,
    power: null,
    might: null,
    variants: 1,
    keywords: [],
    ...overrides,
  };
};

const bookOf = (...cards: DeckCard[]): CardBook => Object.fromEntries(cards.map((c) => [c.key, c]));
const line = (c: DeckCard, qty: number) => ({ set: c.set_id, id: c.card_id, qty });
const deck = (parts: Partial<DeckContentV2>): DeckContentV2 => ({ ...emptyContent, ...parts });

describe('deckStats (F5-i step 4)', () => {
  it('an empty deck has zeros, no averages and empty buckets', () => {
    const stats = deckStats(emptyContent, {});
    expect(stats.mainCount).toBe(0);
    expect(stats.avgEnergy).toBeNull();
    expect(stats.avgMight).toBeNull();
    expect(stats.powerCards).toBe(0);
    expect(stats.energyCurve).toHaveLength(ENERGY_TOP + 1);
    expect(stats.energyCurve.every((bucket) => bucket.total === 0)).toBe(true);
    expect(stats.mightHistogram).toHaveLength(MIGHT_TOP + 1);
    expect(stats.mightHistogram.every((bucket) => bucket.count === 0)).toBe(true);
    expect(stats.powerByDomain).toEqual([]);
    expect(stats.keywords).toEqual([]);
  });

  it('counts the main deck copies only, skipping cards the book does not know', () => {
    const a = card({ energy: 1 });
    const side = card({ energy: 5 });
    const bench = card({ energy: 6 });
    const content = deck({
      main: [line(a, 3), { set: 'OGN', id: 'missing', qty: 2 }],
      sideboard: [line(side, 2)],
      workbench: [line(bench, 1)],
    });
    const stats = deckStats(content, bookOf(a, side, bench));
    expect(stats.mainCount).toBe(3);
    expect(stats.energyCurve[1].total).toBe(3);
    expect(stats.energyCurve[5].total).toBe(0);
    expect(stats.energyCurve[6].total).toBe(0);
  });

  it('buckets the energy curve 0..10+ and splits each bar by Unit, Spell, Gear and Champion', () => {
    const unit = card({ type: 'Unit', energy: 2 });
    const spell = card({ type: 'Spell', energy: 2 });
    const gear = card({ type: 'Gear', energy: 0 });
    const champ = card({ type: 'Unit', supertype: 'Champion', energy: 2 });
    const big = card({ type: 'Spell', energy: 10 });
    const huge = card({ type: 'Unit', energy: 14 });
    const free = card({ type: 'Spell', energy: null });
    const content = deck({
      main: [
        line(unit, 3),
        line(spell, 2),
        line(gear, 1),
        line(champ, 1),
        line(big, 1),
        line(huge, 2),
        line(free, 3),
      ],
    });
    const { energyCurve } = deckStats(content, bookOf(unit, spell, gear, champ, big, huge, free));
    expect(energyCurve.map((bucket) => bucket.value)).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
    expect(energyCurve.map((bucket) => bucket.top)).toEqual([...Array(10).fill(false), true]);
    expect(energyCurve[2]).toEqual({
      value: 2,
      top: false,
      total: 6,
      groups: { unit: 3, spell: 2, gear: 0, champion: 1 },
    });
    expect(energyCurve[0].groups).toEqual({ unit: 0, spell: 0, gear: 1, champion: 0 });
    // 10 and above share the last bucket
    expect(energyCurve[10]).toEqual({
      value: 10,
      top: true,
      total: 3,
      groups: { unit: 2, spell: 1, gear: 0, champion: 0 },
    });
    // a card without an energy cost is in no bucket
    expect(energyCurve.reduce((total, bucket) => total + bucket.total, 0)).toBe(10);
  });

  it('averages energy and might over the copies that have the value', () => {
    const a = card({ type: 'Unit', energy: 2, might: 3 });
    const b = card({ type: 'Unit', energy: 5, might: 6 });
    const c = card({ type: 'Spell', energy: null, might: null });
    const content = deck({ main: [line(a, 3), line(b, 1), line(c, 4)] });
    const stats = deckStats(content, bookOf(a, b, c));
    expect(stats.avgEnergy).toBeCloseTo((2 * 3 + 5) / 4);
    expect(stats.avgMight).toBeCloseTo((3 * 3 + 6) / 4);
  });

  it('has no average when no main card has the value', () => {
    const spell = card({ energy: null, might: null });
    const stats = deckStats(deck({ main: [line(spell, 3)] }), bookOf(spell));
    expect(stats.mainCount).toBe(3);
    expect(stats.avgEnergy).toBeNull();
    expect(stats.avgMight).toBeNull();
  });

  it('counts the power cards: copies with a power cost greater than 0', () => {
    const one = card({ power: 1 });
    const two = card({ power: 2 });
    const zero = card({ power: 0 });
    const none = card({ power: null });
    const content = deck({ main: [line(one, 3), line(two, 2), line(zero, 3), line(none, 1)] });
    expect(deckStats(content, bookOf(one, two, zero, none)).powerCards).toBe(5);
  });

  it('counts a multi-domain card fully in each of its domains, colourless apart', () => {
    const calm = card({ domains: ['Calm'], power: 1 });
    const both = card({ domains: ['Calm', 'Chaos'], power: 2 });
    const plain = card({ domains: [], power: null });
    const grey = card({ domains: ['Colorless'], power: 0 });
    const content = deck({
      main: [line(calm, 3), line(both, 2), line(plain, 1), line(grey, 1)],
    });
    const { powerByDomain } = deckStats(content, bookOf(calm, both, plain, grey));
    expect(powerByDomain.map((row) => row.domain)).toEqual(['Calm', 'Chaos', 'Colorless']);
    const [calmRow, chaosRow, greyRow] = powerByDomain;
    expect(calmRow).toMatchObject({ cards: 5, power: 3 + 4, runes: 0 });
    expect(chaosRow).toMatchObject({ cards: 2, power: 4, runes: 0 });
    expect(greyRow).toMatchObject({ cards: 2, power: 0, runes: 0 });
    // shares are of the rows' sums, so each column adds up to 1
    expect(calmRow.cardShare).toBeCloseTo(5 / 9);
    expect(calmRow.powerShare).toBeCloseTo(7 / 11);
    expect(chaosRow.powerShare).toBeCloseTo(4 / 11);
    expect(greyRow.powerShare).toBe(0);
    expect(calmRow.runeShare).toBe(0);
  });

  it('adds the runes of each domain from the runes zone', () => {
    const calm = card({ domains: ['Calm'], power: 1 });
    const calmRune = card({ type: 'Rune', domains: ['Calm'] });
    const chaosRune = card({ type: 'Rune', domains: ['Chaos'] });
    const content = deck({
      main: [line(calm, 3)],
      runes: [line(chaosRune, 7), line(calmRune, 5), { set: 'OGN', id: 'lost', qty: 2 }],
    });
    const { powerByDomain } = deckStats(content, bookOf(calm, calmRune, chaosRune));
    // the game's domain order, whatever the deck's
    expect(powerByDomain.map((row) => row.domain)).toEqual(['Calm', 'Chaos']);
    expect(powerByDomain[0]).toMatchObject({ cards: 3, power: 3, runes: 5 });
    expect(powerByDomain[1]).toMatchObject({ cards: 0, power: 0, runes: 7 });
    expect(powerByDomain[0].runeShare).toBeCloseTo(5 / 12);
    expect(powerByDomain[1].runeShare).toBeCloseTo(7 / 12);
    expect(powerByDomain[1].powerShare).toBe(0);
  });

  it('draws the might histogram 0..12+ from the units only', () => {
    const unit = card({ type: 'Unit', might: 3 });
    const champ = card({ type: 'Unit', supertype: 'Champion', might: 5 });
    const giant = card({ type: 'Unit', might: 15 });
    const gear = card({ type: 'Gear', might: 3 });
    const weak = card({ type: 'Unit', might: null });
    const content = deck({
      main: [line(unit, 3), line(champ, 1), line(giant, 2), line(gear, 2), line(weak, 1)],
    });
    const { mightHistogram } = deckStats(content, bookOf(unit, champ, giant, gear, weak));
    expect(mightHistogram).toHaveLength(13);
    expect(mightHistogram[3]).toEqual({ value: 3, top: false, count: 3 });
    expect(mightHistogram[5].count).toBe(1);
    expect(mightHistogram[12]).toEqual({ value: 12, top: true, count: 2 });
    expect(mightHistogram.reduce((total, bucket) => total + bucket.count, 0)).toBe(6);
  });

  it('counts the keywords by copies, most used first, then by name', () => {
    const a = card({ keywords: ['Hidden', 'Action'] });
    const b = card({ keywords: ['Reaction'] });
    const c = card({ keywords: ['Action', 'Action', 'Equip'] });
    const side = card({ keywords: ['Deflect'] });
    const content = deck({
      main: [line(a, 2), line(b, 3), line(c, 1)],
      sideboard: [line(side, 3)],
    });
    expect(deckStats(content, bookOf(a, b, c, side)).keywords).toEqual([
      { name: 'Action', count: 3 },
      { name: 'Reaction', count: 3 },
      { name: 'Hidden', count: 2 },
      { name: 'Equip', count: 1 },
    ]);
  });
});
