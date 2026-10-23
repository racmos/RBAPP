# F9: Account — phase spec

Status: planned · Depends on: F1 (shell, auth screens, prefs, API client); F4 scheduler only for F9-a purge and F9-k · Order (`docs/knowledge/roadmap.md`): medium priority, before production; F9-f/F9-g (Google/Discord) are done just before production (F12); F10 user admin waits for F9 · Source: roadmap §5 (F9), §4, design-handoff §3.11, §3.12, §6-10..17, §7.2-V5..V7, §7.3-D4/D6, §7.6-L14, §9 F9, §10-2/3/4, product.md "Users, accounts and security" and "Scope by phase"

## Goal

Each user manages their account from the app: an extended profile with avatar, a real password change,
TOTP two-factor authentication with recovery codes, the list of signed-in devices (server-side sessions)
with revoke, sign-in with Discord or Google, and a personal read-only API key. There are no payments and no
e-mail recovery (no mail server): the admin resets passwords (F10) and OAuth is the alternative way in.

## Current state

- **`rbusers`** (`app/models/user.py`): `id`, `username` (unique, 3-32 `[A-Za-z0-9._-]`, LOGIN-9),
  `email` (NOT NULL, unique), `password_hash` (NOT NULL, Werkzeug), `created_at`, `is_admin`, `is_blocked`
  (`is_active` = not blocked), `failed_login_count`, `locked_until`, `last_login_at`. `rbcollection` and
  `rbdecks` reference **`username`** (ON UPDATE CASCADE, ON DELETE RESTRICT); `rbuserprefs` references `id`.
- **Sessions are cookie-only**: Flask signed session + Flask-Login; `User.get_id()` is the default (the
  user id), so a session cannot be listed or revoked, and a password change does not end other sessions.
  Remember-me: 30-day absolute cookie, API login only (`config.py` `_session_settings`, F1 D8). Cookies
  HttpOnly + SameSite=Lax (kept Lax for future OAuth callbacks, `config.py` comment) + Secure in production.
- **Login**: `app/services/auth.py` (`authenticate` with lockout LOGIN-2/3, constant-time dummy hash
  LOGIN-5, `register_user`), API `app/api/v1/auth.py` (`/auth/session`, `/auth/captcha`, `/auth/login`,
  `/auth/logout`, `/auth/register`), Jinja `app/routes/auth.py` (`/riftbound/login`, `/register`, POST
  `/logout`). Limits: login 10/min + 50/h, register 5/h per IP (`Flask-Limiter`, memory per worker).
- **Profile**: Jinja page `/riftbound/profile` + `POST /riftbound/profile/update` (`ProfileUpdate`: email,
  password with `current_password`, PROF-1..3). No display name, bio, country, avatar.
- **Admin CLI** `flask users promote|demote|block|unblock|set-password|list|unlock` (`app/cli/users.py`).
- **Frontend**: `/riftbound/app/account` redirects to `/account/interface` (`frontend/src/app/routes.tsx`);
  `InterfacePage`; `SettingsCard`, `PasswordInput`, `Avatar`, `Switch`, `Modal`, `ConfirmDialog`, `Toast`
  primitives exist. Nav entry `profile` is `legacy` (Jinja profile).
- **Dependencies** (`requirements.txt`): no Pillow, no TOTP, no OAuth, no crypto library.

## Scope

In:
- Server-side session table; devices list; revoke one / all others; sessions end on password change,
  2FA change and block.
- Extended profile (display name, bio, country, city), avatar upload stored server-side, password change.
- TOTP 2FA: enroll with QR, verify, recovery codes, disable, challenge at every sign-in path.
- Discord and Google OAuth: sign in, sign up (D-F9-5), link/unlink; step-by-step owner guide.
- Personal API key: created server-side, stored hashed, shown once, read-only.
- Account section in React (`/account/profile`, `/account/security`, `/account/api`, `/account/interface`).
- Scheduled account deletion if the owner adopts it (D-F9-2).

Out (design-handoff §3.11 verdicts): subscription plans, payments, invitations, multiple e-mails with
verification, providers other than Discord/Google, currency/provider selector, public profile pages
(D-F9-3), e-mail password recovery. Admin actions on other users (F10).

