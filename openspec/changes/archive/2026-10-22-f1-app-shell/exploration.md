# Exploration: f1-app-shell (F1 "Estructura app")

> sdd-explore, 2026-10-19. Read-only investigation of `openspec/roadmap.md`, `openspec/design-handoff.md`,
> the design prototype (zip), `openspec/specs/` (F0) and the Flask app. Saved by the orchestrator.

## 1. Current state (facts that shape F1)

- F0 is archived; `openspec/specs/` holds 14 capabilities. F1 writes MODIFIED deltas against `api-v1`,
  `ci-pipeline`, `session-security`.
- Jinja URLs: `/riftbound/` (dashboard), `/set`, `/card`, `/collection`, `/deck`, `/price` (admin), `/profile`,
  `/login`, `/register`, `POST /logout`, `/riftbound/static/*`; landing at `/`. **`/riftbound/app` is free.**
- JSON API (`app/api/v1/{auth,meta}.py`): `GET /health`, `GET /meta/config`, `GET /auth/session`
  (`{authenticated, csrf_token, user?{id,username,email,is_admin}}`), `GET /auth/captcha`,
  `POST /auth/login|logout|register`. Error envelope `{success:false, error, message, details?}` —
  **no machine `code`/`params`** (handoff §9 asked for them). Validation `details[]` = `{field, message, type}` (English text).
- **Login never sets `remember`** (`login_user(user)` in API and Jinja); no `PERMANENT_SESSION_LIFETIME` /
  `REMEMBER_COOKIE_DURATION` → browser-session cookie only. Real problem for an installed PWA.
- CSRF: Flask-WTF on every unsafe method, no API exemption; token from `/auth/session`, sent as `X-CSRFToken`,
  no time limit; Referer checked over HTTPS (SPA must never use `no-referrer`).
- ALTCHA: Jinja uses vendored widget 2.3.0 (PoW v1, `challengejson`); Python `altcha==2.3.0` v1 functions;
  300 s expiry; payload single-use (`rbcaptcha_used`) and consumed **before** the duplicate check (a 409 burns it).
  Needs secure context and `worker-src data:`. Widget 3.x = PoW v2, incompatible.
- DB: Alembic head `0005_login_protection`; `batch_alter_table`; `flask db check` must pass on PG and SQLite.
- Nginx template: HTTPS, 80→443, `/` and `/riftbound/` to one upstream; no static location, gzip, HSTS or CSP.
  F0 follow-ups 4.31 (limit_req burst) and 4.32-style smoke remain manual.
- CI: `frontend` job exists, every step gated on `hashFiles('frontend/package.json')` (npm ci, lint, typecheck,
  vitest run, build), Node from `.nvmrc` (24). `.gitignore` has `node_modules/`, `frontend/dist/`, `.vite/`.
- **Test traps**:
  - `tests/test_ci_workflows.py::TestFrontendPlaceholderJob::test_the_workflow_does_not_need_a_frontend_directory`
    asserts `frontend/package.json` does NOT exist → must be rewritten in the first F1 PR.
  - `tests/test_docs.py`: AGENTS.md tree paths must exist; every table and blueprint named in AGENTS.md;
    every `.env.example` var described in README.md.
  - `tests/test_nginx_config_doc.py`: exactly two `proxy_pass http://\w+;` lines (`/` and `/riftbound/` → :8000);
    a static `location` must not use `proxy_pass`.
- Prototype: `riftbound.css` tokens (handoff §1.1); `app.jsx` shell = sticky 64 px topbar, 7-item nav,
  lang toggle, avatar, non-functional logout, 5-item `.botnav` (no Sales/Dashboard/Account).
  **No manifest, favicon or app icon in the zip**; only visual asset `new_rift.webp` (1920×1079, 185 KB).
- Untracked `.agents/skills/` has frontend skills (accessibility, frontend-design, responsive-design,
  modern-web-guidance, web-design-guidelines, ui-ux-pro-max, nodejs-best-practices) — inject into apply prompts.

## 2. Affected areas

