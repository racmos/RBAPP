import { getSession, request, requestFile, requestWithMeta } from './client';
import type {
  AdminCatalog,
  CaptchaData,
  CardDetail,
  CardListMeta,
  CardPricesData,
  CardSummary,
  CollectionAddBody,
  CollectionBulkSet,
  CollectionGroup,
  CollectionLineWithCard,
  CollectionMeta,
  CollectionPatchBody,
  CollectionSplitBody,
  DeckContentV2,
  DeckCreateBody,
  DeckDetail,
  DeckDiff,
  DeckHead,
  DeckImportBody,
  DeckImportPreview,
  DeckImportWarning,
  DeckListItem,
  DeckPatchBody,
  DeckShare,
  DeckVersionDetail,
  DeckVersionItem,
  GameMeta,
  ImportMode,
  ImportPreview,
  ImportResult,
  KeepPlaysetResult,
  LineLocationMove,
  LineLocations,
  LocationBump,
  LocationCreateBody,
  LocationList,
  LocationPatchBody,
  LoginBody,
  MetaConfig,
  MyProductAddBody,
  MyProductPatchBody,
  MyProducts,
  OwnedProductLine,
  Prefs,
  ProductDetail,
  ProductKind,
  ProductListMeta,
  ProductPricesData,
  ProductSummary,
  RegisterBody,
  Session,
  StorageLocation,
  UserPayload,
} from './types';

/** `GET /auth/session` reduced to what the cache keeps; the CSRF token goes to `csrf.ts`. */
export async function fetchSession(): Promise<Session> {
  const data = await getSession();
  return {
    authenticated: data.authenticated,
    user: data.user ?? null,
    prefs: data.prefs ?? null,
  };
}

export const login = (body: LoginBody) =>
  request<{ user: UserPayload }>('/auth/login', { method: 'POST', body });

export const logout = () => request<Record<string, never>>('/auth/logout', { method: 'POST' });

export const register = (body: RegisterBody) =>
  request<{ user: { id: number; username: string } }>('/auth/register', { method: 'POST', body });

export const getCaptcha = (signal?: AbortSignal) =>
  request<CaptchaData>('/auth/captcha', { signal });

export const getMetaConfig = (signal?: AbortSignal) =>
  request<MetaConfig>('/meta/config', { signal });

/** F13-b admin API (F13-f S1). Every mutation invalidates `['admin']`. */
export type AdminSet = {
  id: string;
  name: string;
  release_date: string | null;
  card_count: number;
  declared_count: number | null;
  window: string;
  next_run_at: string | null;
};

export type AdminCard = {
  set_id: string;
  card_id: string;
  key: string;
  name: string;
  domain: string | null;
  type: string | null;
  tags: string | null;
  energy: number | null;
  power: number | null;
  might: number | null;
  ability: string | null;
  rarity: string | null;
  artist: string | null;
  image: string | null;
  image_url: string | null;
  image_src: string | null;
};

export const listAdminSets = (signal?: AbortSignal) =>
  request<AdminSet[]>('/admin/sets', { signal });

export const createAdminSet = (body: {
  id: string;
  name: string;
  release_date: string;
  declared_count?: number | null;
}) => request<AdminSet>('/admin/sets', { method: 'POST', body });

export const patchAdminSet = (
  id: string,
  body: {
    id?: string;
    name?: string;
    release_date?: string | null;
    declared_count?: number | null;
  },
) => request<AdminSet>(`/admin/sets/${id}`, { method: 'PATCH', body });

export const deleteAdminSet = (id: string) =>
  request<{ deleted: string }>(`/admin/sets/${id}`, { method: 'DELETE' });

export type AdminCardList = {
  items: AdminCard[];
  meta: { page: number; per_page: number; total: number; pages: number };
};

export const listAdminCards = (params: Record<string, string | string[]>, signal?: AbortSignal) => {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    for (const one of Array.isArray(value) ? value : [value]) query.append(key, one);
  }
  const suffix = query.toString();
  return request<AdminCardList>(`/admin/cards${suffix ? `?${suffix}` : ''}`, { signal });
};

