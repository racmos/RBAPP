import { colours, entries } from './cards';
import type { RulesContext } from './constants';
import { compareNames } from './sortNames';
import type { Cards, DeckContent } from './types';

/**
 * The union of the colours (domains without Colorless) of the legend, the champion and the
 * main deck, in the context's domain order, then unknown domains by `name_sort_key` (S14).
 */
export function deckDomains(deck: DeckContent, cards: Cards, rules: RulesContext): string[] {
  const found = new Set<string>();
  for (const { zone, card } of entries(deck, cards)) {
    if (zone === 'legend' || zone === 'champion' || zone === 'main') {
      for (const colour of colours(card)) found.add(colour);
    }
  }
  const known = rules.domains.filter((domain) => found.has(domain));
  const unknown = [...found].filter((domain) => !rules.domains.includes(domain));
  return [...known, ...unknown.sort(compareNames)];
}
