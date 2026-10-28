import { describe, expect, it } from 'vitest';
import {
  activeFilterCount,
  DEFAULT_PER_PAGE,
  parseCollectionSearch,
  serializeCollectionParams,
  withChange,
} from './params';

const parse = (query: string) => parseCollectionSearch(new URLSearchParams(query));

describe('collection params (F3-g S1)', () => {
  it('has the documented defaults', () => {
    expect(parse('')).toEqual({ sort: 'number', dir: 'asc', page: 1, per_page: 50 });
    expect(DEFAULT_PER_PAGE).toBe(50);
  });

  it('serialises nothing for the defaults', () => {
    expect(serializeCollectionParams(parse(''))).toBe('');
    expect(serializeCollectionParams({ foil: 'any', selling: 'any', has_purchase: 'any' })).toBe(
      '',
    );
  });

  it('round-trips every parameter in a stable order', () => {
    const query =
      'q=ayla&set=OGN&set=SFD&domain=Fury&type=Unit&rarity=Rare&condition=NM&language=English' +
      '&foil=foil&selling=yes&has_purchase=no&sort=value&dir=desc&page=3&per_page=100';
    expect(serializeCollectionParams(parse(query))).toBe(query);
  });

  it('drops invalid values', () => {
    const params = parse(
      'sort=popularity&dir=up&page=0&per_page=10&foil=maybe&selling=x&has_purchase=y&q=%20&set=',
    );
    expect(params).toEqual({ sort: 'number', dir: 'asc', page: 1, per_page: 50 });
    expect(parse('per_page=201').per_page).toBe(50);
    expect(parse('page=2.5').page).toBe(1);
  });

  it('keeps the page only when it is not the first', () => {
    expect(serializeCollectionParams({ page: 1 })).toBe('');
    expect(serializeCollectionParams({ page: 2 })).toBe('page=2');
  });

  it('goes back to page 1 on any change but a page change', () => {
    const current = parse('page=4&sort=name');
    expect(withChange(current, { page: 5 }).page).toBe(5);
    expect(withChange(current, { q: 'x' }).page).toBeUndefined();
    expect(withChange(current, { sort: 'value', page: 2 }).page).toBeUndefined();
  });

  it('counts the active filters, not the search or the sort', () => {
    expect(activeFilterCount(parse('q=a&sort=name'))).toBe(0);
    expect(
      activeFilterCount(
        parse('set=OGN&set=SFD&foil=foil&selling=no&condition=NM&has_purchase=yes'),
      ),
    ).toBe(6);
  });
});
