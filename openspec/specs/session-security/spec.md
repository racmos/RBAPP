# session-security Specification

Source: change f0-foundation (archived 2026-10-19); updated by change f1-app-shell (archived 2026-10-22)

> Tags: `[a]`..`[e]` = delivery unit of change f0-foundation. `[MANUAL]` = manual/ops check. Untagged scenarios are pytest-testable (HTTPS simulated with `base_url='https://localhost'`).
>
> F1 Tags: unit `[c]` of change f1-app-shell. `[MANUAL]` = manual/ops check. Untagged scenarios are pytest-testable (HTTPS simulated with `base_url='https://localhost'`). The Jinja form login is unchanged (no "remember me" option there; out of scope). Reason: an installed PWA has its own cookie jar and loses a browser-session cookie every time it is closed.

## Requirements

### Requirement: SESS-1 Session and remember cookie flags [d]

The session cookie and the remember cookie MUST be `HttpOnly` and `SameSite=Lax` (never `Strict`: future OAuth callbacks are cross-site top-level GETs). In the production environment `Secure` MUST be on. Outside production `Secure` MUST be off unless overridden by env (`SESSION_COOKIE_SECURE`, `REMEMBER_COOKIE_SECURE`). The remember cookie MUST actually be issued when `POST /api/v1/auth/login` is called with `remember: true` and MUST NOT be issued otherwise; its lifetime (`REMEMBER_COOKIE_DURATION`) MUST be 30 days. Logging out MUST clear the remember cookie, and a client holding only a valid remember cookie MUST be treated as authenticated.

#### Scenario: Production login cookie
- GIVEN a production-config app and a user
- WHEN they log in over `https://localhost`
- THEN the `Set-Cookie` header for `session` contains `HttpOnly`, `SameSite=Lax` and `Secure`

#### Scenario: Development cookie
- GIVEN a development or testing config app
- WHEN the user logs in over http
- THEN `Set-Cookie` has `HttpOnly` and `SameSite=Lax` and no `Secure`

#### Scenario: Remember cookie config
- GIVEN a production-config app
- WHEN `REMEMBER_COOKIE_*` settings are read
- THEN `HTTPONLY=True`, `SAMESITE='Lax'`, `SECURE=True` and `DURATION` equals 30 days

#### Scenario: HTTPS behind Nginx [MANUAL]
- GIVEN the deployed site over HTTPS through Nginx
- WHEN logging in from a browser
- THEN the cookie is stored with Secure/HttpOnly/Lax and the app works

#### Scenario: Remember cookie issued with 30-day expiry
- GIVEN a user and a production-config app
- WHEN `POST /api/v1/auth/login` is sent over `https://localhost` with `remember:true`
- THEN a `remember_token` cookie is set with `HttpOnly`, `SameSite=Lax`, `Secure` and an expiry (`Max-Age`/`Expires`) within one minute of 30 days from now

#### Scenario: No remember cookie when not requested
- GIVEN a user
- WHEN login is sent with `remember:false` and again without the field
- THEN no `remember_token` cookie is set

#### Scenario: Session restored from remember cookie
- GIVEN a client that logged in with `remember:true` and then drops its `session` cookie but keeps `remember_token`
- WHEN `GET /api/v1/auth/session` is called
- THEN `authenticated` is `true`

#### Scenario: Logout clears remember
- GIVEN a client with both cookies
- WHEN `POST /api/v1/auth/logout` is called
- THEN the response expires the `remember_token` cookie and a later `/auth/session` is anonymous

#### Scenario: Blocked user with remember cookie
- GIVEN a client with a valid remember cookie whose user is then blocked
- WHEN `GET /api/v1/auth/session` is called
- THEN `authenticated` is `false`

### Requirement: SESS-2 Debug off by default; local bind [a]

The local entry point `run.py` MUST start with debug OFF and bind `127.0.0.1` by default. Debug and a wider bind MAY be enabled only through explicit env settings. The Werkzeug debugger MUST NOT be reachable by default.

#### Scenario: Defaults
- GIVEN no debug-related env vars
- WHEN `run.py` is executed as `__main__` with `Flask.run` patched
- THEN `run` is called with `debug=False` and `host='127.0.0.1'`

#### Scenario: Explicit opt-in
- GIVEN the documented debug env var set to true
- WHEN `run.py` is executed as `__main__`
- THEN `run` is called with `debug=True`

### Requirement: SESS-3 Key rotation invalidates sessions [a]

A session cookie signed with a different `SECRET_KEY` MUST be treated as anonymous.

#### Scenario: Rotated key
- GIVEN a session cookie from an app with key A
- WHEN presented to an app with key B
- THEN `GET /riftbound/` gives anonymous denial
