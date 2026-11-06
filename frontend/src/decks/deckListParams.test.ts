import { describe, expect, it } from 'vitest';
import type { DeckListItem } from '@/api/types';
import { deckList } from '@/test/fixtures/decks';
import {
  DEFAULT_DECK_LIST_PARAMS,
  hasDeckFilters,
  parseDeckListParams,
  selectDecks,
  serializeDeckListParams,
} from './deckListParams';

const names = (items: DeckListItem[]) => items.map((deck) => deck.name);
const parse = (search: string) => parseDeckListParams(new URLSearchParams(search));

describe('deck list params (F5 deck list grid)', () => {
  it('reads q, mode, legal and sort; unknown values fall back to the defaults', () => {
    expect(parse('')).toEqual(DEFAULT_DECK_LIST_PARAMS);
    // the search is kept as typed (the input owns it); filtering trims it
    expect(parse('q=%20riven%20&mode=2v2&legal=no&sort=name')).toEqual({
      q: ' riven ',
      mode: '2v2',
      legal: 'no',
      sort: 'name',
    });
    expect(parse('mode=3v3&legal=maybe&sort=random')).toEqual(DEFAULT_DECK_LIST_PARAMS);
  });

  it('writes only what differs from the defaults and keeps other params', () => {
    expect(serializeDeckListParams(DEFAULT_DECK_LIST_PARAMS)).toBe('');
    expect(serializeDeckListParams({ ...DEFAULT_DECK_LIST_PARAMS, q: '  ' })).toBe('');
    expect(
      serializeDeckListParams(
        { q: 'cup', mode: '1v1', legal: 'yes', sort: 'value' },
        new URLSearchParams('other=1&q=old'),
      ),
    ).toBe('other=1&q=cup&mode=1v1&legal=yes&sort=value');
  });

  it('knows when a filter is on (the sort is not a filter)', () => {
    expect(hasDeckFilters(DEFAULT_DECK_LIST_PARAMS)).toBe(false);
    expect(hasDeckFilters({ ...DEFAULT_DECK_LIST_PARAMS, sort: 'name' })).toBe(false);
    expect(hasDeckFilters({ ...DEFAULT_DECK_LIST_PARAMS, q: 'x' })).toBe(true);
    expect(hasDeckFilters({ ...DEFAULT_DECK_LIST_PARAMS, q: ' ' })).toBe(false);
    expect(hasDeckFilters({ ...DEFAULT_DECK_LIST_PARAMS, mode: '2v2' })).toBe(true);
    expect(hasDeckFilters({ ...DEFAULT_DECK_LIST_PARAMS, legal: 'no' })).toBe(true);
  });

  it('searches the name without case or accents', () => {
    const sel = (q: string) => names(selectDecks(deckList, { ...DEFAULT_DECK_LIST_PARAMS, q }));
    expect(sel(' RIVEN ')).toEqual(['Riven, The Exile', 'Riven tournament']);
    expect(sel('ídéas')).toEqual(['Draft ideas']);
    expect(sel('nothing')).toEqual([]);
  });

  it('filters by mode and by legality in the deck mode', () => {
    const sel = (patch: Partial<typeof DEFAULT_DECK_LIST_PARAMS>) =>
      names(selectDecks(deckList, { ...DEFAULT_DECK_LIST_PARAMS, ...patch }));
    expect(sel({ mode: '2v2' })).toEqual(['Riven tournament']);
    expect(sel({ mode: '1v1' })).toEqual(['Riven, The Exile', 'Draft ideas']);
    expect(sel({ legal: 'yes' })).toEqual(['Riven tournament']);
    expect(sel({ legal: 'no' })).toEqual(['Riven, The Exile', 'Draft ideas']);
    // legal in 2v2 only counts for a 2v2 deck
    const twoVsTwoOnly = { ...deckList[0], legal: { '1v1': false, '2v2': true } };
    expect(
      names(selectDecks([twoVsTwoOnly], { ...DEFAULT_DECK_LIST_PARAMS, legal: 'yes' })),
    ).toEqual([]);
  });

  it('sorts by updated (newest or oldest), name and value (highest first)', () => {
    const sel = (sort: (typeof DEFAULT_DECK_LIST_PARAMS)['sort']) =>
      names(selectDecks(deckList, { ...DEFAULT_DECK_LIST_PARAMS, sort }));
    expect(sel('updated')).toEqual(['Riven, The Exile', 'Riven tournament', 'Draft ideas']);
    expect(sel('updated_asc')).toEqual(['Draft ideas', 'Riven tournament', 'Riven, The Exile']);
    expect(sel('name')).toEqual(['Draft ideas', 'Riven tournament', 'Riven, The Exile']);
    const byValue = [...deckList].sort((a, b) => b.value - a.value).map((deck) => deck.name);
    expect(sel('value')).toEqual(byValue);
  });

  it('never changes the list it is given', () => {
    const before = names(deckList);
    selectDecks(deckList, { ...DEFAULT_DECK_LIST_PARAMS, sort: 'name' });
    expect(names(deckList)).toEqual(before);
  });
});
