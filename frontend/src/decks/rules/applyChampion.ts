import {
  cloneData,
  cloneDeck,
  copiesOf,
  getCard,
  isChampionUnit,
  isToken,
  missingSlot,
  offIdentity,
  refusal,
  shareTag,
} from './cards';
import { COPY_ZONES, type RulesContext } from './constants';
import { nameKey } from './sortNames';
import type { ApplyResult, CardRef, Cards, DeckContent, DeckLine } from './types';

/**
 * `{ok: true, deck}` with `champion` chosen (or removed with null), or a refusal (F5-a S12).
 * The champion is a Champion Unit sharing a tag with the legend. While its name has no room
 * left in main + sideboard + workbench, one copy is removed (main, then sideboard, then
 * workbench; in each zone from the printing with the most copies, the first on ties; a
 * line at 0 disappears). The previous champion no longer counts.
 */
export function applyChampion(
  deck: DeckContent,
  cards: Cards,
  champion: CardRef | null,
  rules: RulesContext,
): ApplyResult {
  const out = cloneDeck(deck);
  if (champion === null) {
    out.champion = null;
    return { ok: true, deck: out };
  }
  const data = getCard(cards, champion);
  if (isToken(data)) return refusal('token_in_deck', { name: data.name, zone: 'champion' });
  if (!isChampionUnit(data)) {
    return refusal('card_off_identity', offIdentity(data, 'champion', 'type'));
  }
  if (!deck.legend) return refusal('legend_missing', missingSlot());
  if (!shareTag(data, getCard(cards, deck.legend))) {
    return refusal('champion_tag', { name: data.name });
  }
  out.champion = cloneData(champion);
  const key = nameKey(data.name);
  while (copiesOf(out, cards, data.name, COPY_ZONES, false) + 1 > rules.deck.copies_max) {
    for (const zone of COPY_ZONES) {
      const lines = (out[zone] || []).filter(
        (line) => nameKey(getCard(cards, line).name) === key && line.qty > 0,
      );
      if (lines.length > 0) {
        const line = lines.reduce((best: DeckLine, item) => (item.qty > best.qty ? item : best));
        line.qty -= 1;
        if (line.qty === 0) out[zone] = out[zone].filter((item) => item !== line);
        break;
      }
    }
  }
  return { ok: true, deck: out };
}
