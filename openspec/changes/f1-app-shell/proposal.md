# Proposal: F1 App Shell (roadmap phase F1 "Estructura app")

## Intent

F0 left a secured JSON API (`/riftbound/api/v1`) and no frontend. Every later phase (F2–F11) moves one module into
a React PWA, so F1 has to provide the base those phases build on: toolchain, hosting, auth screens, i18n,
account-level UI preferences, shell/navigation, design tokens and primitives, and an installable PWA.
F1 also fixes one real defect: login never sets `remember`, so an installed PWA (which has its own cookie jar)
loses its session every time it is closed.

**Brand:** the app is called **"Rift Manager"**. The user supplied a mark and a wordmark (`brand/`). They replace the
`◆` icon that the exploration proposed. The brand orange already matches the default accent (orange).

## Scope

### In Scope: 7 PR-sized units (a, b, c in parallel → d → e → f → g)
- **a** frontend-toolchain: Vite 8 / React 19 / TS 6, ESLint + Prettier + Vitest, live CI job and artifact,
  tokens/base/fonts/background, `breakpoints.ts`, `bgVars`, **brand asset pipeline**
- **b** spa-hosting: `spa_bp` serves `frontend/dist` at `/riftbound/app/`
- **c** api-prefs-session: `0006_user_prefs`, `GET`/`PATCH /me/prefs`, `prefs` in the session payload, `remember`
  (30 days), optional error `code`/`params`
- **d** frontend-auth-i18n: API client, CSRF, router, guards, ES/EN, login/register (with ALTCHA 2.3.0, wordmark)
- **e** app-shell-prefs: AppShell, Topbar, BottomNav + "Más" sheet, Interface page, states, Toast, Dialog, 404,
  legacy hub, `base.html` link, **Jinja visible titles → "Rift Manager"**
- **f** pwa: manifest, icons from the mark, SW precache + update prompt, install (with iOS dialog), offline banner
- **g** hardening (optional): CSP Report-Only, axe pass, Lighthouse, docs

### Out of Scope
- Moving the SPA to `/riftbound/` and retiring Jinja (F11/F12). Nginx static serving (F12, optional). Landing rename/restyle (F11).
- Runtime caching of the API, IndexedDB and image cache (F2+). `GET /me` (F9). `/meta` rules and enums (F2/F5).
- Components deferred until a phase first uses them (exploration §3.7). Playwright/E2E (F11). A "remember me" option on the Jinja login.

## Capabilities

### New Capabilities
- `spa-hosting`: `/riftbound/app/` serving, cache headers, the extension-less fallback rule, 503 when the build is missing, manifest mimetype
- `ui-preferences`: `rbuserprefs` (NULL = Auto), `GET`/`PATCH /me/prefs` semantics, client defaults, apply before first render
- `frontend-auth`: session boot, login/register/logout flows, CSRF retry, 401/429 handling, guards, `safeNext`
- `i18n`: ES/EN catalogs, detection order, parity test, server errors translated by `code`
- `design-system`: tokens, accent rule, density, breakpoints, a11y baseline, primitives, brand assets
- `app-shell`: topbar, bottom nav + "Más", nav registry (`spa|legacy|planned`), states, 404
- `pwa`: manifest identity/scope, icons, SW scope and precache, update prompt, install, offline banner

### Modified Capabilities
- `api-v1`: API-1 (optional `code`/`params` on errors), API-4 (`data.prefs`), API-5 (`remember`)
- `session-security`: SESS-1 (remember cookie actually issued; `REMEMBER_COOKIE_DURATION` 30 days)
- `ci-pipeline`: CI-5 (placeholder job becomes a live job that uploads the `frontend-dist` artifact and checks the manifest)

## Approach and Rollback per Unit

