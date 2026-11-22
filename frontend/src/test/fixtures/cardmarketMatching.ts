/** MSW data and handlers of the Cardmarket matching workbench (CM-b). */
import { http, type JsonBodyType } from 'msw';
import type { AdminCard } from '@/api/endpoints';
import { API, adminSession, failure, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';

export const STATUS = {
  last_load: { date: '2026-11-06', status: 'success', loaded_at: '2026-11-06T05:30:14' },
  loaded_today: true,
  job: null,
  unmatched: 305,
  unmapped_expansions: 2,
  prices_as_of: '2026-11-06',
};

const ORIGINS = { id: 6286, name: 'Origins', set_id: 'OGN' };

export const AHRI = {
  id_product: 501,
  name: 'Ahri, Alluring',
  type: 'single',
  category: 'Riftbound Single',
  expansion: ORIGINS,
  low_price: 0.12,
  first_seen_date: '2026-11-01',
  suggestions: [
    {
      kind: 'card',
      id: 'OGN-066',
      name: 'Ahri, Alluring',
      set: 'OGN',
      number: '066',
      score: 1,
      free_foils: ['N', 'S'],
    },
    {
      kind: 'card',
      id: 'OGS-005',
      name: 'Ahri, Alluring',
      set: 'OGS',
      number: '005',
      score: 0.9,
      free_foils: [null],
    },
    {
      kind: 'card',
      id: 'OGN-299',
      name: 'Ahri, Alluring',
      set: 'OGN',
      number: '299',
      score: 0.9,
      free_foils: [],
    },
  ],
};

export const BOX = {
  id_product: 777,
  name: 'Origins Booster Box',
  type: 'nonsingle',
  category: 'Riftbound Booster Box',
  expansion: null,
  low_price: 95,
  first_seen_date: '2026-10-01',
  suggestions: [
    {
      kind: 'product',
      id: 777,
      name: 'Origins Booster Box',
      set: 'OGN',
      number: null,
      score: 1,
      free_foils: [],
    },
  ],
};

export const MYSTERY = {
  ...AHRI,
  id_product: 502,
  name: 'Mystery Card',
  expansion: null,
  low_price: null,
  suggestions: [],
};

export const unmatchedList = (items: unknown[] = [AHRI, BOX, MYSTERY], total = items.length) => ({
  items,
  meta: {
    page: 1,
    per_page: 50,
    total,
    pages: Math.max(1, Math.ceil(total / 50)),
    date: '2026-11-06',
  },
});

export const CANDIDATES = {
  product: {
    id_product: 501,
    name: 'Ahri, Alluring',
    type: 'single',
    category: 'Riftbound Single',
    expansion: ORIGINS,
    date: '2026-11-06',
    link: null,
  },
  cards: [
    {
      set_id: 'OGN',
      card_id: '066',
      name: 'Ahri, Alluring',
      rarity: 'Common',
      type: 'Unit',
      image_src: '/riftbound/media/cards/ogn/066.webp',
      links: [],
    },
    {
      set_id: 'OGN',
      card_id: '299',
      name: 'Ahri, Alluring',
      rarity: 'Showcase',
      type: 'Unit',
      image_src: null,
      links: [{ id_product: 900, foil: null }],
    },
  ],
  products: [],
};

export const link = (
  id: number,
  setId: string,
  cardId: string,
  foil: 'N' | 'S' | null,
  extra: Record<string, unknown> = {},
) => ({
  id_product: id,
  product_name: `Product ${id}`,
  product_type: 'single',
  in_latest_load: true,
  set_id: setId,
  card_id: cardId,
  card_name: `Card ${cardId}`,
  foil,
  match_type: 'auto',
  confidence: 0.7,
  low_price: 1.5,
  price_date: '2026-11-06',
  ...extra,
});

export const LINKS = [
  link(601, 'OGN', '066', 'N'),
  link(602, 'OGN', '067', null, { match_type: 'manual', in_latest_load: false, low_price: null }),
];

export const CONFLICTS = [
  link(701, 'OGN', '010', 'N'),
  link(702, 'OGN', '010', 'N'),
  link(703, 'OGN', '020', null),
  link(704, 'OGN', '020', null),
];

export const linkList = (items: unknown[], conflictSlots = 0) => ({
  items,
  meta: { page: 1, per_page: 50, total: items.length, pages: 1, conflict_slots: conflictSlots },
});

export const IGNORED = [
  { id_product: 801, name: 'Token Pack', low_price: 1.5, ignored_at: '2026-11-05T10:00:00' },
];

const PROPOSED = [
  {
    id_product: 503,
    product_name: 'Garen, Rugged',
    low_price: 0.2,
    set_id: 'OGN',
    card_id: '100',
    card_name: 'Garen, Rugged',
    foil: 'N',
  },
];

export const REVIEW_ITEM = {
  product_id: 501,
  name: 'Ahri, Alluring',
  expansion_id: 6286,
  reason: 'ambiguous',
  candidates: [
    { set: 'OGN', id: '066', name: 'Ahri, Alluring' },
    { set: 'OGS', id: '005', name: 'Ahri, Alluring' },
  ],
};

export const PREVIEW = {
  date: '2026-11-06',
  proposed: 5,
  clear: 3,
  doubtful: 2,
  links: PROPOSED,
  review: [REVIEW_ITEM],
  review_total: 2,
};

export const reviewList = (items: unknown[] = [REVIEW_ITEM]) => ({
  items,
  meta: {
    page: 1,
    per_page: 50,
    total: items.length,
    pages: 1,
    date: '2026-11-06',
    reasons: { ambiguous: 1, no_candidates: 3 },
  },
});

/** `GET /admin/sets` (the set select of the create-card form, CM-c). */
export const ADMIN_SETS = [
  {
    id: 'OGS',
    name: 'Proving Grounds',
    release_date: '2025-09-01',
    card_count: 24,
    declared_count: 24,
    window: 'none',
    next_run_at: null,
  },
  {
    id: 'OGN',
    name: 'Origins',
    release_date: '2025-10-31',
    card_count: 298,
    declared_count: 298,
    window: 'none',
    next_run_at: null,
  },
];

/** `GET /admin/cardmarket/expansions` (CM-d): the sets they map to, newest release first. */
export const EXPANSION_SETS = [
  { id: 'OGN', name: 'Origins', release_date: '2025-10-31' },
  { id: 'OGS', name: 'Proving Grounds', release_date: '2025-09-01' },
];

export const expansion = (
  id: number,
  name: string | null,
  setId: string | null,
  extra: Record<string, unknown> = {},
) => ({
  id,
  name,
  products_count: 0,
  singles_count: 0,
  sealed_count: 0,
  mapped_set_id: setId,
  mapped_set_name: EXPANSION_SETS.find((one) => one.id === setId)?.name ?? null,
  sample_products: [] as unknown[],
  price_range: null as { min: number; max: number } | null,
  first_seen: null as string | null,
  suggested_set_id: null as string | null,
  suggested_set_name: null as string | null,
  suggested_confidence: null as number | null,
  suggested_count: null as number | null,
  linked_count: 0,
  ...extra,
});

export const sampleProduct = (
  id_product: number,
  name: string,
  low_price: number | null,
  type = 'single',
) => ({ id_product, name, type, low_price });

/** An expansion Cardmarket gives no name, with the context that tells it apart. */
export const UNNAMED = expansion(6567, null, null, {
  products_count: 120,
  singles_count: 115,
  sealed_count: 5,
  sample_products: [
    sampleProduct(9001, 'Ahri, Nine-Tailed Fox', 34),
    sampleProduct(9002, 'Vi, Enforcer', 12.5),
    sampleProduct(9003, 'Jinx, Loose Cannon', 3.2),
    sampleProduct(9101, 'Proving Grounds Booster Box', 95, 'nonsingle'),
    sampleProduct(9102, 'Proving Grounds Booster', null, 'nonsingle'),
  ],
  price_range: { min: 0.02, max: 34 },
  first_seen: '2025-07-14',
  suggested_set_id: 'OGS',
  suggested_set_name: 'Proving Grounds',
  suggested_confidence: 0.8,
  suggested_count: 4,
  linked_count: 5,
});

export const EXPANSIONS = [
  expansion(6399, 'Spiritforged', null, {
    products_count: 310,
    singles_count: 300,
    sealed_count: 10,
  }),
  expansion(6400, 'Arcane Box Set', null),
  expansion(6286, 'Origins', 'OGN', {
    products_count: 1250,
    singles_count: 1200,
    sealed_count: 50,
    // its linked cards point to the set it is mapped to: no hint
    suggested_set_id: 'OGN',
    suggested_set_name: 'Origins',
    suggested_confidence: 1,
    suggested_count: 900,
    linked_count: 900,
  }),
];

const NO_PRICES = null as null | Record<string, number | null>;

/** A product of `GET /admin/cardmarket/expansions/<id>/products` (CM-f). */
export const expansionProduct = (
  id_product: number,
  name: string,
  extra: Record<string, unknown> = {},
) => ({
  id_product,
  name,
  type: 'single' as 'single' | 'sealed',
  kind: 'card' as string,
  category: 'Riftbound Single' as string | null,
  category_id: 1 as number | null,
  date_added: null as string | null,
  price: null as number | null,
  price_source: null as 'low' | 'avg7' | 'trend' | null,
  prices: NO_PRICES,
  linked: null as { set_id: string; card_id: string; foil: 'N' | 'S' | null } | null,
  catalog: null as { kind: string | null; set_id: string | null } | null,
  ...extra,
});

export const prices = (values: Record<string, number>) => ({
  low: null,
  trend: null,
  avg7: null,
  avg30: null,
  avg: null,
  low_foil: null,
  trend_foil: null,
  ...values,
});

/** The products of an expansion on the latest load: a linked single, a catalog box, an unpriced one. */
export const EXPANSION_PRODUCTS = [
  expansionProduct(9101, 'Proving Grounds Booster Box', {
    type: 'sealed',
    kind: 'booster_box',
    category: 'Riftbound Booster Box',
    category_id: 2,
    date_added: '2025-07-14',
    price: 95,
    price_source: 'avg7',
    prices: prices({ low: 90, trend: 97.5, avg7: 95, avg30: 96, avg: 94 }),
    catalog: { kind: 'booster_box', set_id: 'OGS' },
  }),
  expansionProduct(9001, 'Ahri, Nine-Tailed Fox', {
    date_added: '2025-07-15',
    price: 34,
    price_source: 'low',
    prices: prices({
      low: 34,
      trend: 36.1,
      avg7: 35,
      avg30: 33,
      avg: 34.5,
      low_foil: 60,
      trend_foil: 64,
    }),
    linked: { set_id: 'OGS', card_id: '001', foil: 'N' },
  }),
  expansionProduct(9003, 'Jinx, Loose Cannon'),
];

/** The kinds of the counters (CM-g, taxonomy 2026-11-20): card, the product kinds, unused. */
const KIND_ORDER = [
  'card',
  'booster',
  'booster_box',
  'champion_deck',
  'sealed_box_set',
  'accessory',
  'other',
  'unused',
];

export type KindCount = { kind: string; count: number };

/** `meta.kinds` of `products`: the count of each kind present, in the counters' order. */
export const kindCounts = (products: { kind: string }[]): KindCount[] =>
  KIND_ORDER.map((kind) => ({
    kind,
    count: products.filter((one) => one.kind === kind).length,
  })).filter((one) => one.count > 0);

/**
 * The answer of the products endpoint for one request: `items` filtered by `type`, `kind` and
 * `q` (a name search ignoring case) and paged by `page` / `per_page`, with the figures of the
 * whole expansion in `meta` (`kinds` from `products`, unless given).
 */
export function expansionProductsAnswer(
  item: ReturnType<typeof expansion>,
  products: ReturnType<typeof expansionProduct>[],
  search: URLSearchParams,
  kinds: KindCount[] = kindCounts(products),
) {
  const type = search.get('type') ?? 'all';
  const kind = search.get('kind') ?? 'all';
  const q = (search.get('q') ?? '').toLowerCase();
  const page = Number(search.get('page') ?? 1);
  const perPage = Number(search.get('per_page') ?? 50);
  const found = products.filter(
    (one) =>
      (type === 'all' || one.type === type) &&
      (kind === 'all' || one.kind === kind) &&
      one.name.toLowerCase().includes(q),
  );
  return {
    expansion: {
      id: item.id,
      name: item.name,
      mapped_set_id: item.mapped_set_id,
      mapped_set_name: item.mapped_set_name,
    },
    items: found.slice((page - 1) * perPage, page * perPage),
    meta: {
      page,
      per_page: perPage,
      total: found.length,
      pages: Math.max(1, Math.ceil(found.length / perPage)),
      singles: item.singles_count,
      sealed: item.sealed_count,
      kinds,
      price_range: item.price_range,
      first_seen: item.first_seen,
      date: '2026-11-06',
    },
  };
}

/** Missing promo cards (CM-h): the promo sets and the plan of OGNX. */
export const PROMO_SETS = [
  {
    id: 'OGNX',
    name: 'Origins Promos',
    base: 'OGN',
    base_name: 'Origins',
    expansions: [6322],
    products_missing: 3,
    cards_to_create: 2,
  },
  {
    id: 'SFDX',
    name: 'Spiritforged Promos',
    base: 'SFD',
    base_name: 'Spiritforged',
    expansions: [6483],
    products_missing: 0,
    cards_to_create: 0,
  },
];

const baseCard = (cardId: string, name: string, rarity: string, type = 'Unit') => ({
  set_id: 'OGN',
  card_id: cardId,
  name,
  rarity,
  type,
});

export const promoItem = (
  id: number,
  name: string,
  price: number | null,
  extra: Record<string, unknown> = {},
) => ({
  product_id: id,
  product_ids: [id],
  product_name: name,
  price,
  expansion_id: 6322,
  products: [{ id, name, price, foil: null as 'N' | 'S' | null }],
  base: null as ReturnType<typeof baseCard> | null,
  proposed: null as { set_id: string; card_id: string } | null,
  status: 'manual',
  reason: 'no_base_card',
  ...extra,
});

export const PROMO_ITEMS = [
  promoItem(1011, 'Already There', 1.5, {
    base: baseCard('077', 'Already There', 'Rare'),
    proposed: { set_id: 'OGNX', card_id: '077' },
    status: 'exists',
    reason: 'in_catalog',
  }),
  promoItem(1002, 'Little Spark', 0.5, {
    product_ids: [1002, 1003],
    products: [
      { id: 1002, name: 'Little Spark', price: 0.5, foil: 'N' },
      { id: 1003, name: 'Little Spark (Foil)', price: 2, foil: 'S' },
    ],
    base: baseCard('010', 'Little Spark', 'Common'),
    proposed: { set_id: 'OGNX', card_id: '010' },
    status: 'create',
    reason: 'clone',
  }),
  promoItem(1004, 'Little Spark', 3, {
    base: baseCard('010', 'Little Spark', 'Common'),
    reason: 'no_slot',
  }),
  promoItem(1010, 'Nobody Known', 0.1),
  promoItem(1001, 'Vayne, Hunter', 12, {
    base: baseCard('035', 'Vayne, Hunter', 'Rare'),
    proposed: { set_id: 'OGNX', card_id: '035' },
    status: 'create',
    reason: 'clone',
  }),
];

export const promoPlan = (items = PROMO_ITEMS) => ({
  set: {
    id: 'OGNX',
    name: 'Origins Promos',
    base: 'OGN',
    base_name: 'Origins',
    expansions: [6322],
  },
  date: '2026-11-06',
  items,
  summary: {
    cards_to_create: items.filter((one) => one.status === 'create').length,
    products_to_create: items
      .filter((one) => one.status === 'create')
      .reduce((sum, one) => sum + one.product_ids.length, 0),
    exists: items
      .filter((one) => one.status === 'exists')
      .reduce((sum, one) => sum + one.product_ids.length, 0),
    manual: items
      .filter((one) => one.status === 'manual')
      .reduce((sum, one) => sum + one.product_ids.length, 0),
    products: items.reduce((sum, one) => sum + one.product_ids.length, 0),
  },
});

/** The `AdminCard` the API answers a create with: the card id lower-cased, as the server does. */
export const adminCard = (body: Record<string, unknown>) => {
  const setId = String(body.set_id);
  const cardId = String(body.card_id).toLowerCase();
  return {
    domain: null,
    type: null,
    tags: null,
    energy: null,
    power: null,
    might: null,
    ability: null,
    rarity: null,
    artist: null,
    image_url: null,
    ...body,
    set_id: setId,
    card_id: cardId,
    key: `${setId}-${cardId}`,
    image: null,
    image_src: null,
  };
};

/** A catalog card of `GET /admin/cards` (the "Copy from an existing card" search, CM-i). */
export const catalogCard = (
  setId: string,
  cardId: string,
  name: string,
  extra: Partial<AdminCard> = {},
): AdminCard => ({
  ...(adminCard({ set_id: setId, card_id: cardId, name }) as AdminCard),
  ...extra,
});

export const CATALOG_CARDS = [
  catalogCard('OGN', '007', 'Fury Rune', {
    type: 'Rune',
    domain: 'Fury',
    rarity: 'Common',
    artist: 'Kudos Productions',
    ability: 'Exhaust: add 1 Fury power.',
    image_src: '/riftbound/media/cards/ogn/007.webp',
  }),
  catalogCard('OGN', '042', 'Calm Rune', { type: 'Rune', domain: 'Calm', rarity: 'Common' }),
  catalogCard('UNLX', '001', 'Fury Rune', { type: 'Rune', domain: 'Fury', rarity: 'Showcase' }),
  catalogCard('OGN', '066', 'Ahri, Alluring', {
    type: 'Unit',
    domain: 'Calm',
    tags: 'Ahri',
    energy: 3,
    power: 1,
    might: 3,
    rarity: 'Common',
    artist: 'Someone',
    ability: 'When you play me, draw 1.',
  }),
];

/**
 * `GET /admin/cards` over `cards` as the server filters: `q` a name part or a `SET-ID`
 * code, `set` one of the sets, `type` a part of the type; first page of `per_page`.
 */
export function adminCardsAnswer(cards: AdminCard[], search: URLSearchParams) {
  const q = (search.get('q') ?? '').toLowerCase();
  const sets = search.getAll('set');
  const type = (search.get('type') ?? '').toLowerCase();
  const perPage = Number(search.get('per_page') ?? 50);
  const found = cards.filter(
    (card) =>
      (q === '' || card.name.toLowerCase().includes(q) || card.key.toLowerCase() === q) &&
      (sets.length === 0 || sets.includes(card.set_id)) &&
      (type === '' || (card.type ?? '').toLowerCase().includes(type)),
  );
  return {
    items: found.slice(0, perPage),
    meta: { page: 1, per_page: perPage, total: found.length, pages: 1 },
  };
}

/** Where the admin cards endpoint is recorded: outside the `/admin/cardmarket` base. */
export const CARDS_PATH = `${API}/admin/cards`;

export type Call = { method: string; path: string; search: URLSearchParams; body: unknown };

const BASE = `${API}/admin/cardmarket`;

/**
 * An admin session and every matching endpoint, answering with the fixtures above. Each
 * request is recorded in `calls`; tests override one endpoint with `server.use(...)`.
 */
export function matchingApi({
  unmatched = unmatchedList() as JsonBodyType,
  links = linkList(LINKS) as JsonBodyType,
  conflicts = linkList(CONFLICTS, 2) as JsonBodyType,
  ignored = IGNORED as unknown[],
  review = reviewList() as JsonBodyType,
  expansions = EXPANSIONS as ReturnType<typeof expansion>[],
  products = EXPANSION_PRODUCTS as ReturnType<typeof expansionProduct>[],
  kinds = undefined as KindCount[] | undefined,
  promoSets = PROMO_SETS as unknown[],
  promo = promoPlan() as JsonBodyType,
  catalog = CATALOG_CARDS as AdminCard[],
} = {}) {
  const calls: Call[] = [];
  const record = async (request: Request) => {
    const url = new URL(request.url);
    const text = request.method === 'GET' ? '' : await request.clone().text();
    calls.push({
      method: request.method,
      path: url.pathname.replace(BASE, ''),
      search: url.searchParams,
      body: text ? JSON.parse(text) : undefined,
    });
  };
  server.use(
    http.get(`${API}/auth/session`, () => adminSession()),
    http.get(`${API}/admin/overview`, () =>
      ok({
        catalog: { sets: 1, sets_without_release_date: 0, cards: 1, cards_without_image: 0 },
        riot: { pending_changes: 0, active_sets: [], last_sync: null, placeholder_sets: [] },
      }),
    ),
    http.get(`${BASE}/status`, async ({ request }) => {
      await record(request);
      return ok(STATUS);
    }),
    http.get(`${API}/admin/sets`, () => ok(ADMIN_SETS)),
    http.get(`${API}/admin/cards`, async ({ request }) => {
      await record(request);
      return ok(adminCardsAnswer(catalog, new URL(request.url).searchParams));
    }),
    http.post(`${API}/admin/cards`, async ({ request }) => {
      await record(request);
      const body = (await request.json()) as Record<string, unknown>;
      return ok(adminCard(body), 201);
    }),
    http.get(`${BASE}/unmatched`, async ({ request }) => {
      await record(request);
      return ok(unmatched);
    }),
    http.get(`${BASE}/unmatched/:id/candidates`, async ({ request }) => {
      await record(request);
      return ok(CANDIDATES);
    }),
    http.get(`${BASE}/links`, async ({ request }) => {
      await record(request);
      return ok(new URL(request.url).searchParams.get('conflicts') ? conflicts : links);
    }),
    http.post(`${BASE}/links`, async ({ request }) => {
      await record(request);
      const body = (await request.json()) as {
        id_product: number;
        card: { set_id: string; card_id: string };
        foil: 'N' | 'S' | null;
      };
      return ok(
        link(body.id_product, body.card.set_id, body.card.card_id, body.foil, {
          match_type: 'manual',
          product_name: 'Ahri, Alluring',
        }),
        201,
      );
    }),
    http.put(`${BASE}/links/:id`, async ({ request, params }) => {
      await record(request);
      const body = (await request.json()) as {
        card: { set_id: string; card_id: string };
        foil: 'N' | 'S' | null;
      };
      const id = Number(params.id);
      return ok({
        link: link(id, body.card.set_id, body.card.card_id, body.foil, { match_type: 'manual' }),
        previous: LINKS.find((one) => one.id_product === id) ?? link(id, 'OGN', '066', 'N'),
      });
    }),
    http.delete(`${BASE}/links/:id`, async ({ request, params }) => {
      await record(request);
      const id = Number(params.id);
      return ok({
        link: LINKS.find((one) => one.id_product === id) ?? link(id, 'OGN', '066', 'N'),
      });
    }),
    http.get(`${BASE}/ignored`, async ({ request }) => {
      await record(request);
      return ok({ items: ignored });
    }),
    http.post(`${BASE}/ignored`, async ({ request }) => {
      await record(request);
      const body = (await request.json()) as { id_product: number; name: string };
      return ok(
        { item: { ...body, low_price: null, ignored_at: '2026-11-07T10:00:00' }, created: true },
        201,
      );
    }),
    http.delete(`${BASE}/ignored/:id`, async ({ request, params }) => {
      await record(request);
      const name = new URL(request.url).searchParams.get('name') ?? '';
      return ok({ removed: [{ id_product: Number(params.id), name }] });
    }),
    http.post(`${BASE}/auto-match/preview`, async ({ request }) => {
      await record(request);
      return ok(PREVIEW);
    }),
    http.post(`${BASE}/auto-match/apply`, async ({ request }) => {
      await record(request);
      return ok({
        date: '2026-11-06',
        linked: 3,
        clear: 3,
        remaining_clear: 0,
        doubtful: 2,
        links: PROPOSED,
      });
    }),
    http.get(`${BASE}/review`, async ({ request }) => {
      await record(request);
      return ok(review);
    }),
    http.get(`${BASE}/expansions`, async ({ request }) => {
      await record(request);
      const unmapped = new URL(request.url).searchParams.get('unmapped') === 'true';
      const items = expansions.filter((one) => !unmapped || one.mapped_set_id === null);
      return ok({
        items,
        sets: EXPANSION_SETS,
        meta: {
          unmapped: expansions.filter((one) => one.mapped_set_id === null).length,
          total: items.length,
          date: '2026-11-06',
        },
      });
    }),
    http.put(`${BASE}/expansions/:id`, async ({ request, params }) => {
      await record(request);
      const body = (await request.json()) as {
        set_id: string;
        create_set?: { name: string; release_date: string; declared_count: number | null };
      };
      const current = expansions.find((one) => one.id === Number(params.id))!;
      const setId = body.create_set ? body.set_id.toUpperCase() : body.set_id;
      return ok({
        expansion: {
          ...current,
          mapped_set_id: setId,
          mapped_set_name:
            body.create_set?.name ?? EXPANSION_SETS.find((one) => one.id === setId)?.name ?? null,
        },
        previous: current.mapped_set_id,
        created_set: body.create_set
          ? {
              id: setId,
              name: body.create_set.name,
              release_date: body.create_set.release_date,
              card_count: 0,
              declared_count: body.create_set.declared_count,
              window: 'none',
              next_run_at: null,
            }
          : null,
      });
    }),
    http.get(`${BASE}/expansions/:id/products`, async ({ request, params }) => {
      await record(request);
      const current = expansions.find((one) => one.id === Number(params.id));
      if (!current) {
        return failure(404, {
          error: 'Not Found',
          message: `Cardmarket expansion ${String(params.id)} not found.`,
        });
      }
      return ok(
        expansionProductsAnswer(current, products, new URL(request.url).searchParams, kinds),
      );
    }),
    http.get(`${BASE}/promo-cards`, async ({ request }) => {
      await record(request);
      const set = new URL(request.url).searchParams.get('set');
      if (set === null) return ok({ date: '2026-11-06', sets: promoSets });
      if (set !== 'OGNX') {
        const message = `${set} is not a promo set: a promo set id is its base set id followed by X (OGN -> OGNX).`;
        return failure(400, { error: 'Validation Error', message, code: 'validation_error' });
      }
      return ok(promo);
    }),
    http.post(`${BASE}/promo-cards`, async ({ request }) => {
      await record(request);
      const body = (await request.json()) as { set_id: string; product_ids: number[] };
      const chosen = PROMO_ITEMS.filter(
        (one) =>
          one.status === 'create' && one.product_ids.some((id) => body.product_ids.includes(id)),
      );
      return ok(
        {
          created: chosen.map((one) => ({
            set_id: body.set_id,
            card_id: one.proposed!.card_id,
            name: one.base!.name,
            base: { set_id: 'OGN', card_id: one.base!.card_id },
            product_ids: one.product_ids,
          })),
          skipped: [],
        },
        chosen.length > 0 ? 201 : 200,
      );
    }),
    http.delete(`${BASE}/expansions/:id/mapping`, async ({ request, params }) => {
      await record(request);
      const current = expansions.find((one) => one.id === Number(params.id))!;
      return ok({
        expansion: { ...current, mapped_set_id: null, mapped_set_name: null },
        previous: current.mapped_set_id,
      });
    }),
  );
  return calls;
}

/** The recorded calls of one method and path (without the `/admin/cardmarket` base). */
export const callsTo = (calls: Call[], method: string, path: string | RegExp) =>
  calls.filter(
    (call) =>
      call.method === method &&
      (typeof path === 'string' ? call.path === path : path.test(call.path)),
  );
