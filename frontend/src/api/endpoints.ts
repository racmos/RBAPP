import { getSession, request } from './client';
import type {
  CaptchaData,
  LoginBody,
  MetaConfig,
  Prefs,
  RegisterBody,
  Session,
  UserPayload,
} from './types';

/** `GET /auth/session` reduced to what the cache keeps; the CSRF token goes to `csrf.ts`. */
export async function fetchSession(): Promise<Session> {
  const data = await getSession();
  return {
    authenticated: data.authenticated,
    user: data.user ?? null,
    prefs: data.prefs ?? null,
  };
}

export const login = (body: LoginBody) =>
  request<{ user: UserPayload }>('/auth/login', { method: 'POST', body });

export const logout = () => request<Record<string, never>>('/auth/logout', { method: 'POST' });

export const register = (body: RegisterBody) =>
  request<{ user: { id: number; username: string } }>('/auth/register', { method: 'POST', body });

export const getCaptcha = (signal?: AbortSignal) =>
  request<CaptchaData>('/auth/captcha', { signal });

export const getMetaConfig = (signal?: AbortSignal) =>
  request<MetaConfig>('/meta/config', { signal });

/** `PATCH /me/prefs`: absent fields stay, `null` resets to Auto (PREF-4). Returns the full prefs. */
export const patchPrefs = async (changes: Partial<Prefs>): Promise<Prefs> =>
  (await request<{ prefs: Prefs }>('/me/prefs', { method: 'PATCH', body: changes })).prefs;