| Unit | Approach | Depends | Rollback |
|---|---|---|---|
| a | Pins from exploration §3.6 (`--save-exact`, `--before=2026-10-05`). Plain CSS tokens and CSS Modules. Rewrite the CI placeholder test. Brand: copy the originals to `frontend/assets-src/brand/`. Produce a clean SVG trace of the mark (fallback: white→transparent WebP/PNG) and a cropped transparent wordmark in `frontend/src/assets/brand/`. Check for white halos on `#06222c`. | — | Revert the PR. The CI job falls back to skipped steps. |
| b | `spa_bp`, `FRONTEND_DIST`. Hashed assets `immutable`; `index.html`/`sw.js`/manifest `no-cache`. Tests use a tmp dist. Docs cover build/deploy. Keep 2 `proxy_pass` lines in nginx. | — | Revert or unregister `spa_bp`. Jinja is unaffected. |
| c | 1:1 `rbuserprefs`, named CHECKs, PG + SQLite. PATCH: a missing field means unchanged, `null` means Auto. `LoginRequest.remember` (default `False` in the API; the SPA sends ON by default). | — | `flask db downgrade 0005_login_protection`, then revert. All changes add fields only. |
| d | React Router 8 data mode with basename `/riftbound/app`. TanStack Query 5. react-i18next. npm `altcha@2.3.0` lazy-loaded, with a contract test that the JS and Python pins match. Login/register designed from the tokens, with the wordmark. | a, b, c | Revert. Jinja login is still there. |
| e | Shell per §3.7. Prefs mirror in `localStorage` (`rb_prefs_v1`) so the first render does not flash. Topbar shows the wordmark at ≥ md and the mark below md. Rename Jinja `<title>`s and the visible brand to "Rift Manager". | d | Revert. This removes the `base.html` link and title rename. |
| f | `vite-plugin-pwa` 1.3.0 `generateSW`, `registerType: 'prompt'`. Manifest `name`/`short_name` "Rift Manager", `id` `/riftbound/`, `scope` `/riftbound/`, `start_url` `/riftbound/app/`. SW scope `/riftbound/app/`, no API caching. Icons from the mark: 192, 512, maskable 512 (mark inside the 80% safe zone on `#06222c`), apple-touch 180, favicon (simplified mark if 16–32 px is illegible). Icons are committed. | a, b, e | Deploy a self-destroying SW (`selfDestroying: true`), then revert. A plain revert leaves the old SW installed on clients. |
| g | CSP `Content-Security-Policy-Report-Only`, axe, Lighthouse, docs. | f | Drop the header (env toggle). |

**Roadmap deviation:** this supersedes roadmap §2 "Nginx sirve el build en /riftbound/". In F1, Flask serves the
SPA at `/riftbound/app/`. The move to `/riftbound/` (with a redirect, keeping the PWA `id`) happens in F11/F12.

**User decisions (2026-10-19):** density Auto (compact on mobile, regular on desktop). Collection view Auto (grid on
mobile, table on desktop). Accent orange. Background intensity 100. Language: browser, then `es`. Prefs are
account-level. "Remember me" is ON by default (30 days). Interactive elements follow the accent; cyan stays as the
info colour. `2xl 1600` / `--maxw-wide 1760`. The "Más" sheet holds Account/Interface, legacy modules, language,
install, Admin (admin only) and logout.

## Jinja Coexistence

- Every Jinja route and test stays as it is. `/riftbound/app` is a free prefix.
- Jinja and the SPA share one session cookie: logging in or out in either one applies to both.
- `base.html` gets a "Nueva app" link. Visible titles are renamed in unit e. The landing `/` stays until F11.
- With manifest scope `/riftbound/`, Jinja pages open inside the installed window. The SW never controls or caches them.

## Affected Areas

| Area | Impact | Units |
|---|---|---|
| `frontend/` (incl. `assets-src/brand/`, `src/assets/brand/`, `public/icons/`), `.npmrc` | New | a,d,e,f |
| `app/routes/spa.py`, `app/__init__.py`, `config.py`, `.env.example` | New/Modified | b,c |
| `app/models/prefs.py`, `migrations/versions/0006_user_prefs.py`, `app/api/v1/{auth,me}.py`, `app/schemas/validators.py`, `app/errors.py`, `app/api/responses.py` | New/Modified | c |
| `app/templates/base.html` (+ titles) | Modified | e |
| `.github/workflows/ci.yml`, `tests/test_ci_workflows.py`, `tests/test_docs.py`, `docs/{nginx_config,migrations.md}`, `README.md`, `AGENTS.md` | Modified | a,b,c,g |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Installed PWA loses its session | High (today) | `remember` set to 30 days (c), with a test on the cookie expiry |
| Thin swirl tips blur at 16–32 px; the raster leaves a white halo on dark | High | SVG trace; simplified favicon; manual review at 16/32/48 px |
| A broken SW is stuck on clients | Med | `prompt` update flow, `no-cache` on `sw.js`, self-destroying SW for rollback |
| Version churn (Vite 8, RR 8, Vitest 5); TS 7 is not supported by typescript-eslint | Med | Exact pins, cutoff date, re-check with `npm view` |
| Existing tests break (CI placeholder, docs, nginx doc, "Riftbound Manager" strings) | High | Rewrite them in the same PR; grep for the old title before unit e |
| ALTCHA payload burned on a 409; JS/Python version drift | Med | Refetch and reset the widget on any error; pin contract test |
| The wordmark is an image, so screen readers get no text | Low | Accessible name "Rift Manager" (`alt` or a visually hidden label) |

