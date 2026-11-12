# F9-h: Personal API key (read-only)

| Field | Value |
|---|---|
| Phase / unit | F9 / h |
| Branch | `feat/f9h-api-key` (from up-to-date `main`, F9-a and F9-b merged) |
| Depends on | F9-a (identity loading), F9-b (re-auth rule, `GET /me` `security.api_key`) |
| Size forecast | ~400 authored lines (tests and docs included) |
| Risk | `Risk: item 2 (an alternate authentication path next to the session cookie) + item 1 (migration 0032_api_keys)` |
| TDD | ON (strict). Runners: `venv/bin/pytest`, `cd frontend && npx vitest run` (types and endpoints only) |
| Save as | `docs/requirements/F9/F9-h-api-key.md` |

## Objective

A user can create one personal API key to read their own data from scripts or other tools (for
example their collection or decks) with a plain HTTP client. The key is shown once, stored only as a
hash, can be replaced or revoked at any time, and can only **read**: it never changes anything, never
reaches account or admin routes and never creates a browser session. No screen here (F9-j).

## Read first

- `AGENTS.md` (Roles and Authorization, CSRF), `docs/knowledge/conventions.md`
- `docs/requirements/F9/README.md` (D-F9-8, risks: CSRF has no exemptions; rate limits per worker)
- `F9-a-sessions.md` (S2, S3: the loader), `F9-b-profile-reauth.md` (S7, S9, S10)
- `app/__init__.py` (`login`, `limiter`, `csrf` wiring), `app/security.py`, `app/api/v1/__init__.py`,
  `app/api/admin/__init__.py`, `app/errors.py`
- `tests/test_authz_matrix.py`, `tests/test_api_auth_guards.py`

## Scope

In:
- Migration `0032_api_keys`, model `RbApiKey` (`app/models/api_key.py`), `app/services/api_keys.py`
- `GET`/`POST`/`DELETE /me/api-key`
- Bearer authentication for safe requests under `/riftbound/api/v1/` with a deny list
- Per-key rate limit, `last_used_at`
- Error codes `api_key_invalid`, `api_key_read_only`
- Frontend: types and endpoint functions only

Out (do not do, even if tempting):
- Write scopes, several keys per user, expiry dates, key names (D-F9-8: one read-only key)
- Any screen (F9-j), an OAuth server, CORS headers for third-party sites
- A CSRF exemption of any kind

## Specs

S1. Migration `0032_api_keys` (down revision: the current head; take the next free number):
    `riftbound.rbapikeys` (model `RbApiKey`): `rbapk_id` BIGINT PK `rbapikeys_pkey` (SQLite INTEGER
    variant); `rbapk_user_id` INTEGER NOT NULL, UNIQUE `rbapikeys_user_key`, FK `rbapikeys_user_fk` →
    `rbusers.id` ON DELETE CASCADE; `rbapk_prefix` VARCHAR(16) NOT NULL; `rbapk_key_hash` CHAR(64) NOT
    NULL, UNIQUE `rbapikeys_key_hash_key`; `rbapk_created_at` TIMESTAMP NOT NULL; `rbapk_last_used_at`
    TIMESTAMP NULL. Downgrade drops the table (docstring: every key stops working).
S2. Key format: `rb_live_` + 40 lower-case hex characters (`secrets.token_hex(20)`, 160 bits). Stored:
    `rbapk_key_hash = sha256(key)` (hex) and `rbapk_prefix` = the first 14 characters (`rb_live_` + 6
    hex). The full key is never stored or logged.
S3. `GET /me/api-key` (U) → 200 `{api_key: {prefix, created_at, last_used_at} | null}`.
S4. `POST /me/api-key` (U, re-auth per F9-b S9, no body) → 201 `{key, api_key: {prefix, created_at,
    last_used_at: null}}`, `Cache-Control: no-store`. It creates the key, or **replaces** the existing
    one in the same transaction (the old key stops working at once). The key appears only in this
    response.
S5. `DELETE /me/api-key` (U, no re-auth) → 200 `{api_key: null}`; idempotent.
S6. `GET /me` `security.api_key` = the S3 object or `null`.
S7. Bearer recognition: a request whose path starts with `/riftbound/api/v1/` and whose `Authorization`
    header uses the `Bearer` scheme (case-insensitive) is authenticated **only** by that key: the
    session cookie and the remember cookie are ignored for it. Outside `/riftbound/api/v1/` the header
    is ignored and nothing changes.
