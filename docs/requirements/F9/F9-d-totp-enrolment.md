# F9-d: TOTP two-factor enrolment

| Field | Value |
|---|---|
| Phase / unit | F9 / d |
| Branch | `feat/f9d-totp-enrolment` (from up-to-date `main`, F9-a and F9-b merged) |
| Depends on | F9-a (sessions, revocation), F9-b (`reauth_required`, `POST /me/reauth`, `GET /me` `security.mfa`) |
| Size forecast | ~550 authored lines (tests and docs included) |
| Risk | `Risk: item 2 (second-factor secrets and recovery codes; re-auth gating) + item 5 (new pinned crypto dependencies pyotp, segno, cryptography; new required production secret) + item 1 (migration 0031_mfa)` |
| TDD | ON (strict). Runners: `venv/bin/pytest`, `cd frontend && npx vitest run` (types and endpoints only) |
| Save as | `docs/requirements/F9/F9-d-totp-enrolment.md` |

## Objective

A user can turn on two-factor authentication with any authenticator app: scan a QR code (or type the
secret), confirm a code, and keep ten one-time recovery codes. They can regenerate the codes or turn 2FA
off. Secrets are encrypted at rest; codes cannot be replayed; every change ends the user's other
sessions. Sign-in does not ask for the code yet (F9-e); no screen yet (F9-j). 2FA is optional for every
user, admins included.

## Read first

- `AGENTS.md`, `docs/knowledge/conventions.md` (sections 4, 5 pins, 7)
- `docs/requirements/F9/README.md` (D-F9-2fa, D-F9-4, D-F9-10, data model `0031_mfa`)
- `F9-a-sessions.md` (revocation helpers, `rbses_mfa`), `F9-b-profile-reauth.md` (S7, S9-S11)
- `config.py` (`validate_settings`, `ConfigError`, `_secret_key_problem` pattern), `app/security.py`,
  `app/services/profile.py`, `app/api/v1/me.py`, `app/cli/users.py`
- `tests/test_dependency_pins.py` (from F9-c; create it here if F9-c is not merged), `tests/test_env_docs.py`

## Scope

In:
- Pins: `pyotp`, `segno`, `cryptography` (requirements + `AGENTS.md` table)
- `TOTP_ENCRYPTION_KEY` setting with startup validation
- Migration `0031_mfa`: `rbusermfa`, `rbrecoverycodes`; models `RbUserMfa`, `RbRecoveryCode`
  (`app/models/mfa.py`)
- `app/services/mfa.py`: secret encryption, setup, verify with replay protection, enable, disable,
  recovery codes, reset
- `POST /me/2fa/setup`, `/enable`, `/disable`, `/recovery-codes`; `POST /me/reauth` with `{code}`;
  `GET /me` `security.mfa` filled