export const createAdminCard = (body: Record<string, unknown>) =>
  request<AdminCard>('/admin/cards', { method: 'POST', body });

export const patchAdminCard = (setId: string, cardId: string, body: Record<string, unknown>) =>
  request<AdminCard>(`/admin/cards/${setId}/${cardId}`, { method: 'PATCH', body });

export const deleteAdminCard = (setId: string, cardId: string) =>
  request<{ deleted: string }>(`/admin/cards/${setId}/${cardId}`, { method: 'DELETE' });

export const uploadAdminCardImage = (setId: string, cardId: string, file: File) => {
  const form = new FormData();
  form.append('file', file);
  return request<AdminCard>(`/admin/cards/${setId}/${cardId}/image`, {
    method: 'POST',
    body: form,
  });
};

/** `GET /admin/products` item (F14-d): a `ProductSummary` plus the curation fields. */
export type AdminProduct = ProductSummary & {
  hidden: boolean;
  kind_locked: boolean;
  set_locked: boolean;
  rbpdt_type: string;
  updated_at: string | null;
};

export type AdminProductList = {
  items: AdminProduct[];
  meta: { page: number; per_page: number; total: number; pages: number };
};

/** `kind: null` unlocks the kind; `set_id: null` locks "no set", `'auto'` unlocks the set. */
export type AdminProductPatch = {
  hidden?: boolean;
  kind?: ProductKind | null;
  set_id?: string | null;
};

export const listAdminProducts = (query: string, signal?: AbortSignal) =>
  request<AdminProductList>(`/admin/products${query ? `?${query}` : ''}`, { signal });

export const patchAdminProduct = (id: number, body: AdminProductPatch) =>
  request<AdminProduct>(`/admin/products/${id}`, { method: 'PATCH', body });

export const uploadAdminProductImage = (id: number, file: File) => {
  const form = new FormData();
  form.append('file', file);
  return request<AdminProduct>(`/admin/products/${id}/image`, { method: 'POST', body: form });
};

export type AdminJob = {
  id: number;
  kind: string;
  status: string;
  requested_by: string | null;
  requested_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  message: string | null;
};

export const listAdminJobs = (
  params: Record<string, string | number> = {},
  signal?: AbortSignal,
) => {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries({ limit: 100, ...params })) {
    query.set(key, String(value));
  }
  return request<{ items: AdminJob[] }>(`/admin/jobs?${query.toString()}`, { signal });
};

export const getAdminJob = (id: number, signal?: AbortSignal) =>
  request<AdminJob & { params: Record<string, unknown>; result: unknown }>(`/admin/jobs/${id}`, {
    signal,
  });

export const startRiotSync = (sets: string[]) =>
  request<{ job_id: number }>('/admin/riot/sync', {
    method: 'POST',
    body: sets.length > 0 ? { sets } : {},
  });

/** Cardmarket load log (CM-a). Timestamps are naive UTC ISO strings. */
export type CardmarketFile = {
  type: string;
  rows: number | null;
  status: string;
  message: string | null;
  loaded_at: string | null;
};
export type CardmarketNewProduct = {
  id_product: number;
  name: string;
  category: string | null;
  type: string | null;
  low_price: number | null;
};
export type CardmarketJobBrief = {
  id: number;
  status: string;
  queued_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  message: string | null;
};
export type CardmarketLoadDay = {
  date: string;
  files: CardmarketFile[];
  status: string;
  products_total: number;
  new_products: number | null;
  new_products_sample: CardmarketNewProduct[];
  unmatched_singles: number | null;
  duration_seconds: number | null;
  job_id: number | null;
};
export type CardmarketLoadDetail = Omit<CardmarketLoadDay, 'new_products_sample'> & {
  new_products_list: CardmarketNewProduct[];
  truncated: boolean;
  job: (CardmarketJobBrief & { result: unknown }) | null;
};
export type CardmarketStatus = {
  last_load: { date: string; status: string; loaded_at: string | null } | null;
  loaded_today: boolean;
  job: CardmarketJobBrief | null;
  unmatched: number;
  unmapped_expansions: number;
  prices_as_of: string | null;
};

