import { describe, expect, it } from 'vitest';
import {
  DEFAULT_PER_PAGE,
  activeFilterCount,
  parseProductSearch,
  parseTab,
  productsSearch,
  serializeProductParams,
  withChange,
} from './params';

const parse = (search: string) => parseProductSearch(new URLSearchParams(search));

describe('products params (F14-e S2)', () => {
  it('fills the defaults of GET /products', () => {
    expect(parse('')).toEqual({ sort: 'name', dir: 'asc', page: 1, per_page: 48 });
    expect(DEFAULT_PER_PAGE).toBe(48);
  });

  it('reads search, kinds, sets, sort, direction and paging', () => {
    expect(
      parse('q=+box+&kind=box&kind=booster&set=OGN&sort=price&dir=desc&page=3&per_page=96'),
    ).toEqual({
      q: 'box',
      kind: ['box', 'booster'],
      set: ['OGN'],
      sort: 'price',
      dir: 'desc',
      page: 3,
      per_page: 96,
    });
  });

  it('drops invalid values', () => {
    expect(parse('q=+&kind=deck&kind=box&set=&sort=rarity&dir=up&page=0&per_page=200')).toEqual({
      kind: ['box'],
      sort: 'name',
      dir: 'asc',
      page: 1,
      per_page: 48,
    });
    expect(parse('per_page=10').per_page).toBe(48);
    expect(parse('page=2.5').page).toBe(1);
  });

  it('serialises without the defaults and round-trips', () => {
    expect(serializeProductParams(parse(''))).toBe('');
    const search = 'q=box&kind=box&kind=booster&set=OGN&sort=change_7d&dir=desc&page=2&per_page=24';
    expect(serializeProductParams(parse(search))).toBe(search);
  });

  it('goes back to the first page on any change but the page', () => {
    const params = parse('q=box&page=4');
    expect(withChange(params, { page: 5 }).page).toBe(5);
    expect(serializeProductParams(withChange(params, { sort: 'price' }))).toBe('q=box&sort=price');
  });

  it('counts the active filters', () => {
    expect(activeFilterCount(parse('q=box'))).toBe(0);
    expect(activeFilterCount(parse('kind=box&kind=booster&set=OGN'))).toBe(3);
  });

  it('reads and writes owned=owned, the only owned value the screens use (F14-f S1)', () => {
    expect(parse('owned=owned').owned).toBe('owned');
    expect(parse('owned=missing').owned).toBeUndefined();
    expect(parse('owned=any').owned).toBeUndefined();
    expect(serializeProductParams(parse('set=OGN&owned=owned&sort=price'))).toBe(
      'set=OGN&owned=owned&sort=price',
    );
    expect(activeFilterCount(parse('owned=owned'))).toBe(1);
    expect(
      serializeProductParams(withChange(parse('owned=owned&page=3'), { owned: undefined })),
    ).toBe('');
  });

  it('reads the tab and writes it first', () => {
    expect(parseTab(new URLSearchParams('tab=mine'))).toBe('mine');
    expect(parseTab(new URLSearchParams('tab=catalog'))).toBe('catalog');
    expect(parseTab(new URLSearchParams('tab=other'))).toBeNull();
    expect(parseTab(new URLSearchParams(''))).toBeNull();
    expect(productsSearch('catalog', parse('kind=box&page=2'))).toBe('tab=catalog&kind=box&page=2');
    expect(productsSearch('mine', parse(''))).toBe('tab=mine');
  });
});
