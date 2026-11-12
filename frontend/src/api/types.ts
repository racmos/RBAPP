/** Shapes of the JSON API v1 (`/riftbound/api/v1`). Mirrors the backend envelope (API-1). */

export type UserPayload = { id: number; username: string; email: string; is_admin: boolean };

/** Body of `PATCH /me/account`: the email, or a new password with the current one. */
export type AccountChanges = { email?: string; password?: string; current_password?: string };

/** The stored interface preferences; `null` means Auto (PREF-2). `playset_size` (F3) is not an
    interface preference: `null` means 3 copies. The backend still stores and sends `lang`
    (`rbprf_lang`); the app is English-only (owner feedback S21) and ignores it. */
export type Prefs = {
  density: 'compact' | 'regular' | 'comfy' | null;
  accent: 'orange' | 'cyan' | null;
  bg_intensity: number | null;
  collection_view: 'table' | 'grid' | null;
  playset_size: number | null;
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

/** Mini card shape used for printings and related cards (F2-d), as `card_detail._card_mini`
 *  sends it: no `number` and no price block, the non-foil `market` and the caller's copies. */
export type CardMini = {
  set_id: string;
  card_id: string;
  key: string;
  name: string;
  domains: string[];
  type: string;
  supertype: string | null;
  rarity: string;
  image_src: string | null;
  /** Always null today: the image falls back to `image_src`. */
  image_thumb_src: string | null;
  is_base: boolean;
  /** Non-foil market price (EUR), null when unpriced. */
  market: number | null;
  /** The caller's copies of this printing. */
  owned_total: number;
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
/** `rules.deck` of `GET /meta/game` (`DECK_RULES`, F5-a S1). */
export type DeckRuleValues = {
  main_size: number;
  total_with_champion: number;
  runes: number;
  battlefields: number;
  sideboard: number;
  copies_max: number;
  workbench_max: number;
};

export type GameMeta = {
  modes: string[];
  domains: string[];
  types: string[];
  supertypes: string[];
  rarities: string[];
  sets: { id: string; name: string; released_on: string | null; card_count: number }[];
  price: { provider: string; currency: string; updated_on: string | null };
  /** Game rule values; `deck` since F5-a (read it with `rulesFromMeta` of `@/decks/rules`).
   * Optional only for fixtures that predate it: the server always sends it. */
  rules: { deck?: DeckRuleValues; [key: string]: unknown };
  /** Card conditions, best to worst (F3-b). */
  conditions: string[];
  /** Languages the collection offers (F3-b). */
  languages: string[];
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

/** One row of the collection (`CollectionLine`, F3-b); money is in EUR. */
export type CollectionLine = {
  id: number;
  foil: boolean;
  qty: number;
  condition: string | null;
  language: string | null;
  purchase_price: number | null;
  selling: boolean;
  sell_qty: number;
  sell_price: number | null;
  updated_at: string;
  market: number | null;
  value: number | null;
  pl_abs: number | null;
  pl_pct: number | null;
  /** `GET /collection` only (F16-b): the first 5 locations of the line, in the user's order. */
  locations?: LineLocationSummary[];
  /** `GET /collection` only: how many more locations the line has. */
  locations_more?: number;
  /** `GET /collection` only: copies of the line in no location. */
  unassigned?: number;
};

/** A line as the write endpoints return it. */
export type CollectionLineWithCard = CollectionLine & { set_id: string; card_id: string };

/** A printing and foil of the collection with its lines (`CollectionGroup`, F3-b). */
export type CollectionGroup = {
  key: string;
  card: CardSummary;
  foil: boolean;
  qty: number;
  sell_qty: number;
  value: number | null;
  lines: CollectionLine[];
  keep_playset: boolean;
  playset_short: boolean;
  /** Copies not for sale across every printing of the card name. */
  kept: number;
};

export type CollectionTotals = {
  lines: number;
  qty: number;
  unique: number;
  value: number;
  cost: number | null;
  pl: number | null;
  selling_value: number;
  foil_pct: number;
};

export type CollectionFacets = {
  set?: Record<string, number>;
  rarity?: Record<string, number>;
  condition?: Record<string, number>;
  language?: Record<string, number>;
  foil?: { foil: number; nonfoil: number };
};

/** `meta` of `GET /collection`. */
export type CollectionMeta = {
  page: number;
  per_page: number;
  total_groups: number;
  pages: number;
  totals: CollectionTotals;
  facets: CollectionFacets;
  price_as_of: string | null;
  playset_size: number;
};

export type CollectionSort =
  'number' | 'name' | 'price' | 'qty' | 'value' | 'pl' | 'trend_7d' | 'updated' | 'rarity';

/** Query of `GET /collection` (F3-b). */
export type CollectionParams = {
  q?: string;
  set?: string[];
  domain?: string[];
  type?: string[];
  rarity?: string[];
  condition?: string[];
  language?: string[];
  /** Location codes (F16-b): lines with copies in any of them. */
  location?: string[];
  foil?: 'any' | 'foil' | 'nonfoil';
  selling?: 'any' | 'yes' | 'no';
  has_purchase?: 'any' | 'yes' | 'no';
  sort?: CollectionSort;
  dir?: 'asc' | 'desc';
  page?: number;
  per_page?: number;
};

/** Body of `POST /collection` (F3-c). */
export type CollectionAddBody = {
  set_id: string;
  card_id: string;
  foil: boolean;
  qty: number;
  condition?: string | null;
  language?: string | null;
  purchase_price?: number | null;
  selling?: boolean;
  sell_qty?: number;
  sell_price?: number | null;
};

/** Body of `PATCH /collection/:id`; only the keys sent change. */
export type CollectionPatchBody = Partial<{
  qty: number;
  condition: string | null;
  language: string | null;
  purchase_price: number | null;
  selling: boolean;
  sell_qty: number;
  sell_price: number | null;
  if_updated_at: string;
}>;

export type CollectionSplitBody = {
  qty: number;
  condition?: string | null;
  language?: string | null;
  purchase_price?: number | null;
  selling?: boolean;
  sell_price?: number | null;
};

export type KeepPlaysetResult = {
  name: string;
  keep_playset: boolean;
  kept: number;
  playset_size: number;
  playset_short: boolean;
};

/** `set` of `POST /collection/bulk` (F3-c): only the keys sent change. */
export type CollectionBulkSet = Partial<{
  condition: string | null;
  language: string | null;
  selling: boolean;
  sell_qty_rule: 'all' | 'none' | 'keep_n';
  keep: number;
  sell_price: number | null;
  purchase_price: number | null;
  /** F16-x: absent keeps every line's locations; an id puts all their copies there; `null`
   * makes them all unassigned. */
  location_id: number | null;
}>;

/** `GET /collection/export` formats (F3-d). */
export type ExportFormat = 'rbapp' | 'cardmarket';

export type ImportRowStatus = 'ok' | 'warning' | 'error';

export type ImportReasonCode =
  | 'card_not_found'
  | 'name_mismatch'
  | 'invalid_value'
  | 'foil_not_allowed'
  | 'invalid_qty'
  | 'unknown_condition'
  | 'invalid_price'
  | 'invalid_sell_qty'
  | 'duplicate_row';

/** One parsed row of `POST /collection/import/preview` (F3-e); `line` counts the header as 1. */
export type ImportRow = {
  line: number;
  status: ImportRowStatus;
  reason_codes: ImportReasonCode[];
  card?: CardSummary | null;
  set_id: string;
  card_id: string;
  foil: boolean | null;
  qty: number | null;
  condition: string | null;
  language: string | null;
  purchase_price: number | null;
  selling: boolean | null;
  sell_qty: number | null;
  sell_price: number | null;
};

export type ImportPreview = {
  preview_id: string;
  format: string;
  rows: ImportRow[];
  summary: { total: number; ok: number; warning: number; error: number; printings: number };
};

export type ImportMode = 'add' | 'replace';

export type ImportResult = { created: number; merged: number; replaced: number; skipped: number };

/** Product kinds of `rbproducts` (F14-a), in display order. */
export const PRODUCT_KINDS = [
  'booster',
  'box',
  'case',
  'bundle',
  'starter',
  'sleeves',
  'accessory',
  'other',
] as const;
export type ProductKind = (typeof PRODUCT_KINDS)[number];

/** Price of a product: the first non-zero of `avg7`, `trend`, `low` (F14-b). */
export type ProductPrice = {
  value: number;
  source: string;
  change_7d_pct: number | null;
  change_30d_pct: number | null;
  as_of: string;
};

/** `ProductSummary` (F14-b contract, additive only). */
export type ProductSummary = {
  id: number;
  name: string;
  kind: ProductKind;
  category: string | null;
  set_id: string | null;
  image_src: string | null;
  listed: boolean;
  price: ProductPrice | null;
  owned_qty: number;
};

// --- Products (F14-b, F14-c) ---

export type ProductListSort = 'name' | 'price' | 'change_7d' | 'change_30d';

/** `GET /products` params (F14-b names). */
export type ProductListParams = {
  q?: string;
  kind?: ProductKind[];
  set?: string[];
  sort?: ProductListSort;
  dir?: 'asc' | 'desc';
  page?: number;
  per_page?: number;
};

/** Disjunctive counts: `kind` in `PRODUCT_KINDS` order, `set` by release order. */
export type ProductFacets = { kind: Record<string, number>; set: Record<string, number> };

export type ProductListMeta = {
  page: number;
  per_page: number;
  total: number;
  pages: number;
  facets: ProductFacets;
  price_as_of: string | null;
};

/** An owned line without its product (`GET /products/<id>` `lines`). */
export type OwnedProductLineBase = {
  id: number;
  quantity: number;
  purchase_price: number | null;
  note: string | null;
  value: number | null;
  pl_abs: number | null;
  pl_pct: number | null;
  updated_at: string;
};

/** `OwnedProductLine` (F14-c). */
export type OwnedProductLine = OwnedProductLineBase & { product: ProductSummary };

/** `GET /products/<id>`. */
export type ProductDetail = ProductSummary & {
  description: string | null;
  columns: {
    avg7: number | null;
    trend: number | null;
    low: number | null;
    avg30: number | null;
  } | null;
  lines: OwnedProductLineBase[];
};

export type ProductPricePoint = {
  date: string;
  value: number | null;
  avg7: number | null;
  trend: number | null;
  low: number | null;
};

export type ProductPricesData = { range: string; points: ProductPricePoint[] };

export type MyProductsTotal = { value: number; lines: number; qty: number; unpriced: number };

/** `GET /me/products`. */
export type MyProducts = { items: OwnedProductLine[]; total: MyProductsTotal };

export type MyProductAddBody = {
  product_id: number;
  quantity: number;
  purchase_price?: number | null;
  note?: string | null;
};

export type MyProductPatchBody = Partial<{
  quantity: number;
  purchase_price: number | null;
  note: string | null;
}>;

// --- Storage locations (F16-b) ---

/** `Location` of `GET /locations`; named so it does not shadow the DOM `Location`. */
export type StorageLocation = {
  id: number;
  code: string;
  description: string | null;
  /** 1..n, the user's order. */
  position: number;
  locked: boolean;
  /** The mounted deck (F16-e), else null. */
  deck_id: number | null;
  /** Copies kept there. */
  copies: number;
  /** Lines kept there. */
  cards: number;
};

/** `GET /locations` with its `meta.unassigned_copies`. */
export type LocationList = { items: StorageLocation[]; unassigned: number };

export type LocationBump = 'block' | 'row' | 'pack';

export type LocationCreateBody = { code: string; description?: string | null };

export type LocationPatchBody = Partial<{
  code: string;
  description: string | null;
  locked: boolean;
}>;

/** One location of a line as `GET /collection` lists it (first 5). */
export type LineLocationSummary = {
  location_id: number;
  code: string;
  description: string | null;
  qty: number;
};

/** `LineLocations` of `GET /collection/:id/locations` (all of them, the user's order). */
export type LineLocations = {
  locations: (LineLocationSummary & { locked: boolean })[];
  unassigned: number;
  /** The line quantity. */
  total: number;
};

/** `null` is unassigned on either side. */
export type LineLocationMove = {
  from_location_id: number | null;
  to_location_id: number | null;
  qty: number;
};

// --- Decks v2 (F5-d, F5-e, F5-g) ---

/** A printing in a deck: `{set, id}`. */
export type DeckRef = { set: string; id: string };
/** A printing with its copies (`qty` ≥ 1). */
export type DeckRefLine = DeckRef & { qty: number };

/** Content v2 (F5-R6): the shape `PUT /decks/:id/content` takes and every detail returns. */
export type DeckContentV2 = {
  v: 2;
  legend: DeckRef | null;
  champion: DeckRef | null;
  main: DeckRefLine[];
  runes: DeckRefLine[];
  battlefields: DeckRef[];
  sideboard: DeckRefLine[];
  workbench: DeckRefLine[];
};

export type DeckZoneName =
  'legend' | 'champion' | 'main' | 'runes' | 'battlefields' | 'sideboard' | 'workbench';

/** `DeckCard` = the server `CardMini` plus `tags`, energy, power, might, variants, keywords (docs/api.md "Decks (F5-d)"). */
export type DeckCard = {
  set_id: string;
  card_id: string;
  key: string;
  name: string;
  domains: string[];
  type: string;
  supertype: string | null;
  rarity: string;
  image_src: string | null;
  image_thumb_src: string | null;
  is_base: boolean;
  /** Non-foil market price (EUR) of the printing, null when unpriced. */
  market: number | null;
  /** The caller's copies of the printing; null on the public deck. */
  owned_total: number | null;
  tags: string[];
  energy: number | null;
  power: number | null;
  might: number | null;
  /** Printings in the catalog that share the name; `variants - 1` alt arts. */
  variants: number;
  /** Derived from the ability text (approximate). */
  keywords: string[];
};

/** One legality issue (`deck_rules.validate`, F5-a S7); codes in `ISSUE_CODES`. */
export type DeckIssue = { code: string; params: Record<string, string | number> };

export type DeckSectionCount = { have: number; need: number; missing: number };
export type DeckCompleteness = Record<
  'legend' | 'champion' | 'main' | 'runes' | 'battlefields' | 'sideboard',
  DeckSectionCount
>;

export type DeckLegalityResult = {
  legal: boolean;
  issues: DeckIssue[];
  completeness: DeckCompleteness;
};
export type DeckLegality = Record<GameMode, DeckLegalityResult>;

export type DeckShare = { slug: string; url: string };
export type DeckVisibility = 'private' | 'public';

export type DeckHead = {
  id: number;
  name: string;
  mode: GameMode;
  visibility: DeckVisibility;
  created_at: string;
  updated_at: string;
  share: DeckShare | null;
};

export type DeckCounts = {
  main: number;
  runes: number;
  battlefields: number;
  sideboard: number;
  workbench: number;
};

/** One item of `GET /decks`: issues are codes only (no params). */
export type DeckListItem = DeckHead & {
  legend: DeckCard | null;
  champion: DeckCard | null;
  domains: string[];
  counts: DeckCounts;
  value: number;
  value_unpriced: number;
  legal: Record<GameMode, boolean>;
  issues: Record<GameMode, string[]>;
};

export type DeckUnknownCard = { zone: DeckZoneName; set: string; id: string };

/** What a detail, a version and an import preview share. */
export type DeckBody = {
  content: DeckContentV2;
  /** Every known printing, keyed `"<set>-<id>"`. */
  cards: Record<string, DeckCard>;
  unknown_cards: DeckUnknownCard[];
  domains: string[];
  counts: DeckCounts;
  value: number;
  value_unpriced: number;
  legality: DeckLegality;
};

export type DeckDetail = DeckHead & { current_seq: number } & DeckBody;

export type DeckVersionItem = {
  seq: number;
  note: string | null;
  created_at: string;
  is_current: boolean;
};
export type DeckVersionDetail = DeckVersionItem & DeckBody;

/** One printing whose copies differ between two versions (1 for legend, champion, battlefield). */
export type DeckDiffEntry = { set: string; id: string; before: number; after: number };
export type DeckDiffZone = {
  added: DeckDiffEntry[];
  removed: DeckDiffEntry[];
  changed: DeckDiffEntry[];
};
/** `GET /decks/:id/diff?a=&b=`: per zone from `a` to `b`; `cards` names the known printings. */
export type DeckDiff = {
  a: number;
  b: number;
  zones: Record<DeckZoneName, DeckDiffZone>;
  cards: Record<string, DeckCard>;
};

export type DeckCreateBody = { name: string; mode: GameMode };
export type DeckPatchBody = Partial<{ name: string; mode: GameMode; visibility: DeckVisibility }>;

/** One warning of the text import (F5-e). */
export type DeckImportWarning = {
  line: number | null;
  text: string;
  reason_code: string;
  params: Record<string, string | number>;
};

export type DeckImportPreview = {
  deck_preview: DeckBody;
  warnings: DeckImportWarning[];
  counts: { lines: number; copies: number; unresolved: number };
};

export type DeckImportBody = { text: string; name?: string; mode?: GameMode };

// --- Deck vs collection (F5-f) ---

/** A deck section that holds cards (the workbench is not part of the deck). */
export type DeckSectionZone =
  'legend' | 'champion' | 'main' | 'runes' | 'battlefields' | 'sideboard';

/** One card name of the deck with missing copies: `card` is the deck's printing of it (the
 *  first in deck order), `zone` the first section that uses it; copies count per name across
 *  printings. */
export type DeckMissingCard = {
  card: CardMini;
  zone: DeckSectionZone;
  need: number;
  have: number;
  missing: number;
};

/** `GET /decks/:id/vs-collection`: the current version against the caller's collection. */
export type DeckVsCollection = {
  missing: DeckMissingCard[];
  /** Names fully owned, and every name of the deck. */
  complete: number;
  names: number;
  /** Missing copies x the price of the deck's printing (EUR); `unpriced` names add 0. */
  cost_eur: number;
  /** min(need, have) x price over every name (EUR). */
  owned_value: number;
  unpriced: number;
};

export type MissingSkipReason = 'list_full' | 'qty_cap';

/** `POST /decks/:id/missing-to-wishlist`: lines added, raised (`merged`) or already enough
 *  (`unchanged`); `skipped[].missing` = the copies of that card left out of the list. */
export type MissingToWishlistResult = {
  wishlist: { id: number; name: string };
  added: number;
  merged: number;
  unchanged: number;
  skipped: { card: CardMini; missing: number; reason: MissingSkipReason }[];
  total_missing_names: number;
};

// --- Wishlists (F3-f-2) ---

/** `Wishlist` of `GET /wishlists` (keys in the API order). */
export type Wishlist = {
  id: number;
  name: string;
  /** The starred list: "Add to wishlist" saves there. Exactly one per user. */
  is_default: boolean;
  /** 1..n, the user's order. */
  position: number;
  line_count: number;
  created_at: string;
  updated_at: string;
};

/** The finish a line wants: either, non-foil or foil. */
export type WishFoil = 'any' | 'N' | 'S';

/** The price of a line for its foil wish; a by-name line takes its cheapest printing. */
export type WishlistMarket = {
  value: number;
  source: string | null;
  as_of: string | null;
  set_id: string;
  card_id: string;
  foil: boolean;
};

/** Copies in the caller's collection (A6). A by-name line counts every printing as this version. */
export type WishlistOwned = {
  this_version: { total: number; foil: number };
  other_versions: { total: number; alt_art: number; foil: number };
};

/** `WishlistLine` (contract, additive changes only). */
export type WishlistLine = {
  id: number;
  list_id: number;
  name: string;
  /** Both null for a by-name line (any printing). */
  set_id: string | null;
  card_id: string | null;
  /** The printing, or the base printing of a by-name line; null when it left the catalog. */
  card: CardMini | null;
  foil: WishFoil;
  /** Copies wanted, 1..99. */
  qty: number;
  /** The alert price (EUR); null = no alert. */
  max_price: number | null;
  note: string | null;
  created_at: string;
  updated_at: string;
  market: WishlistMarket | null;
  /** null without a max price; else market <= max price (false when unpriced). */
  reached: boolean | null;
  owned: WishlistOwned;
};

/** `meta` of `GET /wishlists/:id/lines`. */
export type WishlistLinesMeta = {
  /** Lines returned (after `q`). */
  total: number;
  /** Lines in the list. */
  line_count: number;
  max_lines: number;
  market_total: number;
  unpriced: number;
};

export type WishlistLines = { items: WishlistLine[]; meta: WishlistLinesMeta };

export type WishlistPatchBody = Partial<{ name: string; is_default: boolean }>;

/** Body of `POST /wishlists/:id/lines`: a printing (`set_id` + `card_id`) or a `name`. */
export type WishlistLineCreateBody = {
  set_id?: string | null;
  card_id?: string | null;
  name?: string | null;
  foil?: WishFoil;
  qty?: number;
  max_price?: number | null;
  note?: string | null;
};

export type WishlistLinePatchBody = Partial<{
  qty: number;
  foil: WishFoil;
  max_price: number | null;
  note: string | null;
}>;

export type WishlistMoveMode = 'move' | 'copy';

export type WishlistMoveBody = {
  line_ids: number[];
  to_list_id: number;
  mode: WishlistMoveMode;
};

export type WishlistMoveResult = { moved: number; merged: number; skipped: number };

// --- Wishlist price alerts (F4-g-2) ---

/** `WishlistAlert` of `GET /wishlist-alerts`: a card that reached a wishlist max price one day. */
export type WishlistAlert = {
  id: number;
  name: string;
  /** The printing, or the base printing of a by-name alert; null when it left the catalog. */
  card: CardMini | null;
  /** Both null for a by-name alert (any printing). */
  set_id: string | null;
  card_id: string | null;
  /** The market price reached (EUR). */
  price: number;
  /** The lowest max price of the user's lines that the price met (EUR). */
  max_price: number;
  /** The day of the Cardmarket price update, `YYYY-MM-DD`. */
  price_date: string;
  created_at: string;
  /** null while unread. */
  read_at: string | null;
};

/** `meta` of `GET /wishlist-alerts`. */
export type WishlistAlertsMeta = {
  page: number;
  per_page: number;
  /** Alerts that match the filter. */
  total: number;
  pages: number;
  /** Every unread alert of the user, whatever the filter (the badge). */
  unread_count: number;
};

export type WishlistAlerts = { items: WishlistAlert[]; meta: WishlistAlertsMeta };

/** A list of `GET /wishlist-alerts/:id/lists`: holds the alert's card now. */
export type WishlistAlertList = {
  id: number;
  name: string;
  is_default: boolean;
  /** Copies wanted in that list (its matching lines added). */
  qty: number;
  /** The lowest max price of its matching lines; null when none has one. */
  max_price: number | null;
};