export const listCardmarketLoads = (limit: number, signal?: AbortSignal) =>
  request<{ items: CardmarketLoadDay[] }>(`/admin/cardmarket/loads?limit=${limit}`, { signal });

export const getCardmarketLoad = (date: string, signal?: AbortSignal) =>
  request<CardmarketLoadDetail>(`/admin/cardmarket/loads/${encodeURIComponent(date)}`, {
    signal,
  });

export const getCardmarketStatus = (signal?: AbortSignal) =>
  request<CardmarketStatus>('/admin/cardmarket/status', { signal });

/** Queues the `daily_prices` job; 409 `job_running` while one is queued or running. */
export const startCardmarketLoad = () =>
  request<{ job_id: number; job: CardmarketJobBrief }>('/admin/cardmarket/load', {
    method: 'POST',
  });

/** Cardmarket matching workbench (CM-b). A foil slot is `N`, `S` or `null` (one slot). */
export type CardmarketFoil = 'N' | 'S' | null;
export type CardmarketExpansion = { id: number; name: string; set_id: string | null };
export type CardmarketSuggestion = {
  kind: 'card' | 'product';
  /** `SET-ID` for a card, the product id for a product. */
  id: string | number;
  name: string;
  set: string | null;
  number: string | null;
  score: number;
  free_foils: CardmarketFoil[];
};
export type CardmarketUnmatched = {
  id_product: number;
  name: string;
  type: string;
  category: string | null;
  expansion: CardmarketExpansion | null;
  low_price: number | null;
  first_seen_date: string | null;
  suggestions: CardmarketSuggestion[];
};
export type CardmarketPageMeta = { page: number; per_page: number; total: number; pages: number };
export type CardmarketUnmatchedList = {
  items: CardmarketUnmatched[];
  meta: CardmarketPageMeta & { date: string | null };
};
export type CardmarketCandidateCard = {
  set_id: string;
  card_id: string;
  name: string;
  rarity: string | null;
  type: string | null;
  image_src: string | null;
  links: { id_product: number; foil: CardmarketFoil }[];
};
export type CardmarketCandidates = {
  product: {
    id_product: number;
    name: string;
    type: string;
    category: string | null;
    expansion: CardmarketExpansion | null;
    date: string | null;
    link: {
      set_id: string;
      card_id: string;
      foil: CardmarketFoil;
      match_type: string;
    } | null;
  };
  cards: CardmarketCandidateCard[];
  products: { id: number; name: string; set_id: string | null; kind: string; category: string }[];
};
export type CardmarketLink = {
  id_product: number;
  product_name: string | null;
  product_type: string | null;
  in_latest_load: boolean;
  set_id: string;
  card_id: string;
  card_name: string | null;
  foil: CardmarketFoil;
  match_type: string;
  confidence: number | null;
  low_price: number | null;
  price_date: string | null;
};
export type CardmarketLinkList = {
  items: CardmarketLink[];
  meta: CardmarketPageMeta & { conflict_slots: number };
};
export type CardmarketLinkTarget = {
  card: { set_id: string; card_id: string };
  foil: CardmarketFoil;
};
export type CardmarketIgnored = {
  id_product: number;
  name: string;
  low_price: number | null;
  ignored_at: string | null;
};
export type CardmarketProposed = {
  id_product: number;
  product_name: string;
  low_price: number | null;
  set_id: string;
  card_id: string;
  card_name: string;
  foil: CardmarketFoil;
};
export type CardmarketReviewItem = {
  product_id: number;
  name: string;
  expansion_id: number | null;
  reason: string;
  candidates: { set: string; id: string; name: string }[];
};
export type CardmarketPreview = {
  date: string | null;
  proposed: number;
  clear: number;
  doubtful: number;
  links: CardmarketProposed[];
  review: CardmarketReviewItem[];
  review_total: number;
};
export type CardmarketApplied = {
  date: string | null;
  linked: number;
  clear: number;
  remaining_clear: number;
  doubtful: number;
  links: CardmarketProposed[];
};
export type CardmarketReviewList = {
  items: CardmarketReviewItem[];
  meta: CardmarketPageMeta & { date: string | null; reasons: Record<string, number> };
};

