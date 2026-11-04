import {
  cloneData,
  cloneDeck,
  getCard,
  identity,
  isToken,
  offIdentity,
  refusal,
  runeColour,
  shareTag,
  zoneOf,
} from './cards';
import type { ApplyResult, CardRef, Cards, DeckContent } from './types';

/**
 * `{ok: true, deck}` with `legend` set (or removed with null), or a refusal (F5-a S11). Purges
 * the runes whose colour is not one of the new legend's colours and the champion when it
 * shares no tag with it; the main deck, sideboard, battlefields and workbench are untouched.
 */
export function applyLegend(deck: DeckContent, cards: Cards, legend: CardRef | null): ApplyResult {
  const out = cloneDeck(deck);
  if (legend !== null) {
    const data = getCard(cards, legend);
    if (isToken(data)) return refusal('token_in_deck', { name: data.name, zone: 'legend' });
    if (data.type !== 'Legend') {
      return refusal('card_off_identity', offIdentity(data, 'legend', 'type'));
    }
  }
  out.legend = cloneData(legend);
  const cols = identity(out, cards);
  out.runes = zoneOf(out, 'runes').filter((line) => {
    const colour = runeColour(getCard(cards, line));
    return colour !== null && cols.includes(colour);
  });
  if (
    out.champion &&
    (legend === null || !shareTag(getCard(cards, out.champion), getCard(cards, legend)))
  ) {
    out.champion = null;
  }
  return { ok: true, deck: out };
}
