import { HttpResponse, http } from 'msw';
import type { PricePoint } from '@/api/types';
import { cardDetail, cardList } from '@/test/fixtures/cards';

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
    }),
  ),
  // The real `GET /cards` envelope carries `meta` next to `data` (F2-c contract).
  http.get(`${API}/cards`, () =>
    HttpResponse.json(
      { success: true, data: { items: cardList.items }, meta: cardList.meta },
      { status: 200 },
    ),
  ),
  http.get(`${API}/cards/:setId/:cardId`, () => ok(cardDetail)),
  http.get(`${API}/cards/:setId/:cardId/prices`, () => priceHistory()),
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
