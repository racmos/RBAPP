import { describe, expect, it } from 'vitest';
import type { CardListParams } from '@/api/types';
import {
  NO_FILTERS,
  countFilters,
  mergeFilters,
  pruneFilters,
  scopeOf,
  type BrowserFilters,
} from './browserFilters';

/** The main deck of a Calm/Chaos legend, as `pickFilters` builds it. */
const MAIN: Partial<CardListParams> = {
  type: ['Unit', 'Spell', 'Gear'],
  exclude_supertype: ['Token'],
  domain: ['Calm', 'Chaos', 'Colorless'],
  domain_match: 'subset',
};
const RUNES: Partial<CardListParams> = { type: ['Rune'], domain: ['Calm', 'Chaos'] };
const CHAMPION: Partial<CardListParams> = {
  type: ['Unit'],
  supertype: ['Champion'],
  tag: ['Riven'],
  domain: ['Calm', 'Chaos', 'Colorless'],
  domain_match: 'subset',
};
const set = (patch: Partial<BrowserFilters>): BrowserFilters => ({ ...NO_FILTERS, ...patch });

describe('browser filters (F5-i step 3)', () => {
  it('without filters the zone filters go out unchanged', () => {
    expect(mergeFilters(MAIN, NO_FILTERS)).toEqual(MAIN);
    expect(mergeFilters({}, NO_FILTERS)).toEqual({});
  });

  it('narrows the zone lists and keeps the zone match', () => {
    expect(mergeFilters(MAIN, set({ domain: ['Calm'], type: ['Unit'] }))).toEqual({
      ...MAIN,
      domain: ['Calm'],
      type: ['Unit'],
    });
    expect(mergeFilters(CHAMPION, set({ tag: ['Riven'] })).tag).toEqual(['Riven']);
  });

  it('never widens a zone list: values outside it are ignored', () => {
    expect(mergeFilters(MAIN, set({ domain: ['Fury'], type: ['Rune'] }))).toEqual(MAIN);
    expect(mergeFilters(CHAMPION, set({ tag: ['Yasuo'] })).tag).toEqual(['Riven']);
    expect(mergeFilters(RUNES, set({ domain: ['Calm', 'Fury'] })).domain).toEqual(['Calm']);
  });

  it('sends free lists when the zone sets none', () => {
    expect(
      mergeFilters({ type: ['Legend'] }, set({ domain: ['Fury'], rarity: ['Rare'], set: ['OGN'] })),
    ).toEqual({ type: ['Legend'], domain: ['Fury'], rarity: ['Rare'], set: ['OGN'] });
  });

  it('maps a cost value to min and max, the top value to a minimum only', () => {
    expect(mergeFilters(MAIN, set({ energy: 3, power: 0, might: 2 }))).toMatchObject({
      energy_min: 3,
      energy_max: 3,
      power_min: 0,
      power_max: 0,
      might_min: 2,
      might_max: 2,
    });
    const top = mergeFilters(MAIN, set({ energy: 7, power: 3, might: 7 }));
    expect(top).toMatchObject({ energy_min: 7, power_min: 3, might_min: 7 });
    expect(top).not.toHaveProperty('energy_max');
    expect(top).not.toHaveProperty('power_max');
    expect(top).not.toHaveProperty('might_max');
  });

  it('owned only asks for owned cards', () => {
    expect(mergeFilters(MAIN, set({ owned: true })).owned).toBe('owned');
    expect(mergeFilters(MAIN, NO_FILTERS)).not.toHaveProperty('owned');
  });

  it('a zone offers its own types (none when it takes one), domains, tags and costs', () => {
    expect(scopeOf(MAIN, true)).toEqual({
      types: ['Unit', 'Spell', 'Gear'],
      domains: ['Calm', 'Chaos', 'Colorless'],
      tags: null,
      costs: true,
    });
    expect(scopeOf(CHAMPION, true)).toEqual({
      types: [],
      domains: ['Calm', 'Chaos', 'Colorless'],
      tags: ['Riven'],
      costs: true,
    });
    expect(scopeOf({ type: ['Legend'] }, false)).toEqual({
      types: [],
      domains: null,
      tags: [],
      costs: false,
    });
  });

  it('pruning keeps what applies to a zone and drops the rest', () => {
    const chosen = set({
      domain: ['Calm', 'Colorless'],
      type: ['Unit'],
      tag: ['Yasuo'],
      rarity: ['Rare'],
      set: ['OGN'],
      energy: 2,
      power: 1,
      might: 3,
      owned: true,
    });
    expect(pruneFilters(chosen, scopeOf(MAIN, true))).toEqual(chosen);
    expect(pruneFilters(chosen, scopeOf(RUNES, false))).toEqual(
      set({ domain: ['Calm'], rarity: ['Rare'], set: ['OGN'], owned: true }),
    );
    expect(pruneFilters(chosen, scopeOf(CHAMPION, true)).tag).toEqual([]);
  });

  it('counts each value, each cost and owned only', () => {
    expect(countFilters(NO_FILTERS)).toBe(0);
    expect(
      countFilters(
        set({ domain: ['Calm', 'Chaos'], type: ['Unit'], energy: 0, might: 7, owned: true }),
      ),
    ).toBe(6);
  });
});
