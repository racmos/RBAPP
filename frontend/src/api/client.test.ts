import { HttpResponse, http } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { API, ANON_TOKEN, failure, ok } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { ApiError } from './errors';
import { clearCsrfToken, getCsrfToken, setCsrfToken } from './csrf';
import { request, setUnauthorizedHandler } from './client';

beforeEach(() => {
  clearCsrfToken();
  setUnauthorizedHandler(null);
});
afterEach(() => {
  vi.useRealTimers();
});

describe('request: envelope and headers (FAUTH-1)', () => {
  it('unwraps {success, data}', async () => {
    server.use(http.get(`${API}/thing`, () => ok({ name: 'rift' })));
    await expect(request<{ name: string }>('/thing')).resolves.toEqual({ name: 'rift' });
  });

  it('sends Accept: application/json and same-origin credentials, never a no-referrer policy', async () => {
    let seen: Request | undefined;
    server.use(
      http.get(`${API}/thing`, ({ request: req }) => {
        seen = req;
        return ok({});
      }),
    );
    await request('/thing');
    expect(seen?.headers.get('accept')).toBe('application/json');
    expect(seen?.credentials).toBe('same-origin');
    expect(seen?.referrerPolicy).not.toBe('no-referrer');
  });

  it('sends a JSON body with a content type', async () => {
    let body: unknown;
    let type: string | null = null;
    server.use(
      http.post(`${API}/thing`, async ({ request: req }) => {
        body = await req.json();
        type = req.headers.get('content-type');
        return ok({});
      }),
    );
    setCsrfToken('t');
    await request('/thing', { method: 'POST', body: { a: 1 } });
    expect(body).toEqual({ a: 1 });
    expect(type).toBe('application/json');
  });
});

describe('request: failure kinds', () => {
  it('maps a non-2xx answer to an http ApiError carrying the code', async () => {
    server.use(
      http.get(`${API}/thing`, () => failure(404, { error: 'Not Found', message: 'nope' })),
    );
    const error = await request('/thing').catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ kind: 'http', status: 404, message: 'nope', code: null });
  });

  it('maps a dropped connection to kind network', async () => {
    server.use(http.get(`${API}/thing`, () => HttpResponse.error()));
    await expect(request('/thing')).rejects.toMatchObject({ kind: 'network' });
  });

  it('maps a 200 with malformed JSON to kind parse', async () => {
    server.use(http.get(`${API}/thing`, () => new HttpResponse('{not json', { status: 200 })));
    await expect(request('/thing')).rejects.toMatchObject({ kind: 'parse', status: 200 });
  });

  it('maps a 200 that is not the success envelope to kind parse', async () => {
    server.use(http.get(`${API}/thing`, () => HttpResponse.json({ hello: 'world' })));
    await expect(request('/thing')).rejects.toMatchObject({ kind: 'parse' });
  });

  it('gives up after 15 seconds with kind timeout', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
    server.use(http.get(`${API}/thing`, () => new Promise<never>(() => {})));
    const outcome = request('/thing').catch((e: unknown) => e);
    await vi.advanceTimersByTimeAsync(14_999);
    let settled = false;
    void outcome.then(() => (settled = true));
    await vi.advanceTimersByTimeAsync(0);
    expect(settled).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    expect(await outcome).toMatchObject({ kind: 'timeout' });
  });

  it('lets the caller abort without reporting a timeout', async () => {
    server.use(http.get(`${API}/thing`, () => new Promise<never>(() => {})));
    const controller = new AbortController();
    const outcome = request('/thing', { signal: controller.signal }).catch((e: unknown) => e);
    controller.abort();
    const error = await outcome;
    expect(error).not.toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ name: 'AbortError' });
  });
});

