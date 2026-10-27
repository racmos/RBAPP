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

## Content Security Policy

Every response that serves `index.html` (`/riftbound/app/`, `/riftbound/app/index.html` and
every extension-less path that falls back to it) carries this header, byte for byte:

```
Content-Security-Policy-Report-Only: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; worker-src 'self' blob: data:; connect-src 'self'; frame-ancestors 'self'; base-uri 'self'
```

Nothing else gets a CSP: not `assets/*`, `sw.js`, `manifest.webmanifest`, the icons, the 404
for a missing file or the 503 without a build, and no response carries an enforcing
`Content-Security-Policy`. Jinja pages and the API are untouched.

- **Why report-only.** The browser evaluates the policy and reports what it would block, but blocks
  nothing. We learn what an enforcing policy would break (inline styles, `data:`/`blob:` images,
  the ALTCHA worker) before F12 turns it on, without any risk for users.
- **Reading violations.** Open the app with the browser console visible and use it. Each violation
  is a console line that starts with `[Report Only]` and names the directive and the blocked URL.
  There is no `report-uri` / `report-to` endpoint: collect the lines by hand.
- **Turning it off.** `SPA_CSP=off` in the environment and restart: no CSP header at all.
  `SPA_CSP` accepts `report-only` (the default when unset) and `off`; any other value stops the
  app at start with `ConfigError` ("SPA_CSP must be report-only or off"), in every environment,
  exactly like an invalid true/false switch.
- **Moving to enforcing (planned for F12).** 1) Collect the `[Report Only]` lines from every screen
  (sign-in, register with the captcha, shell, settings, install dialog). 2) Fix the code or adjust
  the policy until the console is clean. 3) Switch the header name to
  `Content-Security-Policy` (keep the report-only header for a new stricter draft if needed),
  with a test that pins the new header, and keep `SPA_CSP=off` as the rollback.

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
missing key fails `npm run typecheck`. Both languages need the same keys, the same
`{{placeholders}}` and every plural form the language needs; the unit that adds strings
adds the parity test. The language is the account preference, then
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
3. Add a test that both catalogs have the entry (the unit adds a test for it).

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
`src/app/routes.tsx` and keep the label in `nav.json`. Every URL of `legacy-routes.json` must
exist in the Flask `url_map`; the unit that adds a legacy link adds a test for it.

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

**How to add an admin page.** Add its entry to `src/admin/adminNav.ts` (`{id, to, labelKey}`),
create the page next to `AdminLayout.tsx`, add the child route under `/admin` in
`src/app/routes.tsx` (inside the shell, guarded by `requireAdmin`), and put its strings in the
`admin` namespace. The nav (`NavLink` at ≥ 1240 px, `Select` below) and the mobile hint come
from `AdminLayout`; the page only renders its `PageHeader` and content.

## Service worker and install

The app is an installable PWA named **Rift Manager**. Nothing about it needs a server change:
Flask already sends `sw.js`, `workbox-*.js` and `manifest.webmanifest` with `no-cache`, and the
manifest as `application/manifest+json`.

| Piece | Value |
|---|---|
| Worker | `/riftbound/app/sw.js` (Workbox `generateSW`, prompt mode), so its **scope is `/riftbound/app/`** and it never controls the Jinja pages or the API |
| Manifest | `id` and `scope` `/riftbound/`, `start_url` `/riftbound/app/`, standalone, `#06222c`. The scope is wider than the worker on purpose: the installed window may still open a legacy page |
| Precache | The app shell only: hashed JS and CSS, `index.html`, latin fonts, the background images, the brand SVGs and the icons. **No runtime caching** of `/riftbound/api/*`, `/riftbound/static/*` or Jinja pages |
| Offline | The shell opens from the precache with an offline banner; F1 is read-only offline |
| Updates | A new worker waits. The app shows a "Nueva versión" toast; "Actualizar" activates it and reloads. It checks every hour and when the window becomes visible |
| Development | The worker is disabled in `npm run dev` |

`npm run check:dist` (also run by CI before the upload) fails the build when the manifest has
another name, id, scope or start URL, when an icon is missing or its PNG size differs from the
declared one, when `index.html` lacks the manifest link, `theme-color`, the title or the apple
tags, when the precache lacks `index.html` or a background image or lists an API URL, when a route
is registered for the API, and when `altcha` ends up in the entry chunk.

### Icons

The icons in `frontend/public/` are generated from the brand mark and **committed**; CI only
checks them. To regenerate after the mark changes:

