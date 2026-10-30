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

**Products admin (F14-d).** `/admin/products` (`src/admin/ProductsAdminPage.tsx`, nav entry
`products`) lists `GET /admin/products` with its filters in the URL (`q`, repeated `kind`,
`hidden` and `listed` = `yes` | `no`, `no_set`, `no_image`, `per_page`, `page`); the previous
page stays on screen while the next one loads. ≥ 860 px a table (40 px image or the `gift`
placeholder, name, kind, set, price, listed, hidden, updated) with a side drawer editor, a
persistent panel at ≥ 1600 px; below 860 px cards and a bottom sheet. `ProductEditor` sends
only what changed to `PATCH /admin/products/<id>`: the "automatic" kind is `kind: null`, the
"automatic" set is `set_id: "auto"`, "no set" is `set_id: null`; a locked kind or set shows
the "Set by hand" badge. The image goes to `POST .../image` as multipart `file`. Kind labels
live in the `products` namespace (`products:kind.<kind>`, F14-e adds the rest).

**Sets admin.** `/admin/sets` (`src/admin/SetsPage.tsx`) filters and sorts the
`GET /admin/sets` list in the browser, with the state in the URL: `q` (code or name
substring), `sort` = `id|name|releaseDate|cards` (default `id`) and `dir` = `asc|desc`
(default `asc`). The filters section holds the search, the sort `Select` and the direction
`Select`; the table headers are plain text with `aria-sort` on the sorted column. "Nuevo set"
opens the editor in the side drawer (bottom sheet below 960 px) and in the persistent panel at
≥ 1600 px.

**Riot changes.** `/admin/riot/changes` (`src/admin/ChangesPage.tsx`) wraps long values (URLs,
abilities) so the columns fit; the table sits in a labelled region, `TableScroll fit`, so the page
is the only scroll (no box inside the page) and the header sticks below the topbar. With rows
selected the bulk bar sticks to the bottom of the viewport (opaque, above the header). "Por
página" picks 50 / 100 / 200 rows (`per_page` in the URL, 50 is not written; a change goes back
to page 1).

## Products (F14-e)

`frontend/src/products/` is the products section (nav entry `products`, `spa`, icon `gift`, after
`collection`; top, hub and "Más"). The mobile layout is the target; F14-f adds the desktop one.

- `params.ts` — URL ⇄ `GET /products` params (`q`, repeated `kind` and `set`, `sort` =
  `name|price|change_7d|change_30d`, `dir`, `page`, `per_page` 24-96, default 48; defaults are never
  written, invalid values are dropped, any change but `page` returns to page 1) plus `tab=mine|catalog`,
  always written first. `queries.ts` — `useProductList` (`['products', 'list', <query>]`), `useProduct`,
  `useProductPrices(id, range)`, `useMyProducts` (`['me-products']`) and `useAddProduct`,
  `usePatchProduct`, `useDeleteProduct`, which refresh `['me-products']` and `['products']`.
- `ProductsPage` (`/products`) — a `role="tablist"` with "Mis productos" and "Catálogo" (arrow keys,
  Home/End). Without `?tab=` it opens on the user's products when `GET /me/products` has lines, else on
  the catalog. "Mis productos" (`MineTab`): the total band (value, lines, unpriced count) with the hint
  that it is not part of the collection value, and one row per owned line (image or placeholder, name,
  kind, unit price, line value, quantity stepper → `PATCH /me/products/<id>`); the row opens
  `ProductLineSheet` (quantity, purchase price, note, delete behind a `ConfirmDialog` with "Deshacer"
  for 8 s, which posts the deleted line back). "Catálogo" (`CatalogTab`): search, kind chips with the
  facet counts, set and sort `Select`s, direction, `ProductTile`s (price with the 7-day change, `×N`
  owned badge) and `Pagination`.
- `ProductDetail` (`/products/:id`, a page) — image, kind, set, price and 7/30-day changes, the price
  history (`PriceChart` with 30 d / 90 d / 1 año / Todo; `asChartPoints` maps `{date, value}` to the
  card chart's `market` series), the owned lines and the "Añadir" form (`POST /me/products`; the toast
  says whether it merged). An unknown id renders the shell's `NotFound`.
