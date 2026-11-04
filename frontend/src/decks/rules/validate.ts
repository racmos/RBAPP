import {
  colours,
  copies,
  entries,
  fitReason,
  getCard,
  isChampionUnit,
  isToken,
  missingSlot,
  offIdentity,
  runeColour,
  shareTag,
  size,
  total,
  workbenchNames,
  zoneOf,
} from './cards';
import { ISSUE_CODES, ZONE_ORDER, type RulesContext } from './constants';
import { compareCodePoints, nameKey } from './sortNames';
import type {
  Bans,
  Card,
  Cards,
  Completeness,
  DeckContent,
  Issue,
  SlotParams,
  Validation,
} from './types';

function nameOf(issue: Issue): string {
  return 'name' in issue.params ? issue.params.name : '';
}

function zoneIndex(issue: Issue): number {
  return 'zone' in issue.params ? ZONE_ORDER.indexOf(issue.params.zone) : -1;
}

/** ISSUE_CODES order, then `name_sort_key` of `params.name`, then ZONE_ORDER of `params.zone`. */
function issueOrder(a: Issue, b: Issue): number {
  const nameA = nameOf(a);
  const nameB = nameOf(b);
  return (
    ISSUE_CODES.indexOf(a.code) - ISSUE_CODES.indexOf(b.code) ||
    compareCodePoints(nameKey(nameA), nameKey(nameB)) ||
    compareCodePoints(nameA, nameB) ||
    zoneIndex(a) - zoneIndex(b)
  );
}

function firstName(deck: DeckContent, cards: Cards, card: Card): string {
  const key = nameKey(card.name);
  for (const ref of zoneOf(deck, 'battlefields')) {
    const name = getCard(cards, ref).name;
    if (nameKey(name) === key) return name;
  }
  return card.name;
}

/**
 * `{legal, issues, completeness}` of `deck` in `mode` (F5-a S6, S7). `legal` is true only
 * without issues; one issue per code + name + zone. The workbench only counts for
 * `copies_over` and `workbench_over`.
 */
export function validate(
  deck: DeckContent,
  cards: Cards,
  bans: Bans | null,
  mode: string,
  rules: RulesContext,
): Validation {
  if (!rules.modes.includes(mode)) throw new RangeError(`unknown game mode: ${mode}`);
  const values = rules.deck;
  const legend = deck.legend ? getCard(cards, deck.legend) : null;
  const champion = deck.champion ? getCard(cards, deck.champion) : null;
  const cols = legend ? colours(legend) : [];
  const found = new Map<string, Issue>();

  const add = (issue: Issue) => {
    const params = issue.params;
    const key = JSON.stringify([
      issue.code,
      'name' in params ? nameKey(params.name) : '',
      'zone' in params ? params.zone : null,
    ]);
    if (!found.has(key)) found.set(key, issue);
  };

  if (legend === null) add({ code: 'legend_missing', params: missingSlot() });
  if (champion === null) {
    add({ code: 'champion_missing', params: missingSlot() });
  } else if (
    legend !== null &&
    !isToken(champion) &&
    isChampionUnit(champion) &&
    !shareTag(champion, legend)
  ) {
    add({ code: 'champion_tag', params: { name: champion.name } });
  }

  const main = total(deck, 'main');
  if (main !== values.main_size) add({ code: 'main_size', params: size(main, values.main_size) });
  const runes = total(deck, 'runes');
  if (runes !== values.runes) add({ code: 'runes_count', params: size(runes, values.runes) });
  const battlefields = zoneOf(deck, 'battlefields').length;
  if (battlefields !== values.battlefields) {
    add({ code: 'battlefields_count', params: size(battlefields, values.battlefields) });
  }
  const seenFields = new Set<string>();
  for (const ref of zoneOf(deck, 'battlefields')) {
    const card = getCard(cards, ref);
    const key = nameKey(card.name);
    if (seenFields.has(key)) {
      add({ code: 'battlefields_duplicate', params: { name: firstName(deck, cards, card) } });
    }
    seenFields.add(key);
  }
  const sideboard = total(deck, 'sideboard');
  if (sideboard !== values.sideboard) {
    add({ code: 'sideboard_size', params: size(sideboard, values.sideboard) });
  }

  for (const { name, count } of copies(deck, cards).values()) {
    if (count > values.copies_max) {
      add({ code: 'copies_over', params: { name, count, max: values.copies_max } });
    }
  }
  const workbench = workbenchNames(deck, cards).size;
  if (workbench > values.workbench_max) {
    add({ code: 'workbench_over', params: { count: workbench, max: values.workbench_max } });
  }

  for (const { zone, card } of entries(deck, cards)) {
    if (zone === 'workbench') continue;
    if (isToken(card)) {
      add({ code: 'token_in_deck', params: { name: card.name, zone } });
      continue;
    }
    const reason = fitReason(card, zone, legend, cols);
    if (reason !== null) {
      add({ code: 'card_off_identity', params: offIdentity(card, zone, reason) });
    } else if (zone === 'runes' && legend !== null) {
      const colour = runeColour(card);
      if (colour === null || !cols.includes(colour)) {
        add({ code: 'rune_off_identity', params: { name: card.name } });
      }
    }
  }

  const banned = new Map(Object.entries(bans || {}).map(([name, modes]) => [nameKey(name), modes]));
  for (const { zone, card } of entries(deck, cards)) {
    if (zone !== 'workbench' && (banned.get(nameKey(card.name)) || []).includes(mode)) {
      add({ code: 'banned', params: { name: card.name, mode } });
    }
  }

  const issues = [...found.values()].sort(issueOrder);
  return { legal: issues.length === 0, issues, completeness: completeness(deck, rules) };
}

/** `{section: {have, need, missing}}`; `have` counts every card in the section, fitting or not. */
export function completeness(deck: DeckContent, rules: RulesContext): Completeness {
  const values = rules.deck;
  const entry = (have: number, need: number): SlotParams => ({
    have,
    need,
    missing: Math.max(0, need - have),
  });
  return {
    legend: entry(deck.legend ? 1 : 0, 1),
    champion: entry(deck.champion ? 1 : 0, 1),
    main: entry(total(deck, 'main'), values.main_size),
    runes: entry(total(deck, 'runes'), values.runes),
    battlefields: entry(zoneOf(deck, 'battlefields').length, values.battlefields),
    sideboard: entry(total(deck, 'sideboard'), values.sideboard),
  };
}
