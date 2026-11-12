# F9-a: Server-side sessions

| Field | Value |
|---|---|
| Phase / unit | F9 / a |
| Branch | `feat/f9a-sessions` (from up-to-date `main`) |
| Depends on | none (F11-f merged: Alembic head `0028_legacy_schema_cleanup`) |
| Size forecast | ~550 authored lines (about 60 % tests) |
| Risk | `Risk: item 2 (identity loading on every request: every signed-in request now resolves a server-side session) + item 1 (migration 0029_sessions: new table rbsessions and the rbjobs kind CHECK)` |
| TDD | ON (strict). Runner: `venv/bin/pytest` (backend only) |
| Save as | `docs/requirements/F9/F9-a-sessions.md` |

## Objective

Every sign-in becomes a row on the server. A user can see where they are signed in and end any of
those sessions; signing out, changing the password or being blocked ends sessions for real instead of
leaving a valid cookie behind. Non-remembered sessions end after 12 hours without use (or when the
browser closes), remembered ones after 30 days. Old cookies (a plain user id) stop working once, so
every user signs in again after the deploy. No UI here (the device list is F9-j).

## Read first

- `AGENTS.md` (CSRF, Sessions and Login Protection; Adding a Job Kind; Database Changes; Testing)
- `docs/knowledge/conventions.md` (sections 3, 4, 7)
- `docs/requirements/F9/README.md` (owner decisions, data model `0029_sessions`, risks)
- `app/__init__.py` (`login.user_loader`, `unauthorized_handler`), `app/models/user.py`
- `app/api/v1/auth.py` (`auth_login`, `auth_logout`), `app/services/auth.py`
- `app/api/v1/me.py` (`patch_me_account`), `app/services/account.py`
- `app/cli/users.py` (`block`, `set-password`), `app/cli/__init__.py`
- `config.py` (`_session_settings`, `REMEMBER_COOKIE_DURATION`)
- `app/models/job.py` (`JOB_KINDS`), `migrations/versions/0027_jobs_price_alerts.py` (CHECK pattern),
  `app/jobs/heartbeat.py`, `docs/systemd/`, `tests/test_jobs_systemd.py`
- `tests/test_api_auth_guards.py`, `tests/test_authz_matrix.py`, `tests/migration_helpers.py`,
  `tests/test_jobs_migration.py` (pattern)

## Scope

In:
- Migration `0029_sessions`: table `rbsessions` and `sessions_purge` in `ck_rbjobs_kind` (one revision,
  see S1)
- Model `RbSession` (`app/models/session.py`), service `app/services/sessions.py`
- New identity format for Flask-Login, the loader, login/logout wiring
- Revocation on logout, on a password change (`PATCH /me/account`, `flask users set-password`) and on
  `flask users block`
- `GET /me/sessions`, `DELETE /me/sessions/<id>`, `DELETE /me/sessions`
- `flask sessions purge`, job kind `sessions_purge`, systemd timer templates, runbook entry

Out (do not do, even if tempting):
- Any screen (F9-j), any frontend change
- 2FA, re-authentication, OAuth (F9-b, d, e, f); the `mfa`, `reauth_at` and non-`password`
  `auth_method` values exist in the table but nothing sets them here except their defaults
- Geo-IP, device fingerprinting, a User-Agent parsing dependency
- Changing cookie flags (`HttpOnly`, `SameSite=Lax`, `Secure` in production stay as they are)

## Specs

S1. Migration `0029_sessions` (down revision `0028_legacy_schema_cleanup`; if another revision landed
    first, take the next free number and chain to the current head) creates `riftbound.rbsessions`
    (model `RbSession`, `app/models/session.py`, imported in `app/models/__init__.py`):
    - `rbses_id` BIGINT PK `rbsessions_pkey` (INTEGER variant on SQLite, like `rbcol_id`)
    - `rbses_user_id` INTEGER NOT NULL FK `rbsessions_user_fk` → `rbusers.id` ON DELETE CASCADE
    - `rbses_token_hash` CHAR(64) NOT NULL, UNIQUE `rbsessions_token_hash_key`
    - `rbses_created_at`, `rbses_last_seen_at` TIMESTAMP NOT NULL; `rbses_expires_at` TIMESTAMP NULL
    - `rbses_remember` BOOLEAN NOT NULL DEFAULT false
    - `rbses_auth_method` VARCHAR(16) NOT NULL DEFAULT `'password'`, CHECK `ck_rbsessions_auth_method`
      (`IN ('password', 'discord', 'google')`; F9-f needs no CHECK change)
    - `rbses_mfa` BOOLEAN NOT NULL DEFAULT false; `rbses_reauth_at` TIMESTAMP NULL
    - `rbses_user_agent` VARCHAR(255) NULL; `rbses_ip_prefix` VARCHAR(48) NULL
    - `rbses_revoked_at` TIMESTAMP NULL
    - indexes `ix_rbsessions_user_revoked` (`rbses_user_id`, `rbses_revoked_at`) and
      `ix_rbsessions_expires_at` (`rbses_expires_at`).
    The same revision replaces `ck_rbjobs_kind` with the list plus `'sessions_purge'` (pattern of
    `0027`; `JOB_KINDS` in `app/models/job.py` gains it). One revision because both belong to this
    unit and deploy together. The downgrade first refuses (nothing changed, offline mode refused like
    `0027`) while `sessions_purge` jobs exist, then restores the CHECK and drops `rbsessions`; the
    docstring says the downgrade deletes every session (users sign in again).
