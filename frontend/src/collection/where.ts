import type { CollectionLine } from '@/api/types';

/**
 * The short location summary of some lines (F16-R5): the first location code in the user's order
 * and how many other locations hold copies, `B001-F001-P0001 +2`; empty when none does.
 */
export function whereSummary(lines: CollectionLine[]): string {
  const codes: string[] = [];
  let more = 0;
  for (const line of lines) {
    for (const place of line.locations ?? []) {
      if (!codes.includes(place.code)) codes.push(place.code);
    }
    more += line.locations_more ?? 0;
  }
  if (codes.length === 0) return '';
  const others = codes.length - 1 + more;
  return others > 0 ? `${codes[0]} +${others}` : codes[0];
}
