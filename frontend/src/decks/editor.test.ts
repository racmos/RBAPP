import { describe, expect, it } from 'vitest';
import { champion as ayla } from '@/test/fixtures/cards';
import {
  benchCard,
  calmRune,
  draftDeck,
  mainCards,
  rivenContent,
  rivenDeck,
  sideCards,
} from '@/test/fixtures/decks';
import {
  addCopy,
  bookOf,
  contentValue,
  knownContent,
  moveCopy,
  removeCopy,
  removeUnknown,
  rulesCardsOf,
  toDeckCard,
  unknownRefs,
} from './editor';
import { cardKey } from './rules';

const ref = (card: { set_id: string; card_id: string }) => ({ set: card.set_id, id: card.card_id });

describe('deck editor operations (F5-h stage 2)', () => {
  it('adds a copy to a line, or a new line at the end', () => {
    const one = addCopy(rivenContent, 'sideboard', ref(sideCards[2]));
    expect(one.sideboard[2]).toEqual({ ...ref(sideCards[2]), qty: 3 });
    const two = addCopy(rivenContent, 'workbench', ref(benchCard));
    expect(two.workbench).toEqual([{ ...ref(benchCard), qty: 1 }]);
    const three = addCopy(rivenContent, 'battlefields', { set: 'OGN', id: 'x' });
    expect(three.battlefields).toHaveLength(4);
    // inputs are never changed
    expect(rivenContent.sideboard[2].qty).toBe(2);
    expect(rivenContent.workbench).toEqual([]);
  });

  it('removes a copy and drops the line at 0; a battlefield goes at once', () => {
    const once = removeCopy(rivenContent, 'runes', ref(calmRune));
    expect(once.runes[1].qty).toBe(4);
    let content = rivenContent;
    for (let i = 0; i < 3; i += 1) content = removeCopy(content, 'main', ref(mainCards[0]));
    expect(content.main.map((line) => line.id)).not.toContain(mainCards[0].card_id);
    const field = removeCopy(rivenContent, 'battlefields', rivenContent.battlefields[1]);
    expect(field.battlefields).toEqual([
      rivenContent.battlefields[0],
      rivenContent.battlefields[2],
    ]);
  });

  it('moves one copy between zones', () => {
    const moved = moveCopy(rivenContent, 'main', 'sideboard', ref(mainCards[0]));
    expect(moved.main[0].qty).toBe(2);
    expect(moved.sideboard.at(-1)).toEqual({ ...ref(mainCards[0]), qty: 1 });
  });

  it('knows which printings the catalog lacks and can take them out', () => {
    const book = bookOf(draftDeck.cards);
    expect(unknownRefs(draftDeck.content, book)).toEqual([{ zone: 'main', set: 'OGN', id: '999' }]);
    expect(knownContent(draftDeck.content, book).main).toEqual([draftDeck.content.main[0]]);
    expect(removeUnknown(draftDeck.content, book).main).toEqual([draftDeck.content.main[0]]);
  });

  it('values a content like the server: the workbench never counts', () => {
    const book = bookOf(rivenDeck.cards);
    expect(contentValue(rivenContent, book)).toEqual({
      value: rivenDeck.value,
      unpriced: rivenDeck.value_unpriced,
    });
    const withBench = addCopy(rivenContent, 'workbench', ref(benchCard));
    expect(
      contentValue(withBench, bookOf({ ...rivenDeck.cards, [benchCard.key]: benchCard })),
    ).toEqual(contentValue(rivenContent, book));
  });

  it('turns a searched card into a deck card the rules can read', () => {
    const card = toDeckCard(ayla);
    expect(card).toMatchObject({
      key: 'OGN-79',
      name: "Ayla, Fury's Champion",
      type: 'Unit',
      supertype: 'Champion',
      tags: ['champion', 'fury'],
      market: 1.21,
      owned_total: 2,
    });
    const cards = rulesCardsOf({ [card.key]: card });
    expect(cards.get(cardKey(ref(ayla)))?.name).toBe("Ayla, Fury's Champion");
  });
});
