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

| Request                                                        | Answer                                           |
| -------------------------------------------------------------- | ------------------------------------------------ |
| `/riftbound/app`                                               | redirect to `/riftbound/app/`                    |
| `/riftbound/app/`                                              | `index.html`, `Cache-Control: no-cache`          |
| `/riftbound/app/assets/<hashed file>`                          | the file, `public, max-age=31536000, immutable`  |
| `/riftbound/app/sw.js`, `workbox-*.js`, `manifest.webmanifest` | the file, `no-cache`, ETag (304 on revalidation) |
| `/riftbound/app/account/interface` (no file extension)         | `index.html` (a client-side route)               |
| `/riftbound/app/assets/missing.js` (extension, no such file)   | 404, never `index.html`                          |
| any path when `FRONTEND_DIST` has no `index.html`              | 503 with the build command                       |

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

## Sign-in, sessions and CSRF (what the app does)

The app and the Jinja pages share one session cookie, so signing in or out in either
applies to both.

- **Boot.** The app calls `GET /riftbound/api/v1/auth/session` before rendering any
  guarded route and shows a loading state meanwhile, so a signed-in user never sees the
  login form. The answer (`authenticated`, `user`, `prefs`) is the TanStack Query entry
  `['session']`; it is refetched whenever the window regains focus, so a logout done in a
  Jinja page or another tab is noticed.
- **CSRF token.** It comes from `/auth/session`, is held in a module variable only and is
  never written to `localStorage`, `sessionStorage` or a cookie. Every POST, PATCH, PUT
  and DELETE sends it as `X-CSRFToken`. If the server answers `400` with
  `code: "csrf_invalid"`, the client refetches the session and repeats the request once;
  a second failure is shown as an error.
- **Login.** `POST /auth/login` with `{username, password, remember}` ("Remember me" is
  checked by default; the server then sets a 30-day `remember_token`). On success the app
  refetches the session and goes to `next` or home. `next` is an absolute path such as
  `/riftbound/app/account/interface`; `safeNext` accepts only paths under `/riftbound/`
  (paths under `/riftbound/app/` stay in the router, others are a full page load) and sends
  anything else home.
- **Expired session.** A `401` from any call other than login or logout clears the query
  cache, the "was signed in" hint and the CSRF token, and goes to
  `/login?next=<where you were>`.
- **Rate limits.** A `429` shows a countdown taken from `Retry-After` (or
  `params.retry_after`), keeps the submit button disabled until it ends and announces the
  start and the end politely.
- **Register.** The page loads `/meta/config` and `/auth/captcha`. With provider `none`, or a
  null challenge, there is no widget and no `altcha` field. Otherwise the ALTCHA widget
  (npm `altcha` 2.3.0, the same version as the Python pin in `requirements.txt`; a pytest
  contract checks it) is loaded only on this route and the solved payload is sent as
  `altcha`. A payload is single use and is consumed before the duplicate check, so after
  any failed attempt the page fetches a new challenge and remounts the widget.
- **Logout.** `POST /auth/logout`. A `200` and a `401` (already signed out) both clear the
  cache and the hint, keep the current language in `rb_lang` and go to `/login`; any other
  failure keeps the user signed in and shows an error toast.

## Languages and error codes

Text lives in `frontend/src/i18n/locales/{es,en}/{common,nav,auth,errors,prefs}.json`
and is bundled (no translation requests at run time). Spanish is the typed source: a
missing key fails `npm run typecheck`. `src/i18n/parity.test.ts` fails when a key exists
in one language only, when the `{{placeholders}}` of a key differ, or when a plural
group lacks a form the language needs. The language is the account preference, then
`rb_lang` in `localStorage`, then the first supported entry of `navigator.languages`,
then Spanish.

Server errors are translated by `code` (`translateError` in `src/i18n/translateError.ts`):
`errors:code.<code>` with the `params` interpolated, then the API `message`, then
`errors:status.<http status>`, then `errors:unknown`. Field errors in `details[]` use
`errors:validation.<field>.<code>`, then `errors:validation.<code>`, then the detail
`message`.

### How to add an error code

1. Add the value to `ErrorCode` in `app/api/error_codes.py` (a field-level code goes to
   `DetailCode`) and return it from the endpoint (`fail(..., code=ErrorCode.X)`).