S2. Identity format. A session token is `secrets.token_urlsafe(32)`; only `sha256(token)` (64 lowercase
    hex) is stored. `User.get_id()` returns `"s:" + token` for a user object that carries a session
    token (set by the service when the session is created or loaded); Flask-Login therefore keeps
    `"s:<token>"` in the Flask session (`_user_id`) and in the remember cookie. A `User` without a
    token returns `None` from `get_id()` (it can never be logged in by id).
S3. The user loader (`app/__init__.py` → `app.services.sessions.load_identity(raw_id)`):
    - a value without the `s:` prefix (every pre-F9 cookie: a plain user id) → anonymous; nothing is
      written; the response clears nothing special (the normal anonymous path);
    - unknown hash, `revoked_at` set, `remember` and `expires_at <= now`, not `remember` and
      `last_seen_at <= now - 12 h`, or the user `is_blocked` → anonymous;
    - otherwise the user, with the session attached (`sessions.current()` returns it during the
      request).
    The lookup is ONE `SELECT` (session joined with its user). Existing SQL-statement budget tests stay
    green unchanged. Time comes from `clock.utcnow()` (module call, freezable).
S4. `last_seen_at` is written only when the stored value is at least 5 minutes old (one `UPDATE … WHERE
    rbses_id = :id`, committed), so a burst of requests writes at most once per 5 minutes per session.
    A remembered session keeps its absolute `expires_at`; using it does not extend it.
S5. Login (`POST /auth/login` with right credentials, the only sign-in path today) goes through
    `sessions.sign_in(user, *, remember, auth_method)` (the one function that creates a row and calls
    `login_user`; F9-e adds `mfa_passed` to it), which creates one row:
    `remember` from the body, `expires_at = now + 30 days` when `remember` is true else NULL,
    `auth_method = 'password'`, `mfa = false`, `reauth_at = now` (a fresh sign-in counts as a recent
    re-authentication for F9-b), `user_agent` = the request `User-Agent` cut to 255 characters (NULL
    when absent), `ip_prefix` per S6, `created_at = last_seen_at = now`; then `login_user(user,
    remember=…)`. The response body is unchanged (`{user}`). The remember cookie keeps Flask-Login's
    30-day duration (`REMEMBER_COOKIE_DURATION` unchanged) and now carries `s:<token>`.
S6. IP prefix from `request.remote_addr` (already rewritten by ProxyFix) with the standard library
    `ipaddress`: IPv4 → the `/24` network in CIDR text (last octet zeroed, suffix `/24`); IPv6 → the
    `/48` network in compressed CIDR text; an IPv4-mapped IPv6 address is treated as IPv4; missing or
    unparsable → NULL. The full address is never stored or logged by this unit. Tests use only the
    documentation ranges of RFC 5737 (IPv4) and RFC 3849 (IPv6).
S7. Device label (computed on read, no new dependency), `sessions.device_label(user_agent)`:
    browser = first match in this order: `Edg/` → `Edge`, `OPR/` or `Opera` → `Opera`, `Firefox/` →
    `Firefox`, `Chrome/` or `CriOS/` → `Chrome`, `Safari/` → `Safari`, else `Browser`; OS = first match:
    `Windows` → `Windows`, `iPhone` or `iPad` → `iOS`, `Android` → `Android`, `CrOS` → `ChromeOS`,
    `Mac OS X` or `Macintosh` → `macOS`, `Linux` → `Linux`, else none. Result: `"<browser> on <OS>"`,
    `"<browser>"` without an OS, `"Unknown device"` for an empty or missing User-Agent.
    Examples: a desktop Firefox on Windows UA → `Firefox on Windows`; an iPhone Safari UA → `Safari on
    iOS`; a Chrome on Android UA → `Chrome on Android`; an Edge UA (which also says `Chrome/`) → `Edge
    on Windows`; `curl/8.0` → `Browser`.
