/** AC8 (F9-b S14): the profile and re-authentication endpoints go through `request()` with
    the right method, path and body. */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { clearCsrfToken, setCsrfToken } from './csrf';
import {
  completeMfa,
  disableMfa,
  enableMfa,
  getMe,
  login,
  patchMe,
  reauth,
  regenerateRecoveryCodes,
  setupMfa,
} from './endpoints';
import type { LoginResult, MeData, MfaSetup, MfaSignInResult, RecoveryCodes } from './types';

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

/** AC7 (F9-d S18): the two-factor endpoints. */
describe('two-factor endpoints', () => {
  const CODES: RecoveryCodes = {
    recovery_codes: ['abcde-fghjk', 'mnpqr-stuvw'],
    revoked_sessions: 2,
  };

  it('setupMfa posts /me/2fa/setup without a body', async () => {
    setCsrfToken('token-4');
    const setup: MfaSetup = {
      secret: 'ABCD EFGH IJKL MNOP QRST UVWX YZ23 4567',
      otpauth_uri:
        'otpauth://totp/Rift%20Manager:ada?secret=ABCDEFGHIJKLMNOPQRSTUVWXYZ234567&issuer=Rift%20Manager',
      qr: 'data:image/svg+xml;charset=utf-8,%3Csvg%3E%3C/svg%3E',
    };
    const calls = mockFetchJson(setup);
    expect(await setupMfa()).toEqual(setup);
    expect(calls[0].url).toBe('/riftbound/api/v1/me/2fa/setup');
    expect(calls[0].init.method).toBe('POST');
    expect(calls[0].init.body).toBeUndefined();
    expect((calls[0].init.headers as Record<string, string>)['X-CSRFToken']).toBe('token-4');
  });

  it('enableMfa posts the code and returns the recovery codes', async () => {
    setCsrfToken('token-5');
    const calls = mockFetchJson(CODES);
    expect(await enableMfa('123456')).toEqual(CODES);
    expect(calls[0].url).toBe('/riftbound/api/v1/me/2fa/enable');
    expect(calls[0].init.method).toBe('POST');
    expect(calls[0].init.body).toBe('{"code":"123456"}');
  });

  it('disableMfa posts a TOTP or recovery code', async () => {
    setCsrfToken('token-6');
    const calls = mockFetchJson({ revoked_sessions: 1 });
    expect(await disableMfa('abcde-fghjk')).toEqual({ revoked_sessions: 1 });
    expect(calls[0].url).toBe('/riftbound/api/v1/me/2fa/disable');
    expect(calls[0].init.method).toBe('POST');
    expect(calls[0].init.body).toBe('{"code":"abcde-fghjk"}');
  });

  it('regenerateRecoveryCodes posts /me/2fa/recovery-codes without a body', async () => {
    setCsrfToken('token-7');
    const calls = mockFetchJson(CODES);
    expect(await regenerateRecoveryCodes()).toEqual(CODES);
    expect(calls[0].url).toBe('/riftbound/api/v1/me/2fa/recovery-codes');
    expect(calls[0].init.method).toBe('POST');
    expect(calls[0].init.body).toBeUndefined();
  });
});

describe('two-factor sign-in (F9-e S10)', () => {
  const USER = {
    id: 7,
    username: 'ada',
    email: null,
    is_admin: false,
    display_name: null,
    avatar_url: null,
  };

  it('login returns the second-step answer of a 2FA account as is', async () => {
    setCsrfToken('token-8');
    const answer: LoginResult = { mfa_required: true, methods: ['totp', 'recovery'] };
    mockFetchJson(answer);
    const result = await login({ username: 'ada', password: 'secret-pass', remember: true });
    expect(result).toEqual(answer);
    expect('mfa_required' in result && result.mfa_required).toBe(true);
  });

  it('completeMfa posts a TOTP code to /auth/mfa', async () => {
    setCsrfToken('token-9');
    const done: MfaSignInResult = {
      user: USER,
      recovery_code_used: false,
      recovery_codes_left: 10,
    };
    const calls = mockFetchJson(done);
    expect(await completeMfa({ code: '123456' })).toEqual(done);
    expect(calls[0].url).toBe('/riftbound/api/v1/auth/mfa');
    expect(calls[0].init.method).toBe('POST');
    expect(calls[0].init.body).toBe('{"code":"123456"}');
    expect((calls[0].init.headers as Record<string, string>)['X-CSRFToken']).toBe('token-9');
  });

  it('completeMfa posts a recovery code', async () => {
    setCsrfToken('token-10');
    const calls = mockFetchJson({ user: USER, recovery_code_used: true, recovery_codes_left: 9 });
    const result = await completeMfa({ recovery_code: 'abcde-fghjk' });
    expect(result.recovery_codes_left).toBe(9);
    expect(calls[0].init.body).toBe('{"recovery_code":"abcde-fghjk"}');
  });
});