- Frontend (new): `frontend/` (Vite; `src/{api,auth,i18n,prefs,shell,components/ui,styles,lib,pwa}`),
  `frontend/public/` (icons), `.npmrc` (`save-exact`, `engine-strict`).
- Backend: `app/routes/spa.py` (`spa_bp`) + registration; `app/api/v1/{auth,me}.py` (session `prefs`,
  `remember`, `GET`/`PATCH /me/prefs`); `app/models/prefs.py`; `migrations/versions/0006_user_prefs.py`;
  `app/schemas/validators.py` (`LoginRequest.remember`, `PrefsUpdate`); `app/errors.py`,
  `app/api/responses.py` (optional `code`/`params`); `config.py` (`FRONTEND_DIST`, remember duration); `.env.example`.
- Docs/CI: `app/templates/base.html` (link to new app), `.github/workflows/ci.yml`, `docs/nginx_config`,
  `docs/migrations.md`, `README.md`, `AGENTS.md`.
- Tests: `test_ci_workflows.py`, `test_docs.py`, `test_nginx_config_doc.py`; new API, SPA-serving, PG-lane tests.
- Specs: new `spa-hosting`, `ui-preferences`, `app-shell`, `pwa`, `frontend-auth`, `i18n`, `design-system`;
  MODIFIED `api-v1` (API-4, API-5, error `code`), `ci-pipeline`, `session-security`.

## 3. Approaches and recommendations

### 3.1 Where the SPA lives and how it is served

| Option | Pros | Cons | Effort |
|---|---|---|---|
| **A. `/riftbound/app/`, Jinja untouched (recommended)** | No collision with 9 Jinja blueprints / ~100 tests; trivial rollback; clean SW scope; fits "one module per PR" | Longer URL; final move (F11/F12) needs redirect + care with PWA identity | Low |
| B. SPA takes `/riftbound/`, Jinja → `/riftbound/legacy/*` | Final URLs now | Every `url_prefix`, `url_for`, test, bookmark changes; big-bang | High |
| C. SPA catch-all under Jinja routes | Final URLs | Soft 404s; two apps in one URL space | Medium |

Deviates from roadmap §2 ("Nginx sirve el build en /riftbound/") → **Q1**.

Serving: **Flask serves `frontend/dist`** (one deployable, no proxy change; the proxy is on another host).
Nginx static serving deferred to F12 as an optional optimisation.

`spa_bp` (prefix `/riftbound/app`, config `FRONTEND_DIST`, default `<repo>/frontend/dist`):
- `/assets/<path>` → `Cache-Control: public, max-age=31536000, immutable`.
- `sw.js`, `workbox-*.js`, `manifest.webmanifest`, `index.html` → `no-cache` (ETag/304).
- `/riftbound/app` → redirect `/riftbound/app/`.
- Catch-all returns `index.html` **only for extension-less paths**; a missing `.js/.css/.woff2` is a real 404.
- Explicit `application/manifest+json` mimetype (tested).
- `dist/` absent → 503 with a clear message; pytest uses a tmp dist (no Node in the Python lane).
- `index.html` has no secrets/CSRF token (token from `/auth/session`) → cacheable/precachable.
- Optional CSP, Report-Only first: `default-src 'self'; worker-src 'self' blob: data:; img-src 'self' data: blob:;
  connect-src 'self'; frame-ancestors 'self'` (`style-src 'unsafe-inline'` may be needed by ALTCHA).

Build artifact: not in git; build on deploy (`npm ci && npm run build`); CI builds and uploads `frontend-dist`.
`emptyOutDir` leaves a short 503 window in dev; F12 can build to temp and swap.

Dev workflow: `npm run dev` on `127.0.0.1:5173`, `base: '/riftbound/app/'`, `server.proxy` for `/riftbound/api`
and `/riftbound/static` to Flask. Cookies are host-scoped (not port), `SESSION_COOKIE_SECURE` off in development,
Referer check only on HTTPS → CSRF works. ALTCHA needs localhost/HTTPS (or `CAPTCHA_PROVIDER=none`).
SW disabled in dev (test via `vite preview` or Flask-served build). Base paths build-time configurable
(`VITE_BASE`, `VITE_API_BASE`) because the F12 URL is undecided.

