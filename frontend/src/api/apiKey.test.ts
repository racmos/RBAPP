/** AC5 (F9-h S14): the personal API key endpoints go through `request()` with the right
    method and path, and unwrap `api_key`. */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { clearCsrfToken, setCsrfToken } from './csrf';
import { createApiKey, deleteApiKey, getApiKey } from './endpoints';
import type { ApiKeyCreated, ApiKeyInfo, SecuritySummary } from './types';

afterEach(() => {
  vi.unstubAllGlobals();
  clearCsrfToken();
});

function mockFetchJson(data: unknown, status = 200) {
  const calls: { url: unknown; init: RequestInit }[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: unknown, init: RequestInit) => {
      calls.push({ url, init });
      return new Response(JSON.stringify({ success: true, data }), {
        status,
        headers: { 'Content-Type': 'application/json' },
      });
    }),
  );
  return calls;
}

const INFO: ApiKeyInfo = {
  prefix: 'rb_live_0a1b2c',
  created_at: '2030-01-01T12:00:00Z',
  last_used_at: null,
};

describe('personal API key endpoints (F9-h S14)', () => {
  it('getApiKey reads /me/api-key and returns the info', async () => {
    const calls = mockFetchJson({ api_key: INFO });
    expect(await getApiKey()).toEqual(INFO);
    expect(calls[0].url).toBe('/riftbound/api/v1/me/api-key');
    expect(calls[0].init.method ?? 'GET').toBe('GET');
  });

  it('getApiKey returns null without a key', async () => {
    mockFetchJson({ api_key: null });
    expect(await getApiKey()).toBeNull();
  });

  it('createApiKey posts /me/api-key without a body and returns the key once', async () => {
    setCsrfToken('token-k1');
    const created: ApiKeyCreated = { key: `rb_live_0a1b2c${'d'.repeat(34)}`, api_key: INFO };
    const calls = mockFetchJson(created, 201);
    expect(await createApiKey()).toEqual(created);
    expect(calls[0].url).toBe('/riftbound/api/v1/me/api-key');
    expect(calls[0].init.method).toBe('POST');
    expect(calls[0].init.body).toBeUndefined();
    expect((calls[0].init.headers as Record<string, string>)['X-CSRFToken']).toBe('token-k1');
  });

  it('deleteApiKey sends DELETE /me/api-key and returns null', async () => {
    setCsrfToken('token-k2');
    const calls = mockFetchJson({ api_key: null });
    expect(await deleteApiKey()).toBeNull();
    expect(calls[0].url).toBe('/riftbound/api/v1/me/api-key');
    expect(calls[0].init.method).toBe('DELETE');
  });

  it('GET /me types the security api_key', () => {
    const security: Pick<SecuritySummary, 'api_key'> = { api_key: INFO };
    expect(security.api_key?.prefix).toBe('rb_live_0a1b2c');
  });
});
