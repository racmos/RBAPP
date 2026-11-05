import type {
  DeckCard,
  DeckContentV2,
  DeckDetail,
  DeckHead,
  DeckLegality,
  DeckListItem,
  DeckUnknownCard,
  GameMode,
} from '@/api/types';
import { DEFAULT_RULES, ISSUE_CODES, makeCards, validate, type Bans } from '@/decks/rules';

/**
 * Decks v2 fixtures (F5-d shapes). Legality is computed with the deck rules library over the
 * same catalog, so the issues and completeness are what the server would send.
 */
const card = (overrides: Partial<DeckCard> & Pick<DeckCard, 'card_id' | 'name'>): DeckCard => {
  const set_id = overrides.set_id ?? 'OGN';
  return {
    set_id,
    key: `${set_id}-${overrides.card_id}`,
    domains: [],
    type: 'Spell',
    supertype: null,
    rarity: 'Common',
    image_src: `/riftbound/media/cards/${set_id.toLowerCase()}/${overrides.card_id}.png`,
    image_thumb_src: null,
    is_base: true,
    market: 0.5,
    owned_total: 0,
    tags: [],
    energy: null,
    power: null,
    might: null,
    variants: 1,
    keywords: [],
    ...overrides,
  };
};

export const rivenLegend = card({
  card_id: '300',
  name: 'The Exile',
  type: 'Legend',
  domains: ['Calm', 'Chaos'],
  tags: ['Riven'],
  rarity: 'Rare',
  market: 4.2,
});
export const rivenChampion = card({
  card_id: '301',
  name: 'Riven, Broken Blade',
  type: 'Unit',
  supertype: 'Champion',
  domains: ['Chaos'],
  tags: ['Riven'],
  rarity: 'Epic',
  market: 12.5,
  owned_total: 1,
});
const mainNames = [
  'Discipline',
  "Zhonya's Hourglass",
  'Traveling Merchant',
  'Tideturner',
  'Stellacorn Herder',
  'Astral Heron',
  'Blade of the Exile',
  'Defy',
  'Gust',
  'Switcheroo',
  'Battle Preparations',
  'Reckless Innovator',
  'Bedeviling Stranger',
];
export const mainCards = mainNames.map((name, index) =>
  card({
    card_id: String(310 + index),
    name,
    type: index % 2 === 0 ? 'Spell' : 'Unit',
    domains: [index % 3 === 0 ? 'Calm' : 'Chaos'],
    // one unpriced printing, so the value says so
    market: index === 4 ? null : 0.25 * (index + 1),
    // the first one shows every card fact of a row
    ...(index === 0 ? { energy: 2, power: 1, might: null, variants: 3 } : {}),
  }),
);
export const chaosRune = card({
  card_id: 'r05',
  name: 'Chaos Rune',
  type: 'Rune',
  supertype: 'Basic',
  domains: ['Chaos'],
  market: 0.1,
});
export const calmRune = card({
  card_id: 'r02',
  name: 'Calm Rune',
  type: 'Rune',
  supertype: 'Basic',
  domains: ['Calm'],
  market: 0.1,
});
export const battlefields = ['Star Spring', "Hunters' Circle", 'Rakelstake'].map((name, index) =>
  card({ card_id: String(330 + index), name, type: 'Battlefield', market: 0.3 }),
);
export const sideCards = [
  'Decree of Focus',
  "An Offer You Can't Refuse",
  'Hush',
  'Vex, Apathetic',
].map((name, index) =>
  card({ card_id: String(340 + index), name, type: 'Spell', domains: ['Calm'], market: 0.2 }),
);
export const benchCard = card({ card_id: '350', name: 'Baron Nashor', type: 'Unit', market: 3 });

/** A Fury unit on a Calm/Chaos legend's workbench: outside the legend's domains. */
export const furyBench = card({
  card_id: '351',
  name: 'Fury Brawler',
  type: 'Unit',
  domains: ['Fury'],
  market: 1,
});

export const deckCatalog: DeckCard[] = [
  rivenLegend,
  rivenChampion,
  ...mainCards,
  chaosRune,
  calmRune,
  ...battlefields,
  ...sideCards,
  benchCard,
  furyBench,
];

const ref = (c: DeckCard) => ({ set: c.set_id, id: c.card_id });
export const line = (c: DeckCard, qty: number) => ({ ...ref(c), qty });

export const emptyContent: DeckContentV2 = {
  v: 2,
  legend: null,
  champion: null,
  main: [],
  runes: [],
  battlefields: [],
  sideboard: [],
  workbench: [],
};

/** The shape of the owner's migrated deck: legend, champion, 39 main, 12 runes, 3 battlefields
 *  and 8 sideboard cards (2 missing). */
export const rivenContent: DeckContentV2 = {
  v: 2,
  legend: ref(rivenLegend),
  champion: ref(rivenChampion),
  main: mainCards.map((c) => line(c, 3)),
  runes: [line(chaosRune, 7), line(calmRune, 5)],
  battlefields: battlefields.map(ref),
  sideboard: sideCards.map((c) => line(c, 2)),
  workbench: [],
};

/** Zhonya's Hourglass is banned in 2v2 in these fixtures. */
export const deckBans: Bans = { "Zhonya's Hourglass": ['2v2'] };

const byKey = new Map(deckCatalog.map((c) => [c.key, c]));
const keyOf = (r: { set: string; id: string }) => `${r.set}-${r.id}`;