Nginx/HTTPS left: nothing required for the SPA. Run the pending F0 manual checks as the first deploy smoke test.
Optional template additions: gzip (js/css/svg/webmanifest), HSTS (small max-age first), note on caching
`/riftbound/app/assets/`; keep the proxy_pass count at 2.

### 3.2 PWA

- `vite-plugin-pwa` 1.3.0, `generateSW` (Workbox 7.4.1), `registerType: 'prompt'`, `injectRegister: false`,
  update UI with `useRegisterSW` (`virtual:pwa-register/react`).
- Manifest: `id: '/riftbound/'`, `start_url: '/riftbound/app/'`, `display: 'standalone'`,
  `theme_color`/`background_color: #06222c`, `name: 'Riftbound Manager'`, `short_name: 'Riftbound'`,
  `categories: ['games']`. **`scope: '/riftbound/'`** so Jinja pages stay inside the standalone window during the
  migration (→ **Q2**). SW scope narrower: `/riftbound/app/` (never sees/caches authenticated Jinja HTML).
- Icons: 192, 512, maskable 512, apple-touch 180, favicon.
- SW in F1: precache app shell only (hashed js/css, `index.html`, latin fonts, `new_rift.webp`, icons);
  `navigateFallback` `/riftbound/app/index.html`, allowlist `^/riftbound/app/`, denylist API/static/legacy;
  `cleanupOutdatedCaches`. **No runtime caching of `/riftbound/api/*` in F1.**
- Offline data later (F2/F3/F5): per-user TanStack Query/IndexedDB persistence wiped on logout; SW runtime cache
  only for images (cache-first, LRU).
- Update flow: prompt toast ("Nueva versión / Actualizar"), check hourly and on focus — avoids reload mid-edit.
- F1 offline: shell opens; network error on `/auth/session` + "was signed in" hint → shell + `OfflineBanner`
  (read-only); 401 → login.
- Icons: none in zip → `logo.svg` from the brand mark (rounded square, `150deg #2ec6e6 → #1c8aa6`, path-drawn
  diamond `#04222b`); PNGs via `@vite-pwa/assets-generator` 1.x (`npm run icons`), **committed** so CI needs no
  `sharp`; maskable diamond inside the safe zone.
- iOS: Share → Add to Home Screen only (instructions dialog); apple-touch-icon + `apple-mobile-web-app-*` meta;
  `viewport-fit=cover` + safe-area insets; `100dvh`; separate storage/cookie jar in the installed app
  (→ `remember` matters); push only installed iOS 16.4+ (F4/F8). Install entry lives in the "Más" sheet.

### 3.3 Auth in the SPA (same session cookie as Jinja)

1. Boot: `GET /auth/session`; CSRF token in memory; keep `authenticated`, `user`, new `prefs`.
2. Login: `POST /auth/login {username, password, remember}` + `X-CSRFToken`, refetch session, go to validated `next`.
3. Register: `GET /auth/captcha` (`null` challenge = no widget), `GET /meta/config` for requirement, post `altcha`;
   201 → `/login` + toast (no session). **On any register error refetch the challenge and reset the widget.**
4. Logout: `POST /auth/logout`, clear Query cache + hint, go to `/login`; 401 on logout = success.
5. Errors: CSRF 400 → refetch session + one retry; 401 → anonymous + login with `next`; 429 → `Retry-After` countdown.
6. Guards: React Router data mode `requireAuth`, `requireAnon`, UX-only `requireAdmin`.
7. `next` accepted only as a same-origin path under `/riftbound/`.

ALTCHA: **npm `altcha@2.3.0` exact, lazy-loaded on the register route** (lockfile, same contract as Python v1,
React 19 custom elements). Listen to `statechange` (`detail.payload`; confirm API in design). Contract test:
JS altcha version == Python pin. Style through its CSS variables. 3.x rejected (PoW v2).