## Dependencies

- F0 archived (done). npm registry access for unit a. No proxy/HTTPS change needed. Run the pending F0 manual checks as the first deploy smoke test.

## Success Criteria

- [ ] CI `frontend` job runs (steps not skipped) and is green: `npm ci`, lint, typecheck, `vitest run`, build; the `frontend-dist` artifact is uploaded; the manifest check passes.
- [ ] The full pytest suite (F0 tests included) and the PG lane are green. `0006` upgrades and downgrades on SQLite and PG. `flask db check` is clean after `0006`.
- [ ] pytest with a tmp dist: `/riftbound/app` redirects to `/riftbound/app/`; assets are `immutable`; `index.html`/`sw.js` are `no-cache`; a missing `.js` returns 404 (not HTML); the manifest is `application/manifest+json`; no dist returns 503.
- [ ] Login with `remember: true` issues a remember cookie that expires in about 30 days; `false` issues none. `PATCH /me/prefs` handles missing, `null` and invalid values (400). `/auth/session` includes `prefs`.
- [ ] Vitest: i18n parity, `bgVars` vs handoff §1.4, breakpoint scan, auth/guard flows (MSW), `vitest-axe` clean on login, register, shell and Interface.
- [ ] Manifest has `name` "Rift Manager" and the agreed `id`/`scope`/`start_url`; icons 192/512/maskable/180 and the favicon are present.
- [ ] [MANUAL] Lighthouse installability passes. Install works on Android and on iOS. Offline, the shell opens with the banner. The update prompt works. The maskable icon is inside the safe zone. The favicon is legible at 16/32 px.
- [ ] Every Jinja page still works; `base.html` links to `/riftbound/app/`.

## Open Items

- Rename the legacy Jinja visible titles in unit e (recommended, low risk) or in F11. The landing is renamed in F11.
- SVG trace: automated (potrace-style) plus hand cleanup, or a user-supplied vector. Whether the simplified favicon needs user sign-off.
- Is the error `code`/`params` set in c enough for the F1 screens, or should it cover all endpoints? (Recommendation: the F1 endpoints only.)

## Addendum (2026-10-19): app background — user decision

- Background image: the Summoner's Rift map `new_rift.webp` from the design handoff (byte-identical to the image the
  user re-sent). Copied into the frontend build and precached; add a ~1280 px variant for mobile (`image-set`).
- The user wants it **slightly blurred and darkened so text and UI on top stay readable**. This changes the
  prototype formula (handoff §1.4), whose upper range *brightens and saturates* the image (brightness up to 1.13):
  - Add a blur to `--bg-image-filter` (start around 2–4 px, tuned visually; scale the layer slightly so blurred
    edges do not show).
  - Never brighten: brightness ≤ 1 and saturation ≤ 1 at every slider value; keep the dark overlay gradients.
  - Slider semantics: 0 % = no image, 100 % = image fully visible but still blurred and darkened.
  - `bgVars(percent)` is redefined accordingly (tests replace the §1.4 table) and a contrast check keeps body text
    ≥ 4.5:1 over the darkest/brightest background state.
  - The default value (proposal said 100) is confirmed visually by the user in the unit-a/e PR screenshots.
- Riot Games artwork: fine for this non-commercial fan project; add Riot's fan-content disclaimer
  ("not endorsed by Riot Games…") in the app footer/about by F11, and review licensing before F12 production.
