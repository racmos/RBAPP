# F9-f: Sign-in with Discord or Google (backend + owner guide)

| Field | Value |
|---|---|
| Phase / unit | F9 / f |
| Branch | `feat/f9f-oauth-backend` (from up-to-date `main`; done last in F9, just before F12) |
| Depends on | F9-a (sessions, `auth_method`), F9-b (nullable e-mail and password, re-auth), F9-e (pending 2FA step, `sessions.sign_in`), the owner's OAuth applications (created with the guide this unit writes) |
| Size forecast | ~600 authored lines (tests and docs included) |
| Risk | `Risk: item 2 (third-party authentication, account creation and linking) + item 5 (new pinned dependency Authlib, new secrets) + item 1 (migration 0033_oauth_links)` |
| TDD | ON (strict). Runners: `venv/bin/pytest`, `cd frontend && npx vitest run` (types only) |
| Save as | `docs/requirements/F9/F9-f-oauth-backend.md` |

## Objective

A person can sign in with a Discord or Google account: an existing user who connected that account gets
in (after the 2FA code when they use 2FA), and a new person creates an account by choosing a username.
Accounts are matched only by the provider's own user id, never by e-mail, so nobody can take over an
account by owning a matching address. A signed-in user can connect or disconnect a provider and can use
it to confirm their identity. The owner gets a step-by-step guide to create the two OAuth applications.
The screens are F9-g.

## Read first

- `AGENTS.md` (Blueprints, CSRF, Sessions, Configuration, Security), `docs/knowledge/conventions.md`
- `docs/requirements/F9/README.md` (D-F9-5, D-F9-6, D-F9-1, risks: SameSite, no bypass)
- `F9-a-sessions.md` (S5), `F9-b-profile-reauth.md` (S2, S5, S7, S9-S11), `F9-e-2fa-sign-in.md` (S1-S4)
- `app/__init__.py` (blueprint registration order), `app/routes/redirects.py` (`login_location`, the
  safe-`next` rule), `app/api/v1/auth.py`, `app/api/v1/meta.py`, `config.py`
- `app/schemas/validators.py` (`USERNAME_PATTERN`), `tests/test_authz_matrix.py`

## Scope

In:
- Authlib pin; settings `OAUTH_DISCORD_CLIENT_ID`, `OAUTH_DISCORD_CLIENT_SECRET`,
  `OAUTH_GOOGLE_CLIENT_ID`, `OAUTH_GOOGLE_CLIENT_SECRET`
- Migration `0033_oauth_links`, model `RbOAuthLink` (`app/models/oauth_link.py`)
- `app/services/oauth.py` (flows, identity fetch, matching, sign-up, link, unlink, re-auth)
- Blueprint `oauth` (`app/routes/oauth.py`): `GET /riftbound/auth/oauth/<provider>/start` and
  `/callback`
- `GET`/`POST /auth/oauth/complete`, `DELETE /me/connections/<provider>`; `/meta/config` providers;
  `GET /me` `security.connections`; re-auth `methods` with linked providers
- Error codes `oauth_failed`, `oauth_cancelled`, `oauth_identity_in_use`, `last_sign_in_method`
- `docs/oauth-setup.md` (owner guide, placeholders only)
- Frontend: types and endpoint functions only

Out (do not do, even if tempting):
- Any screen (F9-g)
- Other providers, linking by e-mail, importing the provider's avatar, e-mail verification
- Storing provider access or refresh tokens (they are used once and dropped)

## Specs

S1. Pin `Authlib==…` (newest release at least two weeks old; version and date in the PR) and its row in
    the `AGENTS.md` technology table; `tests/test_dependency_pins.py` extended.
S2. Settings (config, `.env.example` with empty values, `README.md`): a provider is **enabled** only when
    both its id and secret are non-blank. Outside `testing`, exactly one of a pair set → `ConfigError`
    naming the missing variable (never a value). Secrets are never logged or returned.
S3. Migration `0033_oauth_links` (next free number): `riftbound.rboauthlinks` (model `RbOAuthLink`):
    `rboal_id` BIGINT PK `rboauthlinks_pkey` (SQLite INTEGER variant); `rboal_user_id` INTEGER NOT NULL
    FK `rboauthlinks_user_fk` → `rbusers.id` ON DELETE CASCADE; `rboal_provider` VARCHAR(16) NOT NULL,
    CHECK `ck_rboauthlinks_provider` (`IN ('discord', 'google')`); `rboal_subject` VARCHAR(255) NOT NULL;
    `rboal_display` VARCHAR(120) NULL; `rboal_linked_at` TIMESTAMP NOT NULL; `rboal_last_login_at`
    TIMESTAMP NULL; UNIQUE `rboauthlinks_provider_subject_key` (`rboal_provider`, `rboal_subject`),
    UNIQUE `rboauthlinks_user_provider_key` (`rboal_user_id`, `rboal_provider`). Downgrade: refuses,
    changing nothing, while any user has no password **and** a link (they could not sign in afterwards;
    the message lists up to 20 usernames), else drops the table (docstring: connections lost).