## Decisions already taken

- No mail server → no e-mail recovery or verification; admin resets passwords (product.md).
- TOTP 2FA, sessions/devices with a **server-side session table**, Discord/Google login with a guided setup
  for the owner, API key; no payments (product.md F9, roadmap F9).
- Session cookie + CSRF, no JWT; remember-me 30 days absolute (product.md "Architecture decisions").
- CSRF has no exemptions (AGENTS.md); secrets only in environment variables.
- The prototype's account data is client-only; everything becomes server state; API key server-generated,
  hashed, shown once (design-handoff §6-17).
- `is_admin`/`is_blocked` are never changed by account endpoints (ACL-1/ACL-6).
- Google/Discord login (owner, 2026-10-22): kept in F9 and done just before production; the owner creates
  the OAuth apps following a step-by-step guide (`docs/oauth-setup.md`, F9-R22). The OAuth apps are an
  owner input still pending, needed for F9-f.
- Job runner (owner, 2026-10-22): F9's daily purges register job kinds on the F4-a runner; F9 builds no
  runner of its own.
- Tests (owner, 2026-10-22, unit M-a): each F9 unit writes its own tests and re-creates the removed guard of
  the area it touches (migration round-trip + drift test, error-code catalog test, ES/EN parity, pin check
  for new dependencies).

## Requirements

### Sessions (F9-a)
- **F9-R1** Every successful sign-in (password, password + TOTP, OAuth) MUST create a row in `rbsessions`
  and store only an opaque random token (32 bytes, urlsafe) in the Flask-Login identity: `User.get_id()`
  returns `"s:" + token` for the session being created; `user_loader` resolves it by sha256, rejecting
  revoked, expired or blocked rows. The remember cookie carries the same token, so it is revocable too.
- **F9-R2** Pre-F9 cookies (plain numeric ids) MUST load as anonymous (one forced sign-in after deploy).
- **F9-R3** Expiry: remember sessions 30 days absolute (unchanged); other sessions end with the browser
  session or after 12 h without activity (D-F9-9). `last_seen_at` updated at most once every 5 minutes.
- **F9-R4** Logout revokes the current row. Password change, 2FA enable/disable and recovery-code
  regeneration revoke every other session of the user; block (CLI or F10) revokes all.
- **F9-R5** `GET /me/sessions` lists active sessions (created, last seen, approximate IP = IPv4 /24 or IPv6
  /48 prefix, device label parsed from the User-Agent without a new dependency, auth method, remember,
  `current`). `DELETE /me/sessions/{id}` and `DELETE /me/sessions` (all except current).
- **F9-R6** `flask sessions purge` deletes rows revoked or expired more than 30 days ago (a job kind on the F4-a runner, enqueued daily).

### Re-authentication
- **F9-R7** Sensitive actions (2FA setup/disable/regenerate, API key create, unlink a provider, password
  change without a current password, delete account) require a re-authentication in the last 10 minutes:
  `POST /me/reauth {password}` or `{code}` (TOTP) sets `rbses_reauth_at`; otherwise 403 `reauth_required`.
  OAuth-only accounts without 2FA re-authenticate with an OAuth round trip (`intent=reauth`).

### Profile, password, avatar (F9-b, F9-c)
- **F9-R8** `GET /me` returns user (id, username, email, is_admin, created_at), profile (display_name,
  bio, country, city, avatar_url), security summary (has_password, mfa_enabled, connections, api_key
  prefix or null, delete_after). `/auth/session` adds `display_name` and `avatar_url` to `user` (additive
  change of the F1 contract; frontend types updated in the same unit).
- **F9-R9** `PATCH /me`: display_name 1..40, bio ≤ 240, country ISO 3166-1 alpha-2 (from the meta list),
  city ≤ 80, email (format as LOGIN-9; case-insensitive unique → 409 `email_taken`; `null` allowed only if
  D-F9-1 makes e-mail optional). Username is not editable (D-F9-7).
- **F9-R10** `POST /me/password {current_password, new_password}`: 8..PASSWORD_MAX_LENGTH; wrong current →
  400 `current_password_invalid`; OAuth-only accounts (no password) set one after re-auth. One service
  shared with the Jinja `/profile/update` until F11 (both revoke other sessions).