function refs(content: DeckContentV2, withWorkbench = false) {
  return [
    ...(content.legend ? [{ ...content.legend, qty: 1 }] : []),
    ...(content.champion ? [{ ...content.champion, qty: 1 }] : []),
    ...content.main,
    ...content.runes,
    ...content.battlefields.map((b) => ({ ...b, qty: 1 })),
    ...content.sideboard,
    ...(withWorkbench ? content.workbench : []),
  ];
}

const round2 = (value: number) => Math.round(value * 100) / 100;

/** `DeckDetail` of a content the way `GET /decks/:id` builds it. */
export function deckDetail(
  head: Partial<DeckHead> & Pick<DeckHead, 'id' | 'name'>,
  content: DeckContentV2,
  { unknown = [], bans = deckBans }: { unknown?: DeckUnknownCard[]; bans?: Bans } = {},
): DeckDetail {
  const unknownKeys = new Set(unknown.map((u) => `${u.set}-${u.id}`));
  const known = (lines: { set: string; id: string }[]) =>
    lines.filter((l) => !unknownKeys.has(keyOf(l)));
  const clean: DeckContentV2 = {
    ...content,
    legend: content.legend && unknownKeys.has(keyOf(content.legend)) ? null : content.legend,
    champion:
      content.champion && unknownKeys.has(keyOf(content.champion)) ? null : content.champion,
    main: known(content.main) as DeckContentV2['main'],
    runes: known(content.runes) as DeckContentV2['runes'],
    battlefields: known(content.battlefields),
    sideboard: known(content.sideboard) as DeckContentV2['sideboard'],
    workbench: known(content.workbench) as DeckContentV2['workbench'],
  };
  const cards: Record<string, DeckCard> = {};
  for (const r of refs(clean, true)) {
    const c = byKey.get(keyOf(r));
    if (c) cards[c.key] = c;
  }
  const rulesCards = makeCards(deckCatalog.map((c) => [ref(c), c] as const));
  const legality = Object.fromEntries(
    (['1v1', '2v2'] as GameMode[]).map((mode) => [
      mode,
      validate(clean, rulesCards, bans, mode, DEFAULT_RULES),
    ]),
  ) as unknown as DeckLegality;
  let value = 0;
  let unpriced = 0;
  for (const r of refs(content)) {
    const price = byKey.get(keyOf(r))?.market ?? null;
    if (price === null || unknownKeys.has(keyOf(r))) unpriced += r.qty;
    else value += price * r.qty;
  }
  const sum = (lines: { qty: number }[]) => lines.reduce((total, l) => total + l.qty, 0);
  return {
    mode: '1v1',
    visibility: 'private',
    created_at: '2026-10-01T10:00:00Z',
    updated_at: '2026-11-04T18:30:00Z',
    share: null,
    current_seq: 1,
    ...head,
    content,
    cards,
    unknown_cards: unknown,
    domains: ['Calm', 'Chaos'].filter(() => clean.legend !== null),
    counts: {
      main: sum(content.main),
      runes: sum(content.runes),
      battlefields: content.battlefields.length,
      sideboard: sum(content.sideboard),
      workbench: sum(content.workbench),
    },
    value: round2(value),
    value_unpriced: unpriced,
    legality,
  };
}

/** The `GET /decks` item of a detail. */
export function listItemOf(detail: DeckDetail): DeckListItem {
  const codes = (mode: GameMode) => {
    const seen = detail.legality[mode].issues.map((issue) => issue.code);
    return ISSUE_CODES.filter((code) => seen.includes(code));
  };
  return {
    id: detail.id,
    name: detail.name,
    mode: detail.mode,
    visibility: detail.visibility,
    created_at: detail.created_at,
    updated_at: detail.updated_at,
    share: detail.share,
    legend: detail.content.legend ? (detail.cards[keyOf(detail.content.legend)] ?? null) : null,
    champion: detail.content.champion
      ? (detail.cards[keyOf(detail.content.champion)] ?? null)
      : null,
    domains: detail.domains,
    counts: detail.counts,
    value: detail.value,
    value_unpriced: detail.value_unpriced,
    legal: { '1v1': detail.legality['1v1'].legal, '2v2': detail.legality['2v2'].legal },
    issues: { '1v1': codes('1v1'), '2v2': codes('2v2') },
  };
}

/** The owner's migrated Riven deck: not legal (sideboard 8/10), Zhonya's banned in 2v2. */
export const rivenDeck = deckDetail(
  { id: 41, name: 'Riven, The Exile', updated_at: '2026-11-04T18:30:00Z' },
  rivenContent,
);

/** A complete deck (sideboard 10) without the banned card: legal in both modes. */
export const legalDeck = deckDetail(
  { id: 42, name: 'Riven tournament', mode: '2v2', updated_at: '2026-11-03T09:00:00Z' },
  {
    ...rivenContent,
    main: [
      ...mainCards.filter((c) => c.name !== "Zhonya's Hourglass").map((c) => line(c, 3)),
      line(benchCard, 3),
    ],
    sideboard: sideCards.map((c, index) => line(c, index < 2 ? 3 : 2)),
  },
);

/** A draft: no legend, a few cards, a workbench and a printing missing from the catalog. */
export const draftDeck = deckDetail(
  { id: 43, name: 'Draft ideas', updated_at: '2026-10-20T12:00:00Z' },
  {
    ...emptyContent,
    main: [line(mainCards[0], 2), { set: 'OGN', id: '999', qty: 1 }],
    workbench: [line(benchCard, 2)],
  },
  { unknown: [{ zone: 'main', set: 'OGN', id: '999' }] },
);

export const deckDetails: DeckDetail[] = [rivenDeck, legalDeck, draftDeck];
export const deckList: DeckListItem[] = deckDetails.map(listItemOf);
