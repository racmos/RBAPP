/** F9-j: signed-in devices, two-factor and API key answers for the Security and API pages. */
import type { DeviceSession, MeData, MfaSetup } from '@/api/types';
import { ME } from '@/test/msw/handlers';

const ago = (minutes: number) => new Date(Date.now() - minutes * 60_000).toISOString();

/** This browser (password + 2FA), a remembered phone and a tablet without a known network. */
export function deviceSessions(): DeviceSession[] {
  return [
    {
      id: 3,
      current: true,
      device: 'Firefox on Linux',
      user_agent: 'Mozilla/5.0 (X11; Linux x86_64) Firefox/140.0',
      ip_prefix: '192.0.2.0/24',
      created_at: '2026-11-14T10:00:00Z',
      last_seen_at: ago(0),
      expires_at: null,
      remember: false,
      auth_method: 'password',
      mfa: true,
    },
    {
      id: 4,
      current: false,
      device: 'Chrome on Android',
      user_agent: 'Mozilla/5.0 (Linux; Android 15) Chrome/140.0',
      ip_prefix: '2001:db8:1::/48',
      created_at: '2026-11-01T08:00:00Z',
      last_seen_at: ago(5),
      expires_at: '2026-12-01T08:00:00Z',
      remember: true,
      auth_method: 'password',
      mfa: false,
    },
    {
      id: 5,
      current: false,
      device: 'Safari on iPadOS',
      user_agent: 'Mozilla/5.0 (iPad) Safari/605.1.15',
      ip_prefix: null,
      created_at: '2026-10-02T08:00:00Z',
      last_seen_at: '2026-10-20T08:00:00Z',
      expires_at: null,
      remember: false,
      auth_method: 'google',
      mfa: false,
    },
  ];
}

type Mfa = MeData['security']['mfa'];
export const MFA_OFF: Mfa = {
  available: true,
  enabled: false,
  pending: false,
  recovery_codes_left: 0,
};
export const MFA_ON: Mfa = {
  available: true,
  enabled: true,
  pending: false,
  recovery_codes_left: 8,
};
export const MFA_UNAVAILABLE: Mfa = {
  available: false,
  enabled: false,
  pending: false,
  recovery_codes_left: 0,
};

/** `GET /me` of `USER` with its security summary changed. */
export const meWith = (security: Partial<MeData['security']> = {}): MeData => ({
  ...ME,
  security: { ...ME.security, ...security },
});

export const SETUP: MfaSetup = {
  secret: 'ABCD EFGH IJKL MNOP QRST UVWX YZ23 4567',
  otpauth_uri:
    'otpauth://totp/Rift%20Manager:ada?secret=ABCDEFGHIJKLMNOPQRSTUVWXYZ234567&issuer=Rift%20Manager',
  qr: 'data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%2F%3E',
};

export const RECOVERY_CODES = [
  'abcde-fghjk',
  'bcdef-ghjkm',
  'cdefg-hjkmn',
  'defgh-jkmnp',
  'efghj-kmnpq',
  'fghjk-mnpqr',
  'ghjkm-npqrs',
  'hjkmn-pqrst',
  'jkmnp-qrstu',
  'kmnpq-rstuv',
];

export const API_KEY_INFO = {
  prefix: 'rb_live_a1b2c3',
  created_at: '2026-11-10T09:00:00Z',
  last_used_at: null as string | null,
};
export const NEW_KEY = 'rb_live_ffeeddccbbaa99887766554433221100ffeeddcc';