- **F9-R11** `POST /me/avatar` (multipart `file`): ≤ 2 MB (413 `file_too_large`); format detected by Pillow
  (PNG, JPEG, WebP; not by extension) else 400 `image_invalid`; reject > 4096 px per side and decompression
  bombs; apply EXIF orientation, strip metadata, centre-crop square, store 256 and 64 px WebP in
  `AVATAR_DIR` (env, default `<instance>/avatars`) as `<user_id>-<random>.webp`; old files deleted.
  `DELETE /me/avatar`. Served by `GET /users/{id}/avatar?size=256|64&v=<n>` (U) with long-lived private
  cache headers; never from user-chosen paths.

### TOTP 2FA (F9-d, F9-e)
- **F9-R12** `POST /me/2fa/setup` (re-auth) creates a pending secret (160-bit base32) and returns `secret`,
  `otpauth_uri` (`otpauth://totp/Rift%20Manager:<username>?secret=…&issuer=Rift%20Manager&digits=6&period=30`)
  and `qr_svg` (rendered server-side; shown as `data:` image, CSP-compatible).
- **F9-R13** `POST /me/2fa/enable {code}` accepts the current or adjacent 30 s step, enables 2FA, returns 10
  one-time recovery codes once (format `xxxxx-xxxxx`, base32 lowercase), stores only their sha256.
  `POST /me/2fa/disable {code | recovery_code}` (re-auth) removes secret and codes.
  `POST /me/2fa/recovery-codes {code}` (re-auth) regenerates them. A code whose step is ≤ the last accepted
  step is rejected (replay).
- **F9-R14** The secret MUST be encrypted at rest with `TOTP_ENCRYPTION_KEY` (env; D-F9-4); production
  refuses to start without a valid key once F9-d is deployed (`validate_settings`, name only in the error).
- **F9-R15** Sign-in with 2FA enabled: `POST /auth/login` with the right password answers 200
  `{mfa_required: true}` and creates **no** session; the pending step (user, remember, method, 5-minute
  expiry, attempt count) lives in the Flask session. `POST /auth/mfa {code}` or `{recovery_code}` completes
  it. Wrong code → 401 `mfa_invalid` and counts as a failed login (same lockout, LOGIN-2/3); 5 wrong codes
  or expiry → 401 `mfa_expired` (start again). Same rate limits as login.
- **F9-R16** No path bypasses 2FA: API login, Jinja login form (for a 2FA user it creates no session and
  redirects to `/riftbound/app/login?next=…`), OAuth sign-in (D-F9-6), remember cookies created before 2FA
  was enabled (revoked by F9-R4).

### OAuth (F9-f, F9-g)
- **F9-R17** Providers `discord` (scopes `identify email`) and `google` (OpenID Connect: `openid email
  profile`). A provider is enabled only when both `OAUTH_<PROVIDER>_CLIENT_ID` and `_CLIENT_SECRET` are set;
  `GET /meta/config` lists enabled providers. Library: Authlib, pinned (D-F9-10).
- **F9-R18** Browser routes (not under `/api/`): `GET /riftbound/auth/oauth/<provider>/start?intent=
  login|link|reauth&next=` → redirect with `state` (random, in session, single use), PKCE S256 and, for
  Google, `nonce`; `GET /riftbound/auth/oauth/<provider>/callback` validates state, exchanges the code,
  verifies the identity (Google id_token signature, `aud`, `nonce`; Discord `/users/@me`). Errors redirect
  to `/riftbound/app/login?oauth_error=<code>` (`oauth_failed`, `oauth_cancelled`,
  `oauth_identity_in_use`) — never a JSON page in the browser.
- **F9-R19** Identities are matched only by (provider, subject). An account is **never** linked
  automatically by e-mail (e-mails are unverified in this app). Linking happens only from a signed-in,
  re-authenticated session (`intent=link`); an identity linked to another account → `oauth_identity_in_use`.
