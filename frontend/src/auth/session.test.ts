import { QueryClient, QueryObserver, focusManager } from '@tanstack/react-query';
import { HttpResponse, http } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/api/errors';
import { getCsrfToken, clearCsrfToken } from '@/api/csrf';
import {
  API,
  NO_PREFS,
  USER,
  anonymousSession,
  failure,
  signedInSession,
} from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { hasSignedInHint } from './hint';
import { SESSION_STALE_MS, sessionQuery, shouldRetry } from './session';

const newClient = () =>
  new QueryClient({ defaultOptions: { queries: { retry: shouldRetry, retryDelay: 0 } } });

beforeEach(() => clearCsrfToken());

describe('sessionQuery', () => {
  it('caches {authenticated, user, prefs} and holds the CSRF token outside the cache', async () => {
    server.use(http.get(`${API}/auth/session`, () => signedInSession()));
    const client = newClient();
    const session = await client.fetchQuery(sessionQuery);
    expect(session).toEqual({ authenticated: true, user: USER, prefs: NO_PREFS });
    expect(client.getQueryData(sessionQuery.queryKey)).toEqual(session);
    expect(
      JSON.stringify(
        client
          .getQueryCache()
          .getAll()
          .map((q) => q.state.data),
      ),
    ).not.toContain('token-user');
    expect(getCsrfToken()).toBe('token-user');
  });

  it('sets the was-signed-in hint when authenticated and clears it when anonymous', async () => {
    const client = newClient();
    server.use(http.get(`${API}/auth/session`, () => signedInSession()));
    await client.fetchQuery(sessionQuery);
    expect(hasSignedInHint()).toBe(true);

    server.use(http.get(`${API}/auth/session`, () => anonymousSession()));
    await client.fetchQuery({ ...sessionQuery, staleTime: 0 });
    expect(hasSignedInHint()).toBe(false);
  });

  it('keeps nothing sensitive under the hint key', async () => {
    server.use(http.get(`${API}/auth/session`, () => signedInSession()));
    await newClient().fetchQuery(sessionQuery);
    const stored = Object.values(localStorage).join(' ') + Object.values(sessionStorage).join(' ');
    expect(stored).not.toContain('token-user');
    expect(stored).not.toContain(USER.email);
  });

  it('stays fresh for 5 minutes: a second read makes no request', async () => {
    expect(SESSION_STALE_MS).toBe(5 * 60 * 1000);
    let calls = 0;
    server.use(
      http.get(`${API}/auth/session`, () => {
        calls += 1;
        return anonymousSession();
      }),
    );
    const client = newClient();
    await client.ensureQueryData(sessionQuery);
    await client.ensureQueryData(sessionQuery);
    expect(calls).toBe(1);
  });

  it('refetches when the window regains focus, so a logout elsewhere is noticed', async () => {
    let signedIn = true;
    server.use(
      http.get(`${API}/auth/session`, () => (signedIn ? signedInSession() : anonymousSession())),
    );
    const client = newClient();
    client.mount(); // QueryClientProvider does this in the app
    const observer = new QueryObserver(client, sessionQuery);
    const stop = observer.subscribe(() => {});
    await expect.poll(() => client.getQueryData(sessionQuery.queryKey)?.authenticated).toBe(true);

    signedIn = false;
    focusManager.setFocused(false);
    focusManager.setFocused(true);
    await expect.poll(() => client.getQueryData(sessionQuery.queryKey)?.authenticated).toBe(false);
    stop();
    client.unmount();
  });
});

describe('shouldRetry (D11)', () => {
  const http4xx = (status: number) => new ApiError({ kind: 'http', status });

  it.each([400, 401, 403, 404, 429])('never retries a %i', (status) => {
    expect(shouldRetry(0, http4xx(status))).toBe(false);
  });

  it('retries a network error once', () => {
    const network = new ApiError({ kind: 'network' });
    expect(shouldRetry(0, network)).toBe(true);
    expect(shouldRetry(1, network)).toBe(false);
  });

  it('does not retry while the browser reports it is offline (PWA-7)', () => {
    const offline = vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    expect(shouldRetry(0, new ApiError({ kind: 'network' }))).toBe(false);
    offline.mockRestore();
    expect(shouldRetry(0, new ApiError({ kind: 'network' }))).toBe(true);
  });

  it('does not retry a parse error or a server error', () => {
    expect(shouldRetry(0, new ApiError({ kind: 'parse', status: 200 }))).toBe(false);
    expect(shouldRetry(0, http4xx(500))).toBe(false);
  });

  it('does not retry an unknown thrown value', () => {
    expect(shouldRetry(0, new Error('boom'))).toBe(false);
  });
});

describe('retries on the real client', () => {
  it('retries once after a network error and then succeeds', async () => {
    let calls = 0;
    server.use(
      http.get(`${API}/auth/session`, () => {
        calls += 1;
        return calls === 1 ? HttpResponse.error() : anonymousSession();
      }),
    );
    const session = await newClient().fetchQuery(sessionQuery);
    expect(session.authenticated).toBe(false);
    expect(calls).toBe(2);
  });

  it('does not retry a 401', async () => {
    let calls = 0;
    server.use(
      http.get(`${API}/auth/session`, () => {
        calls += 1;
        return failure(401, { error: 'Unauthorized', code: 'unauthenticated' });
      }),
    );
    await expect(newClient().fetchQuery(sessionQuery)).rejects.toMatchObject({ status: 401 });
    expect(calls).toBe(1);
  });
});