S4. Providers: `discord` (OAuth 2.0 authorization code + PKCE S256, scopes `identify email`; identity =
    the current-user endpoint: `id` → subject, `global_name` or `username` → display, `email` and
    `verified`) and `google` (OpenID Connect authorization code + PKCE S256 + `nonce`, scopes `openid
    email profile`; the ID token is verified by Authlib: signature with the provider's published keys,
    `iss`, `aud`, `exp`, `nonce`; `sub` → subject, `name` → display, `email`, `email_verified`).
    Endpoints are taken from each provider's documentation and kept as constants in
    `app/services/oauth.py`. Every provider call goes through one function, `oauth.fetch_identity(
    provider, code, code_verifier, nonce, redirect_uri) -> Identity(subject, display, email,
    email_verified)`, which tests replace (nothing in the tests reaches the internet). Provider tokens
    are used for that call only and never stored or logged; neither is the `code`.
S5. `GET /riftbound/auth/oauth/<provider>/start?intent=login|link|reauth&next=<path>&remember=true|false`
    (blueprint `oauth`, endpoint `oauth.start`, **P**, 20/minute per IP `scope='oauth'`):
    - unknown or disabled provider → 404 (the `wants_json()` rule; browsers get the inline page);
    - `intent` absent = `login`; another value, or `remember` not `true`/`false` → 302 to the intent's
      error target (S8) with `oauth_error=oauth_failed`;
    - `login` while signed in → 302 `/riftbound/app/`; `link`/`reauth` while anonymous → 302
      `/riftbound/app/login`;
    - `link` without a recent re-auth (F9-b S9) → 302 `/riftbound/app/account/profile?oauth_error=reauth_required`;
    - `next` must pass the safe-path rule of `app/routes/redirects.py` (a `/riftbound/` path), else the
      default: `login` → `/riftbound/app/`, `link` → `/riftbound/app/account/profile`, `reauth` →
      `/riftbound/app/account/security`; `remember` absent = `true`;
    - stores `oauth_flow = {provider, intent, state, code_verifier, nonce, next, remember, uid,
      started_at}` in the Flask session (`state` and the verifier from `secrets`, `uid` for `link` and
      `reauth`), replacing any previous flow, and answers 302 to the provider's authorization URL with
      `redirect_uri = url_for('oauth.callback', provider=…, _external=True)` (ProxyFix gives the
      public scheme and host; nothing is hard-coded).
S6. `GET /riftbound/auth/oauth/<provider>/callback` (`oauth.callback`, **P**, same limit): the flow is
    read and **removed** from the Flask session first. No flow, older than 10 minutes, another provider
    or `state` mismatch → `oauth_failed`; `error=access_denied` → `oauth_cancelled`; any other `error`
    or a failing `fetch_identity` → `oauth_failed` (logged without codes or tokens). Then by intent
    (S7-S9). Cookies stay `SameSite=Lax` (the callback is a cross-site top-level GET, which Lax allows).
S7. Intent `login`:
    - a link `(provider, subject)` exists → its user. Blocked → `oauth_failed` (no hint). 2FA enabled →
      F9-e pending step `{uid, remember, method: <provider>, …}` and 302 `/riftbound/app/login/2fa`
      (plus `?next=` when `next` is not the default); the code is then required exactly as after a
      password (D-F9-6). Otherwise `sessions.sign_in(user, remember=flow.remember,
      auth_method=<provider>, mfa_passed=False)`, link `last_login_at = now`, user `last_login_at =
      now`, 302 to `next`. A running password lock does not stop an OAuth sign-in (it guards the
      password); the 2FA step still honours it (F9-e S4).
    - no link → sign-up pending: `oauth_signup = {provider, subject, display, email, remember,
      started_at}` (10 minutes) where `email` is the provider e-mail **only** when the provider marks it
      verified and no account uses it (ignoring case), else `null`; 302 `/riftbound/app/oauth/complete`.
      **Never auto-link by e-mail**: a verified e-mail equal to an existing account's e-mail neither
      links nor signs in that account (D-F9-5).
