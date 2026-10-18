# Delta for session-security

> Tags: `[a]`..`[e]` = delivery unit. `[MANUAL]` = manual/ops check. Untagged scenarios are pytest-testable (HTTPS simulated with `base_url='https://localhost'`).

## ADDED Requirements

### Requirement: SESS-1 Session and remember cookie flags [d]

The session cookie and the remember cookie MUST be `HttpOnly` and `SameSite=Lax` (never `Strict`: future OAuth callbacks are cross-site top-level GETs). In the production environment `Secure` MUST be on. Outside production `Secure` MUST be off unless overridden by env (`SESSION_COOKIE_SECURE`, `REMEMBER_COOKIE_SECURE`).

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
- THEN `HTTPONLY=True`, `SAMESITE='Lax'`, `SECURE=True`

#### Scenario: HTTPS behind Nginx [MANUAL]
- GIVEN the deployed site over HTTPS through Nginx
- WHEN logging in from a browser
- THEN the cookie is stored with Secure/HttpOnly/Lax and the app works

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
