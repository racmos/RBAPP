import { describe, expect, it } from 'vitest';
import { bookOf } from './editor';
import { pickFilters } from './browserFilters';
import type { DeckEditor } from './useDeckEditor';
import { deckCatalog, emptyContent, rivenContent } from '@/test/fixtures/decks';

/** The part of the editor `pickFilters` reads. */
const editorOf = (withLegend: boolean) =>
  ({
    content: withLegend ? rivenContent : emptyContent,
    book: bookOf(Object.fromEntries(deckCatalog.map((card) => [card.key, card]))),
    identityDomains: withLegend ? ['Calm', 'Chaos'] : [],
  }) as unknown as DeckEditor;

const IDENTITY = { domain: ['Calm', 'Chaos', 'Colorless'], domain_match: 'subset' };

describe('pickFilters: the editor only lists the cards the legend allows (F5-i)', () => {
  it('with a legend, the main deck and the sideboard ask for its domains as a subset', () => {
    const editor = editorOf(true);
    for (const zone of ['main', 'sideboard'] as const) {
      expect(pickFilters(zone, editor)).toEqual({
        type: ['Unit', 'Spell', 'Gear'],
        exclude_supertype: ['Token'],
        ...IDENTITY,
      });
    }
  });

  it('with a legend, the champion keeps its tag and asks for the legend domains too', () => {
    expect(pickFilters('champion', editorOf(true))).toEqual({
      type: ['Unit'],
      supertype: ['Champion'],
      tag: ['Riven'],
      ...IDENTITY,
    });
  });

  it('without a legend, no domain filter is added', () => {
    const editor = editorOf(false);
    for (const zone of ['main', 'sideboard'] as const) {
      expect(pickFilters(zone, editor)).toEqual({
        type: ['Unit', 'Spell', 'Gear'],
        exclude_supertype: ['Token'],
      });
    }
    expect(pickFilters('champion', editor)).toEqual({
      type: ['Unit'],
      supertype: ['Champion'],
      tag: [],
    });
  });

  it('runes, battlefields, legend and workbench are unchanged', () => {
    const editor = editorOf(true);
    expect(pickFilters('runes', editor)).toEqual({ type: ['Rune'], domain: ['Calm', 'Chaos'] });
    expect(pickFilters('battlefields', editor)).toEqual({ type: ['Battlefield'] });
    expect(pickFilters('legend', editor)).toEqual({ type: ['Legend'] });
    expect(pickFilters('workbench', editor)).toEqual({});
  });
});
