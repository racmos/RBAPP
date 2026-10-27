/** AC1 (F13-f S1): `request` sends FormData without a JSON content type. */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { request, requestWithMeta, setUnauthorizedHandler } from './client';
import { clearCsrfToken, setCsrfToken } from './csrf';

afterEach(() => {
  vi.unstubAllGlobals();
  clearCsrfToken();
});

function mockFetchJson(body: unknown, status = 200) {
  const calls: { url: unknown; init: RequestInit }[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: unknown, init: RequestInit) => {
      calls.push({ url, init });
      return new Response(JSON.stringify(body), {
        status,
        headers: { 'Content-Type': 'application/json' },
      });
    }),
  );
  return calls;
}

function mockFetchWithSequence(responses: (() => Response)[]) {
  let index = 0;
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => responses[index++]()),
  );
}

describe('request bodies (F13-f S1)', () => {
  it('a FormData body keeps the CSRF header and has no JSON content type', async () => {
    setCsrfToken('token-1');
    const calls = mockFetchJson({ success: true, data: {} });
    const form = new FormData();
    form.append('file', new Blob(['png']), 'ogn_1.png');
    await request('/admin/cards/OGN/1/image', { method: 'POST', body: form });

    expect(calls).toHaveLength(1);
    const headers = calls[0].init.headers as Record<string, string>;
    expect(headers['X-CSRFToken']).toBe('token-1');
    expect(headers).not.toHaveProperty('Content-Type');
    expect(calls[0].init.body).toBe(form);
  });

  it('a JSON body still sends the JSON content type', async () => {
    setCsrfToken('token-2');
    const calls = mockFetchJson({ success: true, data: {} });
    await request('/admin/sets', { method: 'POST', body: { id: 'TST' } });

    const headers = calls[0].init.headers as Record<string, string>;
    expect(headers['Content-Type']).toBe('application/json');
    expect(headers['X-CSRFToken']).toBe('token-2');
    expect(calls[0].init.body).toBe('{"id":"TST"}');
  });
});

describe('requestWithMeta (F2-h S1)', () => {
  it('returns data and meta from a successful envelope', async () => {
    mockFetchJson({ success: true, data: { items: [] }, meta: { page: 1, pages: 1 } });
    const result = await requestWithMeta<{ items: string[] }, { page: number }>('/cards');
    expect(result.data).toEqual({ items: [] });
    expect(result.meta).toEqual({ page: 1, pages: 1 });
  });

  it('returns undefined meta when the envelope has none', async () => {
    mockFetchJson({ success: true, data: { ok: true } });
    const result = await requestWithMeta<{ ok: boolean }, { page: number }>('/meta/config');
    expect(result.data).toEqual({ ok: true });
    expect(result.meta).toBeUndefined();
  });

  it('shares the error path with request', async () => {
    mockFetchJson({ success: false, error: 'Validation Error', message: 'bad' }, 400);
    await expect(requestWithMeta('/cards')).rejects.toMatchObject({ kind: 'http', status: 400 });
  });

  it('calls the unauthorized handler on 401 like request', async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    mockFetchJson({ success: false, error: 'Unauthorized', message: 'no' }, 401);
    await expect(requestWithMeta('/cards')).rejects.toMatchObject({ kind: 'http', status: 401 });
    expect(handler).toHaveBeenCalled();
    setUnauthorizedHandler(null);
    clearCsrfToken();
  });

  it('retries once on csrf_invalid like request', async () => {
    setCsrfToken('stale');
    mockFetchWithSequence([
      () =>
        new Response(
          JSON.stringify({
            success: false,
            error: 'CSRF Error',
            message: 'CSRF',
            code: 'csrf_invalid',
          }),
          { status: 400, headers: { 'Content-Type': 'application/json' } },
        ),
      () =>
        new Response(
          JSON.stringify({ success: true, data: { csrf_token: 'fresh', authenticated: false } }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          },
        ),
      () =>
        new Response(JSON.stringify({ success: true, data: { items: [] }, meta: { page: 1 } }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
    ]);
    const result = await requestWithMeta('/cards', { method: 'POST', body: {} });
    expect(result.data).toEqual({ items: [] });
  });
});