const withQuery = (path: string, query: string) => (query ? `${path}?${query}` : path);

export const listCardmarketUnmatched = (query: string, signal?: AbortSignal) =>
  request<CardmarketUnmatchedList>(withQuery('/admin/cardmarket/unmatched', query), { signal });

/** Without `q` the API sends the suggested cards; `q` must have 2-100 characters. */
export const getCardmarketCandidates = (idProduct: number, q: string, signal?: AbortSignal) =>
  request<CardmarketCandidates>(
    withQuery(
      `/admin/cardmarket/unmatched/${idProduct}/candidates`,
      q ? new URLSearchParams({ q }).toString() : '',
    ),
    { signal },
  );

export const listCardmarketLinks = (query: string, signal?: AbortSignal) =>
  request<CardmarketLinkList>(withQuery('/admin/cardmarket/links', query), { signal });

export const createCardmarketLink = (idProduct: number, target: CardmarketLinkTarget) =>
  request<CardmarketLink>('/admin/cardmarket/links', {
    method: 'POST',
    body: { id_product: idProduct, card: target.card, foil: target.foil },
  });

export const relinkCardmarketLink = (idProduct: number, target: CardmarketLinkTarget) =>
  request<{ link: CardmarketLink; previous: CardmarketLink }>(
    `/admin/cardmarket/links/${idProduct}`,
    { method: 'PUT', body: { card: target.card, foil: target.foil } },
  );

export const deleteCardmarketLink = (idProduct: number) =>
  request<{ link: CardmarketLink }>(`/admin/cardmarket/links/${idProduct}`, { method: 'DELETE' });

export const listCardmarketIgnored = (signal?: AbortSignal) =>
  request<{ items: CardmarketIgnored[] }>('/admin/cardmarket/ignored', { signal });

export const ignoreCardmarketProduct = (idProduct: number, name: string) =>
  request<{ item: CardmarketIgnored; created: boolean }>('/admin/cardmarket/ignored', {
    method: 'POST',
    body: { id_product: idProduct, name },
  });

/** Restores one name of the id, or every name when `name` is left out. */
export const unignoreCardmarketProduct = (idProduct: number, name?: string) =>
  request<{ removed: { id_product: number; name: string }[] }>(
    withQuery(
      `/admin/cardmarket/ignored/${idProduct}`,
      name ? new URLSearchParams({ name }).toString() : '',
    ),
    { method: 'DELETE' },
  );

export const previewCardmarketAutoMatch = () =>
  request<CardmarketPreview>('/admin/cardmarket/auto-match/preview', { method: 'POST' });

export const applyCardmarketAutoMatch = () =>
  request<CardmarketApplied>('/admin/cardmarket/auto-match/apply', { method: 'POST', body: {} });

export const listCardmarketReview = (query: string, signal?: AbortSignal) =>
  request<CardmarketReviewList>(withQuery('/admin/cardmarket/review', query), { signal });

/** Cardmarket expansions (CM-d): counts are of the latest load; `null` set = not mapped. */
export type CardmarketExpansionItem = {
  id: number;
  name: string | null;
  products_count: number;
  singles_count: number;
  sealed_count: number;
  mapped_set_id: string | null;
  mapped_set_name: string | null;
};
export type CardmarketExpansionSet = { id: string; name: string; release_date: string | null };
export type CardmarketExpansionList = {
  items: CardmarketExpansionItem[];
  sets: CardmarketExpansionSet[];
  meta: { unmapped: number; total: number; date: string | null };
};
/** The fields of a new set, as `POST /admin/sets` takes them but the id (`set_id`). */
export type CardmarketNewSet = {
  name: string;
  release_date: string;
  declared_count: number | null;
};
export type CardmarketExpansionMapped = {
  expansion: CardmarketExpansionItem;
  previous: string | null;
  created_set: AdminSet | null;
};

