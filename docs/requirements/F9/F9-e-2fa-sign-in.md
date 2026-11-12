# F9-e: Two-factor step at sign-in

| Field | Value |
|---|---|
| Phase / unit | F9 / e |
| Branch | `feat/f9e-2fa-sign-in` (from up-to-date `main`, F9-d merged) |
| Depends on | F9-d (`rbusermfa`, `mfa.verify_totp`, recovery codes), F9-a (session creation) |
| Size forecast | ~450 authored lines (tests and docs included) |
| Risk | `Risk: item 2 (every login path must require the second factor; lockout coupling; no bypass)` |
| TDD | ON (strict). Runners: `venv/bin/pytest`, `cd frontend && npx vitest run` (types, endpoint, client path list) |
| Save as | `docs/requirements/F9/F9-e-2fa-sign-in.md` |

## Objective

A user who turned on two-factor authentication must give a code from the authenticator app (or a
recovery code) after the password before any session exists. Wrong codes count towards the same account
lock as wrong passwords, the step expires after 5 minutes, and no way of signing in skips it. 2FA stays
optional for everyone, admins included. The sign-in screen for the code is F9-j.

## Read first

- `AGENTS.md` (CSRF, Sessions and Login Protection), `docs/knowledge/conventions.md`
- `docs/requirements/F9/README.md` (risks: no bypass, lockout coupling), `F9-a-sessions.md` (S5),
  `F9-d-totp-enrolment.md` (S5, S6, S11, S16)
- `app/api/v1/auth.py`, `app/services/auth.py` (state machine, `_register_failure`, lock lengths),
  `app/services/sessions.py`, `app/services/mfa.py`
- `frontend/src/api/client.ts` (`AUTH_ANSWER_PATHS`), `frontend/src/api/types.ts`, `endpoints.ts`
- `tests/test_api_auth_guards.py`

## Scope

In:
- `POST /auth/login` answers `{mfa_required: true, …}` without a session for 2FA users
- The pending step in the Flask session; `POST /auth/mfa`
- One sign-in function that refuses to create a session for a 2FA user without the second factor
- Lockout coupling, rate limits, `/auth/session` `mfa_pending` flag
- Frontend: types, `completeMfa`, `/auth/mfa` added to the client's auth-answer paths

Out (do not do, even if tempting):
- The `/login/2fa` screen and the login page redirect (F9-j)
- OAuth (F9-f wires its own sign-in into the same pending step)
- "Trust this device", mandatory 2FA, changes to the lock lengths

## Specs

S1. Single entry: every session is created by one function, `sessions.sign_in(user, *, remember,
    auth_method, mfa_passed)`, the only caller of `flask_login.login_user` in the app (a test greps
    `app/` and fails if `login_user(` appears anywhere else). When the user has 2FA enabled and
    `mfa_passed` is false it raises and creates nothing. It sets `rbses_mfa = mfa_passed`.
S2. `POST /auth/login`, right password, account not blocked or locked, 2FA **enabled** → 200
    `{mfa_required: true, methods: ["totp", "recovery"]}`; no session row, no `login_user`, no
    remember cookie; `failed_login_count` and `locked_until` are **not** reset (they are reset only when
    the code succeeds); the Flask session stores `mfa_pending = {uid, remember, method: "password",
    started_at, attempts: 0}` (replacing any previous pending step). Accounts without 2FA keep today's
    answer `{user}` and session (F9-a S5). Wrong password, locked and blocked answers are unchanged.
S3. Pending step lifetime: 5 minutes from `started_at` (`clock.utcnow()`); at most 5 code attempts. It
    is removed on success, on expiry, after the 5th wrong code, on logout, and when a new password
    login starts. It never authenticates anything: while it exists every U route answers 401
    `unauthenticated` and `GET /auth/session` answers `authenticated: false` plus `mfa_pending: true`
    (the key appears only when a live pending step exists; additive).
S4. `POST /auth/mfa` (P, CSRF required like every unsafe route, body `MfaSignIn`: exactly one of
    `code` (TOTP) or `recovery_code`; both or neither → 400 `validation_error`):
    - no pending step, expired, the user now blocked or deleted, or the user no longer has 2FA → 401
      `{error: "Unauthorized", message: "The sign-in step expired", code: "mfa_expired"}`, pending
      removed;
    - account locked (`locked_until > now`) → 429 `locked` with `Retry-After` and `params.retry_after`
      (the login answer), pending removed;
    - wrong or replayed TOTP / unknown or used recovery code → `attempts + 1` and one failure counted
      exactly like a wrong password (`_register_failure`); when that failure locks the account → 429
      `locked` (pending removed); otherwise 401 `{code: "mfa_invalid", message: "The code is not
      valid"}`; when `attempts` reaches 5 the pending step is removed (the next call is `mfa_expired`);
    - right code → `sessions.sign_in(user, remember=pending.remember, auth_method=pending.method,
      mfa_passed=True)`, `failed_login_count = 0`, `locked_until = NULL`, `last_login_at = now`, pending
      removed → 200 `{user, recovery_code_used: <bool>, recovery_codes_left: <n>}` (`user` =
      `user_payload`). A recovery code is marked used in the same transaction.
    - the secret cannot be decrypted (F9-d S11) → 503 for `code`; `recovery_code` still works.
