# F9-b: Profile, optional e-mail and re-authentication API

| Field | Value |
|---|---|
| Phase / unit | F9 / b |
| Branch | `feat/f9b-profile-reauth` (from up-to-date `main`, F9-a merged) |
| Depends on | F9-a (`rbsessions`, `rbses_reauth_at`, `sessions.current()`) |
| Size forecast | ~500 authored lines (tests and docs included) |
| Risk | `Risk: item 1 (migration 0030_user_profile: nullable rbusers.email and rbusers.password_hash, new table) + item 3 (the /auth/session user payload, consumed by the SPA, gains fields and email becomes nullable)` |
| TDD | ON (strict). Runners: `venv/bin/pytest` (backend), `cd frontend && npx vitest run` (types and endpoints only) |
| Save as | `docs/requirements/F9/F9-b-profile-reauth.md` |

## Objective

A user has a private profile (display name, bio, country, city) they can read and change through the
API; the e-mail becomes optional (registration may leave it empty and the account page may remove it);
an account may exist without a password (prepared for OAuth sign-up in F9-f); and sensitive actions can
demand a recent re-authentication on the current session. No screens here (F9-i, F9-j).

## Read first

- `AGENTS.md`, `docs/knowledge/conventions.md`
- `docs/requirements/F9/README.md` (D-F9-1, D-F9-3/D-F9-12, D-F9-7, data model `0030_user_profile`)
- `docs/requirements/F9/F9-a-sessions.md` (session row, `reauth_at = now` at sign-in, revocation)
- `app/models/user.py`, `app/services/auth.py` (`authenticate`, `_dummy_hash`, `register_user`),
  `app/services/account.py`, `app/api/v1/me.py`, `app/api/v1/auth.py` (`user_payload`,
  `auth_session`), `app/api/v1/meta.py` (`meta_config`), `app/security.py`
- `app/schemas/validators.py` (`RegisterRequest`, `ProfileUpdate`, `AccountUpdate`), `app/cli/users.py`
- `frontend/src/api/types.ts`, `frontend/src/api/endpoints.ts`, `frontend/src/account/ProfilePage.tsx`
- `tests/test_api_me_account.py`, `tests/test_api_auth_guards.py`, `tests/migration_helpers.py`

## Scope

In:
- Migration `0030_user_profile`, model `RbUserProfile` (`app/models/profile.py`), `User` changes
- `app/services/profile.py` (read/update profile, security summary), `app/schemas/profile_domain.py`
  (country codes and field limits)
- `GET /me`, `PATCH /me`, `POST /me/reauth`; the re-auth rule (`app/security.py`)
- Optional e-mail in `POST /auth/register` and `PATCH /me/account`; `password_hash` NULL handling in
  login; `password_changed_at`
- `/auth/session` and every `user_payload` gain `display_name`, `avatar_url`; `/meta/config` gains
  `countries`
- Frontend: types and endpoint functions only, plus the minimum to keep `ProfilePage` compiling with a
  nullable e-mail

Out (do not do, even if tempting):
- Any new screen or form (F9-i builds the profile UI and the optional e-mail in the register form)
- Avatar upload (F9-c; `avatar_url` is always `null` here)
- TOTP re-authentication (`{code}` is wired by F9-d), OAuth (F9-f)
- Editing the username (D-F9-7), public profiles, social links (D-F9-3)

## Specs

S1. Migration `0030_user_profile` (down revision: the F9-a revision) creates
    `riftbound.rbuserprofile` (model `RbUserProfile`, `app/models/profile.py`): `rbupf_user_id`
    INTEGER PK `rbuserprofile_pkey`, FK `rbuserprofile_user_fk` → `rbusers.id` ON DELETE CASCADE;
    `rbupf_display_name` VARCHAR(40) NULL; `rbupf_bio` VARCHAR(240) NULL; `rbupf_country` CHAR(2) NULL;
    `rbupf_city` VARCHAR(80) NULL; `rbupf_avatar_file` VARCHAR(64) NULL; `rbupf_avatar_version`
    INTEGER NOT NULL DEFAULT 0; `rbupf_updated_at` TIMESTAMP NOT NULL. It alters `rbusers`
    (`op.batch_alter_table`): `email` → NULL allowed (constraint `rbusers_email_key` stays; several NULLs
    are allowed on PostgreSQL and SQLite), `password_hash` → NULL allowed, new `password_changed_at`
    TIMESTAMP NULL (no backfill: NULL = unknown). The downgrade first checks for rows with a NULL
    `email` or `password_hash` and aborts, changing nothing, with a message listing up to 20 usernames
    (pattern of `0003`); otherwise it restores NOT NULL, drops `password_changed_at` and the table. The
    docstring states the data loss (profiles, `password_changed_at`).