Backend deltas (additive): `LoginRequest.remember: bool = False` + `login_user(user, remember=...)` +
`REMEMBER_COOKIE_DURATION` (30 days); optional `code`/`params` on errors (409 `username_taken`/`email_taken`,
429 `locked` + `retry_after`, 400 `captcha_failed`, stable validation codes) so the SPA translates by code;
`prefs` in the session payload.

### 3.4 UI preferences

| Option | Verdict |
|---|---|
| Columns on `rbusers` | Simplest, but UI state in the hot auth table; each pref = ALTER |
| **1:1 table `rbuserprefs`, typed columns (recommended)** | Separation, DB CHECKs, lazy rows, extensible |
| JSON column | Flexible, no DB validation; only if prefs grow a lot (F9) |

Migration `0006_user_prefs` (down `0005_login_protection`): `rbuserprefs` = `rbprf_user_id` (PK, FK
`riftbound.rbusers.id` ON DELETE CASCADE), `rbprf_lang`, `rbprf_density`, `rbprf_accent`,
`rbprf_bg_intensity` (SMALLINT 0–100), `rbprf_collection_view`, `rbprf_updated_at`. Pref columns nullable,
**NULL = Auto/default** (device-dependent defaults). Named CHECKs. PG + SQLite, `flask db check`, PG lane,
`docs/migrations.md`.

Endpoints: `GET /api/v1/me/prefs`; `PATCH /api/v1/me/prefs` (absent = unchanged, explicit `null` = reset to Auto,
via `model_fields_set`; CSRF + `@validate_json`); `/auth/session` adds `data.prefs` (`user` keeps its 4 fields).
Full `GET /me` waits for F9.

Client defaults: density Auto = compact ≤ 860 px else regular; collection view Auto = grid mobile / table desktop;
accent orange; bg intensity 100 (→ **Q3**); lang stored → `navigator.languages` → `es`.
Apply via `data-density`/`data-accent` on `<html>`; `bgVars(percent)` pure function tested against handoff §1.4;
mirror in `localStorage` (`rb_prefs_v1`) applied before first render (no theme flash, also for anonymous);
optimistic save + toast with revert; debounced slider. Account-level vs per-device → **Q4**.

### 3.5 i18n

**react-i18next + i18next, bundled JSON, typed resources (recommended)** over a custom catalog or FormatJS.
Catalogs `src/i18n/locales/{es,en}/{common,nav,auth,errors,prefs}.json` (more namespaces per phase), bundled
(precached, offline). Own ~10-line detection (pref → browser → `es`). Language in DB prefs / `rb_lang` for anonymous.
`<html lang>` + `document.title` update. `Intl` locales `es-ES` / `en-GB`. Server errors translated by
`code`+`params` (API `message` = fallback). Vitest parity test (keys + `{{placeholders}}`, plural suffixes
normalised). Migrate the 99 used prototype keys; drop unused ones.

### 3.6 Stack and versions

- React 19, React Router 8 data mode (`createBrowserRouter`, basename `/riftbound/app`, lazy routes, per-route
  errorElement), TanStack Query 5, no form/schema library in F1.
- TypeScript 6.0.3 (TS 7 unsupported by typescript-eslint 8.71.x, peer `<6.1.0`); avoid `baseUrl`/`node10`.
- Vite 8 + `@vitejs/plugin-react` 6.x.
- Tests: Vitest + Testing Library (react, user-event, jest-dom) + MSW + jsdom + `vitest-axe`; no E2E in F1
  (Playwright/Lighthouse in F11); MANUAL device checklist for SW/install.
- Lint: ESLint flat + typescript-eslint + react-hooks + jsx-a11y; Prettier checked in `npm run lint`.
  Scripts: `dev`, `build` (`tsc -b && vite build`), `preview`, `lint`, `typecheck`, `test`, `icons`.
- Fonts: `@fontsource-variable/manrope`, `@fontsource-variable/space-grotesk` (latin + latin-ext only,
  `font-display: swap`, precache `globIgnores` for other subsets).