export const listCardmarketExpansions = (unmappedOnly: boolean, signal?: AbortSignal) =>
  request<CardmarketExpansionList>(
    withQuery('/admin/cardmarket/expansions', unmappedOnly ? 'unmapped=true' : ''),
    { signal },
  );

/** Map (or re-map) to `setId`; with `createSet` the set is created first, in one transaction. */
export const mapCardmarketExpansion = (id: number, setId: string, createSet?: CardmarketNewSet) =>
  request<CardmarketExpansionMapped>(`/admin/cardmarket/expansions/${id}`, {
    method: 'PUT',
    body: createSet ? { set_id: setId, create_set: createSet } : { set_id: setId },
  });

export const unmapCardmarketExpansion = (id: number) =>
  request<{ expansion: CardmarketExpansionItem; previous: string }>(
    `/admin/cardmarket/expansions/${id}/mapping`,
    { method: 'DELETE' },
  );

/** `GET /admin/overview` (F13-a, extended in F13-e with the `riot` block). */
export type AdminRiotActive = {
  id: string;
  name: string;
  window: string;
  next_run_at: string | null;
};
export type AdminRiot = {
  pending_changes: number;
  active_sets: AdminRiotActive[];
  last_sync: {
    job_id: number;
    status: string;
    finished_at: string | null;
    trigger: string;
  } | null;
  placeholder_sets: string[];
};

export const getAdminOverview = (signal?: AbortSignal) =>
  request<{ catalog: AdminCatalog; riot: AdminRiot }>('/admin/overview', { signal });

/** `PATCH /me/prefs`: absent fields stay, `null` resets to Auto (PREF-4). Returns the full prefs. */
export const patchPrefs = async (changes: Partial<Prefs>): Promise<Prefs> =>
  (await request<{ prefs: Prefs }>('/me/prefs', { method: 'PATCH', body: changes })).prefs;

/** `GET /meta/game` (F2-h S2). */
export const getGameMeta = (signal?: AbortSignal) => request<GameMeta>('/meta/game', { signal });

/** `GET /cards` (F2-h S2). The caller serialises the params with `serializeCatalogParams`.
    `meta` travels at the envelope level (F2-c contract), so this keeps it via `requestWithMeta`. */
export const listCards = (query: string, signal?: AbortSignal) =>
  requestWithMeta<{ items: CardSummary[] }, CardListMeta>(`/cards${query ? `?${query}` : ''}`, {
    signal,
  });

/** `GET /cards/:set/:id` (F2-d). */
export const getCard = (setId: string, cardId: string, signal?: AbortSignal) =>
  request<CardDetail>(`/cards/${encodeURIComponent(setId)}/${encodeURIComponent(cardId)}`, {
    signal,
  });

export type PriceRange = '30d' | '90d' | '1y' | 'all';

/** `GET /cards/:set/:id/prices` (F2-d / F2-g). */
export const getCardPrices = (
  setId: string,
  cardId: string,
  range: PriceRange,
  signal?: AbortSignal,
) =>
  request<CardPricesData>(
    `/cards/${encodeURIComponent(setId)}/${encodeURIComponent(cardId)}/prices?range=${range}`,
    { signal },
  );

// --- Collection (F3-b, F3-c) ---

/** `GET /collection`; the caller serialises the params with `serializeCollectionParams`. */
export const listCollection = (query: string, signal?: AbortSignal) =>
  requestWithMeta<{ items: CollectionGroup[] }, CollectionMeta>(
    `/collection${query ? `?${query}` : ''}`,
    { signal },
  );

export const addCollectionLine = (body: CollectionAddBody) =>
  request<{ line: CollectionLineWithCard; merged: boolean }>('/collection', {
    method: 'POST',
    body,
  });

export const patchCollectionLine = (id: number, body: CollectionPatchBody) =>
  request<CollectionLineWithCard>(`/collection/${id}`, { method: 'PATCH', body });

