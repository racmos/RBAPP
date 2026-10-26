/** AC1 (F13-f S1): `request` sends FormData without a JSON content type. */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { request } from './client';
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
