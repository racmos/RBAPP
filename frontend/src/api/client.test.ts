/** AC1 (F13-f S1): `request` sends FormData without a JSON content type. */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { request, requestFile, requestWithMeta, setUnauthorizedHandler } from './client';
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

describe('requestFile (F3-i S1)', () => {
  function mockFetchFile(response: Response) {
    const calls: { url: unknown; init: RequestInit }[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: unknown, init: RequestInit) => {
        calls.push({ url, init });
        return response;
      }),
    );
    return calls;
  }

  it('returns the body as a Blob with the file name and the exported rows', async () => {
    const calls = mockFetchFile(
      new Response('set_id,card_id\nOGN,79\n', {
        status: 200,
        headers: {
          'Content-Type': 'text/csv; charset=utf-8',
          'Content-Disposition': 'attachment; filename="rbapp_collection_20261028101500.csv"',
          'X-Rows-Exported': '1',
        },
      }),
    );
    const file = await requestFile('/collection/export?format=rbapp');
    expect(calls[0].url).toBe('/riftbound/api/v1/collection/export?format=rbapp');
    expect(calls[0].init.method).toBe('GET');
    expect(calls[0].init.credentials).toBe('same-origin');
    expect(calls[0].init.signal).toBeInstanceOf(AbortSignal);
    expect(file.filename).toBe('rbapp_collection_20261028101500.csv');
    expect(file.rowsExported).toBe(1);
    expect(await file.blob.text()).toBe('set_id,card_id\nOGN,79\n');
  });

  it('reads an unquoted file name and leaves missing headers null', async () => {
    mockFetchFile(
      new Response('x', {
        status: 200,
        headers: { 'Content-Disposition': 'attachment; filename=20261028_cardmarket.csv' },
      }),
    );
    const file = await requestFile('/collection/export');
    expect(file.filename).toBe('20261028_cardmarket.csv');
    expect(file.rowsExported).toBeNull();
    mockFetchFile(new Response('x', { status: 200 }));
    expect((await requestFile('/collection/export')).filename).toBeNull();
  });

  it('throws the ApiError of a JSON failure and reports a 401', async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    mockFetchFile(
      new Response(
        JSON.stringify({
          success: false,
          error: 'Unauthorized',
          message: 'no',
          code: 'unauthenticated',
        }),
        { status: 401, headers: { 'Content-Type': 'application/json' } },
      ),
    );
    await expect(requestFile('/collection/export')).rejects.toMatchObject({
      kind: 'http',
      status: 401,
      code: 'unauthenticated',
    });
    expect(handler).toHaveBeenCalled();
    setUnauthorizedHandler(null);
  });

  it('a network failure is an ApiError of kind network', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch');
      }),
    );
    await expect(requestFile('/collection/export')).rejects.toMatchObject({ kind: 'network' });
  });
});
