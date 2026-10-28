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
  GameMeta,
  ImportMode,
  ImportPreview,
  ImportResult,
  KeepPlaysetResult,
  LoginBody,
  MetaConfig,
  Prefs,
  RegisterBody,
  Session,
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
