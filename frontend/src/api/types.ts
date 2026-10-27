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

export type GameMode = '1v1' | '2v2';
export type CardBans = Record<GameMode, boolean>;

export type CardOwned = {
  total: number;
  foil: number;
};

export type CardPrice = {
  market: number | null;
  market_source: string | null;
  market_foil: number | null;
  market_foil_source: string | null;
  trend_7d_pct: number | null;
  trend_30d_pct: number | null;
  as_of: string | null;
};

/** `CardSummary` mirrors the contract in `docs/api.md` (F2-b). */
export type CardSummary = {
  set_id: string;
  card_id: string;
  key: string;
  number: string | null;
  name: string;
  domains: string[];
  type: string;
  supertype: string | null;
  type_raw: string;
  tags: string[];
  energy: number | null;
  power: number | null;
  might: number | null;
  rarity: string;
  image_src: string | null;
  image_thumb_src: string | null;
  foilable: boolean;
  is_base: boolean;
  price: CardPrice | null;
  bans: CardBans;
  owned: CardOwned;
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