2. Add `code.<value>` to `frontend/src/i18n/locales/es/errors.json` and
   `.../en/errors.json` (for a field-level code, `validation.<value>`).
3. Run `pytest tests/test_frontend_contracts.py` (it fails until both catalogs have the
   entry) and `npx vitest run src/i18n` in `frontend/`.

An older server may answer without codes: `deriveCode` in `src/api/errors.ts` maps the
F0 bodies (401 login, 409 duplicates, 429) so the screens still work.

## App shell, navigation and preferences (unit e)

**Shell anatomy.** Signed-in routes render inside `src/shell/AppShell.tsx`: a skip link
(first tab stop), the sticky `Topbar` (64 px, 56 px below `sm`), one `main`
(content capped at `--maxw`, `--maxw-wide` from `2xl`) and, below 860 px, the `BottomNav`
(Inicio, Cartas, Colección, Mazos and "Más", which opens a native `<dialog>` sheet).
The top or the bottom navigation is *mounted* by `useMediaQuery(up('md'))`, not hidden, and
`main` carries `data-botnav` (bottom padding) only while the bottom navigation exists.
Pages sit under a pathless route with `ShellError` as its `errorElement`, so a page that
throws keeps the topbar; its retry resets the failed queries and renders the page again.
Unknown paths render `NotFound` inside the shell.

**Navigation registry.** `src/shell/navRegistry.ts` is the one list behind the topbar, the
bottom navigation, the sheet and the home hub. Every entry has a `status`:
`spa` (a router link, `to` is a path under the basename), `legacy` (a plain `<a href>` to a
Jinja page, key in `legacy-routes.json`) or `planned` (never rendered). `placements` says
where it appears (`top`, `bottom`, `hub`, `more`); `adminOnly` hides it from non-admins (UX
only, the server still enforces). **To port a module, flip its entry**: change
`status: 'legacy', legacy: 'cards'` to `status: 'spa', to: '/cards'`, add the route in
`src/app/routes.tsx` and keep the label in `nav.json`. `legacy-routes.json` is checked by
`tests/test_frontend_contracts.py::TestLegacyRoutes` against the Flask `url_map`.

**Preferences.** The account stores five values (`lang`, `density`, `accent`,
`bg_intensity`, `collection_view`; `null` is Auto). `src/prefs/`:

- `bootstrap.ts` runs before React renders: it reads the `rb_prefs_v1` mirror (corrupt or
  out-of-domain values are dropped), resolves Auto for the viewport and writes
  `data-accent`, `data-density` (absent for regular), `lang` and the background variables to
  `<html>`. Auto means compact density and grid view below 860 px, regular and table above;
  accent orange; background 100.
- `PrefsProvider` keeps `<html>` in step with the session query, re-resolves Auto when the
  viewport crosses 860 px, copies the server prefs into the mirror and lets the account
  language drive i18next. `rb_lang` stays the device choice (written by the toggle and on
  logout).
- `sync.ts` saves optimistically: the change is written to the session cache at once, one
  PATCH is in flight at a time, each request carries only the changed fields (`null` for
  Auto), the slider waits 400 ms (and flushes on pointerup, blur and pagehide), and a failure
  restores the previous value with an error toast and a "Reintentar" action.
- `AccountLanguageToggle` is the ES/EN toggle of the login screen, the topbar and the sheet:
  it always writes `rb_lang`; when signed in it also saves `lang` to the account.

`/account/interface` (`src/account/InterfacePage.tsx`) edits all five; at 1240 px and above a
live preview sits beside the controls.

**How to add a catalog namespace.** Create `locales/es/<ns>.json` and `locales/en/<ns>.json`,
import both in `src/i18n/resources.ts`, add the name to `NAMESPACES` and to both `resources`
objects, and call `useTranslation('<ns>')`. Spanish types the keys; the parity test covers
English.

**Development.** `/riftbound/app/_kitchen` shows every primitive; the route exists only in
`npm run dev` (the production table has no `/_kitchen`).

## Build output

The production build writes `dist/.vite/manifest.json` (`build.manifest`). It lists the
chunks and what imports what; `altcha` must appear only behind the dynamic import of
`src/auth/RegisterPage.tsx`, never in the entry chunk of `/login`.