S8. Intent `link` (the flow's `uid` must be the signed-in user, else `oauth_failed`): the subject is
    linked to another user → `oauth_identity_in_use`; already linked to this user → nothing changes;
    the user already has a link to this provider with another subject → `oauth_failed`; otherwise a new
    link (`display`, `linked_at = now`). Success → 302 `/riftbound/app/account/profile?oauth_linked=<provider>`.
    Error targets: `login` → `/riftbound/app/login?oauth_error=<code>`; `link` →
    `/riftbound/app/account/profile?oauth_error=<code>`; `reauth` → `next` with `oauth_error=<code>`
    appended.
S9. Intent `reauth` (flow `uid` = the signed-in user): the subject must be the user's link for that
    provider → the current session's `reauth_at = now` → 302 `next`; else `oauth_failed`.
S10. `GET /auth/oauth/complete` (**P**, API v1) → 200 `{provider, display, email, suggested_username}`
    while a sign-up is pending, else the 404 envelope. `suggested_username` = `display` reduced to the
    characters `USERNAME_PATTERN` allows, cut to 32, `null` when shorter than 3 or already taken.
S11. `POST /auth/oauth/complete` (**P**, CSRF, body `{username}`, `10/hour` per IP
    `scope='oauth_complete'`): no or expired pending sign-up → 400 `{code: "oauth_failed"}`; username
    invalid → 400 `validation_error` (same rule and message as register); taken → 409 `username_taken`;
    the subject got linked meanwhile → 400 `oauth_identity_in_use`. Success, one transaction: a user
    with `password_hash = NULL`, `email` = the pending e-mail (NULL if it was taken meanwhile), a link
    row, then `sessions.sign_in(..., auth_method=<provider>, mfa_passed=False)` (a new account has no
    2FA) → 201 `{user}`; the pending sign-up is removed. No captcha (the provider account stands in).
S12. `DELETE /me/connections/<provider>` (U, re-auth): unknown provider or not linked → 404 envelope;
    it is the user's last way to sign in (no password and no other link) → 409 `{code:
    "last_sign_in_method"}`; otherwise the link is deleted → 200 `{connections: [...]}`.
S13. `GET /me` `security.connections` = `[{provider, display, linked_at, last_login_at}]` in the order
    `discord`, `google`; `reauth_required.params.methods` (F9-b S9) adds the linked providers;
    `GET /meta/config` gains `oauth: {providers: [...]}` = the enabled providers in that order (empty
    list when none).
S14. 2FA after OAuth, blocked users, and the never-by-e-mail rule are tested as no-bypass cases (F9-e
    S8 list extended).
S15. Error codes (enum, `errors.json`, catalog test; used in JSON bodies and as `oauth_error` redirect
    values): `oauth_failed` → "Sign-in with the provider failed. Try again."; `oauth_cancelled` →
    "Sign-in with the provider was cancelled."; `oauth_identity_in_use` → "That account is already
    connected to another Rift Manager user."; `last_sign_in_method` (409) → "You can't remove your only
    way to sign in. Set a password or connect another account first."
S16. `docs/oauth-setup.md` (owner guide, new file, placeholders only, no real hosts, ids or secrets):
    1. What it enables and what it never does (no e-mail linking, tokens not stored).
    2. Discord: create an application in the Discord Developer Portal → OAuth2 → add the redirect
       `https://<your-host>/riftbound/auth/oauth/discord/callback` → copy the client id and secret.
    3. Google: Google Cloud console → OAuth consent screen (external; scopes `openid`, `email`,
       `profile`; app name "Rift Manager") → Credentials → OAuth client "Web application" → authorised
       redirect `https://<your-host>/riftbound/auth/oauth/google/callback` → copy id and secret.
    4. Put the four values in the service environment file (never in git), restart, check
       `GET /riftbound/api/v1/meta/config` lists the providers.
    5. Turning a provider off (blank both values), rotating a secret, and what users who signed up
       with a provider need (set a password before a provider is removed).
    6. Proxy requirement: Nginx must send `X-Forwarded-Proto` and `Host` (the redirect URI is built
       from them).
S17. Frontend (types only): `MetaConfig.oauth`, `OAuthPending`, `MeData.security.connections`;
    `getOAuthPending`, `completeOAuth`, `deleteConnection` in `api/endpoints.ts`; a helper
    `oauthStartUrl(provider, intent, next, remember)` in `src/auth/` that builds the start URL (the SPA
    navigates there with a full page load).

## API / data contract

| Method | Path | Auth | Endpoint name | Notes |
|---|---|---|---|---|
| GET | `/riftbound/auth/oauth/<provider>/start` | P | `oauth.start` | S5, browser redirect |
| GET | `/riftbound/auth/oauth/<provider>/callback` | P | `oauth.callback` | S6-S9, browser redirect |
| GET | `/riftbound/api/v1/auth/oauth/complete` | P | `api_v1.oauth_pending` | S10 |
| POST | `/riftbound/api/v1/auth/oauth/complete` | P (pending sign-up) | `api_v1.oauth_complete` | S11 |
| DELETE | `/riftbound/api/v1/me/connections/<provider>` | U (re-auth) | `api_v1.delete_connection` | S12 |
| GET | `/riftbound/api/v1/meta/config` | P | existing | S13 (additive) |

