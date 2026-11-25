import { describe, expect, it } from 'vitest';
import {
  apiQuery,
  cardNameFrom,
  cardRef,
  defaultFoil,
  groupConflicts,
  canonicalSearch,
  matchingTabUrl,
  parseTab,
  parseView,
  scoreText,
  suggestionFoil,
  TABS,
  typeFromCategory,
  viewSearch,
} from './format';

const link = (id: number, setId: string, cardId: string, foil: 'N' | 'S' | null) => ({
  id_product: id,
  product_name: `Product ${id}`,
  product_type: 'single',
  in_latest_load: true,
  set_id: setId,
  card_id: cardId,
  card_name: `Card ${cardId}`,
  foil,
  match_type: 'auto',
  confidence: 0.7,
  low_price: 1,
  price_date: '2026-11-06',
});

describe('matching format helpers (CM-b)', () => {
  it('cardRef joins set and number', () => {
    expect(cardRef('OGN', '001')).toBe('OGN-001');
  });

  it('matchingTabUrl is the one place that builds a tab URL (CM-m, CM-l)', () => {
    expect(matchingTabUrl('prepare', { view: 'missing' })).toBe(
      '/admin/cardmarket/matching?tab=prepare&view=missing',
    );
    expect(matchingTabUrl('prepare', { printings: 'RAD', view: 'missing' })).toBe(
      '/admin/cardmarket/matching?tab=prepare&view=missing&printings=RAD',
    );
    expect(matchingTabUrl('prepare', { view: 'expansions' })).toBe(
      '/admin/cardmarket/matching?tab=prepare&view=expansions',
    );
    expect(matchingTabUrl('prepare')).toBe('/admin/cardmarket/matching?tab=prepare');
    expect(matchingTabUrl('link')).toBe('/admin/cardmarket/matching');
    expect(matchingTabUrl('link', { type: 'single' })).toBe(
      '/admin/cardmarket/matching?type=single',
    );
    expect(matchingTabUrl('link', { view: 'ignored' })).toBe(
      '/admin/cardmarket/matching?view=ignored',
    );
    // the default view of To link and Linked is never written
    expect(matchingTabUrl('link', { view: 'link' })).toBe('/admin/cardmarket/matching');
    expect(matchingTabUrl('linked', { view: 'all', q: '9' })).toBe(
      '/admin/cardmarket/matching?tab=linked&q=9',
    );
    expect(matchingTabUrl('linked', { q: 'a&b' })).toBe(
      '/admin/cardmarket/matching?tab=linked&q=a%26b',
    );
    expect(matchingTabUrl('linked', { view: 'conflicts' })).toBe(
      '/admin/cardmarket/matching?tab=linked&view=conflicts',
    );
    expect(matchingTabUrl('auto')).toBe('/admin/cardmarket/matching?tab=auto');
  });

  it('parseTab knows the four tabs in workflow order and defaults to "link" (CM-l S1)', () => {
    expect(TABS).toEqual(['prepare', 'auto', 'link', 'linked']);
    expect(parseTab(null)).toBe('link');
    expect(parseTab('prepare')).toBe('prepare');
    expect(parseTab('auto')).toBe('auto');
    expect(parseTab('linked')).toBe('linked');
    expect(parseTab('conflicts')).toBe('link');
    expect(parseTab('nope')).toBe('link');
  });

  it('parseView reads the view of a merged tab, its first view by default (CM-l S2-S4)', () => {
    expect(parseView('prepare', null)).toBe('expansions');
    expect(parseView('prepare', 'missing')).toBe('missing');
    expect(parseView('prepare', 'ignored')).toBe('expansions');
    expect(parseView('link', null)).toBe('link');
    expect(parseView('link', 'ignored')).toBe('ignored');
    expect(parseView('linked', null)).toBe('all');
    expect(parseView('linked', 'conflicts')).toBe('conflicts');
    expect(parseView('linked', 'nope')).toBe('all');
  });

  it('canonicalSearch rewrites the old tabs and an unknown one, keeping the filters (CM-l S5)', () => {
    const canonical = (search: string) => canonicalSearch(new URLSearchParams(search))?.toString();
    expect(canonical('tab=conflicts')).toBe('tab=linked&view=conflicts');
    expect(canonical('tab=ignored&q=ahri')).toBe('view=ignored&q=ahri');
    expect(canonical('tab=expansions&show=all')).toBe('tab=prepare&view=expansions&show=all');
    expect(canonical('tab=missing&set=OGNX')).toBe('tab=prepare&view=missing&set=OGNX');
    expect(canonical('printings=RAD&tab=missing')).toBe('tab=prepare&view=missing&printings=RAD');
    // an old tab wins over a view of the URL
    expect(canonical('tab=conflicts&view=all&page=2')).toBe('tab=linked&view=conflicts&page=2');
    // an unknown tab falls back to To link
    expect(canonical('tab=nope&q=x')).toBe('q=x');
    // the new tabs, and no tab, are already canonical
    expect(canonical('')).toBeUndefined();
    expect(canonical('tab=auto')).toBeUndefined();
    expect(canonical('tab=linked&q=9')).toBeUndefined();
    expect(canonical('tab=prepare&view=missing&set=OGNX')).toBeUndefined();
    expect(canonical('view=ignored')).toBeUndefined();
  });

  it('viewSearch keeps q, set and category and drops page and the other filters (CM-l S6)', () => {
    const view = (tab: 'prepare' | 'link' | 'linked', search: string, next: string) =>
      viewSearch(tab, next as never, new URLSearchParams(search)).toString();
    expect(view('link', 'q=ahri&type=single&page=3', 'ignored')).toBe('view=ignored&q=ahri');
    expect(view('link', 'view=ignored&q=ahri&category=Box', 'link')).toBe('q=ahri&category=Box');
    expect(
      view('linked', 'tab=linked&q=9&set=OGN&foil=N&match_type=auto&page=2', 'conflicts'),
    ).toBe('tab=linked&view=conflicts&q=9&set=OGN');
    expect(view('prepare', 'tab=prepare&show=all', 'missing')).toBe('tab=prepare&view=missing');
    expect(view('prepare', 'tab=prepare&view=missing&set=OGNX&printings=RAD', 'expansions')).toBe(
      'tab=prepare&view=expansions&set=OGNX',
    );
  });

  it('defaultFoil follows the matcher slots: runes and rares one slot, commons N then S', () => {
    expect(defaultFoil({ rarity: 'Common', type: 'Unit' }, [])).toBe('N');
    expect(defaultFoil({ rarity: 'Uncommon', type: 'Spell' }, ['N'])).toBe('S');
    expect(defaultFoil({ rarity: 'Common', type: 'Rune' }, [])).toBeNull();
    expect(defaultFoil({ rarity: 'Rare', type: 'Unit' }, [])).toBeNull();
    expect(defaultFoil({ rarity: null, type: null }, [])).toBeNull();
    // both taken: keep N, the API answers who holds it
    expect(defaultFoil({ rarity: 'Common', type: 'Unit' }, ['N', 'S'])).toBe('N');
  });

  it('suggestionFoil takes the first free slot; undefined when none is free', () => {
    expect(suggestionFoil(['N', 'S'])).toBe('N');
    expect(suggestionFoil([null])).toBeNull();
    expect(suggestionFoil(['S'])).toBe('S');
    expect(suggestionFoil([])).toBeUndefined();
  });

  it('scoreText shows two decimals', () => {
    expect(scoreText(1)).toBe('1.00');
    expect(scoreText(0.856)).toBe('0.86');
  });

  it('apiQuery keeps only the keys each endpoint takes, with the per_page default', () => {
    const params = new URLSearchParams(
      'tab=link&q=ahri&type=single&page=2&set=OGN&foil=N&reason=ambiguous&match_type=auto',
    );
    expect(apiQuery('link', params)).toBe('q=ahri&type=single&page=2&per_page=50');
    expect(apiQuery('linked', params)).toBe(
      'q=ahri&set=OGN&foil=N&match_type=auto&page=2&per_page=50',
    );
    expect(apiQuery('conflicts', params)).toBe('conflicts=true&page=2&per_page=50');
    expect(apiQuery('review', params)).toBe('reason=ambiguous&page=2&per_page=50');
    expect(apiQuery('link', new URLSearchParams('type=bogus&page=x'))).toBe('per_page=50');
  });

  it('groupConflicts gathers the links of one slot, in order of first appearance', () => {
    const groups = groupConflicts([
      link(1, 'OGN', '001', 'N'),
      link(2, 'OGN', '001', 'N'),
      link(3, 'OGN', '002', null),
      link(4, 'OGN', '001', 'S'),
      link(5, 'OGN', '002', null),
    ]);
    expect(groups.map((group) => [group.key, group.links.map((one) => one.id_product)])).toEqual([
      ['OGN|001|N', [1, 2]],
      ['OGN|002|', [3, 5]],
      ['OGN|001|S', [4]],
    ]);
    expect(groups[0]).toMatchObject({ set_id: 'OGN', card_id: '001', card_name: 'Card 001' });
  });
});

