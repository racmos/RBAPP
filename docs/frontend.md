# Frontend (new app) - build, hosting and deploy

The new app is a React single-page app built from `frontend/` (Vite). Flask serves the
build itself at `/riftbound/app/` (blueprint `spa_bp`, `app/routes/spa.py`). The Jinja
pages, the landing page and the JSON API are not affected.

## Build

Node 24 (see `.nvmrc`) and npm are needed on the machine that builds, never to run the
Python tests.

```bash
cd frontend
npm ci
npm run build        # writes frontend/dist/
```

## FRONTEND_DIST

`FRONTEND_DIST` is the directory Flask serves (default `<project>/frontend/dist`; blank
counts as unset). It is read on every request, so a new build is picked up without a
restart. Set it in the environment file only when the build lives elsewhere, for example
`FRONTEND_DIST=/srv/riftbound/frontend-dist`.

## What Flask does with it

| Request | Answer |
|---|---|
| `/riftbound/app` | redirect to `/riftbound/app/` |
| `/riftbound/app/` | `index.html`, `Cache-Control: no-cache` |
| `/riftbound/app/assets/<hashed file>` | the file, `public, max-age=31536000, immutable` |
| `/riftbound/app/sw.js`, `workbox-*.js`, `manifest.webmanifest` | the file, `no-cache`, ETag (304 on revalidation) |
| `/riftbound/app/account/interface` (no file extension) | `index.html` (a client-side route) |
| `/riftbound/app/assets/missing.js` (extension, no such file) | 404, never `index.html` |
| any path when `FRONTEND_DIST` has no `index.html` | 503 with the build command |

Every response carries `X-Content-Type-Options: nosniff` and
`Referrer-Policy: strict-origin-when-cross-origin` (the CSRF Referer check needs that
policy). No response sets a cookie: the CSRF token comes from
`GET /riftbound/api/v1/auth/session`, never from the HTML. `manifest.webmanifest` is sent
as `application/manifest+json`.

Errors under `/riftbound/app/` (404 for a missing file, 503 without a build) are JSON for
clients that ask for it (`Accept: application/json` or `*/*`, which is what `fetch`
sends) and a minimal inline HTML page otherwise. They never use the Jinja error pages.

## Deploy

Pick one:

1. **Build on the server** (Node 24 installed there): update the working tree, then
   `cd frontend && npm ci && npm run build`.
2. **Unpack the CI artifact**: the `frontend` job of GitHub Actions uploads the build as
   `frontend-dist` (kept 7 days). Download it and unpack it into `FRONTEND_DIST`.

No service restart is needed for the frontend alone. Restart is still needed when
Python code or migrations changed (see [migrations.md](migrations.md)).

The build empties its output directory first, so `/riftbound/app/` answers 503 for the
few seconds a rebuild takes. To avoid that, build into a temporary directory and swap it
in with a `mv` (atomic rename). This is optional in F1 and becomes the standard
procedure in the deploy-tooling phase (F12).

## Nginx

Nginx needs no change in F1: `/riftbound/` already proxies to Flask, so
`/riftbound/app/` is covered. Optional hardening notes live in [nginx_config](nginx_config).

## Rollout order and smoke checklist

1. Merge the PR and update the working tree.
2. `cd frontend && npm ci && npm run build` (once the frontend toolchain unit is merged).
3. Restart the service (needed for the Python change that registers `spa_bp`).
4. Smoke test over HTTPS:
   - `/riftbound/app/` loads;
   - a deep link such as `/riftbound/app/account/interface` reloads correctly;
   - `/riftbound/app` redirects to `/riftbound/app/`;
   - `/riftbound/app/assets/missing.js` is a 404, not the app shell;
   - the Jinja pages, the landing page and `/riftbound/api/v1/health` still work;
   - the pending manual checks of the foundation phase (F0) pass.