S5. Rate limit of `POST /auth/mfa`: `10/minute;50/hour` per IP (`@limiter.shared_limit(...,
    scope='mfa')`; 11th in a minute → 429 `rate_limited`).
S6. Lockout coupling example (default settings: lock at the 5th consecutive failure): a user with 0
    failures signs in with the right password, then sends 4 wrong codes (401 `mfa_invalid` each,
    `failed_login_count` 4) and a 5th wrong code → 429 `locked` for 15 minutes; a later right password
    during the lock → 429 `locked` (unchanged rule). A right code after 3 wrong ones resets the count to 0.
S7. Remember: the `remember` flag sent to `POST /auth/login` reaches the session created by S4 (a
    remember cookie only when it was true).
S8. No bypass (each a test): password login of a 2FA user gives no access to `GET /me` until the code;
    a remember cookie or session created before 2FA was enabled is revoked (F9-d S8) and stays
    anonymous; the pending step of user A cannot complete for user B (the body names no user); a
    pending step copied to another client (same Flask session cookie) still needs the code and counts
    the same attempts; `sessions.sign_in` refuses `mfa_passed=False` for a 2FA user; admins follow the
    same rules (an admin with 2FA cannot reach `/admin/*` with the password alone).
S9. Error code (enum, `errors.json`, catalog test): `mfa_expired` (401) → "The sign-in step expired.
    Sign in again." (`mfa_invalid` comes from F9-d; on `/auth/mfa` it is 401.)
S10. Frontend (no screen): `LoginResult = {user} | {mfa_required: true, methods: string[]}`;
    `SessionData.mfa_pending?: boolean`; `MfaSignInBody`, `MfaSignInResult`; `completeMfa(body)` in
    `api/endpoints.ts`; `/auth/mfa` added to `AUTH_ANSWER_PATHS` in `api/client.ts` so its 401 answers
    do not trigger the signed-out handler (client test).

## API / data contract

| Method | Path (prefix `/riftbound/api/v1`) | Auth | Endpoint name | Notes |
|---|---|---|---|---|
| POST | `/auth/login` | P | existing | S2: `{mfa_required, methods}` for 2FA users |
| POST | `/auth/mfa` | P (pending step) | `api_v1.auth_mfa` | S4, S5 |
| GET | `/auth/session` | P | existing | S3: `mfa_pending` (additive) |

Schema `MfaSignIn` in `app/schemas/validators.py`. `docs/api.md`: "Two-factor sign-in (F9-e)" and the
`/auth/login` and `/auth/session` sections. No migration.

## UI

none (F9-j builds `/login/2fa`). Until F9-j is deployed nobody can turn 2FA on from the app, so the
login screen never receives `mfa_required`.

## Acceptance criteria

- [ ] AC1 `tests/test_api_auth_guards.py` extended — class `TestTwoFactorSignIn`: S2 answer and no
      session/cookie; S3 lifetime (4:59 works, 5:01 `mfa_expired` with `frozen_clock`), 5-attempt
      limit, pending removed on logout and on a new login; S4 every branch; S6 example step by step;
      S7 remember; rate limit with `limited_app`; CSRF required on `/auth/mfa` with `csrf_app`
- [ ] AC2 `tests/test_api_auth_guards.py::TestNoMfaBypass`: every S8 case, including the grep test of S1
- [ ] AC3 `tests/test_sessions_service.py` extended: `sign_in` refuses `mfa_passed=False` for a 2FA user
      and sets `rbses_mfa` (S1)
- [ ] AC4 Error catalog test green with `mfa_expired`; authz matrix: `api_v1.auth_mfa` → `P`
- [ ] AC5 Frontend: `client.test.ts` (a 401 from `/auth/mfa` does not call the unauthorized handler),
      endpoint test for `completeMfa` (S10)
- [ ] AC6 Full lanes green: `venv/bin/pytest`; `cd frontend && npm run lint && npm run typecheck &&
      npx vitest run && npm run build && npm run check:dist`
- [ ] AC7 Docs: `docs/api.md`; `AGENTS.md` (CSRF, Sessions and Login Protection: the 2FA step, the
      coupling with the lock; public endpoints list gains `POST /auth/mfa`; API list); `docs/knowledge/state.md`

## Delivery

- Conventional Commits; commit messages end with the attribution lines the session supplies.
- PR title: `feat(auth): two-factor step at sign-in with lockout coupling (F9 unit e)`. PR body: S# →
  tests, the no-bypass list, rollback (revert: 2FA users then sign in with the password only).
- Never merge. The owner merges.

## After merge

- Deploy to dev (no migration): backend restart, frontend rebuild.
- Live checks (with a test account that enabled 2FA through the API): `POST /auth/login` → `mfa_required`;
  `GET /me` → 401; `POST /auth/mfa` with a code → `{user}`; a recovery code works once.
- Manual checks for the owner: none until F9-j.

## Open questions

none