- CSS: **global tokens in plain CSS (`tokens.css`, `base.css`, `@layer`) + CSS Modules** (highest fidelity to
  `riftbound.css`; no new toolchain). Accent via `color-mix(in srgb, var(--accent) N%, transparent)` and
  `--accent`, `--accent-bright`, `--accent-dim`, `--accent-ink` per `[data-accent]`. Breakpoints
  (sm 680, md 860, lg 960, xl 1240, 2xl 1600) in `breakpoints.ts` + vitest scan of CSS `@media` widths.

Pins (verified 2026-10-19; cutoff = published ≤ 2026-10-05):

| Package | Pin | Published |
|---|---|---|
| react, react-dom | 19.3.0 | 2026-09-09 |
| vite | 8.3.2 | 2026-10-01 |
| @vitejs/plugin-react | 6.1.1 | 2026-08-28 |
| vite-plugin-pwa | 1.3.0 | 2026-05 |
| workbox-build, workbox-window | 7.4.1 | 2026-05-04 |
| react-router | 8.4.0 | 2026-09-15 |
| typescript | 6.0.3 | 2026-04-16 |
| @tanstack/react-query | 5.100.0 (floor) | 2026-04-23 |
| altcha | 2.3.0 | (vendored version) |

Too new, do not pin: react 19.3.1, vite 8.3.4, vitest 5.0.5, eslint 10.13.0, typescript-eslint 8.71.2,
i18next 26.5.2, react-i18next 17.1.0, @tanstack/react-query 5.104.4, altcha 3.4.1, vite-plugin-pwa 2.0.0.
Everything else: `npm install --save-exact --before=2026-10-05`, re-verify with `npm view <pkg> time`.
Engines: `.nvmrc` 24 satisfies Vite 8, Vitest 5, React Router 8 (`>=22.22`); set `engines.node >= 22.22`.

### 3.7 Design-handoff items

IN F1: ported tokens + `--z-*` scale (popover 30, topbar 40, botnav 50, modal 80, toast 90), `--maxw-wide` 1760,
`--accent-*`, `color-scheme: dark`, `theme-color`, `scrollbar-color`; accent via `color-mix` (interactive states
follow the accent, brand/data cyan stays as info colour → **Q6**); density `--row-h` on row/list/menu primitives,
`--radius-sm` on small controls; global `:focus-visible`; `prefers-reduced-motion`; safe areas, `100dvh`,
`backdrop-filter` fallback, botnav padding only when shown; self-hosted fonts and background (`bgVars`);
47 prototype icons as typed SVG (`aria-hidden` default) + `more`, `install`, `warning`, `offline`, `settings`,
`info`, `external-link`, `check-circle`, brand mark SVG; primitives Button, Field/Input/Select/PasswordInput
(`useId` + `aria-describedby`), Switch, SegmentedControl, Slider, Panel, PageHeader, Badge, Avatar, SettingsCard;
overlays on native `<dialog>` (Modal/Sheet/ConfirmDialog) + Toast (`aria-live`, action slot); states Skeleton,
EmptyState, ErrorState, OfflineBanner, ErrorBoundary, 404; botnav labels 11 px; contrast fixes used by the shell
(`--muted-2` 4.26:1, white on red 4.14, `--red` text 3.98); `breakpoints.ts` + `useMediaQuery`, `format.ts`
(EUR), `useOnline`; bottom nav "Más" sheet (§10-9).

DEFERRED to first use (deviation from handoff §9): DomainPips, RarityDot, CardImage, AbilityText, CardCombobox,
Chip → F2; DataTable, Pagination → F2/F3; Stepper, Checkbox, Combobox → F3; Sparkline, PriceChart, Donut, Bars,
MiniCurve, StatCard → F4/F6; CollapsibleSection → F5; CopyButton, `downloadFile` → F3/F5. DEV-only kitchen-sink route.

Shell content: nav registry with status `spa | legacy | planned` (legacy = plain `<a href>` from a tested
`legacyRoutes.ts`; planned hidden); topbar (brand, nav, ES/EN, avatar initials, logout); home = launcher hub to
Dashboard, Sets, Cards, Collection, Decks, Profile (+ Price if admin); Interface settings at `/account/interface`
(density Auto/Compact/Regular/Comfy, accent, bg slider, language, default collection view Auto/Table/Grid).