- **F9-R20** Sign-in with an unknown identity (D-F9-5): the callback stores the identity for 10 minutes and
  redirects to `/riftbound/app/oauth/complete`; `POST /auth/oauth/complete {username}` creates the account
  (e-mail = provider e-mail only if the provider says it is verified and no account uses it, else per
  D-F9-1), links it and signs in. Register rate limits apply; blocked users cannot sign in.
- **F9-R21** `DELETE /me/connections/{provider}` (re-auth) → 409 `last_sign_in_method` when it is the only
  way in (no password, no other link).
- **F9-R22** `docs/oauth-setup.md` (owner guide, ES with EN headings, placeholders `<BASE_URL>` only):
  Discord — Developer Portal → New Application "Rift Manager" → OAuth2 → Redirects
  `<BASE_URL>/riftbound/auth/oauth/discord/callback` → copy Client ID, reset and copy Client Secret → put both
  in the server environment file → restart → test. Google — Cloud console → new project → OAuth consent
  screen (External, app name, support e-mail, scopes openid/email/profile, test users while "Testing", then
  publish) → Credentials → OAuth client "Web application" → redirect URI
  `<BASE_URL>/riftbound/auth/oauth/google/callback` → copy ID/secret → environment → restart → test. It warns
  that the production URL (F12) needs its own redirect URIs (D-F12-9) and that secrets never go into chats,
  tickets or the repo.

### API key (F9-h)
- **F9-R23** One key per user: `rb_live_` + 40 lowercase hex (160 bits); stored as sha256 + 12-char prefix;
  `POST /me/api-key` (re-auth) creates or replaces and returns the key once; `GET` metadata (prefix,
  created_at, last_used_at); `DELETE` revokes.
- **F9-R24** `Authorization: Bearer <key>` authenticates **GET** requests under `/riftbound/api/v1/` only
  (Flask-Login `request_loader`), never sets a cookie, never grants admin, and is refused on `/auth/*`,
  `/me/sessions*`, `/me/api-key`, `/me/2fa/*`, `/me/connections*`, `/admin/*` (403). Unsafe methods with a
  key → 403 `api_key_read_only`; bad key → 401 `api_key_invalid`. 60 requests/min per key;
  `last_used_at` updated at most once a minute.

### Account deletion (F9-k, only if D-F9-2 = yes)
- **F9-R25** `POST /me/delete` (re-auth) sets `delete_after = now + 10 days` (server clock, design-handoff
  §7.6-L14), revokes other sessions, shows a global banner with "Cancelar"; `POST /me/delete/cancel`.
  Admins cannot schedule their own deletion (409 `admin_cannot_delete`).
- **F9-R26** `flask users purge-deleted` (a job kind on the F4-a runner, enqueued daily) deletes, in one
  transaction per user, every row that references the user (collection and decks by username first — their
  FKs are RESTRICT — then sales, profile, prefs, sessions, 2FA, links, keys and every other user table that
  exists at the time) and the avatar files, then the user; logs counts only. Phases that land after F9
  (F14 products, F15 rules, F8 events, results, saves, feeds) add their tables to the purge.

### UI, i18n, a11y, offline
- **F9-R27** Account routes are URLs (`/account/:section`); mobile horizontal tabs, desktop sidebar
  (design-handoff §3.11); every destructive action uses `ConfirmDialog` (design-handoff §7.3-D4).
- **F9-R28** Namespaces `account` and `auth` (new keys), ES/EN parity; recovery codes and API key in a
  monospace block with copy (`useCopyToClipboard` with fallback) and "Descargar .txt".
- **F9-R29** Forms use `Field` (labels, `aria-invalid`, `aria-describedby`); the 2FA code input is
  `inputmode="numeric" autocomplete="one-time-code"`; QR has a text alternative (the secret, grouped by 4).
- **F9-R30** Offline: account pages show cached data read-only (session/prefs only); every action is disabled
  with the offline reason.

## Data model changes

All reversible, one revision per unit. Risk: item 1 (and item 2).