```bash
cd frontend
npm run brand:trace -- mark-simple        # only if the favicon silhouette changed
npm run icons                             # pwa-{64,192,512}, maskable-icon-512, apple-touch-icon-180, favicon.ico, favicon.svg
```

`npm run icons` uses the presets of `frontend/pwa-assets.config.ts`: the mark on `#06222c` with 10 %
padding for the normal icons, 30 % padding for the maskable one (the mark stays inside the central
80 % circle) and 20 % for the iOS icon. The favicon comes from the simplified mark
(`src/assets/brand/mark-simple.svg`), which keeps the swirl legible at 16 to 48 px.

## Rolling back the PWA

A plain revert of the frontend is **not** a rollback of the PWA: every browser that already
installed the worker keeps serving the old shell from its cache. Use the self-destroying worker
first.

1. Build the frontend with the self-destroying option and deploy that build as usual:
   `cd frontend && VITE_PWA_SELF_DESTROY=true npm run build` (no restart: the files are
   read per request). Check it with `node scripts/check-dist.mjs --self-destroy dist`. This build
   serves a `sw.js` that unregisters itself, deletes every cache and reloads the open windows, and
   the app does not register a worker at all.
2. Wait until clients have fetched it. Browsers re-check `sw.js` on every navigation inside the
   scope, so a day is plenty for devices that are used; a device that is switched off picks it up
   the next time it opens the app.
3. Only then revert the frontend (or deploy the normal build again). Reverting earlier brings the
   old worker back to the devices that have not updated yet.

CI builds the self-destroying worker on every run (outside the uploaded artifact) and checks it, so
this procedure cannot rot unnoticed. Rehearse it on dev at least once (task 6.34).

## PWA device checklist

Run on the dev server over HTTPS (a service worker needs it; `localhost` is the only exception).

- **Installability (desktop Chrome):** DevTools, Application, Manifest shows no installability
  error. Lighthouse 12+ has no "Progressive Web App" category; see "Lighthouse baseline".
- **Android (Chrome):** the menu offers "Install app" (also the "Instalar app" item in "Más"). The
  launched window is called "Rift Manager" and shows the swirl icon on the dark teal background.
- **iPhone (Safari):** "Más" then "Instalar app" shows the three steps; Share, Add to Home Screen.
  Name "Rift Manager" and the mark icon, no black corners.
- **Desktop (Chrome or Edge):** the install button in the address bar and "Instalar app" in the
  topbar; the app opens in its own window.
- **Scope:** DevTools, Application, Service Workers shows the scope `/riftbound/app/`; a Jinja page
  (for example `/riftbound/deck`) is "not controlled".
- **Offline:** with the installed app, airplane mode, open it: the shell opens with the offline
  banner and the preference controls and "Cerrar sesión" are disabled. Back online: the banner goes.
- **Update:** deploy a second build, reopen the installed app, wait for the "Nueva versión" toast,
  accept it and see the new version. Dismissing it must keep a half-filled form.
- **Session:** sign in with "Recordarme", close the installed app completely and reopen it the next
  day: still signed in.

## Lighthouse baseline

Status: **pending (owner)**. Lighthouse is not installed on the server, so F1-g could not record it.
Run Lighthouse (Chrome DevTools or the CLI, desktop and mobile) against the dev server on
`/riftbound/app/login` and, signed out, `/riftbound/app/`, and write the performance,
accessibility and best-practices scores here with the date. Lighthouse 12+ has no PWA category;
installability is covered by the live PWA check.

| Date | Page | Form factor | Performance | Accessibility | Best practices |
| ---- | ---- | ----------- | ----------- | ------------- | -------------- |
| —    | —    | —           | —           | —             | —              |

## Card components

Reusable card UI atoms live in `frontend/src/components/card/`:

- `CardImage` — 352×492 image wrapper with thumb/tile/full source selection, lazy loading and a
  placeholder fallback on error or missing image.
- `CardArtPlaceholder` — procedural placeholder using domain colours, gloss, frame, domain glyph,
  type text, energy/might indicators and the card name.
- `DomainPips` — one pip per domain with an SVG glyph and an accessible list label.
- `RarityDot` — 9 px rarity colour dot; optionally with the translated rarity text.
- `BanBadge` — per-mode ban indicator (`full` uses `Badge tone="danger"`; `compact` uses a warning
  icon + modes).
- `PriceTag` — market/foil amount plus a 7-day or 30-day trend chip with screen-reader text.

These components may import from `@/lib`, `@/i18n`, `@/components/ui` and **type-only** from
`@/api`. They never import `auth`, `prefs`, `pwa`, `shell`, `account`, `app` or other feature
folders. The boundary is enforced by `frontend/eslint.config.js` and tested in
`src/test/eslint-boundaries.test.ts`.

