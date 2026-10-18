# Delta for login-protection

> Tags: `[a]`..`[e]` = delivery unit. `[MANUAL]` = manual/ops check. Untagged scenarios are pytest-testable; time-dependent ones use an injectable test clock (no sleeping). Default test config has rate limiting, captcha and CSRF OFF (`RATELIMIT_ENABLED=False`, `CAPTCHA_PROVIDER=none`, `WTF_CSRF_ENABLED=False`) so the 93 baseline tests are unaffected; dedicated fixtures turn each on. Applies to the Jinja forms (`/riftbound/login`, `/riftbound/register`) in unit d and to the API (see api-v1) through one shared auth service. "Locked response" = HTTP 429 with integer `Retry-After` (seconds) and the generic message "Invalid credentials or account temporarily locked".

## ADDED Requirements

### Requirement: LOGIN-1 Lockout columns [d]

`rbusers` MUST gain `failed_login_count INTEGER NOT NULL DEFAULT 0`, `locked_until TIMESTAMP NULL`, `last_login_at TIMESTAMP NULL` in their own Alembic revision (SQLite + PostgreSQL, reversible). Any captcha replay store is added in the same or a sibling revision.

#### Scenario: Existing users
- GIVEN a user row at the previous revision
- WHEN the revision runs
- THEN `failed_login_count=0`, `locked_until` and `last_login_at` are NULL; downgrade drops the columns

### Requirement: LOGIN-2 Account lockout [d]

For an existing, active user, each wrong password MUST increment `failed_login_count`. The 5th consecutive failure MUST set `locked_until = now + 15 min`. While `locked_until` is in the future, every login attempt (even with the correct password) MUST return the locked response, MUST NOT create a session, and MUST NOT increment the counter or extend the lock. Failures 1-4 return the normal invalid-credentials response (Jinja: redirect to login with a flash containing "Invalid"; API: 401).

#### Scenario: Fifth failure locks, sixth is refused
- GIVEN user `u` with count 0 and clock at T
- WHEN 5 wrong passwords are submitted, then the correct one at T+1 min
- THEN `locked_until == T+15min`, and the last response is 429 with `Retry-After` between 1 and 900 and no session

#### Scenario: Lock expires
- GIVEN the lock above
- WHEN the correct password is submitted at T+16 min
- THEN login succeeds

#### Scenario: Attempts during lock don't extend it
- GIVEN a locked user
- WHEN 3 more attempts are made before expiry
- THEN `failed_login_count` and `locked_until` are unchanged

### Requirement: LOGIN-3 Escalating lock [d]

After the threshold, each further failed attempt made after a lock expired MUST re-lock for `min(15 min * 2^(n-5), 24 h)`, where `n` is the new `failed_login_count` (n=5: 15 min, 6: 30, 7: 60, 11: 960 min, 12 and above: 24 h).

#### Scenario: Escalation
- GIVEN `failed_login_count=5` and an expired lock
- WHEN a wrong password is submitted
- THEN count is 6 and `locked_until = now + 30 min`

#### Scenario: Cap
- GIVEN `failed_login_count=11` and an expired lock
- WHEN a wrong password is submitted
- THEN count is 12 and `locked_until = now + 24 h`; a further failure keeps 24 h

### Requirement: LOGIN-4 Success resets state [d]

A successful login MUST set `failed_login_count=0`, `locked_until=NULL`, `last_login_at=now`. A lock MUST NOT invalidate an existing valid session.

#### Scenario: Reset
- GIVEN `failed_login_count=3`
- WHEN the correct password is submitted
- THEN count is 0, `locked_until` NULL, `last_login_at` set

#### Scenario: Existing session survives
- GIVEN client 1 logged in as `u`, and client 2 triggers a lock on `u`
- WHEN client 1 requests `GET /riftbound/`
- THEN status 200

### Requirement: LOGIN-5 No account oracle [d]

An unknown username MUST produce the same status and body shape as a wrong password and MUST do equivalent password-hash work (a dummy hash is verified). Only IP limits apply to unknown names. Blocked (`is_active=false`) users get the same response as wrong password.

