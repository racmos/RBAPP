import { HttpResponse, http } from 'msw';
import type { PricePoint } from '@/api/types';
import { cardDetail, cardList } from '@/test/fixtures/cards';
import {
  aylaLines,
  collectionGroups,
  collectionMeta,
  exportCsv,
  importPreview,
  importResult,
  withCard,
} from '@/test/fixtures/collection';
import { adminProductList } from '@/test/fixtures/products';

/** Base of the API as the SPA sees it (same-origin, behind Nginx). */
export const API = '/riftbound/api/v1';

export const ANON_TOKEN = 'token-anon';
export const USER_TOKEN = 'token-user';

export const USER = { id: 7, username: 'ada', email: 'ada@example.com', is_admin: false };
export const NO_PREFS = {
  lang: null,
  density: null,
  accent: null,
  bg_intensity: null,
  collection_view: null,
  playset_size: null,
};

export const ok = <T>(data: T, status = 200) =>
  HttpResponse.json({ success: true, data }, { status });

export function failure(
  status: number,
  body: {
    error?: string;
    message?: string;
    code?: string;
    params?: Record<string, unknown>;
    details?: unknown[];
  } = {},
  headers: Record<string, string> = {},
) {
  return HttpResponse.json(
    { success: false, error: 'Error', message: 'Something went wrong', ...body },
    { status, headers },
  );
}

export const anonymousSession = () => ok({ authenticated: false, csrf_token: ANON_TOKEN });

export const signedInSession = (prefs: Record<string, unknown> = NO_PREFS) =>
  ok({ authenticated: true, csrf_token: USER_TOKEN, user: USER, prefs });

export const ADMIN = { ...USER, id: 1, username: 'root', is_admin: true };
export const adminSession = () =>
  ok({ authenticated: true, csrf_token: USER_TOKEN, user: ADMIN, prefs: NO_PREFS });

/**
 * Default handlers: an anonymous visitor on a server without captcha. Tests override what they
 * exercise with `server.use(...)`; any request without a handler fails the test.
 */