### 3.8 Slicing (PR-sized, each deployable without breaking Jinja)

| Unit | Content | Depends |
|---|---|---|
| a. frontend-toolchain | Vite/React/TS, ESLint/Prettier/Vitest, live CI job + artifact, `.npmrc`, tokens/base/fonts/background/icons, `breakpoints.ts`, `bgVars`; rewrite the CI placeholder test | — |
| b. spa-hosting | `spa_bp`, `FRONTEND_DIST`, tmp-dist tests, docs, nginx notes, build/deploy commands | — |
| c. api-prefs-session | `0006`, `RbUserPrefs`, `GET`/`PATCH /me/prefs`, session `prefs`, `remember`, error `code`/`params`, MODIFIED specs, PG lane | — |
| d. frontend-auth-i18n | API client + CSRF + 401, Query, router, i18n + parity, login/register + ALTCHA, guards, `safeNext` | a, b, c |
| e. app-shell-prefs | AppShell, Topbar, BottomNav + Más, PrefsProvider + bootstrap cache, Interface page, states, Toast, Dialog, legacy hub, 404, `base.html` link | d |
| f. pwa | Manifest, icons, SW precache + prompt, install hook + iOS dialog, offline banner, meta, CI manifest check, MANUAL device checklist | a, b, e |
| g. hardening (optional) | CSP Report-Only, axe pass, Lighthouse PWA, docs | f |

Order: a, b, c in parallel → d → e → f → g. Strict TDD on both sides.
Rollbacks: a remove `frontend/`; b remove `spa_bp`; c `flask db downgrade 0005_login_protection`.

## 4. Questions for the user (each with a recommended default)

- **Q1.** SPA at `/riftbound/app/`, Jinja untouched, Flask serves the build (Nginx static only in F12)? Default yes.
- **Q2.** Manifest `scope: '/riftbound/'`, `start_url: '/riftbound/app/'`? Default yes.
- **Q3.** Defaults: density Auto, view Auto, accent orange, bg intensity 100, language from browser (fallback es)? Default yes.
- **Q4.** Prefs account-level with explicit "Auto" (not per-device)? Default yes.
- **Q5.** "Remember me" checkbox, default ON, 30-day cookie? Default yes.
- **Q6.** Interactive elements follow the accent; brand/data cyan stays cyan? Default yes.
- **Q7.** Port components on first use; breakpoints `2xl 1600` + `--maxw-wide 1760`; "Más" sheet = Account/Interface,
  legacy modules, language, install, Admin (if admin), logout? Default yes.
- **Q8.** Login/register designed from the tokens (no design exists), reviewed in the PR; PWA icon = `◆` mark in the
  brand gradient unless the user provides a logo? Default yes.

Decided without asking: install entry in "Más"; Jinja login/dashboard not redirected in F1 (only a "new app" link in
`base.html`); F0 manual checks as first deploy smoke test; CSP Report-Only in unit g.

## 5. Risks

- PWA session loss without `remember` (separate cookie jar in installed app, iOS) — main UX risk.
- Version churn (Vite 8, RR 8, Vitest 5, ESLint 10, i18next 26); TS 7 unsupported by typescript-eslint.
- Existing tests break/constrain (CI placeholder test, docs tests, nginx doc test).
- Captcha: payload consumed on any register error; dev needs localhost/HTTPS; CSP `worker-src data:`; JS/Python pins move together.
- SW must never runtime-cache `/riftbound/api`; per-user offline data wiped on logout; missing hashed asset → 404, not HTML.
- Update prompt must not drop in-flight form data.
- CSRF over HTTPS needs Referer; refetch + one retry on CSRF 400.
- Design gaps: contrast fixes change brand tokens; no design for login/register/offline; orange/cyan rule (Q6).
- API error prose is English until `code` ships.
- Nginx `limit_req` on auth POSTs also counts logout/register (fine for normal use).
- F1 is large → slicing required; ~598 MB of tracked card images affect F2 offline caching.

## 6. Ready for proposal

Yes, once Q1–Q8 are answered (or defaults accepted).