S8. Checks, in this order (hooks run before CSRF so a refused key never reaches the CSRF check):
    1. the value is not `rb_live_` + 40 hex, no key has that hash, or its user is blocked → 401
       `{error: "Unauthorized", message: "The API key is not valid", code: "api_key_invalid"}`;
    2. the method is not `GET` or `HEAD` → 403 `{error: "Forbidden", message: "API keys can only
       read data", code: "api_key_read_only"}`;
    3. the path is on the deny list → 403 `api_key_read_only`. Deny list (prefix match on the path
       after `/riftbound/api/v1`): `/auth/`, `/admin/`, `/me/account`, `/me/reauth`, `/me/sessions`,
       `/me/2fa`, `/me/api-key`, `/me/avatar`, `/me/connections`, and exactly `/me`;
    4. otherwise the request runs as the key's user.
    Examples: `GET /riftbound/api/v1/collection` with a valid key → 200 with the user's collection;
    `POST /riftbound/api/v1/collection` with a valid key → 403 `api_key_read_only`; `GET
    /riftbound/api/v1/admin/overview` with an admin's key → 403 `api_key_read_only`; `GET
    /riftbound/api/v1/me/products` and `/me/prefs` → 200; `GET /riftbound/api/v1/health` with a bad key
    → 401 `api_key_invalid`.
S9. A key request never creates or changes a session: the response carries no `Set-Cookie` (session,
    remember or CSRF), no session row is created, `rbses_last_seen_at` is untouched. Admin rights never
    apply through a key (S8.3 refuses `/admin/`; the key never satisfies `require_admin`).
S10. 2FA does not apply to key requests (the key was created after a re-auth); the key is independent
    of password changes and session revocation; `flask users block` makes it invalid (S8.1) and
    `flask users unblock` makes it work again.
S11. Rate limit: `60/minute` per key (Flask-Limiter key function = the key's row id, `scope='api_key'`,
    applied to every bearer request under `/riftbound/api/v1/`); the 61st → 429 `rate_limited` with
    `Retry-After`. Cookie requests keep their existing limits. Limits are per worker (memory storage,
    README risks).
S12. `last_used_at` is written only when it is null or at least 1 minute old (one `UPDATE`). Key
    authentication is one `SELECT` (key joined with its user).
S13. Error codes (enum, `errors.json`, catalog test): `api_key_invalid` (401) → "The API key is not
    valid."; `api_key_read_only` (403) → "API keys can only read data."
S14. Frontend (types only): `ApiKeyInfo`, `ApiKeyCreated`; `getApiKey`, `createApiKey`, `deleteApiKey`
    in `api/endpoints.ts`; `MeData.security.api_key` typed.
S15. `docs/api.md` → "API key (F9-h)": format, how to send it, read-only rule, the deny list, the limit,
    and an example with placeholders only:
    `curl -H "Authorization: Bearer rb_live_<your key>" https://<your-host>/riftbound/api/v1/collection`.

## API / data contract

| Method | Path (prefix `/riftbound/api/v1`) | Auth | Endpoint name | Notes |
|---|---|---|---|---|
| GET | `/me/api-key` | U | `api_v1.get_my_api_key` | S3 |
| POST | `/me/api-key` | U (re-auth) | `api_v1.create_my_api_key` | S4 |
| DELETE | `/me/api-key` | U | `api_v1.delete_my_api_key` | S5 |

Bearer authentication is a cross-cutting rule (S7-S12), not a route. Migration `0032_api_keys` (S1).

## UI

none (F9-j builds the API page).

## Acceptance criteria

- [ ] AC1 `tests/test_api_keys_migration.py`: round trip, names, `drift()` clean (S1)
- [ ] AC2 `tests/test_api_me_api_key.py`: create (201, no-store, format, prefix), replace (old key 401),
      delete (idempotent), re-auth required on create, `GET /me` field, the hash is what is stored
      (S2-S6)
- [ ] AC3 `tests/test_api_key_auth.py`: every S8 example and step order (invalid before read-only;
      read-only before CSRF with `csrf_app`); bearer wins over a signed-in cookie of another user;
      outside `/riftbound/api/v1/` ignored; no `Set-Cookie`, no session row; blocked/unblocked; admin key
      refused on `/admin/`; rate limit 60/61 with `limited_app`; `last_used_at` throttle with
      `frozen_clock`; one statement per key load (S7-S12)
- [ ] AC4 `tests/test_authz_matrix.py`: the three endpoints → `U`, and a parametrised test that a valid
      key gets 403 `api_key_read_only` on every unsafe rule of the matrix and on every deny-list GET
      rule (S8)
- [ ] AC5 Error catalog test green with both codes; frontend endpoint tests (S13, S14)
- [ ] AC6 Full lanes green: `venv/bin/pytest`; `cd frontend && npm run lint && npm run typecheck &&
      npx vitest run && npm run build && npm run check:dist`; `flask db upgrade`, `flask db check`,
      `flask db downgrade -1`, upgrade again on a throw-away database
- [ ] AC7 Docs: `docs/api.md` (S15); `AGENTS.md` (tree, table `rbapikeys`, API list, "Roles and
      Authorization" and "CSRF" sections: bearer keys read only, no exemption); `docs/knowledge/state.md`

## Delivery

- Conventional Commits; commit messages end with the attribution lines the session supplies.
- Own PR (migration). PR title: `feat(api): personal read-only API key (F9 unit h)`. PR body: S# →
  tests, rollback (`flask db downgrade` one step; revert).
- Never merge. The owner merges.

## After merge

- Deploy to dev: **`pg_dump` backup first**, `flask db upgrade` (`0032_api_keys`), `flask db check`,
  restart.
- Live checks: create a key (`POST /riftbound/api/v1/me/api-key` after a fresh sign-in), read the
  collection with `curl` and the key, a `POST` with it → 403, delete the key → 401.
- Manual checks for the owner: none (no screen yet).

## Open questions

none