- `ProductThumb` — the image, or the `gift` icon with the kind label (`data-slot="product-placeholder"`).
- States: skeletons, empty mine (button to the catalog tab), empty catalog (clear filters), unpriced
  text, error with retry, offline (cached data stays, edits are disabled with
  `common:offline.editDisabled`). The quantity stepper and the price field are the collection's
  `Stepper` and `MoneyField`. A `ConfirmDialog` is rendered next to the sheet, not inside it: the close
  event of a nested `<dialog>` would close the sheet as well.
- ESLint: `products` may import everything below `app`, like `collection`.

Desktop (F14-f). `ProductsPage` picks `ProductsMobile` (the F14-e layout above) below 1240 px
(`up('xl')`) and `ProductsDesktop` from there; both read `useProductsScreen` (tab, URL params,
`setParams`, owned lines) and render `ProductTabs`. `params.ts` also carries `owned=owned` ("solo los
míos", counted as a filter and cleared with the others). `ProductsDesktop`: a sticky 240 px rail
(`ProductsRail`, `aside` "Filtros": search, kind checkboxes with facet counts, `SetSelect`, the
`Switch` "Solo los míos"; any rail change shows the catalog tab) and, under the tabs, `CatalogTable`
(caption "Productos de Cardmarket"; image, name, kind, set, price, 7 d and 30 d signed in the text,
`×N` owned, "Ya no aparece" badge when `listed` is false; name, price, 7 d and 30 d headers sort with
`aria-sort`, a new column starts descending except the name; "Por página" 48/96) or `MineTable`
(caption "Tus productos"; `MineSummary` band, quantity `Stepper`, purchase price and note inline,
labelled `<column>: <product>` and saved with `useProductLineSaver`; the name opens
`ProductLineSheet`). From 1600 px (`up('2xl')`) a row click selects the product for the sticky 380 px
`ProductPanel` (`aside` "Detalle del producto": image, price facts, 90-day `ProductHistory`,
`ProductLines`, `AddProductForm`, shared with `ProductDetail` through `ProductSections.tsx`); below it a
row click opens `/products/:id`. Clicks on inline editors never reach the row.

## Shared primitives: tables, dropdowns, checkboxes

- **Tables.** Every data table sits in `components/ui/TableScroll`: the box scrolls both ways,
  capped at the viewport below the topbar, and its `thead th` stick to the top of the box on the
  opaque `--table-head` token. A sticky header inside an `overflow` box sticks to that box, never
  to the page, so a page offset such as `top: 64px` pushed the header over the first rows.
  `src/test/primitives-guard.test.ts` fails when a `<table>` is not wrapped or a sticky `th` has a
  `top` other than `0` (the import preview and the chart fallback table keep their own box).
  `<TableScroll fit>` is for a table whose columns wrap to the width (the Riot changes): no
  vertical cap and `overflow-x: clip`, which makes no scroll container, so the page scrolls and
  the `thead` (not the `th`) sticks at `calc(64px + var(--safe-top))`, below the topbar. Anything
  wider than the box is clipped, not scrolled.
- **Dropdowns.** Use `components/ui/Select` only; the guard test fails on a raw `<select>`. It
  drops the platform look (`appearance: none`, its own arrow), uses an opaque dark field with dark
  options and 16 px text below 860 px (iOS zooms into smaller fields).
- **Checkboxes.** `components/ui/Checkbox` is a toggle button that lights up when checked (accent
  fill, dark ink, glow, check mark as the non-colour cue). It is still a native checkbox, stretched
  over the button and transparent, so `getByRole('checkbox', {name})`, Space and the focus ring
  behave as before. Same props plus `hideLabel` (the label stays the accessible name; table
  selection boxes) and `indeterminate`. The guard test fails on a raw `type="checkbox"`.

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
- `CardCombobox` — reusable card picker (`import { CardCombobox } from '@/catalog'`). ARIA 1.2
  editable combobox with list autocomplete: it searches `GET /cards` as you type (2 or more
  characters, 250 ms debounce, `sort=name`, `per_page=20`, the previous request aborted, results
  cached by `useCardSearch`). Props: `label` (+ `hideLabel`), `onSelect(card)`, `filters` (any
  `GET /cards` param, e.g. `{ base_only: true, exclude_supertype: ['Token'] }` for F3/F5 pickers),
  `placeholder`, `autoFocus`, `clearOnSelect` (default `true`), `id`, `className`, `inputRef`.
  The search also matches ability text and tags, so the options are ranked by name: exact name,
  then names that start with the query, then names that contain it, then the rest (case and accents
  ignored, API order kept inside each group); Enter takes the first, so a text-only match never wins
  over a name match. The popup has an opaque background (`--bg-0` under the panel tone) and stacks
  above what follows it (`--z-popover`).
  Keys: ↓/↑ (wrapping), Home/End, Enter, Esc (closes, a second Esc clears), Tab. Loading, empty,
  error and offline states (no request while offline unless cached) are announced through a polite
  live region together with the result count and the active card. The popup stays inside the
  component, so it also works inside a `Modal` (`--z-popover`). The topbar uses it at ≥ 1240 px as
  the global "Buscar cartas" box; `/` focuses it from anywhere except an editable field, and
  choosing a card navigates to `/cards/<set>/<id>` with state `{ fromCatalog: true }` (a modal
  over the catalog at ≥ 860 px).
- `useSearchNavigation()` — `{ current, go }` for the screens whose filters live in the URL
  (catalog, collection, products). The router applies a navigation inside a React transition, so the
  rendered `useSearchParams` can lag behind it; `current()` is the search of the last `go()` until the
  rendered location changes again, and every params helper builds its next search from it, so a
  change made before the page rendered the previous one never drops it.
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

## Collection (F3-g)

`frontend/src/collection/` is the `/collection` screen (nav entry `collection` is `spa`; the Jinja page
stays linked as "Versión clásica"). Below 1240 px it is a grid or a list, and until F3-h it is the same
layout on a desktop.

- `params.ts` — URL ⇄ `GET /collection` params (F3-b names): defaults `sort=number`, `per_page=50`
  are never written, invalid values are dropped, any change but `page` returns to page 1.
  `queries.ts` — `useCollectionList` (key `['collection', 'list', <query>]`) and one mutation hook per
  write (`useAddLine`, `usePatchLine`, `useDeleteLine`, `useSplitLine`, `useKeepPlayset`); every mutation
  refreshes `['collection']` and `['cards']` (the owned counts of the catalog).
- `CollectionPage` — header with the summary line, summary strip (copies, unique, value), search
  (`DebouncedInput`, writes `q`), toolbar (filters sheet with the count of active ones, sort, direction,
  grid/list; the start view comes from the `collection_view` preference, `table` meaning the list,
  Auto the grid), removable chips, `Pagination`, and a floating "Añadir carta" button. States: skeleton,
  empty collection, empty filters, error with retry, offline (the button and every edit control are
  disabled with `common:offline.editDisabled`).
- `CollectionItem` — tile or row. A group whose `playset_short` is true gets an outline **and** the text
  "Playset incompleto (kept/size)"; `kept` comes from the API (`CollectionGroup.kept`).
- `LineSheet` — the lines of a group: quantity stepper, condition and language selects, purchase price,
  selling switch, copies to sell, sale price. Each change is a `PATCH` that sends the change time the
  server last returned (`if_updated_at`, `useLineSaver`); saves of one line run one after another, typed
  numbers wait 500 ms, and a failure (`stale_line` included) shows the translated message and reloads the
  list. "Separar copias" splits, "Eliminar" asks first and then offers "Deshacer" for 8 s (it posts the
  deleted line back). The "keep a playset" checkbox calls `keep-playset`.
- `AddSheet` — set filter (`GET /meta/game` sets; narrows the `CardCombobox` search with `set`),
  `CardCombobox`, foil, quantity, condition, language, purchase price, selling; the same sheet on
  mobile and desktop. It stays open for the next card: after an add the search is cleared and
  focused and every choice stays as it was; the choices are kept for the browser session in
  `sessionStorage` `rb_quick_add_v1` (`quickAdd.ts`, never in the URL) and restored when the sheet
  opens again. Enter in the search adds the highlighted card with the current choices
  (`CardCombobox` `onEnterSelect`). Foil on a card without a foil version shows
  `errors:code.foil_not_allowed` and posts nothing. "Añadidas en esta sesión" lists the last 10
  adds (one row per line; repeated adds that merge into it sum up) with "Deshacer": a line the
  session created is deleted (the toast offers to put it back), copies merged into an existing line
  are taken off it with a `PATCH` of `qty` guarded by `if_updated_at`. Offline disables adding and
  undoing.
- The playset size is set in `/account/interface` (`collection:settings.*`, `PATCH /me/prefs`
  `playset_size`, empty = 3). Condition and language labels live in the `enums` namespace.
- From 1240 px (F3-h) `CollectionPage` renders `CollectionDesktop` instead of `CollectionMobile`; both use
  `useCollectionScreen` (URL params, the list, the open sheets). Desktop: sticky facet sidebar
  (`CollectionFilters variant="sidebar"`), `SummaryBand` (value, cost, profit in € and % with a written
  sign, lines, unique, on sale, % foil), toolbar (count, sort, direction, page size 25/50/100/200,
  grid/table; table is the default when the preference is Auto), and `CollectionTable`.
- `CollectionTable` — one row per card and foil with its lines folded below (expand button with
  `aria-expanded`); single-line cards are edited in their own row. `LineCells` holds the seven editable
  cells (copies, to sell, on sale, sale price, condition, language, purchase) and saves like the line
  sheet. Sortable headers carry `aria-sort`: number, name, copies, market, profit €, 7 d, updated.
- Selection (`useSelection`, forgotten when the filters change): a box per line, per card (indeterminate
  when partial) and per page; when the page is only a part of the result, "Seleccionar las N líneas
  filtradas" reads the ids page by page (`fetchFilteredLineIds`, at most 1000 lines). `BulkBar` (sticky,
  while something is selected): condition, language, on sale, copies-to-sell rule (all / none / keep N),
  prices; apply and delete go through a `ConfirmDialog`, delete offers "Deshacer" for 8 s (it posts
  the deleted lines back).
