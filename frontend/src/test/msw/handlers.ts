import { HttpResponse, http } from 'msw';
import { cardDetail } from '@/test/fixtures/cards';

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
  http.get(`${API}/cards/:setId/:cardId`, () => ok(cardDetail)),
];
