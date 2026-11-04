import {
  copies,
  copiesOf,
  fitReason,
  getCard,
  identity,
  isToken,
  missingSlot,
  offIdentity,
  refusal,
  runeColour,
  size,
  total,
  workbenchNames,
  zoneOf,
} from './cards';
import { ADD_ZONES, COPY_ZONES, MOVE_ZONES, type RulesContext } from './constants';
import { nameKey } from './sortNames';
import type { AddZone, Card, CardRef, Cards, CheckResult, DeckContent, MoveZone } from './types';

/**
 * `{ok: true}` or the refusal for one more copy of `card` in `zone` (F5-a S8). Refuses the
 * hard limits and the cards that do not fit the zone by type; colour, Signature tag and the
 * main deck size are soft (`validate` reports them). Params describe the deck after the add.
 */
export function canAdd(
  deck: DeckContent,
  cards: Cards,
  card: CardRef,
  zone: AddZone,
  rules: RulesContext,
): CheckResult {
  if (!(ADD_ZONES as readonly string[]).includes(zone))
    throw new RangeError(`unknown zone: ${zone}`);
  const values = rules.deck;
  const data = getCard(cards, card);
  if (zone !== 'workbench' && isToken(data)) {
    return refusal('token_in_deck', { name: data.name, zone });
  }
  if (zone !== 'workbench' && fitReason(data, zone, null, []) === 'type') {
    return refusal('card_off_identity', offIdentity(data, zone, 'type'));
  }
  if (zone === 'runes') {
    if (!deck.legend) return refusal('legend_missing', missingSlot());
    const colour = runeColour(data);
    if (colour === null || !identity(deck, cards).includes(colour)) {
      return refusal('rune_off_identity', { name: data.name });
    }
    const runes = total(deck, 'runes') + 1;
    if (runes > values.runes) return refusal('runes_count', size(runes, values.runes));
    return { ok: true };
  }
  if (zone === 'battlefields') {
    const key = nameKey(data.name);
    for (const ref of zoneOf(deck, 'battlefields')) {
      if (nameKey(getCard(cards, ref).name) === key) {
        return refusal('battlefields_duplicate', { name: getCard(cards, ref).name });
      }
    }
    const fields = zoneOf(deck, 'battlefields').length + 1;
    if (fields > values.battlefields) {
      return refusal('battlefields_count', size(fields, values.battlefields));
    }
    return { ok: true };
  }
  const count = copiesOf(deck, cards, data.name, COPY_ZONES) + 1;
  if (count > values.copies_max) {
    return refusal('copies_over', copiesParams(deck, cards, data, count, rules));
  }
  return zoneRoom(deck, cards, data, zone, rules);
}

/**
 * `{ok: true}` or the refusal for moving one copy of the printing `card` from `from` to `to`
 * (main, sideboard, workbench; F5-a S9). The prototype rules are kept: workbench → main /
 * sideboard needs room for one more copy in main + sideboard + champion, and the workbench
 * holds at most 3 copies of a name.
 */
export function canMove(
  deck: DeckContent,
  cards: Cards,
  card: CardRef,
  from: MoveZone,
  to: MoveZone,
  rules: RulesContext,
): CheckResult {
  const zones = MOVE_ZONES as readonly string[];
  if (!zones.includes(from) || !zones.includes(to) || from === to) {
    throw new RangeError(`unknown move: ${from} -> ${to}`);
  }
  if (!zoneOf(deck, from).some((line) => line.set === card.set && line.id === card.id)) {
    throw new RangeError(`card not in ${from}`);
  }
  const values = rules.deck;
  const data = getCard(cards, card);
  if (to !== 'workbench' && isToken(data)) {
    return refusal('token_in_deck', { name: data.name, zone: to });
  }
  if (to !== 'workbench' && fitReason(data, to, null, []) === 'type') {
    return refusal('card_off_identity', offIdentity(data, to, 'type'));
  }
  let count = 0;
  if (from === 'workbench') {
    count = copiesOf(deck, cards, data.name, ['main', 'sideboard']) + 1;
  } else if (to === 'workbench') {
    count = copiesOf(deck, cards, data.name, ['workbench'], false) + 1;
  }
  if (count > values.copies_max) {
    return refusal('copies_over', copiesParams(deck, cards, data, count, rules));
  }
  return zoneRoom(deck, cards, data, to, rules);
}

function copiesParams(
  deck: DeckContent,
  cards: Cards,
  data: Card,
  count: number,
  rules: RulesContext,
) {
  const name = copies(deck, cards).get(nameKey(data.name))?.name ?? data.name;
  return { name, count, max: rules.deck.copies_max };
}

function zoneRoom(
  deck: DeckContent,
  cards: Cards,
  data: Card,
  zone: MoveZone,
  rules: RulesContext,
): CheckResult {
  const values = rules.deck;
  if (zone === 'sideboard') {
    const sideboard = total(deck, 'sideboard') + 1;
    if (sideboard > values.sideboard) {
      return refusal('sideboard_size', size(sideboard, values.sideboard));
    }
  }
  if (zone === 'workbench') {
    const names = workbenchNames(deck, cards);
    if (!names.has(nameKey(data.name)) && names.size + 1 > values.workbench_max) {
      return refusal('workbench_over', { count: names.size + 1, max: values.workbench_max });
    }
  }
  return { ok: true };
}
