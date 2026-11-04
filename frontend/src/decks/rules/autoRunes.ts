import { cloneDeck, getCard, identity, isToken, refOfKey, runeColour, zoneOf } from './cards';
import type { RulesContext } from './constants';
import type { Card, CardRef, Cards, DeckContent } from './types';

/** Safety cap of the balancing loops (design-handoff §5.3). */
const MAX_STEPS = 200;

/**
 * The deck with its runes balanced by colour demand (F5-a S13, design-handoff §5.3).
 *
 * Demand of a legend colour = main deck copies whose domains include it, plus the chosen
 * champion. Runes per colour = `floor(12 / colours)` without demand, else
 * `max(1, floor(demand / total * 12 + 0.5))` (`Math.floor(x + 0.5)`, the expression Python
 * uses; not `Math.round`). Then, over the colours ordered by runes descending (stable), one
 * rune is taken from (while over 12, never below 1) or given to (while under) each colour in
 * turn, at most 200 steps. Each colour uses the rune printing already in the deck, else the
 * first rune of that colour in `cards` order; a colour without a rune card is skipped. Every
 * previous rune is replaced. No legend or no colour: the deck unchanged (a copy).
 */
export function autoRunes(deck: DeckContent, cards: Cards, rules: RulesContext): DeckContent {
  const out = cloneDeck(deck);
  if (!deck.legend) return out;
  const runeFor = new Map<string | null, CardRef>();
  for (const line of zoneOf(deck, 'runes')) {
    const card = getCard(cards, line);
    const colour = runeColour(card);
    if (card.type === 'Rune' && !runeFor.has(colour)) {
      runeFor.set(colour, { set: line.set, id: line.id });
    }
  }
  for (const [key, card] of cards) {
    const colour = runeColour(card);
    if (card.type === 'Rune' && !isToken(card) && !runeFor.has(colour)) {
      runeFor.set(colour, refOfKey(key));
    }
  }
  const cols = identity(deck, cards).filter((colour) => runeFor.has(colour));
  if (cols.length === 0) return out;

  const demand = new Map(cols.map((colour) => [colour, 0]));
  const counted: [Card, number][] = zoneOf(deck, 'main').map((line) => [
    getCard(cards, line),
    line.qty,
  ]);
  if (deck.champion) counted.push([getCard(cards, deck.champion), 1]);
  for (const [card, qty] of counted) {
    for (const colour of cols) {
      if ((card.domains || []).includes(colour)) demand.set(colour, demand.get(colour)! + qty);
    }
  }
  const sum = (values: Iterable<number>) => [...values].reduce((a, b) => a + b, 0);
  const totalDemand = sum(demand.values());
  const target = rules.deck.runes;
  const runes = new Map<string, number>(
    cols.map((colour) => [
      colour,
      totalDemand === 0
        ? Math.floor(target / cols.length)
        : Math.max(1, Math.floor((demand.get(colour)! / totalDemand) * target + 0.5)),
    ]),
  );

  // Array.prototype.sort is stable, like Python's sorted.
  const order = [...cols].sort((a, b) => runes.get(b)! - runes.get(a)!);
  let step = 0;
  while (sum(runes.values()) > target && step < MAX_STEPS) {
    const colour = order[step % order.length];
    if (runes.get(colour)! > 1) runes.set(colour, runes.get(colour)! - 1);
    step += 1;
  }
  while (sum(runes.values()) < target && step < MAX_STEPS) {
    const colour = order[step % order.length];
    runes.set(colour, runes.get(colour)! + 1);
    step += 1;
  }

  out.runes = cols
    .filter((colour) => runes.get(colour)! > 0)
    .map((colour) => ({ ...runeFor.get(colour)!, qty: runes.get(colour)! }));
  return out;
}
