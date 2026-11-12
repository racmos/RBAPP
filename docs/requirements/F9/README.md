# F9: Account — phase spec

Status: planned (spec updated 2026-11-12) · Depends on: F1 (shell, auth screens, prefs, API client), F11-f (legacy schema gone, migration 0028) · Order (`docs/knowledge/roadmap.md`): before the production data reset and F12; **F9-f/F9-g (Google/Discord) are done last, just before F12** · Source: roadmap §5 (F9), `docs/knowledge/product.md`, design-handoff §3.11/§3.12.

## Goal

Each user manages their account from the app: an extended private profile with avatar, a real password flow with re-authentication, TOTP two-factor authentication with recovery codes, the list of signed-in devices (server-side sessions) with revoke, sign-in with Discord or Google, and a personal read-only API key. There are no payments and no e-mail recovery (no mail server): the admin resets passwords and 2FA (F10) and OAuth is the alternative way in.

**Out of scope now:** scheduled account deletion (F9-k, owner 2026-11-12: deferred, see "Deferred"), subscription plans, payments, invitations, several e-mails or e-mail verification, providers other than Discord/Google, public profile pages, social links, e-mail password recovery, admin actions on other users (F10).

## Owner decisions (2026-11-12)

| ID | Decision |
|---|---|
| D-F9-scope | Before production: sessions/devices (a), profile + avatar (b, c), TOTP 2FA (d, e), API key read-only (h), account UI (i, j), OAuth Google/Discord (f, g) last, just before F12. Account deletion is **not** built (D-F9-2 = none). |
| D-F9-1 | E-mail is **optional**: `rbusers.email` nullable, unique case-insensitively when present. Password registration still asks for it but accepts an empty value. |
| D-F9-3 / D-F9-12 | Profile is **private**: no public page, no social links. Display name, bio, country, city. Avatar and display name are visible to signed-in users only. |
| D-F9-2fa | 2FA is **optional for everyone**, admins included. Lost device: recovery codes, then admin reset (F10). |

Kept from the earlier spec (nothing in the code contradicts them): D-F9-4 TOTP secrets encrypted with Fernet and `TOTP_ENCRYPTION_KEY` · D-F9-5 OAuth sign-up allowed, never auto-link by e-mail · D-F9-6 2FA also after OAuth sign-in · D-F9-7 username not editable · D-F9-8 API key read-only (GET) · D-F9-9 non-remembered sessions end after 12 h idle or when the browser closes · D-F9-10 new pinned dependencies, each added by the unit that needs it (Pillow, pyotp, segno, cryptography, Authlib; none is in `requirements.txt` today) · D-F9-11 sessions store an IP prefix only (IPv4 /24, IPv6 /48), no geo-IP.

## Current state (verified 2026-11-12, main `c8a6da2`)