S8. Logout (`POST /auth/logout`) sets `revoked_at = now` on the current session, then `logout_user()`
    (which also expires the remember cookie, as today). Re-using the old Flask session cookie or the old
    remember cookie afterwards is anonymous.
S9. A password change through `PATCH /me/account` (status `OK` with `password` sent) revokes every other
    active session of the user (`revoked_at = now`) in the same transaction; the current one stays.
    `flask users set-password USERNAME` revokes **all** sessions of that user and prints
    `Password updated for '<username>'; <n> session(s) ended`. `flask users block USERNAME` revokes all
    sessions of that user and prints `'<username>' is now blocked; <n> session(s) ended` (the
    "already blocked" message is unchanged). An e-mail-only change revokes nothing.
S10. `GET /me/sessions` (U) → 200 `{items: [Session]}` with the caller's **active** sessions (not revoked,
    not expired per S3), the current one first, then by `last_seen_at` descending. `Session` =
    `{id, current, device, user_agent, ip_prefix, created_at, last_seen_at, expires_at, remember,
    auth_method, mfa}`; times are ISO 8601 UTC with `Z`
    (`%Y-%m-%dT%H:%M:%SZ`, as `app/services/wishlists.py` writes them); `expires_at` null for
    non-remembered sessions. Never the token or its hash, never another user's
    rows. At most 3 SQL statements.
S11. `DELETE /me/sessions/<int:id>` (U) → 200 `{revoked: 1, current: <bool>}`. An id that is not one of
    the caller's active sessions (other user, unknown, already revoked or expired) → the 404 envelope,
    nothing changes. Revoking the **current** session behaves like logout (S8: the response logs the
    caller out and expires the remember cookie) and answers `current: true`.
S12. `DELETE /me/sessions` (U) → 200 `{revoked: <n>}`: revokes every active session of the caller except
    the current one; `n` may be 0.
S13. `flask sessions purge [--dry-run]` (new group `app/cli/sessions.py`, registered in
    `app/cli/__init__.py`) deletes every row that is revoked, or remembered with `expires_at <= now`,
    or not remembered with `last_seen_at <= now - 12 h`; prints `Purged <n> session(s)` (`Would purge
    <n> session(s)` with `--dry-run`, which deletes nothing); exit 0. Active sessions are never
    touched.
S14. Job kind `sessions_purge` (`app/jobs/sessions_purge.py`, imported by `app/jobs/__init__.py`,
    `timeout_seconds=300`) runs the same purge and returns `{purged: n}`. Templates
    `docs/systemd/riftbound-sessions-purge.service` and `.timer` (daily 04:15 Europe/Madrid,
    `Persistent=true`, `flask jobs enqueue sessions_purge --unless-succeeded-today`, the same user,
    working directory and environment file placeholders as the other templates); runbook
    `docs/knowledge/ops-runbook.md` → "Scheduled jobs" → "Session purge (F9-a)" (install, check,
    rollback).
S15. Pre-F9 cookies: a Flask session or remember cookie created before the deploy (holding a plain user
    id) loads as anonymous on every route (S3); `GET /auth/session` answers `authenticated: false`;
    the SPA's existing 401 handling sends the user to the login screen. Nothing else is migrated.
S16. Unchanged behaviour (pinned by CHAR tests written first and passing before the change): lockout,
    blocked-user answer, rate limits, captcha, CSRF on every unsafe rule, `remember` strictness
    (non-boolean → 400), cookie flags (`HttpOnly`, `SameSite=Lax`, `Secure` per config), the
    `/auth/login` and `/auth/session` bodies.

## API / data contract

| Method | Path (prefix `/riftbound/api/v1`) | Auth | Endpoint name | Response |
|---|---|---|---|---|
| GET | `/me/sessions` | U | `api_v1.list_my_sessions` | `{items: [Session]}` |
| DELETE | `/me/sessions/<int:id>` | U | `api_v1.revoke_my_session` | `{revoked: 1, current}` / 404 |
| DELETE | `/me/sessions` | U | `api_v1.revoke_my_other_sessions` | `{revoked: n}` |

