import { describe, expect, it } from 'vitest';
import { sortSetsNewestFirst, sortSetIdsNewestFirst } from './sets';

const SETS = [
  { id: 'OLD', released_on: '2024-03-01' },
  { id: 'NOD', released_on: null },
  { id: 'NEW', released_on: '2026-09-01' },
  { id: 'MID', released_on: '2025-06-01' },
  { id: 'AAA', released_on: null },
];

describe('sortSetsNewestFirst (owner feedback S19)', () => {
  it('puts the newest release first and the sets without a date last', () => {
    const ids = sortSetsNewestFirst(SETS, (set) => set.released_on).map((set) => set.id);
    expect(ids.slice(0, 3)).toEqual(['NEW', 'MID', 'OLD']);
    expect([...ids.slice(3)].sort()).toEqual(['AAA', 'NOD']);
  });

  it('reads any date field and leaves the input untouched', () => {
    const admin = [
      { id: 'A', release_date: null },
      { id: 'B', release_date: '2025-01-01' },
      { id: 'C', release_date: '2026-01-01' },
    ];
    const sorted = sortSetsNewestFirst(admin, (set) => set.release_date);
    expect(sorted.map((set) => set.id)).toEqual(['C', 'B', 'A']);
    expect(admin.map((set) => set.id)).toEqual(['A', 'B', 'C']);
  });

  it('orders bare set ids by the meta dates; unknown ids count as undated', () => {
    expect(sortSetIdsNewestFirst(['OLD', 'XYZ', 'NEW', 'MID'], SETS)).toEqual([
      'NEW',
      'MID',
      'OLD',
      'XYZ',
    ]);
  });
});
