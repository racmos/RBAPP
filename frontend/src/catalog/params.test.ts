import { describe, expect, it } from 'vitest';
import {
  DEFAULT_PAGE,
  DEFAULT_PER_PAGE,
  DEFAULT_SORT,
  parseCatalogSearch,
  serializeCatalogParams,
  withChange,
} from './params';

describe('parseCatalogSearch (F2-h S3)', () => {
  it('returns defaults for an empty search', () => {
    expect(parseCatalogSearch(new URLSearchParams())).toEqual({
      sort: DEFAULT_SORT,
      dir: 'asc',
      page: DEFAULT_PAGE,
      per_page: DEFAULT_PER_PAGE,
    });
  });

  it('reads repeated keys as arrays', () => {
    const params = parseCatalogSearch(new URLSearchParams('domain=Fury&domain=Chaos'));
    expect(params.domain).toEqual(['Fury', 'Chaos']);
  });

  it('falls unknown sort back to number', () => {
    expect(parseCatalogSearch(new URLSearchParams('sort=unknown')).sort).toBe(DEFAULT_SORT);
  });

  it('falls invalid page back to 1', () => {
    expect(parseCatalogSearch(new URLSearchParams('page=0')).page).toBe(DEFAULT_PAGE);
    expect(parseCatalogSearch(new URLSearchParams('page=abc')).page).toBe(DEFAULT_PAGE);
    expect(parseCatalogSearch(new URLSearchParams('page=-3')).page).toBe(DEFAULT_PAGE);
  });

  it('falls invalid per_page back to 48', () => {
    expect(parseCatalogSearch(new URLSearchParams('per_page=50')).per_page).toBe(DEFAULT_PER_PAGE);
    expect(parseCatalogSearch(new URLSearchParams('per_page=abc')).per_page).toBe(DEFAULT_PER_PAGE);
  });

  it('accepts 96 and 192 per_page', () => {
    expect(parseCatalogSearch(new URLSearchParams('per_page=96')).per_page).toBe(96);
    expect(parseCatalogSearch(new URLSearchParams('per_page=192')).per_page).toBe(192);
  });

  it('parses booleans only as true', () => {
    expect(parseCatalogSearch(new URLSearchParams('base_only=true')).base_only).toBe(true);
    expect(parseCatalogSearch(new URLSearchParams('base_only=false')).base_only).toBeUndefined();
    expect(parseCatalogSearch(new URLSearchParams('base_only=1')).base_only).toBeUndefined();
  });

  it('parses ranges and banned_in', () => {
    const params = parseCatalogSearch(
      new URLSearchParams('energy_min=1&energy_max=5&price_min=0.5&banned_in=1v1'),
    );
    expect(params).toMatchObject({
      energy_min: 1,
      energy_max: 5,
      price_min: 0.5,
      banned_in: '1v1',
    });
  });
});

describe('serializeCatalogParams (F2-h S3)', () => {
  it('omits all defaults', () => {
    expect(serializeCatalogParams({})).toBe('');
  });

  it('writes keys in fixed order and arrays repeated', () => {
    const params = {
      domain: ['Fury', 'Chaos'],
      set: ['OGN'],
      sort: 'name' as const,
      page: 2,
    };
    expect(serializeCatalogParams(params)).toBe(
      'set=OGN&domain=Fury&domain=Chaos&sort=name&page=2',
    );
  });

  it('omits default sort, dir, page and per_page', () => {
    const params = {
      sort: DEFAULT_SORT,
      dir: 'asc' as const,
      page: DEFAULT_PAGE,
      per_page: DEFAULT_PER_PAGE,
    };
    expect(serializeCatalogParams(params)).toBe('');
  });

  it('serialises range filters', () => {
    expect(serializeCatalogParams({ energy_min: 2, energy_max: 4, price_min: 0.99 })).toBe(
      'energy_min=2&energy_max=4&price_min=0.99',
    );
  });
});

describe('round trip (F2-h S3)', () => {
  it('serialise(parse(x)) === x for canonical strings', () => {
    const canonical =
      'q=aya&text=assault&set=OGN&domain=Fury&domain=Chaos&type=Unit&supertype=Champion&exclude_supertype=Token&rarity=Rare&tag=champion&domain_match=all&energy_min=1&energy_max=5&power_min=2&power_max=4&might_min=0&might_max=2&price_min=0.5&price_max=5&owned=owned&banned_in=1v1&base_only=true&sort=name&dir=desc&page=2&per_page=96';
    expect(serializeCatalogParams(parseCatalogSearch(new URLSearchParams(canonical)))).toBe(
      canonical,
    );
  });
});

describe('withChange (F2-h S3)', () => {
  it('keeps page when only page changes', () => {
    expect(withChange({ page: 3 }, { page: 5 })).toEqual({ page: 5 });
  });

  it('resets page to 1 when any other field changes', () => {
    expect(withChange({ page: 3 }, { q: 'aya' })).toEqual({ q: 'aya' });
    expect(withChange({ page: 3 }, { sort: 'name' })).toEqual({ sort: 'name' });
  });

  it('keeps page when there are no changes', () => {
    expect(withChange({ page: 3 }, {})).toEqual({ page: 3 });
  });
});
