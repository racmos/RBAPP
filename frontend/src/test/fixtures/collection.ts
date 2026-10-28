import type {
  CollectionGroup,
  CollectionLine,
  CollectionLineWithCard,
  CollectionMeta,
} from '@/api/types';
import { champion, foilCommon, basicRune } from './cards';

const line = (overrides: Partial<CollectionLine>): CollectionLine => ({
  id: 1,
  foil: false,
  qty: 1,
  condition: 'NM',
  language: 'English',
  purchase_price: null,
  selling: false,
  sell_qty: 0,
  sell_price: null,
  updated_at: '2026-10-25T09:12:00Z',
  market: 1.21,
  value: 1.21,
  pl_abs: null,
  pl_pct: null,
  ...overrides,
});

/** Ayla: two lines, 4 copies of which 2 are for sale: 2 kept of a playset of 3 (short). */
export const aylaLines: CollectionLine[] = [
  line({
    id: 1201,
    qty: 3,
    purchase_price: 0.8,
    selling: true,
    sell_qty: 2,
    sell_price: 1.3,
    value: 3.63,
    pl_abs: 1.23,
    pl_pct: 50.6,
  }),
  line({ id: 1202, qty: 1, condition: 'EX', language: 'Spanish', value: 1.21 }),
];

export const aylaGroup: CollectionGroup = {
  key: 'OGN-79:N',
  card: { ...champion, owned: { total: 4, foil: 0 } },
  foil: false,
  qty: 4,
  sell_qty: 2,
  value: 4.84,
  lines: aylaLines,
  keep_playset: true,
  playset_short: true,
  kept: 2,
};

export const emberLines: CollectionLine[] = [
  line({ id: 1301, foil: true, qty: 2, market: 2.5, value: 5, condition: 'MT' }),
];

export const emberGroup: CollectionGroup = {
  key: 'OGN-12:S',
  card: foilCommon,
  foil: true,
  qty: 2,
  sell_qty: 0,
  value: 5,
  lines: emberLines,
  keep_playset: false,
  playset_short: false,
  kept: 2,
};

export const runeGroup: CollectionGroup = {
  key: 'OGN-21:N',
  card: basicRune,
  foil: false,
  qty: 10,
  sell_qty: 0,
  value: null,
  lines: [line({ id: 1401, qty: 10, market: null, value: null })],
  keep_playset: false,
  playset_short: false,
  kept: 10,
};

export const collectionGroups: CollectionGroup[] = [aylaGroup, emberGroup, runeGroup];

export const collectionMeta: CollectionMeta = {
  page: 1,
  per_page: 50,
  total_groups: 3,
  pages: 1,
  totals: {
    lines: 4,
    qty: 16,
    unique: 3,
    value: 9.84,
    cost: 2.4,
    pl: 1.23,
    selling_value: 1.3,
    foil_pct: 12.5,
  },
  facets: {
    set: { OGN: 3 },
    rarity: { Common: 2, Rare: 1 },
    condition: { MT: 1, NM: 2, EX: 1 },
    language: { English: 3, Spanish: 1 },
    foil: { foil: 1, nonfoil: 2 },
  },
  price_as_of: '2026-10-25',
  playset_size: 3,
};

export const withCard = (line: CollectionLine, card = champion): CollectionLineWithCard => ({
  ...line,
  set_id: card.set_id,
  card_id: card.card_id,
});