- From 1600 px `CollectionPanel` (380 px) shows the clicked row's card: image, totals, 30-day `PriceChart`
  (foil series for a foil group), lines, the decks using the card (`in_decks`) and a link to the card page.
- Import and export (F3-i): "Exportar" (toolbar on the desktop, header on a phone; off offline) opens
  `ExportDialog`: format RBAPP or Cardmarket (Cardmarket forces "only what is on sale"), scope all / the
  current URL filters (`exportQuery` in `params.ts`, no sort or paging) / on sale. The file comes from
  `requestFile` in `api/client.ts` (same timeout, credentials and `ApiError` as `request`) and is saved
  through a Blob and a temporary link with the `Content-Disposition` name; the toast counts
  `X-Rows-Exported`. "Importar" (header and empty state) opens `/collection/import`, `ImportWizard`:
  `StepIndicator` (`aria-current="step"`; not the numeric `Stepper`) over four steps. File (`.csv` read
  with `FileReader`, or pasted text; empty and over 2 MB are refused before any request), review
  (`POST /collection/import/preview`: summary, status filter, a table from 860 px with a sticky header
  and a list below, the summary as a side column from 1600 px; reasons from `import.reason.<code>`),
  mode (add, or replace behind a `ConfirmDialog` with the number of cards) and result
  (`POST /collection/import/commit`, then `['collection']` and `['cards']` are refreshed).
  `import_expired` returns to the first step with the reason; `import_format_unknown` is shown there.
  Offline the wizard says `common:offline.editDisabled` and its actions are disabled.
- ESLint: `collection` may import everything below `app`, like `catalog`.

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