export const handlers = [
  http.get(`${API}/auth/session`, () => anonymousSession()),
  http.post(`${API}/auth/login`, () => ok({ user: USER })),
  http.post(`${API}/auth/logout`, () => ok({})),
  http.post(`${API}/auth/register`, () => ok({ user: { id: 8, username: 'new' } }, 201)),
  http.get(`${API}/auth/captcha`, () => ok({ provider: 'none', challenge: null })),
  http.get(`${API}/meta/config`, () =>
    ok({
      env: 'test',
      registration_open: true,
      captcha: { provider: 'none', required_for: [] },
      csrf: { header: 'X-CSRFToken' },
    }),
  ),
  http.get(`${API}/me/prefs`, () => ok({ prefs: NO_PREFS })),
  http.patch(`${API}/me/prefs`, () => ok({ prefs: NO_PREFS })),
  http.get(`${API}/meta/game`, () =>
    ok({
      modes: ['1v1', '2v2'],
      domains: ['Fury', 'Calm', 'Mind', 'Body', 'Chaos', 'Order', 'Colorless'],
      types: ['Legend', 'Unit', 'Spell', 'Gear', 'Rune', 'Battlefield'],
      supertypes: ['Champion', 'Signature', 'Token', 'Basic'],
      rarities: ['Common', 'Uncommon', 'Rare', 'Epic', 'Showcase'],
      sets: [{ id: 'OGN', name: 'Origen', released_on: '2024-01-15', card_count: 6 }],
      price: { provider: 'cardmarket', currency: 'EUR', updated_on: '2026-10-25T00:00:00Z' },
      rules: {},
      conditions: ['MT', 'NM', 'EX', 'GD', 'LP', 'PL', 'PO'],
      languages: ['English', 'French', 'German', 'Spanish', 'Italian'],
    }),
  ),
  // The real `GET /cards` envelope carries `meta` next to `data` (F2-c contract).
  http.get(`${API}/cards`, ({ request }) => {
    const url = new URL(request.url);
    const perPage = Math.min(Number(url.searchParams.get('per_page')) || 48, 192);
    const page = Math.max(Number(url.searchParams.get('page')) || 1, 1);
    const q = url.searchParams.get('q') ?? '';
    const domains = url.searchParams.getAll('domain');
    let items = cardList.items;
    if (q) {
      const needle = q.toLowerCase();
      items = items.filter((card) => card.name.toLowerCase().includes(needle));
    }
    if (domains.length > 0) {
      items = items.filter((card) => domains.some((domain) => card.domains.includes(domain)));
    }
    const total = items.length;
    const pages = Math.max(1, Math.ceil(total / perPage));
    const safePage = Math.min(page, pages);
    const start = (safePage - 1) * perPage;
    const pageItems = items.slice(start, start + perPage);
    return HttpResponse.json(
      {
        success: true,
        data: { items: pageItems },
        meta: { ...cardList.meta, page, per_page: perPage, total, pages },
      },
      { status: 200 },
    );
  }),
  http.get(`${API}/collection`, ({ request }) => {
    const url = new URL(request.url);
    const q = (url.searchParams.get('q') ?? '').toLowerCase();
    const foil = url.searchParams.get('foil');
    const selling = url.searchParams.get('selling');
    let items = collectionGroups;
    if (q) items = items.filter((group) => group.card.name.toLowerCase().includes(q));
    if (foil === 'foil') items = items.filter((group) => group.foil);
    if (foil === 'nonfoil') items = items.filter((group) => !group.foil);
    if (selling === 'yes') items = items.filter((group) => group.sell_qty > 0);
    return HttpResponse.json(
      {
        success: true,
        data: { items },
        meta: { ...collectionMeta, total_groups: items.length, pages: items.length ? 1 : 0 },
      },
      { status: 200 },
    );
  }),
  http.post(`${API}/collection`, async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return ok({ line: { ...withCard(aylaLines[0]), ...body, id: 9001 }, merged: false }, 201);
  }),
  http.patch(`${API}/collection/:id`, async ({ params, request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return ok({ ...withCard(aylaLines[0]), ...body, id: Number(params.id) });
  }),
  http.delete(`${API}/collection/:id`, ({ params }) =>
    ok({ deleted: { ...withCard(aylaLines[0]), id: Number(params.id) } }),
  ),
  http.post(`${API}/collection/:id/split`, async ({ params, request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return ok({
      source: { ...withCard(aylaLines[0]), id: Number(params.id), qty: 1 },
      target: { ...withCard(aylaLines[0]), ...body, id: 9002 },
      merged: false,
    });
  }),
  http.post(`${API}/collection/bulk`, async ({ request }) => {
    const body = (await request.json()) as { ids: number[]; delete?: boolean };
    if (body.delete) {
      return ok({ deleted: body.ids.map((id) => ({ ...withCard(aylaLines[0]), id })) });
    }
    return ok({ updated: body.ids.length });
  }),
  http.post(`${API}/collection/keep-playset`, async ({ request }) => {
    const body = (await request.json()) as { keep: boolean };
    return ok({
      name: "Ayla, Fury's Champion",
      keep_playset: body.keep,
      kept: 3,
      playset_size: 3,
      playset_short: false,
    });
  }),
  http.get(`${API}/collection/export`, ({ request }) => {
    const cardmarket = new URL(request.url).searchParams.get('format') === 'cardmarket';
    return new HttpResponse(exportCsv, {
      status: 200,
      headers: {
        'Content-Type': 'text/csv; charset=utf-8',
        'Content-Disposition': `attachment; filename="${
          cardmarket ? '20261028101500_cardmarket.csv' : 'rbapp_collection_20261028101500.csv'
        }"`,
        'X-Rows-Exported': '1',
      },
    });
  }),
  http.post(`${API}/collection/import/preview`, () => ok(importPreview)),
  http.post(`${API}/collection/import/commit`, async ({ request }) => {
    const body = (await request.json()) as { mode: string };
    return ok(body.mode === 'replace' ? { ...importResult, replaced: 2 } : importResult);
  }),
  http.get(`${API}/admin/products`, () => ok(adminProductList)),
  http.patch(`${API}/admin/products/:id`, async ({ params, request }) => {
    const product = adminProductList.items.find((item) => String(item.id) === params.id);
    return product
      ? ok({ ...product, ...((await request.json()) as object) })
      : failure(404, { error: 'Not Found' });
  }),
  http.post(`${API}/admin/products/:id/image`, ({ params }) => {
    const product = adminProductList.items.find((item) => String(item.id) === params.id);
    return product
      ? ok({ ...product, image_src: `/riftbound/media/products/${product.id}.png` })
      : failure(404, { error: 'Not Found' });
  }),
  http.get(`${API}/cards/:setId/:cardId`, () => ok(cardDetail)),
  http.get(`${API}/cards/:setId/:cardId/prices`, ({ request }) => {
    const url = new URL(request.url);
    const range = (url.searchParams.get('range') as '30d' | '90d' | '1y' | 'all') ?? '90d';
    return priceHistory([], { range, foilable: true, product_id: 123456 });
  }),
];

/** Default price history payload for MSW (F2-g). Tests override points/range as needed. */
export function priceHistory(
  points: PricePoint[] = [],
  overrides: Partial<{ range: string; foilable: boolean; product_id: number | null }> = {},
) {
  return ok({
    range: overrides.range ?? '90d',
    currency: 'EUR',
    foilable: overrides.foilable ?? true,
    product_id: overrides.product_id ?? 123456,
    points,
  });
}