export const deleteCollectionLine = (id: number) =>
  request<{ deleted: CollectionLineWithCard }>(`/collection/${id}`, { method: 'DELETE' });

export const splitCollectionLine = (id: number, body: CollectionSplitBody) =>
  request<{ source: CollectionLineWithCard; target: CollectionLineWithCard; merged: boolean }>(
    `/collection/${id}/split`,
    { method: 'POST', body },
  );

export const keepPlayset = (body: { set_id: string; card_id: string; keep: boolean }) =>
  request<KeepPlaysetResult>('/collection/keep-playset', { method: 'POST', body });

export const bulkSetCollection = (ids: number[], set: CollectionBulkSet) =>
  request<{ updated: number }>('/collection/bulk', { method: 'POST', body: { ids, set } });

export const bulkDeleteCollection = (ids: number[]) =>
  request<{ deleted: CollectionLineWithCard[] }>('/collection/bulk', {
    method: 'POST',
    body: { ids, delete: true },
  });

// --- Collection export and import (F3-d, F3-e) ---

/** `GET /collection/export`; the caller builds the query (filters, `format`, `only_selling`). */
export const exportCollection = (query: string, signal?: AbortSignal) =>
  requestFile(`/collection/export${query ? `?${query}` : ''}`, { signal });

export const previewCollectionImport = (text: string) =>
  request<ImportPreview>('/collection/import/preview', { method: 'POST', body: { text } });

export const commitCollectionImport = (previewId: string, mode: ImportMode) =>
  request<ImportResult>('/collection/import/commit', {
    method: 'POST',
    body: { preview_id: previewId, mode },
  });

// --- Products (F14-b) and owned products (F14-c) ---

/** `GET /products`; the caller serialises the params with `serializeProductParams`. */
export const listProducts = (query: string, signal?: AbortSignal) =>
  requestWithMeta<{ items: ProductSummary[] }, ProductListMeta>(
    `/products${query ? `?${query}` : ''}`,
    { signal },
  );

export const getProduct = (id: number, signal?: AbortSignal) =>
  request<ProductDetail>(`/products/${id}`, { signal });

export const getProductPrices = (id: number, range: PriceRange, signal?: AbortSignal) =>
  request<ProductPricesData>(`/products/${id}/prices?range=${range}`, { signal });

export const listMyProducts = (signal?: AbortSignal) =>
  request<MyProducts>('/me/products', { signal });

export const addMyProduct = (body: MyProductAddBody) =>
  request<{ line: OwnedProductLine; merged: boolean }>('/me/products', { method: 'POST', body });

export const patchMyProduct = (id: number, body: MyProductPatchBody) =>
  request<OwnedProductLine>(`/me/products/${id}`, { method: 'PATCH', body });

export const deleteMyProduct = (id: number) =>
  request<{ deleted: OwnedProductLine }>(`/me/products/${id}`, { method: 'DELETE' });

// --- Storage locations (F16-b) ---

/** `GET /locations`: the user's locations in their order and the unassigned copies. */
export const listLocations = async (signal?: AbortSignal): Promise<LocationList> => {
  const { data, meta } = await requestWithMeta<
    { items: StorageLocation[] },
    { unassigned_copies: number }
  >('/locations', { signal });
  return { items: data.items, unassigned: meta?.unassigned_copies ?? 0 };
};

export const createLocation = (body: LocationCreateBody) =>
  request<StorageLocation>('/locations', { method: 'POST', body });

/** `GET /locations/next-code`: `code` is null when `after` has no `B001-F001-P0001` pattern. */
export const suggestLocationCode = (bump: LocationBump, after?: string, signal?: AbortSignal) => {
  const query = new URLSearchParams({ bump });
  if (after) query.set('after', after);
  return request<{ code: string | null }>(`/locations/next-code?${query.toString()}`, { signal });
};

export const patchLocation = (id: number, body: LocationPatchBody) =>
  request<StorageLocation>(`/locations/${id}`, { method: 'PATCH', body });

export const deleteLocation = (id: number) =>
  request<{ deleted: StorageLocation }>(`/locations/${id}`, { method: 'DELETE' });

