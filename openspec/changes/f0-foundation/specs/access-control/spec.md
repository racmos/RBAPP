# Delta for access-control

> Tags: `[a]`..`[e]` = delivery unit. `[PG-CI]` = PostgreSQL CI job; `[MANUAL]` = manual/ops check. Untagged scenarios are pytest-testable. "Anonymous denial" means: HTML/no-Accept client gets 302 to `/riftbound/login`; JSON client (`Accept: application/json` or JSON body) gets 401 `{success:false,error:"Unauthorized",message}`. "Non-admin denial" means 403 (JSON `{success:false,error:"Forbidden",message}` for JSON clients, HTML 403 page otherwise).

## ADDED Requirements

### Requirement: ACL-1 Admin and block flags [c]

`rbusers` MUST gain `is_admin BOOLEAN NOT NULL DEFAULT false` and `is_active BOOLEAN NOT NULL DEFAULT true` through its own Alembic revision, valid on SQLite and PostgreSQL, with server defaults so existing rows are valid. No migration, env var or registration input may make a user admin.

#### Scenario: Existing users after upgrade
- GIVEN a user row created at the previous revision
- WHEN the revision runs
- THEN that row has `is_admin=false` and `is_active=true`; downgrade removes both columns

#### Scenario: No self-promotion
- GIVEN registration is open
- WHEN a register request includes `is_admin=true` (form or JSON)
- THEN the created user has `is_admin=false`

### Requirement: ACL-2 Blocked accounts lose access [c]

A user with `is_active=false` MUST NOT log in and MUST lose any existing session on the next request. The login response MUST be indistinguishable from invalid credentials.

#### Scenario: Existing session is cut
- GIVEN a logged-in user, then `is_active` set to false
- WHEN the next `GET /riftbound/` is made with the same session
- THEN anonymous denial is returned

#### Scenario: Correct password, blocked
- GIVEN a blocked user
- WHEN they submit the correct password to login
- THEN no session is created and the response equals the wrong-password response

### Requirement: ACL-3 Admin guard [c]

Admin-only routes MUST return anonymous denial to anonymous callers (never 403), non-admin denial to authenticated non-admins, and proceed for admins. The guard MUST cover: `POST /riftbound/set/add`, `POST /riftbound/set/update/<id>`, `POST /riftbound/card/add`, `POST /riftbound/card/update/<set>/<card>`, `POST /riftbound/card/upload_image`, and EVERY rule of the `price` blueprint (23 routes, all methods), including routes added later.

#### Scenario: Non-admin cannot change the catalog
- GIVEN a logged-in non-admin
- WHEN they POST valid JSON to `/riftbound/set/add` or `/riftbound/card/add`
- THEN the status is 403 and nothing is inserted

#### Scenario: Non-admin cannot use price tools
- GIVEN a logged-in non-admin
- WHEN they request every `price/*` rule (e.g. `POST /riftbound/price/cardmarket-load`, `GET /riftbound/price`)
- THEN every response is 403 and no outbound request is made

#### Scenario: Admin passes
- GIVEN an admin session
- WHEN they POST valid JSON to `/riftbound/set/add`
- THEN the status is 200 and the set exists

### Requirement: ACL-4 Catalog stays readable; admin UI hidden [c]

Non-admins MUST still read Sets and Cards (`GET /riftbound/set`, `GET /riftbound/card` return 200). Templates MUST NOT render Add/Edit controls, the Price nav link or the Price dashboard card for non-admins; admins MUST see them. The server check stays authoritative.

#### Scenario: Non-admin pages
- GIVEN a logged-in non-admin
- WHEN they GET `/riftbound/set`, `/riftbound/card` and `/riftbound/`
- THEN all return 200 and the HTML has no add/edit controls and no link to `/riftbound/price`

#### Scenario: Admin pages
- GIVEN an admin session
- WHEN the same pages are requested
- THEN the add/edit controls and the Price link are present

### Requirement: ACL-5 Authorization matrix [c]

Every URL rule in `app.url_map` MUST be classified exactly once as P (public), U (authenticated) or A (admin) in an explicit table in the test suite, and enforced accordingly. Rules added by units d and e MUST be added to the table. An unclassified rule MUST fail the suite.

| Class | Rules |
|---|---|
| P | landing (`/`, `/api/*` partials, `/frames/*`, landing static), Flask `static`, `/riftbound/login`, `/riftbound/register`, the captcha challenge endpoint, `/riftbound/api/v1/{health,meta/config,auth/session,auth/login,auth/register}` |
| U | dashboard, logout, `set` list, `card` list, `collection/*`, `deck/*`, `profile/*`, `/riftbound/api/v1/auth/logout` |
| A | ACL-3 list |

#### Scenario: Enforcement per class
- GIVEN the table
- WHEN each rule is called as anonymous, as non-admin and as admin
- THEN P is never 401/403, U gives anonymous denial for anonymous and not 401/403 for users, A gives anonymous denial / 403 / not 401-403 respectively

#### Scenario: Unclassified rule fails
- GIVEN a route registered but missing from the table
- WHEN the matrix test runs
- THEN it fails naming the rule

### Requirement: ACL-6 Admin CLI [c]

`flask users make-admin <username>` MUST set `is_admin=true`; `flask users revoke-admin <username>` MUST clear it; `flask users block|unblock <username>` SHOULD set `is_active`. All MUST be idempotent, exit 0 on success and exit non-zero with a message for an unknown user, changing nothing. The CLI MUST work while no admin exists.

#### Scenario: Promote
- GIVEN user `alice` (non-admin)
- WHEN `flask users make-admin alice` runs (twice)
- THEN `alice.is_admin` is true and both exits are 0

#### Scenario: Unknown user
- GIVEN no user `ghost`
- WHEN `flask users make-admin ghost` runs
- THEN the exit code is non-zero, stderr/stdout names `ghost`, and no row changes

### Requirement: ACL-7 Cardmarket URL allow-list [c]

`price/cardmarket-load` overrides (`singles_url`, `nonsingles_url`, `price_guide_url`) MUST be accepted only if the scheme is `https` and the host is in the configured Cardmarket allow-list (default: the host of the built-in URLs). Otherwise: 400 `{success:false,error,message}` and no outbound request.

#### Scenario: Foreign host rejected
- GIVEN an admin session and the HTTP client mocked
- WHEN `singles_url` is `http://169.254.169.254/x` or `https://evil.example/x`
- THEN the status is 400 and the mock was not called

#### Scenario: Allowed host accepted
- GIVEN an admin session
- WHEN `price_guide_url` has an allow-listed host over https
- THEN the load proceeds using that URL

### Requirement: ACL-8 Test fixtures [c]

The suite MUST provide `admin_client` and `other_user_client` fixtures. Existing tests that call admin-only routes (about 14) MUST move to `admin_client`; none may be deleted or weakened (the one input adaptation in PROF-2 aside), and all 93 baseline tests MUST still pass.

#### Scenario: Baseline intact
- GIVEN the migrated tests
- WHEN `venv/bin/python -m pytest` runs
- THEN the 93 baseline tests pass (plus new ones)
