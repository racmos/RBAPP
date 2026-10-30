/**
 * Set order of every set dropdown and set button group (owner feedback S19): newest release
 * first, sets without a release date last; same date or no date by id. `GET /meta/game` already
 * sends this order; lists from other sources (admin sets, facet keys) go through here.
 */
export function sortSetsNewestFirst<T extends { id: string }>(
  sets: readonly T[],
  releasedOn: (set: T) => string | null | undefined,
): T[] {
  return [...sets].sort((a, b) => {
    const left = releasedOn(a) ?? '';
    const right = releasedOn(b) ?? '';
    if (left !== right) {
      if (left === '') return 1;
      if (right === '') return -1;
      // ISO dates compare as text.
      return left < right ? 1 : -1;
    }
    return a.id.localeCompare(b.id);
  });
}

/** Bare set ids in the same order, dated by `sets`; an id missing there counts as undated. */
export function sortSetIdsNewestFirst(
  ids: readonly string[],
  sets: readonly { id: string; released_on: string | null }[],
): string[] {
  const dates = new Map(sets.map((set) => [set.id, set.released_on]));
  return sortSetsNewestFirst(
    ids.map((id) => ({ id })),
    (set) => dates.get(set.id),
  ).map((set) => set.id);
}
