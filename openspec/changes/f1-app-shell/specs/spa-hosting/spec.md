# Delta for spa-hosting

> Tags: `[a]`..`[g]` = delivery unit of change f1-app-shell (all requirements here are unit `[b]` unless stated). `[MANUAL]` = deploy/ops check. Untagged scenarios are pytest-testable with a temporary `dist/` directory (no Node in the Python lane). The SPA is served by Flask at `/riftbound/app/`; Jinja routes, the landing `/` and `/riftbound/api/v1` are unaffected.

## ADDED Requirements

### Requirement: HOST-1 Mount point and trailing-slash redirect [b]

The app MUST serve the built SPA from the directory configured by `FRONTEND_DIST` (default `<repo>/frontend/dist`) under the prefix `/riftbound/app/`. `GET /riftbound/app` MUST redirect to `/riftbound/app/`. The routes MUST be public (no login required): the SPA hosts the login screen itself. The prefix MUST NOT shadow any existing Jinja or API route.

#### Scenario: Redirect without slash
- GIVEN a dist directory containing `index.html`
- WHEN `GET /riftbound/app` is requested
- THEN the response is a redirect whose `Location` ends with `/riftbound/app/`

#### Scenario: Entry document
- GIVEN the same dist and no session
- WHEN `GET /riftbound/app/` is requested
- THEN status 200, `Content-Type` is `text/html`, and the body is the dist `index.html`

#### Scenario: Existing routes unaffected
- GIVEN `spa_bp` registered
- WHEN `GET /riftbound/login`, `GET /riftbound/api/v1/health` and `GET /riftbound/static/<existing file>` are requested
- THEN they respond exactly as before the change

### Requirement: HOST-2 Cache rules [b]

Files under `/riftbound/app/assets/` MUST be sent with `Cache-Control: public, max-age=31536000, immutable`. `index.html`, `sw.js`, `workbox-*.js` and `manifest.webmanifest` MUST be sent with `Cache-Control: no-cache` and MUST support conditional requests (ETag and `If-None-Match` returning 304). Icons and other non-hashed files outside `assets/` MUST NOT be `immutable`.

#### Scenario: Hashed asset
- GIVEN `dist/assets/index-abc123.js`
- WHEN it is requested
- THEN 200 and `Cache-Control` contains `immutable` and `max-age=31536000`

#### Scenario: Shell files revalidate
- GIVEN `index.html`, `sw.js` and `manifest.webmanifest` in dist
- WHEN each is requested
- THEN `Cache-Control` contains `no-cache` and none contains `immutable`

#### Scenario: Conditional request
- GIVEN a previous `GET /riftbound/app/sw.js` returned an ETag
- WHEN the same request is repeated with `If-None-Match: <etag>`
- THEN status 304

### Requirement: HOST-3 Extension-aware catch-all [b]

A request under `/riftbound/app/` whose last path segment has NO file extension MUST return `index.html` with status 200 (client-side routes). A request whose last segment has a file extension and does not match a file in dist MUST return 404 and MUST NOT return `index.html` (a missing `.js`, `.css`, `.woff2` or `.map` must fail loudly). Paths that resolve outside dist (traversal, encoded or not) MUST return 404.

#### Scenario: Deep link
- GIVEN a dist with `index.html`
- WHEN `GET /riftbound/app/account/interface` is requested
- THEN 200 with the `index.html` body and `Cache-Control: no-cache`

#### Scenario: Missing script
- GIVEN no file `assets/missing.js`
- WHEN `GET /riftbound/app/assets/missing.js` is requested
- THEN 404 and the body is not the `index.html` content

#### Scenario: Traversal
- GIVEN a file `secret.txt` next to (not inside) dist
- WHEN `GET /riftbound/app/..%2Fsecret.txt` and `GET /riftbound/app/../secret.txt` are requested
- THEN neither returns the file content (404)

### Requirement: HOST-4 Manifest mimetype [b]

`GET /riftbound/app/manifest.webmanifest` MUST be served with `Content-Type: application/manifest+json`.

#### Scenario: Manifest content type
- GIVEN a dist containing `manifest.webmanifest`
- WHEN it is requested
- THEN the `Content-Type` header starts with `application/manifest+json`

### Requirement: HOST-5 Missing build returns 503 [b]

When `FRONTEND_DIST` does not exist or has no `index.html`, every request under `/riftbound/app/` (including `/riftbound/app` after redirect) MUST return 503 with a short human-readable message saying the frontend build is missing and how to build it. This MUST NOT affect Jinja routes, the landing or the API, and the application MUST start normally.

#### Scenario: No dist
- GIVEN `FRONTEND_DIST` points to a non-existent directory
- WHEN `GET /riftbound/app/` and `GET /riftbound/app/assets/x.js` are requested
- THEN both return 503 with a non-empty message

#### Scenario: App still healthy
- GIVEN the same configuration
- WHEN `GET /riftbound/api/v1/health` is requested
- THEN 200 `status:"ok"`

### Requirement: HOST-6 No secrets in the shell document [b]

`index.html` MUST be static and MUST NOT embed a CSRF token, session data, user data or secrets; the CSRF token MUST only come from `GET /riftbound/api/v1/auth/session`. The response of `/riftbound/app/` MUST NOT set cookies.

#### Scenario: No Set-Cookie
- GIVEN a dist and an anonymous client
- WHEN `GET /riftbound/app/` is requested
- THEN the response has no `Set-Cookie` header

### Requirement: HOST-7 Configuration and docs [b]

`FRONTEND_DIST` MUST be documented in `.env.example` and described in `README.md` (existing docs test). Docs MUST describe the build (`npm ci && npm run build`) and deploy steps, and state that Nginx needs no change in F1. `docs/nginx_config` MUST keep exactly two `proxy_pass` lines (`/` and `/riftbound/`); any optional static `location` for `/riftbound/app/assets/` MUST NOT use `proxy_pass`.

#### Scenario: Docs tests
- GIVEN `.env.example` with `FRONTEND_DIST`
- WHEN `tests/test_docs.py` and `tests/test_nginx_config_doc.py` run
- THEN they pass (variable described in README, proxy_pass count unchanged)

#### Scenario: Smoke test after deploy [MANUAL]
- GIVEN the deployed build behind Nginx over HTTPS
- WHEN `/riftbound/app/`, a deep link and the F0 pending manual checks are exercised
- THEN the SPA loads, the deep link reloads correctly and the F0 checks pass
