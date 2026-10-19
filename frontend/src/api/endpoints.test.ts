import { http } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';
import { API, NO_PREFS, USER, ok, signedInSession } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { clearCsrfToken, getCsrfToken } from './csrf';
import { fetchSession, getCaptcha, getMetaConfig, login, logout, register } from './endpoints';

beforeEach(() => clearCsrfToken());

describe('fetchSession', () => {
  it('maps an anonymous answer and keeps the CSRF token out of the result', async () => {
    const session = await fetchSession();
    expect(session).toEqual({ authenticated: false, user: null, prefs: null });
    expect(getCsrfToken()).toBe('token-anon');
  });

  it('maps a signed-in answer with user and prefs', async () => {
    server.use(http.get(`${API}/auth/session`, () => signedInSession()));
    const session = await fetchSession();
    expect(session).toEqual({ authenticated: true, user: USER, prefs: NO_PREFS });
    expect(getCsrfToken()).toBe('token-user');
  });
});

describe('write endpoints', () => {
  it('login posts the credentials and the remember flag', async () => {
    let body: unknown;
    server.use(
      http.post(`${API}/auth/login`, async ({ request }) => {
        body = await request.json();
        return ok({ user: USER });
      }),
    );
    await expect(login({ username: 'ada', password: 'pw', remember: false })).resolves.toEqual({
      user: USER,
    });
    expect(body).toEqual({ username: 'ada', password: 'pw', remember: false });
  });

  it('register posts the altcha payload only when it is given', async () => {
    const bodies: unknown[] = [];
    server.use(
      http.post(`${API}/auth/register`, async ({ request }) => {
        bodies.push(await request.json());
        return ok({ user: { id: 1, username: 'x' } }, 201);
      }),
    );
    await register({ username: 'new_user', email: 'a@b.co', password: 'longenough' });
    await register({
      username: 'new_user',
      email: 'a@b.co',
      password: 'longenough',
      altcha: 'payload',
    });
    expect(bodies).toEqual([
      { username: 'new_user', email: 'a@b.co', password: 'longenough' },
      { username: 'new_user', email: 'a@b.co', password: 'longenough', altcha: 'payload' },
    ]);
  });

  it('logout posts to /auth/logout', async () => {
    let called = false;
    server.use(
      http.post(`${API}/auth/logout`, () => {
        called = true;
        return ok({});
      }),
    );
    await logout();
    expect(called).toBe(true);
  });
});

describe('read endpoints', () => {
  it('getCaptcha returns provider and challenge', async () => {
    server.use(
      http.get(`${API}/auth/captcha`, () => ok({ provider: 'altcha', challenge: { salt: 's' } })),
    );
    await expect(getCaptcha()).resolves.toEqual({ provider: 'altcha', challenge: { salt: 's' } });
  });

  it('getMetaConfig returns the captcha provider', async () => {
    const config = await getMetaConfig();
    expect(config.captcha.provider).toBe('none');
  });
});
