import { describe, expect, it } from 'vitest';
import { champion as ayla } from '@/test/fixtures/cards';
import {
  battlefields,
  benchCard,
  calmRune,
  championAlt,
  chaosRune,
  disciplineAlts,
  draftDeck,
  printingDetail,
  mainCards,
  rivenContent,
  rivenDeck,
  rivenChampion,
  rivenLegend,
  sideCards,
} from '@/test/fixtures/decks';
import {
  addCopy,
  bookOf,
  contentValue,
  copiesInDeck,
  knownContent,
  moveCopy,
  printingCard,
  removeCopy,
  removeUnknown,
  rulesCardsOf,
  setPrinting,
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

  it('counts the copies of a printing in the deck, the workbench left out', () => {
    expect(copiesInDeck(rivenContent, ref(mainCards[0]))).toBe(3);
    expect(copiesInDeck(rivenContent, ref(calmRune))).toBe(5);
    expect(copiesInDeck(rivenContent, rivenContent.battlefields[0])).toBe(1);
    expect(copiesInDeck(rivenContent, ref(rivenLegend))).toBe(1);
    const moved = moveCopy(rivenContent, 'main', 'sideboard', ref(mainCards[0]));
    expect(copiesInDeck(moved, ref(mainCards[0]))).toBe(3);
    const benched = moveCopy(rivenContent, 'main', 'workbench', ref(mainCards[0]));
    expect(copiesInDeck(benched, ref(mainCards[0]))).toBe(2);
    expect(copiesInDeck(rivenContent, ref(benchCard))).toBe(0);
  });
});

const discipline = mainCards[0];
const [disciplineOgs, disciplineShowcase] = disciplineAlts;
/** Copies of every printing of a name in one zone's lines. */
const copiesOfName = (lines: { set: string; id: string; qty: number }[], keys: string[]) =>
  lines.filter((l) => keys.includes(`${l.set}-${l.id}`)).reduce((n, l) => n + l.qty, 0);
const DISCIPLINE_KEYS = [discipline, ...disciplineAlts].map((c) => c.key);

describe('setPrinting: another printing of the same card (art switch)', () => {
  it('moves copies of a line to a new line of the target printing, right after it', () => {
    const next = setPrinting(rivenContent, 'main', ref(discipline), ref(disciplineOgs), 2);
    expect(next.main.slice(0, 2)).toEqual([
      { ...ref(discipline), qty: 1 },
      { ...ref(disciplineOgs), qty: 2 },
    ]);
    expect(next.main).toHaveLength(rivenContent.main.length + 1);
    expect(copiesOfName(next.main, DISCIPLINE_KEYS)).toBe(3);
    // inputs are never changed
    expect(rivenContent.main[0]).toEqual({ ...ref(discipline), qty: 3 });
  });

  it('merges into a line of the target printing and drops the source line at 0', () => {
    const split = setPrinting(rivenContent, 'main', ref(discipline), ref(disciplineOgs), 1);
    const merged = setPrinting(split, 'main', ref(discipline), ref(disciplineOgs), 2);
    expect(merged.main[0]).toEqual({ ...ref(disciplineOgs), qty: 3 });
    expect(merged.main.some((l) => l.id === discipline.card_id && l.set === 'OGN')).toBe(false);
    expect(merged.main).toHaveLength(rivenContent.main.length);
    expect(copiesOfName(merged.main, DISCIPLINE_KEYS)).toBe(3);
  });

  it('moves at most the copies the source line has; one copy by default', () => {
    const all = setPrinting(rivenContent, 'main', ref(discipline), ref(disciplineShowcase), 9);
    expect(all.main[0]).toEqual({ ...ref(disciplineShowcase), qty: 3 });
    const one = setPrinting(rivenContent, 'main', ref(discipline), ref(disciplineShowcase));
    expect(one.main.slice(0, 2)).toEqual([
      { ...ref(discipline), qty: 2 },
      { ...ref(disciplineShowcase), qty: 1 },
    ]);
  });

  it('works the same in the runes, the sideboard and the workbench, zone by zone', () => {
    const runeAlt = { set: 'OGS', id: 'r05' };
    const runes = setPrinting(rivenContent, 'runes', ref(chaosRune), runeAlt, 3);
    expect(runes.runes.slice(0, 2)).toEqual([
      { ...ref(chaosRune), qty: 4 },
      { ...runeAlt, qty: 3 },
    ]);
    const sideAlt = { set: 'OGS', id: '341' };
    const side = setPrinting(rivenContent, 'sideboard', ref(sideCards[1]), sideAlt, 1);
    expect(side.sideboard.slice(1, 3)).toEqual([
      { ...ref(sideCards[1]), qty: 1 },
      { ...sideAlt, qty: 1 },
    ]);
    expect(side.main).toEqual(rivenContent.main);
    const benched = { ...rivenContent, workbench: [{ ...ref(benchCard), qty: 2 }] };
    const bench = setPrinting(benched, 'workbench', ref(benchCard), { set: 'OGS', id: '350' }, 2);
    expect(bench.workbench).toEqual([{ set: 'OGS', id: '350', qty: 2 }]);
    // a printing the zone does not have is left alone
    expect(setPrinting(rivenContent, 'sideboard', ref(discipline), ref(disciplineOgs))).toEqual(
      rivenContent,
    );
  });

  it('replaces a battlefield, the legend or the champion ref in place', () => {
    const fieldAlt = { set: 'OGS', id: '331' };
    const fields = setPrinting(rivenContent, 'battlefields', ref(battlefields[1]), fieldAlt);
    expect(fields.battlefields).toEqual([ref(battlefields[0]), fieldAlt, ref(battlefields[2])]);
    const champ = setPrinting(rivenContent, 'champion', ref(rivenChampion), ref(championAlt));
    expect(champ.champion).toEqual(ref(championAlt));
    // same name, same identity: nothing else of the deck changes
    expect({ ...champ, champion: rivenContent.champion }).toEqual(rivenContent);
    const legendAlt = { set: 'OGS', id: '300' };
    const legend = setPrinting(rivenContent, 'legend', ref(rivenLegend), legendAlt);
    expect(legend.legend).toEqual(legendAlt);
    expect(legend.runes).toEqual(rivenContent.runes);
    expect(legend.champion).toEqual(rivenContent.champion);
    // a slot holding another card is left alone
    expect(setPrinting(rivenContent, 'champion', ref(discipline), ref(championAlt))).toEqual(
      rivenContent,
    );
  });

  it('is a no-op for the same printing or no copies', () => {
    expect(setPrinting(rivenContent, 'main', ref(discipline), ref(discipline), 2)).toBe(
      rivenContent,
    );
    expect(setPrinting(rivenContent, 'champion', ref(rivenChampion), ref(rivenChampion))).toBe(
      rivenContent,
    );
    expect(setPrinting(rivenContent, 'main', ref(discipline), ref(disciplineOgs), 0)).toBe(
      rivenContent,
    );
  });
});

describe('printingCard: the deck card of another printing', () => {
  it('keeps the game facts of the deck card and takes the printing of the catalog', () => {
    const detail = printingDetail(discipline, [discipline, ...disciplineAlts]);
    const card = printingCard(discipline, detail.printings[1]);
    expect(card).toEqual({
      ...discipline,
      set_id: 'OGS',
      card_id: '7',
      key: 'OGS-7',
      rarity: 'Rare',
      image_src: disciplineOgs.image_src,
      image_thumb_src: null,
      is_base: false,
      market: 2,
      owned_total: 2,
    });
  });
});
