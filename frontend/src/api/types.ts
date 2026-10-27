/** Shapes of the JSON API v1 (`/riftbound/api/v1`). Mirrors the backend envelope (API-1). */

export type UserPayload = { id: number; username: string; email: string; is_admin: boolean };

/** The five interface preferences; `null` means Auto (PREF-2). */
export type Prefs = {
  lang: 'es' | 'en' | null;
  density: 'compact' | 'regular' | 'comfy' | null;
  accent: 'orange' | 'cyan' | null;
  bg_intensity: number | null;
  collection_view: 'table' | 'grid' | null;
};

/** `GET /auth/session`. `user` and `prefs` exist only when `authenticated`. */
export type SessionData = {
  authenticated: boolean;
  csrf_token: string;
  user?: UserPayload;
  prefs?: Prefs;
};

/** What the app keeps of the session; the CSRF token lives in `csrf.ts`, never in the cache. */
export type Session = { authenticated: boolean; user: UserPayload | null; prefs: Prefs | null };

export type CaptchaData = { provider: string; challenge: Record<string, unknown> | null };

export type MetaConfig = {
  env: string;
  registration_open: boolean;
  captcha: { provider: string; required_for: string[] };
  csrf: { header: string };
};

export type LoginBody = { username: string; password: string; remember: boolean };
export type RegisterBody = { username: string; email: string; password: string; altcha?: string };

export type ErrorParams = Record<string, string | number | boolean>;

/** One item of `details[]` in a validation error. */
/** `GET /admin/overview` (F13-a). */
export type AdminCatalog = {
  sets: number;
  sets_without_release_date: number;
  cards: number;
  cards_without_image: number;
};

/** One item of `details[]` in a validation error. */
export type ErrorDetail = {
  field: string;
  message: string;
  type: string;
  code?: string;
  params?: ErrorParams;
};

export type GameMode = '1v1' | '2v2';
export type CardBans = Record<GameMode, boolean>;

export type CardOwned = {
  total: number;
  foil: number;
};

export type CardPrice = {
  market: number | null;
  market_source: string | null;
  market_foil: number | null;
  market_foil_source: string | null;
  trend_7d_pct: number | null;
  trend_30d_pct: number | null;
  as_of: string | null;
};

/** Mini card shape used for printings and related cards (F2-d). */
export type CardMini = {
  set_id: string;
  card_id: string;
  key: string;
  number: string | null;
  name: string;
  rarity: string;
  image_src: string | null;
  image_thumb_src: string | null;
  price: CardPrice | null;
};

/** Latest Cardmarket price row for a card (F2-d). */
export type CardPriceDetail = {
  date: string;
  product_id: number | null;
  columns: {
    avg7: number | null;
    avg7_foil: number | null;
    avg30: number | null;
    avg30_foil: number | null;
    low: number | null;
    low_foil: number | null;
    trend: number | null;
    trend_foil: number | null;
    avg: number | null;
    avg_foil: number | null;
  };
  foil_product_id: number | null;
  foil_columns: {
    avg7: number | null;
    avg7_foil: number | null;
    avg30: number | null;
    avg30_foil: number | null;
    low: number | null;
    low_foil: number | null;
    trend: number | null;
    trend_foil: number | null;
    avg: number | null;
    avg_foil: number | null;
  };
};

/** One daily price point for a card (F2-d). */
export type PricePoint = {
  date: string;
  market: number | null;
  low: number | null;
  avg7: number | null;
  avg30: number | null;
  market_foil: number | null;
};

/** `GET /meta/game` (F2-h S2). */
export type GameMeta = {
  modes: string[];
  domains: string[];
  types: string[];
  supertypes: string[];
  rarities: string[];
  sets: { id: string; name: string; released_on: string | null; card_count: number }[];
  price: { provider: string; currency: string; updated_on: string | null };
  rules: Record<string, unknown>;
};

export type CardListSort =
  'number' | 'name' | 'price' | 'trend_7d' | 'trend_30d' | 'rarity' | 'energy' | 'power' | 'might';

export type CardListParams = {
  q?: string;
  text?: string;
  set?: string[];
  domain?: string[];
  type?: string[];
  supertype?: string[];
  exclude_supertype?: string[];
  rarity?: string[];
  tag?: string[];
  domain_match?: 'any' | 'all' | 'subset';
  energy_min?: number;
  energy_max?: number;
  power_min?: number;
  power_max?: number;
  might_min?: number;
  might_max?: number;
  price_min?: number;
  price_max?: number;
  owned?: 'any' | 'owned' | 'missing';
  banned_in?: '1v1' | '2v2' | 'any';
  base_only?: boolean;
  sort?: CardListSort;
  dir?: 'asc' | 'desc';
  page?: number;
  per_page?: 48 | 96 | 192;
};

export type CardFacets = {
  set?: Record<string, number>;
  domain?: Record<string, number>;
  type?: Record<string, number>;
  supertype?: Record<string, number>;
  rarity?: Record<string, number>;
  tag?: { tag: string; count: number }[];
};

/** `meta` object of `GET /cards` (F2-h S2). */
export type CardListMeta = {
  page: number;
  per_page: number;
  total: number;
  pages: number;
  facets: CardFacets;
  price_as_of: string | null;
};

/** `GET /cards/:set/:id/prices` response envelope data (F2-g). */
export type CardPricesData = {
  range: string;
  currency: string;
  foilable: boolean;
  product_id: number | null;
  points: PricePoint[];
};

/** Ban information for one mode (F2-d). */
export type BanInfo = {
  mode: GameMode;
  since: string;
  reason: string | null;
};

/** One collection line of the current user (F2-d). */
export type MyLine = {
  id: number;
  foil: boolean;
  qty: number;
  condition: string;
  language: string;
  selling: boolean;
  sell_price: number | null;
  playset: boolean;
  updated_at: string;
};

/** One deck the current user has this card in (F2-d). */
export type InDeck = {
  deck_id: number;
  name: string;
  qty: number;
};

/** `CardSummary` mirrors the contract in `docs/api.md` (F2-b). */
export type CardSummary = {
  set_id: string;
  card_id: string;
  key: string;
  number: string | null;
  name: string;
  domains: string[];
  type: string;
  supertype: string | null;
  type_raw: string;
  tags: string[];
  energy: number | null;
  power: number | null;
  might: number | null;
  rarity: string;
  image_src: string | null;
  image_thumb_src: string | null;
  foilable: boolean;
  is_base: boolean;
  price: CardPrice | null;
  bans: CardBans;
  owned: CardOwned;
};

/** `CardDetail` = `CardSummary` plus the detail payload (F2-d). */
export type CardDetail = CardSummary & {
  ability: string | null;
  artist: string | null;
  set: { id: string; name: string; released_on: string | null };
  price_detail: CardPriceDetail | null;
  printings: CardMini[];
  related: CardMini[];
  ban_info: BanInfo[];
  my_lines: MyLine[];
  in_decks: InDeck[];
};

export type SuccessEnvelope<T> = { success: true; data: T; meta?: Record<string, unknown> };
export type ErrorEnvelope = {
  success: false;
  error: string;
  message: string;
  code?: string;
  params?: ErrorParams;
  details?: ErrorDetail[];
};
