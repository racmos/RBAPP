/** Shapes of the JSON API v1 (`/riftbound/api/v1`). Mirrors the backend envelope (API-1). */

export type UserPayload = { id: number; username: string; email: string; is_admin: boolean };

/** The five interface preferences; `null` means Auto (PREF-2). */
export type Prefs = {
  lang: 'es' | 'en' | null;
  density: 'compact' | 'regular' | 'comfy' | null;
  accent: 'orange' | 'cyan' | null;
  bg_intensity: number | null;
  collection_view: 'table' | 'grid' | null;
};

/** `GET /auth/session`. `user` and `prefs` exist only when `authenticated`. */
export type SessionData = {
  authenticated: boolean;
  csrf_token: string;
  user?: UserPayload;
  prefs?: Prefs;
};

/** What the app keeps of the session; the CSRF token lives in `csrf.ts`, never in the cache. */
export type Session = { authenticated: boolean; user: UserPayload | null; prefs: Prefs | null };

export type CaptchaData = { provider: string; challenge: Record<string, unknown> | null };

export type MetaConfig = {
  env: string;
  registration_open: boolean;
  captcha: { provider: string; required_for: string[] };
  csrf: { header: string };
};

export type LoginBody = { username: string; password: string; remember: boolean };
export type RegisterBody = { username: string; email: string; password: string; altcha?: string };

export type ErrorParams = Record<string, string | number | boolean>;

/** One item of `details[]` in a validation error. */
/** `GET /admin/overview` (F13-a). */
export type AdminCatalog = {
  sets: number;
  sets_without_release_date: number;
  cards: number;
  cards_without_image: number;
};

/** One item of `details[]` in a validation error. */
export type ErrorDetail = {
  field: string;
  message: string;
  type: string;
  code?: string;
  params?: ErrorParams;
};

export type SuccessEnvelope<T> = { success: true; data: T; meta?: Record<string, unknown> };
export type ErrorEnvelope = {
  success: false;
  error: string;
  message: string;
  code?: string;
  params?: ErrorParams;
  details?: ErrorDetail[];
};