## Catalog

Page-level catalog code lives in `frontend/src/catalog/` (one folder per screen, like `account/`):

- `CatalogPage` — the `/cards` layout: toolbar (search, sort, direction, view, page size from
  1240 px), filters (`CatalogFilters`: sheet below 1240, sticky collapsible sidebar at
  ≥ 1240 with `aria-expanded` groups remembered in `rb_cards_facets`), active chips, grid/list
  results, pagination and states. URL parameters mirror the API names (`params.ts`:
  parse/serialize/round-trip; text search debounced with `replace`, other changes push; scroll
  restored per search string). The detail opens as a modal over the catalog at ≥ 860 px and as
  a page below; `navRegistry` entry `cards` is `spa` (the classic Jinja page stays linked as
  "Versión clásica").
- `CatalogTable` — the table view (860 px and up, optional): 13 columns below 1240 (scroll
  wrapper), 16 with tags/foil/30 d at ≥ 1240 (sticky header); sortable headers with `aria-sort`
  (price and trends start descending). Numbers use `tabular-nums`.
- `CatalogPreview` — the ≥ 1600 px third column: art, prices + foil, 30-day `Sparkline`
  (`useCardPrices(…, '30d')`), owned and a link opening the modal; tiles become `aria-pressed`
  buttons selecting via the `selected` URL param (default: first result); empty results show
  `preview.empty`.
- `CardDetailRoute` — the `/cards/:setId/:cardId` route: reads the outlet context (`page` or
  `modal` with `siblings` + `onClose`), handles loading/404/error states and the modal presentation
  (prev/next through siblings, Esc/backdrop/× close).
- `CardDetailView` — the detail content in S7 section order (image, header, bans, prices, chart
  slot, text, attributes, copies, printings, related, decks); one column below 860 px, two from
  860 px, three from 1240 px (widths only from `src/lib/breakpoints.ts`).
- `queries.ts` — `useCardDetail(setId, cardId)` (key `['cards', 'detail', …]`, 5-minute stale,
  no retry on 404); `useGameMeta()` (1-hour stale) and `useCardList(params)` (`keepPreviousData`,
  5-minute stale) for the catalog. List endpoints keep `meta` via `requestWithMeta` (the F2-c
  envelope carries `meta` next to `data`).

Device storage keys: `rb_cards_view` (`grid` | `list` | `table`), `rb_cards_facets` (open filter
  groups), `rb_price_range` (chart range), `rb_cards_scroll` (scroll per search string) — all
  through `lib/storage.ts`, invalid values fall back to defaults.
- `context.ts` — the outlet context type (`presentation`, `siblings`, `onClose`).

`catalog` sits in the `shell`/`account` boundary group (it may import everything below, never
`app`). Links back to Jinja (collection, deck view) are plain `<a>` anchors via
`legacyHref`, not router navigation. The detail data comes from `getCard` (`GET
/riftbound/api/v1/cards/<set>/<id>`, F2-d); the MSW handler serves the `cardDetail` fixture.

## Charts

Charts are hand-made SVG components in `frontend/src/components/charts/`. There is no chart
library dependency.

- `PriceChart` renders a card's daily Cardmarket history: measured container width via
  `ResizeObserver`, `niceTicks` grid, date axis, an area gradient under the market line,
  a dashed foil line, keyboard navigation (arrow keys, Home/End, Esc), a crosshair tooltip
  and a screen-reader summary (`cards:chart.summary`). A "Show as table" button reveals a
  table alternative with the newest rows first.
- `Sparkline` is a compact 120×34 SVG line for small spaces; it turns green when the last
  non-null value is greater than or equal to the first, red otherwise.
- `src/lib/scale.ts` provides `linearScale` (with `.invert`) and `niceTicks` for the chart
  axes.

`CardPriceHistory` wires `PriceChart` into the card detail slot (`data-slot="price-chart"`),
adds a range selector (`30d`, `90d`, `1y`, `all`) and persists the last choice in
`localStorage` (`rb_price_range`).

## Build output

The service worker precaches every URL exactly once: the Workbox glob lists the files in `dist`
and the plugin adds `manifest.webmanifest` (no `includeAssets`, `includeManifestIcons: false`).
`check:dist` fails when a precache URL appears twice (F1 unit g: 40 entries/33 unique before,
33/33 after).

The production build writes `dist/.vite/manifest.json` (`build.manifest`). It lists the
chunks and what imports what; `altcha` must appear only behind the dynamic import of
`src/auth/RegisterPage.tsx`, never in the entry chunk of `/login`.
