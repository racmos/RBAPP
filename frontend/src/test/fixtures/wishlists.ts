import type { CardMini, CardSummary, Wishlist, WishlistLine } from '@/api/types';
import { basicRune, champion, foilCommon, token } from './cards';

const STAMP = '2026-11-10T09:00:00Z';

/** The `CardMini` the API puts on a line, from a catalog card. */
export const miniOf = (card: CardSummary, owned = 0): CardMini => ({
  set_id: card.set_id,
  card_id: card.card_id,
  key: card.key,
  name: card.name,
  domains: card.domains,
  type: card.type,
  supertype: card.supertype,
  rarity: card.rarity,
  image_src: card.image_src,
  image_thumb_src: card.image_thumb_src,
  is_base: card.is_base,
  market: card.price?.market ?? null,
  owned_total: owned,
});

export const wishlist = (
  overrides: Partial<Wishlist> & { id: number; name: string },
): Wishlist => ({
  is_default: false,
  position: 1,
  line_count: 0,
  created_at: STAMP,
  updated_at: STAMP,
  ...overrides,
});

const zeroOwned = () => ({
  this_version: { total: 0, foil: 0 },
  other_versions: { total: 0, alt_art: 0, foil: 0 },
});

export const line = (
  overrides: Partial<WishlistLine> & { id: number; list_id: number; name: string },
): WishlistLine => ({
  set_id: null,
  card_id: null,
  card: null,
  foil: 'any',
  qty: 1,
  max_price: null,
  note: null,
  created_at: STAMP,
  updated_at: STAMP,
  market: null,
  reached: null,
  owned: zeroOwned(),
  ...overrides,
});

/** Ayla (a printing): owned of this version and of other versions, max price reached. */
export const aylaWish = line({
  id: 101,
  list_id: 1,
  name: champion.name,
  set_id: 'OGN',
  card_id: '79',
  card: miniOf(champion, 3),
  qty: 2,
  max_price: 3,
  note: 'For the fury deck',
  market: {
    value: 1.21,
    source: 'avg7',
    as_of: '2026-10-25T00:00:00Z',
    set_id: 'OGN',
    card_id: '79',
    foil: false,
  },
  reached: true,
  owned: {
    this_version: { total: 3, foil: 1 },
    other_versions: { total: 2, alt_art: 1, foil: 0 },
  },
});

/** Ember Wisp foil, no alert price, nothing owned. */
export const emberWish = line({
  id: 102,
  list_id: 1,
  name: foilCommon.name,
  set_id: 'OGN',
  card_id: '12',
  card: miniOf(foilCommon),
  foil: 'S',
  qty: 4,
  market: {
    value: 0.45,
    source: 'avg7_foil',
    as_of: '2026-10-25T00:00:00Z',
    set_id: 'OGN',
    card_id: '12',
    foil: true,
  },
});

/** Fury Rune by name (any printing), max price not reached, no market price. */
export const runeWish = line({
  id: 103,
  list_id: 1,
  name: basicRune.name,
  card: miniOf(basicRune),
  max_price: 0.01,
  reached: false,
  owned: {
    this_version: { total: 1, foil: 0 },
    other_versions: { total: 0, alt_art: 0, foil: 0 },
  },
});

export const tokenWish = line({
  id: 201,
  list_id: 2,
  name: token.name,
  set_id: 'OGN',
  card_id: 't01',
  card: miniOf(token),
});

export const defaultList = wishlist({
  id: 1,
  name: 'Wishlist',
  is_default: true,
  position: 1,
  line_count: 3,
});
export const tradesList = wishlist({ id: 2, name: 'Trades', position: 2, line_count: 1 });

export const wishlistLines: WishlistLine[] = [aylaWish, emberWish, runeWish, tokenWish];