/** `PUT /locations/order`: every id of the user, once, in the new order. */
export const reorderLocations = (ids: number[]) =>
  request<{ items: StorageLocation[] }>('/locations/order', { method: 'PUT', body: { ids } });

export const getLineLocations = (lineId: number, signal?: AbortSignal) =>
  request<LineLocations>(`/collection/${lineId}/locations`, { signal });

/** Replaces the line's assignment; a locked location must keep its quantity. */
export const putLineLocations = (
  lineId: number,
  assignments: { location_id: number; qty: number }[],
) =>
  request<LineLocations>(`/collection/${lineId}/locations`, {
    method: 'PUT',
    body: { assignments },
  });

export const moveLineLocations = (lineId: number, body: LineLocationMove) =>
  request<LineLocations>(`/collection/${lineId}/locations/move`, { method: 'POST', body });

// --- Decks v2 (F5-d, F5-e, F5-g) ---

export const listDecks = (signal?: AbortSignal) =>
  request<{ items: DeckListItem[] }>('/decks', { signal });

export const getDeck = (id: number, signal?: AbortSignal) =>
  request<DeckDetail>(`/decks/${id}`, { signal });

export const createDeck = (body: DeckCreateBody) =>
  request<DeckDetail>('/decks', { method: 'POST', body });

export const patchDeck = (id: number, body: DeckPatchBody) =>
  request<DeckDetail>(`/decks/${id}`, { method: 'PATCH', body });

export const deleteDeck = (id: number) =>
  request<{ deleted: DeckHead }>(`/decks/${id}`, { method: 'DELETE' });

/** Autosave of the current version; a hard limit answers 400 `deck_limit_exceeded`. */
export const putDeckContent = (id: number, content: DeckContentV2) =>
  request<DeckDetail>(`/decks/${id}/content`, { method: 'PUT', body: { content } });

export const listDeckVersions = (id: number, signal?: AbortSignal) =>
  request<{ items: DeckVersionItem[] }>(`/decks/${id}/versions`, { signal });

export const getDeckVersion = (id: number, seq: number, signal?: AbortSignal) =>
  request<DeckVersionDetail>(`/decks/${id}/versions/${seq}`, { signal });

/** Snapshot of the current content as a new version (`{}` without a note). */
export const createDeckVersion = (id: number, note?: string) =>
  request<DeckVersionDetail>(`/decks/${id}/versions`, {
    method: 'POST',
    body: note ? { note } : {},
  });

/** Version `seq` copied into a new current version (note `Restored from version <seq>.`). */
export const restoreDeckVersion = (id: number, seq: number) =>
  request<DeckVersionDetail>(`/decks/${id}/versions/${seq}/restore`, { method: 'POST' });

/** What changed from version `a` to version `b`, per zone and printing. */
export const diffDeckVersions = (id: number, a: number, b: number, signal?: AbortSignal) =>
  request<DeckDiff>(`/decks/${id}/diff?a=${a}&b=${b}`, { signal });

export const previewDeckImport = (text: string) =>
  request<DeckImportPreview>('/decks/import/preview', { method: 'POST', body: { text } });

export const importDeck = (body: DeckImportBody) =>
  request<DeckDetail & { warnings: DeckImportWarning[] }>('/decks/import', {
    method: 'POST',
    body,
  });

/** The text export read as text (the app copies it, never downloads it). */
export const exportDeckText = async (id: number, signal?: AbortSignal) =>
  (await requestFile(`/decks/${id}/export?format=text`, { signal })).blob.text();

/** A new private deck with the current content; `name` defaults to `<name> (copy)` (#107). */
export const duplicateDeck = (id: number, name?: string) =>
  request<DeckDetail>(`/decks/${id}/duplicate`, {
    method: 'POST',
    body: name ? { name } : {},
  });

export const shareDeck = (id: number) =>
  request<DeckShare>(`/decks/${id}/share`, { method: 'POST' });

export const unshareDeck = (id: number) =>
  request<{ share: null }>(`/decks/${id}/share`, { method: 'DELETE' });