| Revision (unit) | Change |
|---|---|
| `00xx_sessions` (F9-a) | `rbsessions` (`rbses_`): `id` BIGINT PK; `user_id` FK `rbusers.id` CASCADE; `token_hash` CHAR(64) UNIQUE; `created_at`, `last_seen_at`, `expires_at` TIMESTAMP NULL; `remember` BOOL; `auth_method` VARCHAR(16) (`password`, `discord`, `google`); `mfa` BOOL; `reauth_at` TIMESTAMP NULL; `user_agent` VARCHAR(255); `ip_prefix` VARCHAR(48); `revoked_at` TIMESTAMP NULL. Index (`user_id`, `revoked_at`). |
| `00xx_user_profile` (F9-b) | `rbuserprofile` (`rbupf_`): `user_id` PK FK CASCADE; `display_name` VARCHAR(40), `bio` VARCHAR(240), `country` CHAR(2), `city` VARCHAR(80), `avatar_file` VARCHAR(64), `avatar_version` INT DEFAULT 0, `updated_at`. `rbusers.password_hash` → nullable (NULL = no password); `rbusers.password_changed_at` TIMESTAMP NULL; `rbusers.email` → nullable if D-F9-1 (unique stays; both engines allow several NULLs). Downgrade refuses (message listing rows) if NULL hashes/e-mails exist. |
| `00xx_mfa` (F9-d) | `rbusermfa` (`rbmfa_`): `user_id` PK FK CASCADE; `secret_enc` TEXT; `enabled_at` TIMESTAMP NULL (NULL = pending); `last_step` BIGINT NULL; `created_at`. `rbrecoverycodes` (`rbrco_`): `id` PK; `user_id` FK CASCADE; `code_hash` CHAR(64); `used_at` NULL; index `user_id`. |
| `00xx_oauth_links` (F9-f) | `rboauthlinks` (`rboal_`): `id` PK; `user_id` FK CASCADE; `provider` VARCHAR(16) CHECK IN ('discord','google'); `subject` VARCHAR(255); `display` VARCHAR(120); `linked_at`, `last_login_at`. UNIQUE (`provider`,`subject`), UNIQUE (`user_id`,`provider`). |
| `00xx_api_keys` (F9-h) | `rbapikeys` (`rbapk_`): `id` PK; `user_id` UNIQUE FK CASCADE; `prefix` VARCHAR(16); `key_hash` CHAR(64) UNIQUE; `created_at`; `last_used_at` NULL. |
| `00xx_account_deletion` (F9-k) | `rbusers.delete_after` TIMESTAMP NULL. |

New environment variables (`.env.example`, `docs/`, validation): `TOTP_ENCRYPTION_KEY`,
`OAUTH_DISCORD_CLIENT_ID`, `OAUTH_DISCORD_CLIENT_SECRET`, `OAUTH_GOOGLE_CLIENT_ID`,
`OAUTH_GOOGLE_CLIENT_SECRET`, `AVATAR_DIR`. New pinned dependencies (D-F9-10): Pillow (already present if
F2-l card thumbnails shipped; otherwise added by F9-c), pyotp, segno (QR SVG), cryptography (Fernet),
Authlib — each added in the unit that needs it, with the `AGENTS.md` table updated and the pin check
re-created (test policy of M-a).

## API

Base `/riftbound/api/v1` unless noted.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET / PATCH | `/me` | U | Profile + security summary / update profile fields. |
| POST | `/me/password` | U | Change or set password. |
| POST | `/me/reauth` | U | Re-authenticate (password or TOTP). |
| POST / DELETE | `/me/avatar` | U | Upload / remove avatar. |
| GET | `/users/{id}/avatar` | U | Avatar image (versioned, cached). |
| GET | `/me/sessions` | U | Active sessions. |
| DELETE | `/me/sessions/{id}` · `/me/sessions` | U | Revoke one / all others. |
| POST | `/me/2fa/setup` · `/me/2fa/enable` · `/me/2fa/disable` · `/me/2fa/recovery-codes` | U | TOTP lifecycle. |
| POST | `/auth/mfa` | P (pending step in session) | Complete a 2FA sign-in. |
| GET | `/riftbound/auth/oauth/<provider>/start` · `/callback` | P | OAuth redirects (browser). |
| POST | `/auth/oauth/complete` | P (pending identity in session) | Finish OAuth sign-up with a username. |
| DELETE | `/me/connections/{provider}` | U | Unlink. |
| GET / POST / DELETE | `/me/api-key` | U | Key metadata / create-or-replace / revoke. |
| POST | `/me/delete` · `/me/delete/cancel` | U | Scheduled deletion (D-F9-2). |