S2. Login with a NULL `password_hash` (OAuth-only account) runs the constant-time dummy check
    (`_dummy_hash()`) and answers exactly like a wrong password (401 `invalid_credentials`), and it
    does **not** count a failure. `User.check_password` returns `False` when the hash is NULL.
    `User.has_password` (property) = hash is not NULL.
S3. `password_changed_at = now` on registration, on a password change through `PATCH /me/account` and
    on `flask users set-password`.
S4. `POST /auth/register`: `email` may be absent, `null` or blank (after trim) → stored NULL; a present
    e-mail keeps today's rules (format, 120 max, unique ignoring case → 409 `email_taken`).
S5. `PATCH /me/account` (body `AccountUpdate`): `email` absent = unchanged; `null` or blank = remove the
    e-mail (stored NULL); a value = today's rules. At least one of `email`, `password` must be **sent**
    (`model_fields_set`), else today's 400. Password rules:
    - account with a password: `current_password` required and checked exactly as today (400
      `current_password_incorrect`; a missing one is today's 400 `validation_error`, pinned by a CHAR
      test first);
    - account without a password (`has_password` false): `current_password` is ignored and the request
      needs a recent re-authentication (S9), else 403 `reauth_required`.
    A successful password change keeps F9-a's rule (the other sessions are revoked). Removing or
    changing the e-mail needs neither the password nor a re-authentication.
S6. `user_payload(user)` (used by `/auth/session`, `/auth/login`, `PATCH /me/account`, `GET /me`) =
    `{id, username, email, is_admin, display_name, avatar_url}`: `email` may be `null`; `display_name`
    is the profile value or `null`; `avatar_url` is `null` in this unit (F9-c fills it). Additive: no
    key is removed or renamed.
S7. `GET /me` (U) → 200 `{user, profile, security}`:
    - `user` = S6;
    - `profile` = `{display_name, bio, country, city, avatar_url, updated_at}` (all `null` when the user
      has no profile row; reading never creates one);
    - `security` = `{has_password, password_changed_at, member_since, mfa: {available: false, enabled:
      false, pending: false, recovery_codes_left: 0}, sessions_active, api_key: null, connections: [],
      reauth_until}`. `member_since` = `rbusers.created_at`; `sessions_active` = the count of the
      caller's active sessions (F9-a rule); `reauth_until` = the current session's `reauth_at + 10 min`
      when that is in the future, else `null`. F9-d fills `mfa`, F9-h `api_key`, F9-f `connections`;
      until then they keep these values. Times use the F9-a format.
    At most 5 SQL statements.
S8. `PATCH /me` (U, body `ProfilePatch`) → 200 with the `GET /me` body. Absent = unchanged; `null` or a
    blank string (after trim) = cleared. Rules, each a 400 `validation_error` with the detail code in
    brackets and nothing stored (all-or-nothing):
    - `display_name`: trimmed, 1-40 characters (`too_long` `{max: 40}`), no control characters
      (`invalid_format`);
    - `bio`: trimmed, at most 240 characters (`too_long` `{max: 240}`), line breaks allowed, other
      control characters refused (`invalid_format`);
    - `country`: an ISO 3166-1 alpha-2 code from `COUNTRY_CODES` in `app/schemas/profile_domain.py`
      (the 249 officially assigned codes), case-insensitive input stored upper case (`invalid_value`
      otherwise);
    - `city`: trimmed, at most 80 characters (`too_long` `{max: 80}`), no control characters.
    Unknown keys are ignored (`username`, `email`, `is_admin` in this body change nothing). The first
    successful PATCH creates the row; every PATCH sets `updated_at = now`.
    Example: `{"display_name": "  Ana  ", "country": "es"}` → `profile.display_name = "Ana"`,
    `profile.country = "ES"`, `bio` and `city` unchanged.