Changed: `POST /auth/login` and `POST /auth/logout` (bodies unchanged, server-side row created /
revoked), `PATCH /me/account` (password change revokes the other sessions). The routes live in a new
`app/api/v1/sessions.py` (imported where `app/api/v1/__init__.py` imports the other modules). No new
error code. `docs/api.md` gains "Sessions (F9-a)" (shape, ordering, revocation rules, the forced
re-login note).

Migration `0029_sessions` (S1): upgrade creates the table and widens the CHECK; downgrade refuses while
`sessions_purge` jobs exist, then narrows the CHECK and drops the table (all sessions lost).

## UI

none (F9-j shows the list).

## Acceptance criteria

- [ ] AC1 Round trip + drift: `tests/test_sessions_migration.py` (upgrade from `0028`, columns,
      constraint and index names, the CHECKs, downgrade refusal with a `sessions_purge` job and success
      without, `drift()` clean) (S1)
- [ ] AC2 `tests/test_sessions_service.py`: token never stored in clear, `get_id` format, loader cases
      (prefix, unknown, revoked, remember expiry, 12 h idle, blocked), one statement per load, the
      5-minute `last_seen_at` throttle with `frozen_clock`, IP prefixes (IPv4, IPv6, mapped, missing),
      device labels (every S7 example) (S2-S4, S6, S7)
- [ ] AC3 `tests/test_api_sessions.py`: list shape and order, current flag, other users' rows absent,
      revoke one / current (logged out) / others / foreign id 404, 3-statement budget (S10-S12)
- [ ] AC4 `tests/test_api_auth_guards.py` extended: login creates a row with the S5 values; logout
      revokes and the old cookie is anonymous; remember cookie signs in through the session row and
      stops after revocation or 30 days (`frozen_clock`); a pre-F9 numeric session cookie and remember
      cookie are anonymous; password change ends the other client and keeps the current one; CHAR tests
      of S16 written first (S5, S8, S9, S15, S16)
- [ ] AC5 New `tests/test_users_cli.py` (no `flask users` test file exists today): `block` and
      `set-password` revoke and print the counts (S9); `tests/test_sessions_cli.py`: purge and
      `--dry-run` (S13)
- [ ] AC6 Job: `tests/test_sessions_purge_job.py` through `app.services.jobs.run_pending()`;
      `tests/test_jobs_systemd.py` extended with the two templates (S14)
- [ ] AC7 Authz matrix: `api_v1.list_my_sessions`, `api_v1.revoke_my_session`,
      `api_v1.revoke_my_other_sessions` classified `U` in `tests/test_authz_matrix.py`
- [ ] AC8 Full lanes green: `venv/bin/pytest`; `cd frontend && npm run lint && npm run typecheck &&
      npx vitest run && npm run build && npm run check:dist` (no frontend change expected); `flask db
      upgrade`, `flask db check`, `flask db downgrade -1`, upgrade again on a throw-away database
- [ ] AC9 Docs: `docs/api.md` "Sessions (F9-a)"; `AGENTS.md` (tree: `app/models/session.py`,
      `app/services/sessions.py`, `app/api/v1/sessions.py`, `app/cli/sessions.py`,
      `app/jobs/sessions_purge.py`; table list `rbsessions`; API list; CLI and job kinds in "Running";
      the CSRF/Sessions section: server-side sessions, 12 h idle / 30 d remember, revocation rules);
      `docs/knowledge/ops-runbook.md` (S14 and the forced re-login announcement); `docs/knowledge/state.md`
      (unit row, deploy pending check)

## Delivery

- Conventional Commits; commit messages end with the attribution lines the session supplies.
- Own PR (migration). PR title: `feat(auth): server-side sessions with device list and revoke (F9 unit a)`.
  PR body: S# → test map, RED evidence, manual checks, rollback (`flask db downgrade 0028_legacy_schema_cleanup`
  after deleting `sessions_purge` jobs, then redeploy the previous commit; everyone signs in again once more).
- Never merge. The owner merges.

## After merge

- Deploy to dev with `docs/knowledge/ops-runbook.md`: **`pg_dump` backup first**, `flask db upgrade`
  (`0029_sessions`), `flask db check`, restart; install the two timer templates.
- **Announce before the deploy: every user signs in again once** (old cookies hold a plain user id and
  load as anonymous). No other deploy action.
- Live checks: sign in, `GET /riftbound/api/v1/me/sessions` lists one item with `current: true` and a
  device label; sign in from a second browser, revoke it with `DELETE /me/sessions/<id>`, the second
  browser lands on the login screen at its next request; `flask sessions purge --dry-run` prints a count.
- Manual checks for the owner: an installed PWA and a browser that were signed in before the deploy both
  show the login screen once, then stay signed in.

## Open questions

none