- **`rbusers`** (`app/models/user.py`): `id`, `username` (unique), `email` (NOT NULL, unique `rbusers_email_key`), `password_hash` (NOT NULL), `created_at`, `is_admin`, `is_blocked`, `failed_login_count`, `locked_until`, `last_login_at`. Almost every user table references `rbusers.id`; **`rbcollection.rbcol_user` and `rblocations.rbloc_user` still reference `rbusers.username`** (ON UPDATE CASCADE, ON DELETE RESTRICT). Username is never editable, so the references stay.
- **Sessions are cookie-only**: Flask signed session + Flask-Login, `User.get_id()` = user id, so a session cannot be listed or revoked and a password change does not end other sessions. Remember-me: 30-day absolute cookie, API login only (`config.py` `_session_settings`, `REMEMBER_COOKIE_DURATION`). Cookies HttpOnly, SameSite=Lax (kept Lax for OAuth callbacks), Secure in production.
- **Login/auth API** (`app/api/v1/auth.py`, logic `app/services/auth.py`): `GET /auth/session`, `GET /auth/captcha`, `POST /auth/login` (10/min + 50/h per IP, lockout with `failed_login_count`/`locked_until`, constant-time dummy hash), `POST /auth/logout`, `POST /auth/register` (5/h, ALTCHA). The old Jinja web is gone (PR #125): `app/routes/redirects.py` only 302s old URLs; there is **no** server-rendered login, profile or logout any more.
- **Account** (PR #122): `PATCH /me/account` (`app/api/v1/me.py`, `app/services/account.py`) changes e-mail and/or password; a new password needs `current_password` (400 `current_password_incorrect`), 409 `email_taken`, 10/hour per IP; React page `/account/profile` (`frontend/src/account/ProfilePage.tsx`); nav `profile` is `spa`. `/account/interface` holds the preferences. There is no display name, bio, country, city, avatar, 2FA, device list, OAuth or API key.
- **Error codes** already present: `invalid_credentials`, `locked`, `rate_limited`, `username_taken`, `email_taken`, `captcha_failed`, `csrf_invalid`, `unauthenticated`, `validation_error`, `current_password_incorrect`.
- **Jobs**: the F4-a runner exists (`flask jobs`, `daily_prices.FOLLOW_UPS`); F9 registers job kinds on it, never its own runner.
- **App is English-only** (S21): strings in `frontend/src/i18n/locales/en/*.json`, tests in English.
- **Test policy**: each unit writes its own tests and re-creates the guard of the area it touches (migration round trip + drift via `tests/migration_helpers.py`, error-code catalog `tests/test_error_catalogs.py`, English catalog `frontend/src/i18n/catalogCheck.test.ts`, pin check for new dependencies, authz matrix `tests/test_authz_matrix.py` for every new route, `tests/test_api_auth_guards.py` when a login path changes).

## Units

Order: a → b → (c, d, h in any order) → e → i → j → [production reset] → f → g. The reset (owner 2026-11-11) runs after F9 and F11 and before F12; it keeps users `rbadmin`, `racmos`, `rbqa`, so F9 revisions back-fill only what keeps the dev database working.

| ID | Title | Depends on | Size | Risk |
|---|---|---|---|---|
| F9-a | Server-side sessions | none | ~550 | item 2 + 1 (identity loading on every request; migration `0029_sessions`) |
| F9-b | Profile, optional e-mail, re-auth API | F9-a | ~500 | item 1 + 3 (nullable columns; `/auth/session` payload consumed by the SPA; migration `0030_user_profile`) |
| F9-c | Avatar | F9-b | ~400 | item 5 + 2 (Pillow; untrusted image parsing) |
| F9-d | TOTP enrolment | F9-a, F9-b | ~550 | item 2 + 5 (secrets, new crypto deps; migration `0031_mfa`) |
| F9-e | 2FA at sign-in | F9-d | ~450 | item 2 (every login path) |
| F9-h | API key (read-only) | F9-a, F9-b | ~400 | item 2 (alternate authentication path; migration `0032_api_keys`) |
| F9-i | Account shell + profile UI | F9-b, F9-c | ~600 | none |
| F9-j | Security + API UI | F9-a, F9-d, F9-e, F9-h, F9-i | ~650 | none |
| F9-f | OAuth backend + owner guide | F9-a, F9-b, F9-e, the owner's OAuth apps | ~600 | item 2 + 5 (third-party auth, Authlib; migration `0033_oauth_links`) |
| F9-g | OAuth UI | F9-f | ~400 | none |

Migration numbers are the next free ones today; they are assigned at build time. Each migration unit is its own PR (deployed with a `pg_dump` first, `docs/knowledge/ops-runbook.md`).

Unit files: `F9-a-sessions.md`, `F9-b-profile-reauth.md`, `F9-c-avatar.md`, `F9-d-totp-enrolment.md`, `F9-e-2fa-sign-in.md`, `F9-f-oauth-backend.md`, `F9-g-oauth-ui.md`, `F9-h-api-key.md`, `F9-i-account-shell-profile-ui.md`, `F9-j-security-api-ui.md`.

## Data model (target)

| Revision | Change |
|---|---|
| `0029_sessions` (F9-a) | `rbsessions` (`rbses_`): `id` BIGINT PK; `user_id` FK `rbusers.id` CASCADE; `token_hash` CHAR(64) UNIQUE; `created_at`, `last_seen_at`, `expires_at` NULL; `remember` BOOL; `auth_method` VARCHAR(16) (`password`, `discord`, `google`); `mfa` BOOL; `reauth_at` NULL; `user_agent` VARCHAR(255); `ip_prefix` VARCHAR(48); `revoked_at` NULL. Indexes (`user_id`, `revoked_at`) and `expires_at`. |
| `0030_user_profile` (F9-b) | `rbuserprofile` (`rbupf_`): `user_id` PK FK CASCADE; `display_name` VARCHAR(40) NULL, `bio` VARCHAR(240) NULL, `country` CHAR(2) NULL, `city` VARCHAR(80) NULL, `avatar_file` VARCHAR(64) NULL, `avatar_version` INT NOT NULL DEFAULT 0, `updated_at`. `rbusers.email` → nullable (unique stays; `lower(email)` uniqueness enforced by the service as today); `rbusers.password_hash` → nullable (NULL = no password, OAuth-only); `rbusers.password_changed_at` NULL. |
| `0031_mfa` (F9-d) | `rbusermfa` (`rbmfa_`): `user_id` PK FK CASCADE; `secret_enc` TEXT; `enabled_at` NULL (NULL = pending); `last_step` BIGINT NULL; `created_at`. `rbrecoverycodes` (`rbrco_`): `id` PK; `user_id` FK CASCADE; `code_hash` CHAR(64); `used_at` NULL; index `user_id`. |
| `0032_api_keys` (F9-h) | `rbapikeys` (`rbapk_`): `id` PK; `user_id` UNIQUE FK CASCADE; `prefix` VARCHAR(16); `key_hash` CHAR(64) UNIQUE; `created_at`; `last_used_at` NULL. |
| `0033_oauth_links` (F9-f) | `rboauthlinks` (`rboal_`): `id` PK; `user_id` FK CASCADE; `provider` VARCHAR(16) CHECK IN ('discord','google'); `subject` VARCHAR(255); `display` VARCHAR(120); `linked_at`, `last_login_at`. UNIQUE (`provider`,`subject`), UNIQUE (`user_id`,`provider`). |

Every revision is reversible and portable on SQLite and PostgreSQL 18; each adds a round-trip + drift test. Downgrades that drop data say so in the docstring.

New environment variables (`.env.example`, `docs/`, startup validation naming the variable only): `TOTP_ENCRYPTION_KEY` (F9-d), `AVATAR_DIR` (F9-c), `OAUTH_DISCORD_CLIENT_ID`/`_SECRET`, `OAUTH_GOOGLE_CLIENT_ID`/`_SECRET` (F9-f). A provider is enabled only when both its id and secret are set.

## API (target)

Base `/riftbound/api/v1` unless noted. "existing" = already in the code.

| Method | Path | Auth | Unit | Purpose |
|---|---|---|---|---|
| GET | `/auth/session` | P | existing; extended in b | adds `display_name`, `avatar_url` to `user` (additive) |
| POST | `/auth/login` | P | existing; extended in e | `200 {mfa_required: true}` and no session when 2FA is on |
| POST | `/auth/mfa` | P (pending step in the Flask session) | e | complete a 2FA sign-in |
| PATCH | `/me/account` | U | existing; extended in b | e-mail may be cleared; a password change revokes the other sessions; re-auth rules |
| GET / PATCH | `/me` | U | b | profile (display name, bio, country, city) + security summary |
| POST | `/me/reauth` | U | b | re-authenticate with password or TOTP code |
| POST / DELETE | `/me/avatar` | U | c | upload / remove |
| GET | `/users/<id>/avatar?size=256\|64&v=<n>` | U | c | versioned image, private cache |
| GET | `/me/sessions` | U | a | active sessions |
| DELETE | `/me/sessions/<id>` · `/me/sessions` | U | a | revoke one / all others |
| POST | `/me/2fa/setup` · `/enable` · `/disable` · `/recovery-codes` | U | d | TOTP lifecycle |
| GET / POST / DELETE | `/me/api-key` | U | h | metadata / create-or-replace (shown once) / revoke |
| GET | `/riftbound/auth/oauth/<provider>/start` · `/callback` | P | f | browser redirects (not under `/api/`) |
| POST | `/auth/oauth/complete` | P (pending identity) | f | finish OAuth sign-up with a username |
| DELETE | `/me/connections/<provider>` | U | f | unlink (re-auth) |
| GET | `/meta/config` | P | existing; extended in f | lists enabled OAuth providers |

New error codes (each: `ErrorCode` value, `errors.json` entry, catalog test): `reauth_required` (403), `mfa_invalid` (401), `mfa_expired` (401), `last_sign_in_method` (409), `api_key_invalid` (401), `api_key_read_only` (403), `image_invalid` (400), `file_too_large` (413), `oauth_failed`, `oauth_cancelled`, `oauth_identity_in_use` (redirect params). `current_password_incorrect` stays the wrong-current-password code (there is no `POST /me/password`; F9-b extends `PATCH /me/account`). CLI: `flask sessions purge` (also a job kind on the F4-a runner, daily).

## UI

Routes under `/riftbound/app/account/` (`requireAuth`): `profile` (exists), `security`, `api`, `interface` (exists); `/account` redirects to `profile`. Auth: `/login` gains a 2FA step (`/login/2fa`, F9-e) and provider buttons (F9-g); `/register` gains provider buttons; new `/oauth/complete` (F9-g).

| Breakpoint | Layout |
|---|---|
| Mobile < 860 | One column; section tabs in a horizontally scrollable row; stacked cards: identity (avatar 80, display name, @username), details form, connections; Security: password, 2FA, sessions as cards. |
| Desktop ≥ 1240 | Sticky sidebar 264 px (avatar 42, name, section links) + content in two card columns. |
| Wide ≥ 1600 | Sidebar + three columns; the API page shows the key card and a `curl` example with a placeholder key side by side. |

Flows: 2FA wizard in a `Modal` (scan QR or enter secret → verify code → recovery codes with copy, download and an "I saved them" checkbox before closing); re-auth dialog opens automatically on `reauth_required` and retries the original request once; avatar upload with preview; API key shown once with copy and a warning. Every destructive action uses `ConfirmDialog`. Forms use `Field` (labels, `aria-invalid`, `aria-describedby`); the code input is `inputmode="numeric" autocomplete="one-time-code"`; the QR has a text alternative (the secret grouped by 4). Offline: account pages show cached session data read-only and disable every action with the offline reason. All strings are English (`account` and `auth` namespaces).

## Deferred: account deletion (was F9-k)

Not built (owner 2026-11-12). If adopted later it needs its own design. The purge would have to delete, in one transaction per user: `rbcollection` and `rbcollection_locations`/`rblocations` first (their FKs use `username`, RESTRICT), then `rbdeckheads` (+`rbdeckversions`), `rbwishlists` (+lines, alerts), `rbuserproducts`, `rbkeepplayset`, `rbvaluesnaps`, `rbimportpreviews`, `rbuserprefs`, the F9 tables, avatar files; and null the soft references `rbadminaudit.rbaud_actor_id`, `rbcardchanges.rbchg_decided_by`, `rbjobs.rbjob_requested_by`. Every later phase adds its tables to that list.

## Risks and notes

- **Forced re-login**: F9-a changes the identity format; every current session and remember cookie stops working once (pre-F9 cookies hold a plain user id and load as anonymous). Announce it; no other deploy action.
- **No bypass of 2FA**: API login, OAuth sign-in and remember cookies created before 2FA was enabled (revoked by the F9-a rules) must all respect it (F9-e, F9-f tests). The Jinja form no longer exists.
- **Lockout coupling**: 2FA failures reuse `failed_login_count`; a correct password followed by wrong codes still locks (extend the lockout tests).
- **OAuth callback and SameSite**: the callback is a cross-site top-level GET; keep Lax cookies.
- **Rate limits are per worker** (memory storage) until F12 decides the storage; API-key limits share it.
- **Recovery without e-mail**: a user who loses the device and the codes needs the admin (F10 "reset 2FA"); F10 users admin waits for F9-a and F9-d.
- **CSRF has no exemptions**: bearer API keys authenticate GET only, so the rule stays intact.