New error codes (enum + `errors.json` ES/EN + contract test): `reauth_required` (403),
`current_password_invalid` (400), `mfa_invalid` (401), `mfa_expired` (401), `oauth_failed`,
`oauth_cancelled`, `oauth_identity_in_use` (409 / redirect param), `last_sign_in_method` (409),
`api_key_invalid` (401), `api_key_read_only` (403), `image_invalid` (400), `file_too_large` (413),
`admin_cannot_delete` (409). `POST /auth/login` gains the success shape `{mfa_required: true}`
(additive; API-5 spec updated in F9-e). CLI: `flask sessions purge`, `flask users purge-deleted`.

## UI

Routes under `/riftbound/app/account/` (`requireAuth`): `profile`, `security`, `api`, `interface`
(existing); `/account` redirects to `profile`. Auth routes: `/login` gains provider buttons and a 2FA step
(`/login/2fa`), `/register` gains provider buttons, new `/oauth/complete`.

| Breakpoint | Layout |
|---|---|
| Mobile < 860 | One column; section tabs in a horizontally scrollable row (design-handoff §0.2 "Account en móvil"); cards stacked: identity (avatar 80, display name, @username), details form, connections; Security: password, 2FA, sessions (list cards), danger zone. |
| Desktop ≥ 1240 | Sticky sidebar 264 px (avatar 42, name, e-mail, section links) + content in 2 card columns: Profile = identity + bio │ country/city + connections; Security = password + 2FA │ sessions table (device, approx. IP, method, last seen, created, revoke) + "Cerrar las demás". |
| Wide ≥ 1600 | Sidebar + 3 card columns (Security adds an activity summary: last sign-in, failed attempts, 2FA status); API page shows key card + usage example (`curl` with a placeholder key) + endpoint list side by side. |

Flows: 2FA wizard in a `Modal` (1 scan QR / enter secret → 2 verify code → 3 recovery codes with copy,
download and "Los he guardado" checkbox before closing); re-auth dialog opened automatically on
`reauth_required` then the original request is retried once; avatar upload with preview and progress;
API key reveal once with copy + warning "No la volverás a ver"; deletion banner in `AppShell` with countdown
from `delete_after`. Remove `profile` legacy nav entry → `spa` (`/account/profile`). Strings ES/EN for every
label above (unit requirements give the exact copy).

## Units