#### Scenario: Same response
- GIVEN unknown `ghost` and known `u`
- WHEN each is given a wrong password
- THEN status and message are identical, and hash verification ran once in both cases (mocked counter)

#### Scenario: Timing [MANUAL]
- GIVEN both cases
- WHEN response times are sampled
- THEN no systematic gap is visible

### Requirement: LOGIN-6 Unlock CLI [d]

`flask users unlock <username>` MUST reset `failed_login_count` to 0 and `locked_until` to NULL. Unknown user: non-zero exit, nothing changed.

#### Scenario: Unlock
- GIVEN a locked `u`
- WHEN `flask users unlock u` runs
- THEN exit 0 and the correct password logs in immediately

### Requirement: LOGIN-7 Rate limits [d]

Flask-Limiter MUST use storage from `RATELIMIT_STORAGE_URI` (default `memory://`) and limit per client IP: login `10/minute;50/hour`, register `5/hour`. Excess requests MUST return 429 with `Retry-After`: JSON envelope `{success:false,error:"Too Many Requests",message}` for JSON clients, an HTML page otherwise. `RATELIMIT_ENABLED=false` MUST disable it.

#### Scenario: Login burst
- GIVEN `limiter_app` (limiter on, lockout irrelevant: unknown usernames)
- WHEN 11 login POSTs come from one IP within a minute
- THEN the 11th returns 429 with `Retry-After`

#### Scenario: Register cap
- GIVEN `limiter_app`
- WHEN 6 register POSTs come from one IP within an hour
- THEN the 6th returns 429

#### Scenario: Nginx layer [MANUAL]
- GIVEN `docs/nginx_config`
- WHEN reviewed
- THEN it documents a `limit_req` zone for `/riftbound/login`, `/riftbound/register` and `/riftbound/api/v1/auth/`, and states the in-app limiter is per Gunicorn worker

### Requirement: LOGIN-8 ALTCHA on register [d]

With `CAPTCHA_PROVIDER=altcha` (the default outside testing), registration MUST require a valid ALTCHA payload solved for a challenge issued by the server (public challenge endpoint, route fixed in design). The payload MUST be rejected if absent, tampered, expired (default TTL 5 min) or already used. No user is created on rejection. With `none` no payload is needed. A replay store shared by workers is preferred; at minimum replay MUST fail within one process.

#### Scenario: Missing payload
- GIVEN provider `altcha`, valid username/email/password
- WHEN the register form is posted without `altcha`
- THEN rejected, no user row, the form is shown again with an error

#### Scenario: Valid payload
- GIVEN a challenge fetched and solved with the `altcha` library
- WHEN it is posted with valid fields
- THEN the user is created (`is_admin=false`)

#### Scenario: Replay and expiry
- GIVEN a payload already accepted once, and another older than the TTL
- WHEN each is posted again
- THEN both are rejected and no user is created

#### Scenario: Tampered
- GIVEN a solved payload with a modified signature
- WHEN posted
- THEN rejected

### Requirement: LOGIN-9 Input validation shared by Jinja and API [d]

Register input MUST be validated by one Pydantic schema: username `^[A-Za-z0-9_.-]{3,32}$`, email valid format and at most 120 chars, password 8-128 chars. Login input MUST only require non-empty username and password (no pattern), so legacy usernames still log in. Duplicate username or email MUST be refused with the existing messages ("Username already exists", "Email already registered"). Registration MUST NOT log the user in.

#### Scenario: Invalid fields
- GIVEN register payloads with username `ab`, `bad name!`, email `x`, password `short7!`
- WHEN each is posted
- THEN each is rejected and no user is created

#### Scenario: Legacy username logs in
- GIVEN an existing user named `Old User (1)`
- WHEN they log in with the right password
- THEN login succeeds

#### Scenario: Duplicate
- GIVEN user `dup`
- WHEN `dup` registers again
- THEN the response contains "already" and no second row exists