S9. Re-authentication rule (`app/security.py`, decorator `reauth_required`, used by the routes of S5 and
    of later units): the request passes when the **current session**'s `reauth_at` is within the last
    10 minutes (`REAUTH_WINDOW = timedelta(minutes=10)`). A fresh sign-in sets `reauth_at` (F9-a S5).
    Otherwise → 403 `{success: false, error: "Forbidden", message: "Confirm your identity to continue",
    code: "reauth_required", params: {methods: [...]}}` where `methods` lists what the caller can use,
    in this order: `password` (when `has_password`), `totp` (F9-d, when 2FA is enabled), `discord`,
    `google` (F9-f, linked providers). Nothing of the request is applied.
S10. Sensitive actions (each unit applies S9 to its own route; this list is the contract):
    setting a first password on an account without one (S5, this unit); `POST /me/2fa/setup`,
    `/enable`, `/disable`, `/recovery-codes` (F9-d); `POST /me/api-key` (F9-h); `DELETE
    /me/connections/<provider>` and the OAuth `link` intent (F9-f). Not sensitive: profile, avatar,
    e-mail change or removal, password change with the current password, revoking sessions, revoking
    the API key, logout.
S11. `POST /me/reauth` (U, body `ReauthRequest`: exactly one of `password` (1-1024 characters) or `code`
    (string)) → 200 `{reauth_until}` and sets the current session's `reauth_at = now`:
    - `password` on an account with a password: wrong → 400 `current_password_incorrect`, nothing
      written; on an account without one → 400 `validation_error` (field `password`, `invalid_value`);
    - `code`: until F9-d → 400 `validation_error` (field `code`, `invalid_value`, message
      "Two-factor authentication is not enabled"); F9-d makes it verify a TOTP code;
    - both or neither → 400 `validation_error`.
    Limited to `20/hour` per IP (`@limiter.shared_limit(..., scope='reauth')`; the 21st → 429
    `rate_limited` with `Retry-After`). A wrong password here does not touch `failed_login_count`.
S12. `GET /meta/config` gains `countries: [codes]` (the S8 list, sorted). Additive; the SPA shows the
    names with `Intl.DisplayNames(['en'], {type: 'region'})`, so no country names enter the catalog.
S13. `flask users list` prints `-` in place of a missing e-mail.
S14. Frontend (types only): `UserPayload` → `{id, username, email: string | null, is_admin,
    display_name: string | null, avatar_url: string | null}`; `MetaConfig` gains `countries: string[]`;
    new `MeData`, `ProfilePatch`, `ReauthBody` types and `getMe`, `patchMe`, `reauth` in
    `api/endpoints.ts` (through `request()`); `ProfilePage` treats a `null` e-mail as an empty field
    (no visible change for users who have one). MSW handlers in `src/test/` return the new keys.

## API / data contract

| Method | Path (prefix `/riftbound/api/v1`) | Auth | Endpoint name | Notes |
|---|---|---|---|---|
| GET | `/me` | U | `api_v1.get_me` | S7 |
| PATCH | `/me` | U | `api_v1.patch_me` | S8, `@validate_json(ProfilePatch)` |
| POST | `/me/reauth` | U | `api_v1.me_reauth` | S11, 20/hour per IP |
| PATCH | `/me/account` | U | existing | S5 |
| POST | `/auth/register` | P | existing | S4 |
| GET | `/auth/session`, `/meta/config` | P | existing | S6, S12 (additive) |

New error code `reauth_required` (403): `ErrorCode.REAUTH_REQUIRED`, `code.reauth_required` in
`frontend/src/i18n/locales/en/errors.json` = "Confirm your identity to continue.", covered by
`tests/test_error_catalogs.py`. New schemas in `app/schemas/validators.py`: `ProfilePatch`,
`ReauthRequest`; `RegisterRequest.email` optional; `AccountUpdate` per S5. `docs/api.md`: "Profile
and re-authentication (F9-b)" (S7-S11, the S10 list), "PATCH /me/account" updated (S5), the
`/auth/session` user shape (S6), `/meta/config` (S12).