describe('cardNameFrom (CM-c)', () => {
  it('keeps a plain Cardmarket name as is, trimmed', () => {
    expect(cardNameFrom('  Ahri, Alluring ')).toBe('Ahri, Alluring');
    expect(cardNameFrom('Fury Rune (V.2)')).toBe('Fury Rune (V.2)');
    expect(cardNameFrom('Ahri - Alluring')).toBe('Ahri - Alluring');
  });

  it('drops a trailing set and number only', () => {
    expect(cardNameFrom('Ahri, Alluring (OGN-066)')).toBe('Ahri, Alluring');
    expect(cardNameFrom('Ahri, Alluring [OGN 066a]')).toBe('Ahri, Alluring');
    expect(cardNameFrom('Ahri, Alluring #066')).toBe('Ahri, Alluring');
  });

  it('never leaves an empty name', () => {
    expect(cardNameFrom('(OGN-066)')).toBe('(OGN-066)');
  });
});

describe('typeFromCategory (CM-c)', () => {
  it('guesses only from an unambiguous category', () => {
    expect(typeFromCategory('Riftbound Single')).toBe('');
    expect(typeFromCategory(null)).toBe('');
    expect(typeFromCategory('Riftbound Runes')).toBe('Rune');
    expect(typeFromCategory('Riftbound Battlefield')).toBe('Battlefield');
    expect(typeFromCategory('Riftbound Legend')).toBe('Legend');
    expect(typeFromCategory('Rune and Battlefield Pack')).toBe('');
  });
});
