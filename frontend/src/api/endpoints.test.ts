/** AC8 (F9-b S14): the profile and re-authentication endpoints go through `request()` with
    the right method, path and body. */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { clearCsrfToken, setCsrfToken } from './csrf';
import { getMe, patchMe, reauth } from './endpoints';
import type { MeData } from './types';

afterEach(() => {
  vi.unstubAllGlobals();
  clearCsrfToken();
});

function mockFetchJson(data: unknown) {
  const calls: { url: unknown; init: RequestInit }[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: unknown, init: RequestInit) => {
      calls.push({ url, init });
      return new Response(JSON.stringify({ success: true, data }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }),
  );
  return calls;
}

const ME: MeData = {
  user: {
    id: 7,
    username: 'ada',
    email: null,
    is_admin: false,
    display_name: 'Ada',
    avatar_url: null,
  },
  profile: {
    display_name: 'Ada',
    bio: null,
    country: 'ES',
    city: null,
    avatar_url: null,
    updated_at: '2030-01-01T12:00:00Z',
  },
  security: {
    has_password: true,
    password_changed_at: null,
    member_since: '2030-01-01T12:00:00Z',
    mfa: { available: false, enabled: false, pending: false, recovery_codes_left: 0 },
    sessions_active: 1,
    api_key: null,
    connections: [],
    reauth_until: null,
  },
};

describe('profile endpoints (F9-b S14)', () => {
  it('getMe reads GET /me', async () => {
    const calls = mockFetchJson(ME);
    expect(await getMe()).toEqual(ME);
    expect(calls[0].url).toBe('/riftbound/api/v1/me');
    expect(calls[0].init.method ?? 'GET').toBe('GET');
  });

  it('patchMe sends the changes with PATCH /me', async () => {
    setCsrfToken('token-1');
    const calls = mockFetchJson(ME);
    expect(await patchMe({ display_name: 'Ada', bio: null })).toEqual(ME);
    expect(calls[0].url).toBe('/riftbound/api/v1/me');
    expect(calls[0].init.method).toBe('PATCH');
    expect(calls[0].init.body).toBe('{"display_name":"Ada","bio":null}');
    expect((calls[0].init.headers as Record<string, string>)['X-CSRFToken']).toBe('token-1');
  });

  it('reauth posts the password to /me/reauth and returns reauth_until', async () => {
    setCsrfToken('token-2');
    const calls = mockFetchJson({ reauth_until: '2030-01-01T12:10:00Z' });
    expect(await reauth({ password: 'secret-pass' })).toEqual({
      reauth_until: '2030-01-01T12:10:00Z',
    });
    expect(calls[0].url).toBe('/riftbound/api/v1/me/reauth');
    expect(calls[0].init.method).toBe('POST');
    expect(calls[0].init.body).toBe('{"password":"secret-pass"}');
  });

  it('reauth can send a code', async () => {
    setCsrfToken('token-3');
    const calls = mockFetchJson({ reauth_until: '2030-01-01T12:10:00Z' });
    await reauth({ code: '123456' });
    expect(calls[0].init.body).toBe('{"code":"123456"}');
  });
});