Migration `0030_user_profile` per S1.

## UI

none (F9-i, F9-j). The frontend change is limited to S14.

## Acceptance criteria

- [ ] AC1 `tests/test_user_profile_migration.py`: upgrade from the F9-a revision, columns and names,
      nullability, downgrade refused with a NULL e-mail or hash (message lists the usernames, nothing
      changed), downgrade succeeds otherwise, `drift()` clean (S1)
- [ ] AC2 `tests/test_api_auth_guards.py` extended: NULL-hash login is `invalid_credentials`, runs the
      dummy check, counts nothing; register without e-mail (absent, `null`, blank) stores NULL; two
      users without e-mail coexist (S2, S4)
- [ ] AC3 `tests/test_api_me_account.py` extended: CHAR tests of today's answers first; e-mail removal
      (`null`, `""`); `email_taken` still ignores case; on an account without a password a first
      password is 403 `reauth_required` with a stale `reauth_at` and 200 with a recent one (the test
      sets `reauth_at` through the session service: such an account cannot re-authenticate by password);
      `password_changed_at` set (S3, S5)
- [ ] AC4 `tests/test_api_me_profile.py`: `GET /me` shape and defaults, no row created on read,
      5-statement budget; `PATCH /me` every S8 rule and boundary (40/41, 240/241, 80/81, control
      characters, country case and unknown code), all-or-nothing, unknown keys ignored, the S8 example
      (S7, S8)
- [ ] AC5 `tests/test_api_reauth.py`: password ok / wrong / account without password, `code` before
      F9-d, both/neither, the 10-minute window with `frozen_clock` (9:59 passes, 10:01 → 403 with
      `methods`), only the current session is marked, rate limit with `limited_app`, lockout counter
      untouched (S9, S11)
- [ ] AC6 `tests/test_api_meta_config.py` (new) or an existing meta test: `countries` sorted, 249 codes,
      all upper case (S12); `user_payload` keys on `/auth/session`, `/auth/login`, `PATCH /me/account`
      (S6); `flask users list` with a NULL e-mail in `tests/test_users_cli.py` (S13)
- [ ] AC7 Error catalog test green with `reauth_required`; authz matrix: `api_v1.get_me`,
      `api_v1.patch_me`, `api_v1.me_reauth` → `U`
- [ ] AC8 Frontend: `src/api/endpoints.test.ts` (or the existing client tests) cover `getMe`, `patchMe`,
      `reauth` paths and bodies; `ProfilePage.test.tsx` still green with a `null` e-mail (S14)
- [ ] AC9 Full lanes green: `venv/bin/pytest`; `cd frontend && npm run lint && npm run typecheck &&
      npx vitest run && npm run build && npm run check:dist`; `flask db upgrade`, `flask db check`,
      `flask db downgrade -1`, upgrade again on a throw-away database
- [ ] AC10 Docs: `docs/api.md` (see contract); `AGENTS.md` (tree: `app/models/profile.py`,
      `app/services/profile.py`, `app/schemas/profile_domain.py`; the table list gains
      `rbuserprofile`; API list; `rbusers.email`/`password_hash` nullable in the conventions; the
      re-auth rule in "Roles and Authorization"); `docs/knowledge/state.md`

## Delivery

- Conventional Commits; commit messages end with the attribution lines the session supplies.
- Own PR (migration). PR title: `feat(account): profile, optional e-mail and re-auth API (F9 unit b)`.
  PR body: S# → tests, RED evidence, rollback (`flask db downgrade` to the F9-a revision; refused while
  an account has no e-mail or no password: give them one first).
- Never merge. The owner merges.

## After merge

- Deploy to dev with `docs/knowledge/ops-runbook.md`: **`pg_dump` backup first**, `flask db upgrade`
  (`0030_user_profile`), `flask db check`, restart. Frontend rebuild (types only).
- Live checks: `GET /riftbound/api/v1/me` answers the S7 shape; `PATCH /me` with a display name, then
  `GET /auth/session` shows it; `GET /meta/config` lists `countries`.
- Manual checks for the owner: the Profile page still shows and saves the e-mail and password.

## Open questions

none
