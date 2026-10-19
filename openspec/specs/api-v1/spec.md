# api-v1 Specification

Source: change f0-foundation (archived 2026-10-19)

> Tags: `[a]`..`[e]` = delivery unit of change f0-foundation; every requirement here is unit `[e]`. All routes are under `/riftbound/api/v1`. Success envelope: `{"success":true,"data":<object>,"meta":<object, optional>}`. Error envelope: `{"success":false,"error":"<name>","message":"<text>","details":[...optional]}`. Legacy Jinja-era JSON endpoints stay flat and unchanged. All scenarios are pytest-testable (SQLite) unless tagged.

## Requirements

### Requirement: API-1 Blueprint and envelope [e]

The API MUST live in a blueprint with prefix `/riftbound/api/v1` and MUST NOT collide with landing `/api/*` routes. Every response from this prefix (including framework errors 400/401/403/404/405/415/429/500 and CSRF errors) MUST use the envelopes above with `Content-Type: application/json`. 500 responses MUST NOT leak stack traces or exception text.

#### Scenario: Unknown path with browser Accept
- GIVEN any client
- WHEN `GET /riftbound/api/v1/nope` is sent with `Accept: text/html`
- THEN status 404, JSON `{success:false,error:"Not Found",message}`

#### Scenario: Wrong method
- GIVEN any client
- WHEN `POST /riftbound/api/v1/health` is sent
- THEN status 405, JSON error envelope with `error:"Method Not Allowed"`

#### Scenario: Unhandled exception
- GIVEN an API route that raises `ValueError('secret detail')`
- WHEN it is called
- THEN status 500, `message` is generic and does not contain `secret detail`

### Requirement: API-2 GET /health [e]

Public. MUST return 200 `{success:true,data:{status:"ok",db:"ok",version:"<non-empty>"}}` after a `SELECT 1`. If the database is unreachable it MUST return 503 with the error envelope. It MUST NOT expose connection strings or secrets.

#### Scenario: Healthy
- GIVEN the app with a working DB, no session
- WHEN `GET /riftbound/api/v1/health`
- THEN 200 with the shape above

#### Scenario: DB down
- GIVEN the DB query raises
- WHEN the endpoint is called
- THEN 503 `{success:false,error:"Service Unavailable",message}`

### Requirement: API-3 GET /meta/config [e]

Public. MUST return `data` with `captcha:{provider, required_for}`, `registration_open` (true) and `env`. `required_for` is `["register"]` when provider is not `none`, else `[]`. It MUST NOT contain secrets (SECRET_KEY, DB URL, captcha keys).

#### Scenario: Altcha on
- GIVEN `CAPTCHA_PROVIDER=altcha`
- WHEN the endpoint is called
- THEN `captcha == {provider:"altcha",required_for:["register"]}`

#### Scenario: Captcha off
- GIVEN `CAPTCHA_PROVIDER=none`
- WHEN called
- THEN `captcha == {provider:"none",required_for:[]}` and the body has no `SECRET`/`DATABASE` keys

### Requirement: API-4 GET /auth/session [e]

Public. MUST return `data:{authenticated:false,csrf_token:"<non-empty>"}` for anonymous callers and `data:{authenticated:true,user:{id,username,email,is_admin},csrf_token}` for logged-in users. It MUST NOT include the password hash. A blocked user is anonymous. The token MUST be accepted as `X-CSRFToken` on later unsafe requests.

#### Scenario: Anonymous
- GIVEN no session
- WHEN called
- THEN 200 and `authenticated == false` with a token

#### Scenario: Logged in
- GIVEN a logged-in user
- WHEN called
- THEN `user` has exactly `id, username, email, is_admin` and no hash

### Requirement: API-5 POST /auth/login [e]

JSON `{username,password}`, validated per LOGIN-9, using the same service, lockout and limits as the form. Success: 200 `data:{user:{id,username,email,is_admin}}` and a session cookie. Invalid or blocked: 401 `error:"Unauthorized"`, `message:"Invalid credentials"`. Locked: 429 with `Retry-After` (LOGIN-2). Invalid body: 400 `Validation Error` with `details`. With CSRF enabled a request without a valid `X-CSRFToken` is 400.

#### Scenario: Success
- GIVEN user `u` / `Passw0rd!x`
- WHEN logged in via the API
- THEN 200, then `GET /auth/session` shows `authenticated:true`

#### Scenario: Bad password then lock
- GIVEN user `u`
- WHEN 5 wrong passwords then the correct one are posted
- THEN the first 5 are 401 and the 6th is 429 with `Retry-After`

#### Scenario: Missing fields
- GIVEN any client
- WHEN `{"username":"u"}` is posted
- THEN 400 with `details` naming `password`

#### Scenario: CSRF
- GIVEN `csrf_app`
- WHEN login is posted without a token, then with the token from `/auth/session`
- THEN 400 then 200

### Requirement: API-6 POST /auth/logout [e]

Authenticated only. MUST end the session and return 200 `{success:true,data:{}}`. Anonymous callers MUST get JSON 401, never a redirect.

#### Scenario: Logout
- GIVEN a logged-in user
- WHEN `POST /auth/logout`
- THEN 200 and `/auth/session` reports `authenticated:false`

#### Scenario: Anonymous logout
- GIVEN no session
- WHEN `POST /auth/logout`
- THEN 401 JSON error envelope, no redirect

### Requirement: API-7 POST /auth/register [e]

JSON `{username,email,password,altcha?}`. Success: 201 `data:{user:{id,username}}`, `is_admin=false`, NO session created. Validation or captcha failure: 400 (`details` for fields; `error:"Captcha Error"` for captcha). Duplicate username or email: 409. Rate-limited: 429. Rules from LOGIN-8/LOGIN-9 apply.

#### Scenario: Created
- GIVEN provider `none`
- WHEN valid fields are posted
- THEN 201 and `/auth/session` is still `authenticated:false`

#### Scenario: Duplicate
- GIVEN user `dup` exists
- WHEN `dup` is registered again
- THEN 409 `{success:false,error:"Conflict",message}`

#### Scenario: Captcha missing
- GIVEN provider `altcha`
- WHEN valid fields are posted without `altcha`
- THEN 400 `error:"Captcha Error"` and no user row

### Requirement: API-8 JSON vs HTML negotiation [e]

An error or unauthorized response MUST be JSON when: the path starts with `/riftbound/api/`; or the request body is JSON; or `Accept` prefers `application/json` over `text/html` (including `*/*`). Otherwise it MUST be HTML (error page, or 302 to `/riftbound/login` for unauthorized). Requests with no `Accept` header MUST be treated as HTML (baseline tests rely on it). Flask-Login's unauthorized handler MUST return JSON 401 in the JSON cases and redirect otherwise.

#### Scenario: Browser 404
- GIVEN `Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8`
- WHEN `GET /riftbound/nope`
- THEN 404 with `text/html`

#### Scenario: fetch default Accept
- GIVEN `Accept: */*`
- WHEN `GET /riftbound/nope`
- THEN 404 JSON `{success:false,error:"Not Found",message}`

#### Scenario: No Accept, protected page
- GIVEN no `Accept` header and no session
- WHEN `GET /riftbound/`
- THEN 302 to `/riftbound/login`

#### Scenario: JSON client unauthorized
- GIVEN `Accept: application/json` and no session
- WHEN `GET /riftbound/collection/api/sets`
- THEN 401 JSON `{success:false,error:"Unauthorized",message}`
