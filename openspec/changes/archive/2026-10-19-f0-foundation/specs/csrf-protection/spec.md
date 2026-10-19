# Delta for csrf-protection

> Tags: `[a]`..`[e]` = delivery unit. `[MANUAL]` = manual/browser check. Untagged scenarios are pytest-testable with the `csrf_app` fixture (CSRF enabled). The default test config keeps CSRF disabled so the 93 baseline tests are untouched.

## ADDED Requirements

### Requirement: CSRF-1 Global protection of unsafe methods [d]

With CSRF enabled, every POST/PUT/PATCH/DELETE (HTML routes, legacy JSON routes, uploads, and the future API blueprint; no exemptions) MUST be rejected with 400 unless it carries a valid token in header `X-CSRFToken` or form field `csrf_token`. Safe methods (GET/HEAD/OPTIONS) MUST NOT require a token. A token MUST stay valid for the life of the session (no time limit).

#### Scenario: JSON POST without token
- GIVEN `csrf_app`, a logged-in user
- WHEN `POST /riftbound/collection/add` is sent as JSON without a token
- THEN status 400 with `{success:false,error:"CSRF Error",message}`

#### Scenario: JSON POST with header token
- GIVEN the same user and the token from the `csrf-token` meta tag of `GET /riftbound/`
- WHEN the POST carries `X-CSRFToken: <token>`
- THEN the request is processed normally (not 400 for CSRF)

#### Scenario: Multipart upload
- GIVEN an admin and a valid token
- WHEN `POST /riftbound/card/upload_image` is multipart with `X-CSRFToken`
- THEN CSRF passes; without the header it returns 400

#### Scenario: Token does not expire
- GIVEN a token issued at T
- WHEN it is used 2 hours later (time patched) in the same session
- THEN it is still accepted

#### Scenario: Invalid token
- GIVEN `csrf_app`
- WHEN a POST carries `X-CSRFToken: forged`
- THEN status 400

### Requirement: CSRF-2 Error format by client type [d]

A CSRF failure MUST return the JSON error envelope above to JSON/API clients and an HTML 400 page to browser navigations.

#### Scenario: Browser form
- GIVEN `csrf_app`
- WHEN a form POST with `Accept: text/html` and no token is sent to `/riftbound/login`
- THEN status 400 and `Content-Type` is `text/html`

### Requirement: CSRF-3 Forms and fetch calls carry the token [d]

`base.html` MUST expose the token in `<meta name="csrf-token">` and include one global wrapper that adds `X-CSRFToken` to same-origin non-safe `fetch` calls (and never to cross-origin ones). The existing `fetch` call sites MUST NOT need edits. Login and register forms MUST include a hidden `csrf_token` field.

#### Scenario: Every page has the meta tag
- GIVEN `csrf_app` and a logged-in user
- WHEN each template extending `base.html` is rendered (login, register and every authenticated page)
- THEN each output contains `<meta name="csrf-token" content="<non-empty>">` and the wrapper script

#### Scenario: Login with token
- GIVEN the login page HTML
- WHEN the hidden `csrf_token` is posted back with valid credentials
- THEN login succeeds (302 to dashboard); without it the status is 400

#### Scenario: Wrapper behavior [MANUAL]
- GIVEN the app in a browser
- WHEN a same-origin POST via `fetch` is made, then a cross-origin one
- THEN the first has `X-CSRFToken`, the second does not

### Requirement: CSRF-4 Logout is POST-only [d]

`POST /riftbound/logout` (with token) MUST end the session and redirect to login. `GET /riftbound/logout` MUST NOT log out (405). The navigation MUST render logout as a POST form/button.

#### Scenario: POST logout
- GIVEN `csrf_app`, a logged-in user, a valid token
- WHEN `POST /riftbound/logout` is sent
- THEN status 302 to `/riftbound/login` and `GET /riftbound/` then denies access

#### Scenario: GET logout
- GIVEN a logged-in user
- WHEN `GET /riftbound/logout` is sent
- THEN status 405 and the session still works

#### Scenario: Nav markup
- GIVEN a logged-in user
- WHEN a page is rendered
- THEN the logout control is inside a `<form method="post">` with a token and no `<a href=".../logout">` exists

### Requirement: CSRF-5 Operator kill switch [d]

CSRF MAY be disabled with `WTF_CSRF_ENABLED=false` for rollback; it MUST be enabled by default outside testing.

#### Scenario: Default
- GIVEN production env and no override
- WHEN the config is read
- THEN CSRF protection is enabled

#### Scenario: Disabled by env
- GIVEN `WTF_CSRF_ENABLED=false`
- WHEN a POST without token is sent
- THEN no CSRF error is returned
