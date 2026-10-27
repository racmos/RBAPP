import type { CardSummary } from '@/api/types';

const base: CardSummary = {
  set_id: 'OGN',
  card_id: '1',
  key: 'OGN-1',
  number: '1',
  name: 'Placeholder',
  domains: [],
  type: 'Unit',
  supertype: null,
  type_raw: 'Unit',
  tags: [],
  energy: null,
  power: null,
  might: null,
  rarity: 'Common',
  image_src: '/riftbound/media/cards/ogn/ogn_1.png',
  image_thumb_src: '/riftbound/media/cards/ogn_thumbs/ogn_1.png',
  foilable: false,
  is_base: true,
  price: {
    market: 1.21,
    market_source: 'avg7',
    market_foil: null,
    market_foil_source: null,
    trend_7d_pct: 10,
    trend_30d_pct: 5,
    as_of: '2026-10-25T00:00:00Z',
  },
  bans: { '1v1': false, '2v2': false },
  owned: { total: 0, foil: 0 },
};

export const champion: CardSummary = {
  ...base,
  card_id: '79',
  key: 'OGN-79',
  number: '79',
  name: "Ayla, Fury's Champion",
  domains: ['Fury', 'Chaos'],
  type: 'Unit',
  supertype: 'Champion',
  type_raw: 'Champion Unit',
  tags: ['champion', 'fury'],
  energy: 3,
  power: 4,
  might: 1,
  rarity: 'Rare',
  foilable: true,
  bans: { '1v1': true, '2v2': false },
  owned: { total: 2, foil: 1 },
};

export const foilCommon: CardSummary = {
  ...base,
  card_id: '12',
  key: 'OGN-12',
  number: '12',
  name: 'Ember Wisp',
  domains: ['Fury'],
  type: 'Unit',
  type_raw: 'Unit',
  rarity: 'Common',
  foilable: true,
  price: {
    market: 0.15,
    market_source: 'low',
    market_foil: 0.45,
    market_foil_source: 'avg7_foil',
    trend_7d_pct: null,
    trend_30d_pct: -2,
    as_of: '2026-10-25T00:00:00Z',
  },
};

export const basicRune: CardSummary = {
  ...base,
  card_id: 'r01',
  key: 'OGN-r01',
  number: 'R01',
  name: 'Fury Rune',
  domains: ['Fury'],
  type: 'Rune',
  supertype: 'Basic',
  type_raw: 'Basic Rune',
  foilable: false,
  price: {
    market: 0.05,
    market_source: 'avg7',
    market_foil: null,
    market_foil_source: null,
    trend_7d_pct: null,
    trend_30d_pct: null,
    as_of: '2026-10-25T00:00:00Z',
  },
};

export const token: CardSummary = {
  ...base,
  card_id: 't01',
  key: 'OGN-t01',
  number: null,
  name: 'Spark Token',
  type: 'Unit',
  supertype: 'Token',
  type_raw: 'Token Unit',
  foilable: false,
};

export const noImage: CardSummary = {
  ...base,
  card_id: '999',
  key: 'OGN-999',
  number: '999',
  name: 'Missing Image',
  image_src: null,
  image_thumb_src: null,
};

export const noPrice: CardSummary = {
  ...base,
  card_id: '998',
  key: 'OGN-998',
  number: '998',
  name: 'No Price Yet',
  price: null,
};
