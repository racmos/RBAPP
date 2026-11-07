import { describe, expect, it } from 'vitest';
import {
  apiQuery,
  cardNameFrom,
  cardRef,
  defaultFoil,
  groupConflicts,
  parseTab,
  scoreText,
  suggestionFoil,
  typeFromCategory,
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

  it('parseTab knows the six tabs and defaults to "link"', () => {
    expect(parseTab(null)).toBe('link');
    expect(parseTab('linked')).toBe('linked');
    expect(parseTab('conflicts')).toBe('conflicts');
    expect(parseTab('ignored')).toBe('ignored');
    expect(parseTab('auto')).toBe('auto');
    expect(parseTab('expansions')).toBe('expansions');
    expect(parseTab('nope')).toBe('link');
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