- `flask users reset-2fa USERNAME` (the owner's way out until the F10 admin reset)
- Frontend: types and endpoint functions only

Out (do not do, even if tempting):
- The 2FA step at sign-in (F9-e), any screen (F9-j)
- WebAuthn, SMS, e-mail codes, "remember this device"
- Making 2FA mandatory for anyone (D-F9-2fa)
- Key rotation tooling (a later decision; the runbook documents the consequence of losing the key)

## Specs

S1. Pins: `pyotp==…`, `segno==…`, `cryptography==…` (each the newest release published at least two
    weeks before the install day; versions and dates in the PR), rows in the `AGENTS.md` technology
    table, covered by `tests/test_dependency_pins.py` (create it as F9-c S12 describes if absent).
S2. `TOTP_ENCRYPTION_KEY` (config, `.env.example` with an empty value and a comment on how to generate
    one, `README.md`): a Fernet key (URL-safe base64 of 32 bytes). `validate_settings`:
    - `RB_ENV=production`: missing → `ConfigError` listing `TOTP_ENCRYPTION_KEY is missing`; not a
      valid Fernet key → `TOTP_ENCRYPTION_KEY is not a valid key`. The message names the variable only,
      never the value.
    - `development`: missing → the app starts and 2FA is unavailable (S9); invalid → `ConfigError`.
    - `testing` skips validation like every other check; the default `app` fixture sets a key generated
      per test session.
S3. Migration `0031_mfa` (down revision: the current head; expected the F9-b revision, or the F9-c/F9-h
    one if merged first; take the next free number). `riftbound.rbusermfa` (model `RbUserMfa`):
    `rbmfa_user_id` INTEGER PK `rbusermfa_pkey`, FK `rbusermfa_user_fk` → `rbusers.id` ON DELETE
    CASCADE; `rbmfa_secret_enc` TEXT NOT NULL; `rbmfa_enabled_at` TIMESTAMP NULL (NULL = pending
    setup); `rbmfa_last_step` BIGINT NULL; `rbmfa_created_at` TIMESTAMP NOT NULL.
    `riftbound.rbrecoverycodes` (model `RbRecoveryCode`): `rbrco_id` BIGINT PK `rbrecoverycodes_pkey`
    (SQLite INTEGER variant); `rbrco_user_id` INTEGER NOT NULL FK `rbrecoverycodes_user_fk` →
    `rbusers.id` ON DELETE CASCADE; `rbrco_code_hash` CHAR(64) NOT NULL; `rbrco_used_at` TIMESTAMP NULL;
    index `ix_rbrecoverycodes_user` (`rbrco_user_id`). Downgrade drops both tables (docstring: every
    user's 2FA is lost).
S4. Secret: `pyotp.random_base32()` (32 characters, 160 bits), stored only as
    `Fernet(TOTP_ENCRYPTION_KEY).encrypt(...)`; the clear secret appears only in the setup response and
    is never logged. TOTP parameters: SHA-1, 6 digits, 30-second period (authenticator-app defaults).
S5. Code check (`mfa.verify_totp(user, code)`): spaces removed; must be 6 digits; accepted when it
    equals the code of step `s` for `s` in `current − 1 … current + 1` (`current = unix_time // 30`,
    time from `clock.utcnow()`), compared with `hmac.compare_digest`, **and** `s > last_step`; on
    success `last_step = s` is stored in the same transaction. A code already used (same or earlier
    step) is refused. Example: a code accepted at step 100 is refused at step 100 and 101 even though
    still inside the window; the next code (step 101) is accepted.
S6. Recovery codes: 10 per generation; each 10 characters from `abcdefghjkmnpqrstuvwxyz23456789`
    (`secrets.choice`), shown as `xxxxx-xxxxx`; stored as `sha256(normalised)` where normalised =
    lower case without spaces or hyphens. A code matches an unused row of the user (constant-time
    comparison) and is marked `used_at = now` on use; a used code never works again. Regenerating
    deletes every previous row of the user.
S7. `POST /me/2fa/setup` (U, re-auth per F9-b S9, no body): 2FA already enabled → 409 `already_exists`
    (message "Two-factor authentication is already on"); otherwise creates or replaces the pending row
    (new secret) → 200 `{secret, otpauth_uri, qr}`: `secret` grouped by 4 with spaces (`ABCD EFGH …`),
    `otpauth_uri` = `otpauth://totp/Rift%20Manager:<username>?secret=<secret>&issuer=Rift%20Manager`,
    `qr` = an SVG data URI of that URI made by `segno` (error level M). `Cache-Control: no-store`.
S8. `POST /me/2fa/enable` (U, re-auth, body `{code}`): no pending row → 404 envelope; already enabled →
    409 `already_exists`; wrong or replayed code → 400 `{code: "mfa_invalid", message: "The code is not
    valid"}`, nothing changes; success → `enabled_at = now`, `last_step` stored, 10 new recovery codes,
    the current session `rbses_mfa = true`, every **other** session revoked, all in one transaction →
    200 `{recovery_codes: [10 strings], revoked_sessions: n}`, `Cache-Control: no-store`.
S9. `POST /me/2fa/disable` (U, re-auth, body `{code}` = a TOTP code or a recovery code): not enabled →
    404 envelope; wrong → 400 `mfa_invalid`; success → deletes the `rbusermfa` row and every recovery
    code of the user, revokes every other session → 200 `{revoked_sessions: n}`.
S10. `POST /me/2fa/recovery-codes` (U, re-auth, no body): not enabled → 404 envelope; otherwise 10 new
    codes replace the old ones, every other session revoked → 200 `{recovery_codes, revoked_sessions}`,
    `Cache-Control: no-store`.
S11. 2FA unavailable (no key in development) → the four routes answer 503 `{error: "Service
    Unavailable", message: "Two-factor authentication is not available"}` (no `code`), and `GET /me`
    `security.mfa.available` is `false`. A secret that cannot be decrypted (the key changed) is logged
    without the secret and answered the same 503.
S12. The four routes share `20/hour` per IP (`scope='mfa_manage'`; 21st → 429 `rate_limited`). A wrong
    code here does not touch `failed_login_count`.
S13. `POST /me/reauth {code}` (F9-b S11): when 2FA is enabled the code is checked with S5 (recovery
    codes are **not** accepted for re-auth) → 200 `{reauth_until}`, wrong → 400 `mfa_invalid`; when it
    is not enabled the F9-b answer stays. `reauth_required.params.methods` includes `totp` when enabled.
S14. `GET /me` `security.mfa` = `{available, enabled, pending, recovery_codes_left}` (`pending` = a
    setup row without `enabled_at`; `recovery_codes_left` = unused codes, 0 when off).
S15. `flask users reset-2fa USERNAME` deletes the user's 2FA row and recovery codes and revokes all
    their sessions; prints `Two-factor authentication removed for '<username>'; <n> session(s) ended`,
    or `'<username>' has no two-factor authentication` (exit 0); unknown user → the existing
    `No such user` error. `mfa.reset(user)` is the service F10 will call.
S16. Status codes: `mfa_invalid` is **400** on these signed-in routes (a 401 would make the SPA's client
    treat the user as signed out); F9-e uses 401 only on the anonymous `POST /auth/mfa`.
S17. Error code (enum, `errors.json`, catalog test): `mfa_invalid` → "That code is not valid. Check
    your authenticator app and try again."
S18. Frontend (types only): `MfaSetup`, `RecoveryCodes`, `MeData.security.mfa` already typed by F9-b;
    endpoint functions `setupMfa`, `enableMfa`, `disableMfa`, `regenerateRecoveryCodes` in
    `api/endpoints.ts`.

## API / data contract

| Method | Path (prefix `/riftbound/api/v1`) | Auth | Endpoint name | Notes |
|---|---|---|---|---|
| POST | `/me/2fa/setup` | U (re-auth) | `api_v1.mfa_setup` | S7 |
| POST | `/me/2fa/enable` | U (re-auth) | `api_v1.mfa_enable` | S8 |
| POST | `/me/2fa/disable` | U (re-auth) | `api_v1.mfa_disable` | S9 |
| POST | `/me/2fa/recovery-codes` | U (re-auth) | `api_v1.mfa_recovery_codes` | S10 |
| POST | `/me/reauth` | U | existing | S13 |

Routes in a new `app/api/v1/mfa.py`. Schemas `MfaCode` (`code`: 1-32 characters) in
`app/schemas/validators.py`. `docs/api.md`: "Two-factor authentication (F9-d)".

## UI

none (F9-j builds the wizard).

## Acceptance criteria

- [ ] AC1 `tests/test_mfa_migration.py`: round trip from the previous head, column, constraint and
      index names, foreign keys, `drift()` clean (S3)
- [ ] AC2 `tests/test_mfa_service.py`: encryption at rest (the column never contains the clear secret),
      S5 window and replay example with `frozen_clock`, non-digit and 5/7-digit codes, recovery code
      format, normalisation (`ABCDE FGHJK` and `abcde-fghjk` match), single use, regeneration (S4-S6)
- [ ] AC3 `tests/test_api_mfa.py`: setup (shape, grouping, URI, `qr` starts with
      `data:image/svg+xml`, no-store), enable/disable/regenerate success and every error, re-auth
      required on all four (403 with stale `reauth_at`), other sessions revoked and the current one
      kept with `mfa = true`, rate limit, unavailable 503 without a key, undecryptable secret 503
      (S7-S12, S14)
- [ ] AC4 `tests/test_api_reauth.py` extended: TOTP re-auth, replay refused, recovery code refused,
      `methods` lists `totp` (S13)
- [ ] AC5 `tests/test_config.py`: production without key / invalid key → `ConfigError` naming only the
      variable (the value never appears in the message); development without key starts (S2)
- [ ] AC6 `tests/test_users_cli.py`: `reset-2fa` (S15); error catalog test green with `mfa_invalid`;
      authz matrix: the four endpoints → `U`; `tests/test_dependency_pins.py` and
      `tests/test_env_docs.py` green; `bandit -r app/ -ll` clean
- [ ] AC7 Frontend: endpoint functions tested for paths and bodies (S18)
- [ ] AC8 Full lanes green: `venv/bin/pytest`; `cd frontend && npm run lint && npm run typecheck &&
      npx vitest run && npm run build && npm run check:dist`; `flask db upgrade`, `flask db check`,
      `flask db downgrade -1`, upgrade again on a throw-away database
- [ ] AC9 Docs: `docs/api.md`; `AGENTS.md` (technology table, Configuration `TOTP_ENCRYPTION_KEY`, tree,
      tables `rbusermfa`, `rbrecoverycodes`, API list, `flask users reset-2fa`); `.env.example`,
      `README.md`; `docs/knowledge/ops-runbook.md` → "Two-factor key (F9-d)": generate the key, store it
      only in the service environment file, back it up apart from the database dumps, losing it =
      every user's 2FA must be reset; `docs/knowledge/state.md`

## Delivery

- Conventional Commits; commit messages end with the attribution lines the session supplies.
- Own PR (migration). PR title: `feat(account): TOTP two-factor enrolment and recovery codes (F9 unit d)`.
  PR body: S# → tests, pins with dates, rollback (`flask db downgrade` one step drops every 2FA; revert).
- Never merge. The owner merges.

## After merge

- Deploy to dev: **`pg_dump` backup first**; `pip install -r requirements.txt`; **before restarting,
  generate `TOTP_ENCRYPTION_KEY` and add it to the service environment file** (the app refuses to start
  in production without it; runbook entry); `flask db upgrade` (`0031_mfa`), `flask db check`, restart.
- Live checks: `GET /riftbound/api/v1/me` shows `mfa.available: true`; with an authenticator app, setup
  → enable with a code → 10 recovery codes; disable with a recovery code.
- Manual checks for the owner: keep a copy of the key outside the server.

## Open questions

none