Blueprint `oauth` registered after `legacy_redirects` and before `spa_bp`; nothing under
`/riftbound/app/`. The `oauth.*` rules are added to the CSRF test's knowledge as GET-only. Migration
`0033_oauth_links` (S3). `docs/api.md`: "Sign-in with Discord or Google (F9-f)".

## UI

none (F9-g).

## Acceptance criteria

- [ ] AC1 `tests/test_oauth_links_migration.py`: round trip, names, CHECK, downgrade refusal and
      success, `drift()` clean (S3)
- [ ] AC2 `tests/test_oauth_flow.py` with `fetch_identity` replaced: start (each branch of S5, the
      authorization URL carries `state`, `code_challenge`, `code_challenge_method=S256`, `nonce` for
      Google, the external `redirect_uri`); callback state, expiry, provider mismatch, `access_denied`,
      fetch failure (S5, S6)
- [ ] AC3 `tests/test_oauth_login.py`: existing link signs in with `auth_method` = provider and
      `remember`; blocked → `oauth_failed`; 2FA → pending step then `POST /auth/mfa` (no session before
      the code); unknown subject → sign-up pending; verified e-mail of an existing user → no link, no
      sign-in, pending e-mail `null`; unverified e-mail → `null`; lock does not stop OAuth (S7, S14)
- [ ] AC4 `tests/test_oauth_link_reauth.py`: link success, no-op, in use, other subject, re-auth needed
      for `link`; `reauth` intent sets `reauth_at` and refuses a foreign subject (S8, S9)
- [ ] AC5 `tests/test_api_oauth_complete.py`: pending info and suggestion rules; complete success (no
      password, e-mail rules, link, session), expired, invalid and taken username, subject linked
      meanwhile, rate limit, CSRF with `csrf_app` (S10, S11)
- [ ] AC6 `tests/test_api_connections.py`: unlink, last method 409, re-auth required, 404s; `GET /me`
      `connections`, `methods` and `/meta/config` providers with and without settings (S12, S13)
- [ ] AC7 `tests/test_config.py`: half-configured provider → `ConfigError` naming the missing variable
      only (S2); `tests/test_dependency_pins.py`, `tests/test_env_docs.py` green
- [ ] AC8 Error catalog test green with the four codes; authz matrix: `oauth.start`, `oauth.callback`,
      `api_v1.oauth_pending`, `api_v1.oauth_complete` → `P`, `api_v1.delete_connection` → `U`;
      `bandit -r app/ -ll` clean
- [ ] AC9 Frontend: `oauthStartUrl` and endpoint tests (S17)
- [ ] AC10 Full lanes green: `venv/bin/pytest`; `cd frontend && npm run lint && npm run typecheck &&
      npx vitest run && npm run build && npm run check:dist`; `flask db upgrade`, `flask db check`,
      `flask db downgrade -1`, upgrade again on a throw-away database
- [ ] AC11 Docs: `docs/oauth-setup.md` (S16); `docs/api.md`; `AGENTS.md` (technology table, Configuration,
      blueprints list gains `oauth`, tree, table `rboauthlinks`, public endpoints list, API list);
      `.env.example`, `README.md`; `docs/knowledge/ops-runbook.md` (enable/disable a provider, link to
      the guide); `docs/knowledge/state.md`

## Delivery

- Conventional Commits; commit messages end with the attribution lines the session supplies.
- Own PR (migration). PR title: `feat(auth): sign-in with Discord and Google, owner setup guide (F9 unit f)`.
  PR body: S# → tests, Authlib version and date, rollback (`flask db downgrade` one step, refused while
  provider-only accounts exist; blank the four settings to switch the feature off without a revert).
- Never merge. The owner merges.

## After merge

- The owner creates the two applications with `docs/oauth-setup.md` and puts the four values in the
  service environment file.
- Deploy to dev: **`pg_dump` backup first**; `pip install -r requirements.txt`; `flask db upgrade`
  (`0033_oauth_links`), `flask db check`, restart.
- Live checks: `GET /riftbound/api/v1/meta/config` lists both providers; open
  `/riftbound/auth/oauth/discord/start` in a private window → provider page → back to
  `/riftbound/app/oauth/complete` (screen in F9-g; until then `GET /riftbound/api/v1/auth/oauth/complete`
  shows the pending sign-up).
- Manual checks for the owner: cancel on the provider page returns with `oauth_error=oauth_cancelled`.

## Open questions

none