| ID | Title | Depends on | Size | Risk | Summary |
|---|---|---|---|---|---|
| F9-a | Server-side sessions | F1 | ~550 | Risk: item 2 + item 1 (identity loading for every request; migration) | `rbsessions`, token identity in Flask-Login, revoke on logout/password/block, `GET/DELETE /me/sessions`, purge CLI, Jinja profile password change revokes too. |
| F9-b | Profile + password + re-auth API | F9-a | ~500 | Risk: item 1 + item 3 (nullable columns; `/auth/session` payload consumed by the SPA) | `rbuserprefs`-style `rbuserprofile`, `GET/PATCH /me`, `POST /me/password`, `POST /me/reauth`, e-mail optional if D-F9-1, session payload extension + frontend types. |
| F9-c | Avatar | F9-b | ~400 | Risk: item 5 + item 2 (Pillow; untrusted image parsing) | Upload/delete/serve, `AVATAR_DIR`, error codes `image_invalid`, `file_too_large`. |
| F9-d | TOTP enrolment | F9-a, F9-b | ~550 | Risk: item 2 + item 5 (secrets, new crypto deps) | `rbusermfa`, recovery codes, setup/enable/disable/regenerate, encryption key + config validation, QR SVG. |
| F9-e | 2FA at sign-in | F9-d | ~550 | Risk: item 2 (every login path) | `{mfa_required}` step, `POST /auth/mfa`, lockout integration, Jinja login guard/redirect, SPA `/login/2fa` screen. |
| F9-f | OAuth backend + owner guide (just before production) | F9-a, F9-b, F9-e, OAuth apps (owner, guided) | ~600 | Risk: item 2 + item 5 (third-party auth; Authlib) | Start/callback, state + PKCE + nonce, link/unlink, sign-in, sign-up completion API, meta providers, `docs/oauth-setup.md`. |
| F9-g | OAuth UI (just before production) | F9-f | ~450 | Risk: none | Provider buttons on login/register, `/oauth/complete`, `oauth_error` mapping, connections card. |
| F9-h | API key | F9-a | ~400 | Risk: item 2 (alternate authentication path) | `rbapikeys`, bearer `request_loader`, read-only + exclusions, rate limit, endpoints, docs. |
| F9-i | Account shell + Profile UI | F9-b, F9-c | ~600 | Risk: none | `/account/:section` layout (tabs/sidebar), profile form, avatar upload, nav flip. |
| F9-j | Security + API UI | F9-a, F9-d, F9-h, F9-i | ~600 | Risk: none | Password card, 2FA wizard, sessions list, re-auth dialog, API key card. |
| F9-k | Scheduled account deletion | F9-i, F4 scheduler, D-F9-2 | ~450 | Risk: item 1 + item 3 (destructive purge across every phase's tables) | `delete_after`, request/cancel, banner, `flask users purge-deleted` with per-table tests. |

## Open decisions

| ID | Question | Options | Recommendation | Blocks |
|---|---|---|---|---|
| D-F9-1 | E-mail (design-handoff §10-2) | keep required / optional informational, unverified | Optional (nullable, unique when present); register keeps the field but optional | F9-b, F9-f |
| D-F9-2 | Scheduled account deletion (design-handoff §10-3) | 10-day grace / immediate / none | 10-day grace with server clock and daily purge | F9-k |
| D-F9-3 | Social links and public profile (design-handoff §10-4) | public profile page / private links / drop links | No public profile; drop social links in F9 (country/city kept for events) | F9-b |
| D-F9-4 | Encrypt TOTP secrets at rest | Fernet with `TOTP_ENCRYPTION_KEY` / plain | Encrypt (DB backups leave the server in F12) | F9-d |
| D-F9-5 | OAuth creates new accounts? | sign-up allowed (username step) / link-only | Allowed, never auto-link by e-mail | F9-f |
| D-F9-6 | 2FA also after OAuth sign-in | yes / no | Yes | F9-e, F9-f |
| D-F9-7 | Username editable | no / yes with limits | No; use display name | F9-b |
| D-F9-8 | API key scope | read-only GET / read-write | Read-only in F9 (keeps the "no CSRF exemptions" rule intact) | F9-h |
| D-F9-9 | Idle expiry of non-remember sessions | 12 h / 24 h / browser close only | 12 h idle + browser close | F9-a |
| D-F9-10 | New dependencies (Pillow, pyotp, segno, cryptography, Authlib) | approve / alternatives | Approve, exact pins, added per unit | F9-c, F9-d, F9-f |
| D-F9-11 | Device location detail | IP prefix only / geo-IP city | Prefix only, no geo-IP database | F9-a |
| D-F9-12 | Who sees avatars and display names | signed-in users only / public | Signed-in users only (avatar route is `U`) | F9-c |

## Risks and notes

- **Forced re-login**: F9-a changes the identity format; every current session and remember cookie stops
  working once. Announce it; the deploy needs no other action.
- **2FA bypass**: the Jinja login form stays until F11; F9-e must guard it (test: 2FA user posts the right
  password to `/riftbound/login` → no session).
- **Lockout coupling**: 2FA failures reuse `failed_login_count`; make sure a correct password followed by
  wrong codes still locks (LOGIN-2/3 tests extended).
- **OAuth callback and SameSite**: the callback is a cross-site top-level GET; Lax cookies are sent, Strict
  would break it (keep `config.py` as is).
- **Username FKs**: deletion must remove `rbcollection`/`rbdecks` rows explicitly (RESTRICT).
- **Admin reset (F10)** relies on F9-a revocation and F9-d "reset 2FA"; F10 must come after F9 (cross-phase).
- **Rate limits are per worker** (memory storage) until F12 decides the storage; API-key limits share it.
- **Recovery without e-mail**: a user who loses device and recovery codes needs the admin (F10 "reset 2FA").
