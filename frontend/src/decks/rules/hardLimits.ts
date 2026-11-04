import { copies, entries, isToken, total, workbenchNames, zoneOf } from './cards';
import type { RulesContext } from './constants';
import { compareNames, nameKey } from './sortNames';
import type { Cards, DeckContent, HardViolation } from './types';

/**
 * The F5-R9 hard limits `deck` breaks, as `deck_limit_exceeded` params `{rule, max, name?}`
 * in HARD_RULES order (copies and token by `name_sort_key`; F5-a S10).
 */
export function hardLimitViolations(
  deck: DeckContent,
  cards: Cards,
  rules: RulesContext,
): HardViolation[] {
  const values = rules.deck;
  const out: HardViolation[] = [];
  const over = [...copies(deck, cards).values()]
    .filter(({ count }) => count > values.copies_max)
    .map(({ name }) => name);
  for (const name of over.sort(compareNames)) {
    out.push({ rule: 'copies', max: values.copies_max, name });
  }
  if (total(deck, 'sideboard') > values.sideboard) {
    out.push({ rule: 'sideboard', max: values.sideboard });
  }
  if (workbenchNames(deck, cards).size > values.workbench_max) {
    out.push({ rule: 'workbench', max: values.workbench_max });
  }
  if (zoneOf(deck, 'battlefields').length > values.battlefields) {
    out.push({ rule: 'battlefields', max: values.battlefields });
  }
  if (total(deck, 'runes') > values.runes) out.push({ rule: 'runes', max: values.runes });
  const tokens = new Map<string, string>();
  for (const { zone, card } of entries(deck, cards)) {
    const key = nameKey(card.name);
    if (zone !== 'workbench' && isToken(card) && !tokens.has(key)) tokens.set(key, card.name);
  }
  for (const name of [...tokens.values()].sort(compareNames)) {
    out.push({ rule: 'token', max: 0, name });
  }
  return out;
}