describe('request: CSRF token (FAUTH-1, FAUTH-6)', () => {
  it.each(['POST', 'PATCH', 'PUT', 'DELETE'] as const)(
    'sends X-CSRFToken on %s',
    async (method) => {
      let header: string | null = null;
      server.use(
        http.all(`${API}/thing`, ({ request: req }) => {
          header = req.headers.get('x-csrftoken');
          return ok({});
        }),
      );
      setCsrfToken('held-token');
      await request('/thing', { method, body: {} });
      expect(header).toBe('held-token');
    },
  );

  it('does not send the token on GET', async () => {
    let header: string | null = 'unset';
    server.use(
      http.get(`${API}/thing`, ({ request: req }) => {
        header = req.headers.get('x-csrftoken');
        return ok({});
      }),
    );
    setCsrfToken('held-token');
    await request('/thing');
    expect(header).toBeNull();
  });

  it('fetches the session first when an unsafe request finds no token', async () => {
    const order: string[] = [];
    let header: string | null = null;
    server.use(
      http.post(`${API}/thing`, ({ request: req }) => {
        order.push('POST');
        header = req.headers.get('x-csrftoken');
        return ok({});
      }),
    );
    server.events.on('request:start', ({ request: req }) => {
      if (req.url.endsWith('/auth/session')) order.push('GET session');
    });
    await request('/thing', { method: 'POST', body: {} });
    server.events.removeAllListeners();
    expect(order).toEqual(['GET session', 'POST']);
    expect(header).toBe(ANON_TOKEN);
    expect(getCsrfToken()).toBe(ANON_TOKEN);
  });

  it('never writes the token to web storage', async () => {
    setCsrfToken('secret-token');
    await request('/auth/session');
    const stored = [...Object.entries(localStorage), ...Object.entries(sessionStorage)];
    expect(stored.flat().join(' ')).not.toContain('secret-token');
    expect(stored.flat().join(' ')).not.toContain(ANON_TOKEN);
  });
});

describe('request: CSRF retry once (FAUTH-6)', () => {
  const csrfFailure = () =>
    failure(400, { error: 'CSRF Error', message: 'stale', code: 'csrf_invalid' });

  it('refreshes the token and repeats the request exactly once', async () => {
    const posts: (string | null)[] = [];
    let sessionGets = 0;
    server.use(
      http.get(`${API}/auth/session`, () => {
        sessionGets += 1;
        return ok({ authenticated: false, csrf_token: 'fresh' });
      }),
      http.post(`${API}/thing`, ({ request: req }) => {
        posts.push(req.headers.get('x-csrftoken'));
        return posts.length === 1 ? csrfFailure() : ok({ done: true });
      }),
    );
    setCsrfToken('stale');
    await expect(request('/thing', { method: 'POST', body: {} })).resolves.toEqual({ done: true });
    expect(posts).toEqual(['stale', 'fresh']);
    expect(sessionGets).toBe(1);
  });

  it('surfaces the error when the retry also fails, with no third POST', async () => {
    let posts = 0;
    server.use(
      http.post(`${API}/thing`, () => {
        posts += 1;
        return csrfFailure();
      }),
    );
    setCsrfToken('stale');
    await expect(request('/thing', { method: 'POST', body: {} })).rejects.toMatchObject({
      status: 400,
      code: 'csrf_invalid',
    });
    expect(posts).toBe(2);
  });

  it('does not retry other 400 errors', async () => {
    let posts = 0;
    server.use(
      http.post(`${API}/thing`, () => {
        posts += 1;
        return failure(400, { code: 'validation_error' });
      }),
    );
    setCsrfToken('t');
    await expect(request('/thing', { method: 'POST', body: {} })).rejects.toMatchObject({
      status: 400,
    });
    expect(posts).toBe(1);
  });
});

describe('request: 401 (FAUTH-7)', () => {
  const unauthorized = () => failure(401, { error: 'Unauthorized', code: 'unauthenticated' });

  it('calls the unauthorized handler once for a 401 on an ordinary path, and still throws', async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    server.use(http.get(`${API}/me/prefs`, unauthorized));
    await expect(request('/me/prefs')).rejects.toMatchObject({ status: 401 });
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it.each(['/auth/login', '/auth/logout'])('does not call the handler for %s', async (path) => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    server.use(http.post(`${API}${path}`, unauthorized));
    setCsrfToken('t');
    await expect(request(path, { method: 'POST', body: {} })).rejects.toMatchObject({
      status: 401,
    });
    expect(handler).not.toHaveBeenCalled();
  });

  it('does not call the handler for other statuses', async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    server.use(http.get(`${API}/thing`, () => failure(403)));
    await expect(request('/thing')).rejects.toMatchObject({ status: 403 });
    expect(handler).not.toHaveBeenCalled();
  });
});
