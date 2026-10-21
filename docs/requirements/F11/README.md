# F11: Close — phase spec

Status: planned · Depends on: F2-F10 (every module migrated to the app and its nav entry flipped to `spa`); F1-g (axe sweep, CSP report-only) · Source: roadmap §5 (F11), design-handoff §3.12, §7 (gaps, esp. §7.4 a11y and §7.5 R10), §8, §9 F11, §10-13, product.md "Coexistence" and "Scope by phase", F1 design D19/D26

## Goal

Finish the migration: the public landing `/` gets the new visual style and an "install the app" call to
action, every Jinja page is retired (old URLs redirect to the app), the app passes an accessibility audit
against the design-handoff checklist and a performance pass, documentation is final, and the Riot
fan-content disclaimer is visible. After F11 the product is feature-complete for production (F12).

## Current state

- **Landing** (`app/routes/landing.py`, blueprint `landing_bp`, no URL prefix): `GET /` renders
  `app/templates/landing/index.html` (+ `components/*.html`: noticias, discord, torneos online/físicos,
  videos, decks, camera_scroll, footer); HTMX partials at `/api/noticias`, `/api/discord`,
  `/api/torneos-online`, `/api/torneos-fisicos`, `/api/videos`, `/api/decks`; a scroll animation served from
  `/frames/manifest.json` and `/frames/<file>` (`app/static/landing/frames/`, 81 JPG frames, ~5.3 MB).
  Feeds come from `app/services/scraper.py` with a per-worker TTL cache (LAND-1) and **fall back to
  fabricated placeholder items** (news, Discord posts, tournaments with random slots, videos, decks).
- **Jinja app**: `app/templates/{base,dashboard,sets,cards,collection,deck,deck_view,profile,price,login,
  register}.html`, `errors/*.html`, `static/css/style.css`, `static/js/csrf.js`, vendored ALTCHA widget
  (`static/vendor/altcha/`, used by the Jinja register form). Blueprints `main_bp`, `auth_bp`, `sets_bp`,
  `cards_bp`, `collection_bp`, `deck_bp`, `price_bp`, `profile_bp` with pages and legacy JSON endpoints
  (`{"success": …}` without the v1 envelope). Flask-Login `login_view = 'auth.login'` (Jinja form).
- **Coexistence tooling**: nav registry entries with `status: 'legacy'` (`frontend/src/shell/navRegistry.ts`),
  `frontend/src/shell/legacy-routes.json` checked by `tests/test_frontend_contracts.py::TestLegacyRoutes`;
  `base.html` links to "Nueva app"; `tests/test_shell_coexistence.py`.
- **Errors**: `app/errors.py` renders `errors/*.html` for HTML clients (they extend the Jinja layout).
- **a11y / perf tooling**: Vitest + `vitest-axe` component tests (F1; F1-g sweeps every route); no browser
  E2E (F1 D26 deferred it to F11); Lighthouse not automated; `check:dist` validates the PWA build.
- **Disclaimer / licences**: none in the app; fonts are OFL (design-handoff §8.2); card images and the map
  background are Riot artwork.

## Scope

In:
- New landing at `/` (design tokens, brand, install CTA, real content only, disclaimer, SEO basics).
- JSON feeds for the landing; removal of placeholder data.
- Retirement of every Jinja page and legacy JSON endpoint, with a redirect map for old URLs.
- Standalone HTML error pages; login redirects to the app.
- Browser E2E + axe harness in CI; a11y audit against design-handoff §7.4 with fixes and a report.
- Performance pass (bundle budgets, rendering cost, backend queries/indexes) and a Lighthouse record.
- About page (version, credits, third-party licences, data sources, disclaimer); final docs.
- Optional cleanup migration of legacy columns (D-F11-9).

Out:
- Production hosting, HTTPS on the final URL, CSP enforcing, backups, monitoring (F12).
- New product features. Native store packaging (Capacitor) — later, outside the roadmap.

## Decisions already taken

- Jinja retires in F11 after the gradual coexistence (product.md "Coexistence"; roadmap F11).
- Landing `/` restyled with an install button; a11y audit; final docs; Riot fan-content disclaimer
  (product.md F11). The audit checklist is design-handoff §7.4 (A1-A20); the performance items include
  `backdrop-filter` and images (design-handoff §7.5-R10, §9 F11).
- PWA scope `/riftbound/`, worker scope `/riftbound/app/`, start URL `/riftbound/app/` (product.md "PWA").
- No design exists for the landing: build from tokens and review with the owner (design-handoff §3.12, §10-13).

## Requirements

### Landing
- **F11-R1** `GET /` serves the new landing (D-F11-1) with the app's fonts, tokens, background and brand;
  sections: hero (name, one-line pitch, buttons **Abrir la app** → `/riftbound/app/` and **Instalar la
  app** → `/riftbound/app/?install=1`), feature tiles (catálogo, colección, mazos, precios, eventos, ventas),
  live blocks, footer (disclaimer, About, privacy page link once F12 adds it).
- **F11-R2** `/riftbound/app/?install=1` opens the existing install flow (prompt where supported, iOS
  instructions dialog otherwise, "ya instalada" when standalone) and removes the parameter from the URL.
- **F11-R3** No fabricated content: placeholder generators are deleted from `scraper.py`; a feed with no real
  items hides its block. Upcoming public events come from `rbevents` (F8) when present (D-F11-2).
- **F11-R4** Feeds move to `GET /riftbound/api/v1/public/feeds/{name}` (P, v1 envelope, LAND-1 cache kept);
  the HTMX partials and `/frames/*` routes are removed with the old landing.
- **F11-R5** SEO: `<title>`, meta description, Open Graph tags, `lang`, canonical built from the request
  host (no domain in the repo), `robots.txt` (allow `/`, disallow `/riftbound/`), no index of app routes.
- **F11-R6** Landing budget: first view ≤ 500 KB transferred, LCP ≤ 2.5 s on a mid-range phone profile; the
  frame animation is replaced or removed (D-F11-7); works without JavaScript except the live blocks.

### Jinja retirement
- **F11-R7** Every former Jinja page answers a redirect (D-F11-3) to its app equivalent, keeping `next`
  where it applied. Map (exact targets verified against `frontend/src/app/routes.tsx` when the unit starts):

  | Legacy URL | Target |
  |---|---|
  | `/riftbound/` | `/riftbound/app/` |
  | `/riftbound/login`, `/riftbound/register` | `/riftbound/app/login`, `/riftbound/app/register` (+ `next`) |
  | `/riftbound/card`, `/riftbound/set` | `/riftbound/app/cards` (set view per D-F10-10) |
  | `/riftbound/collection` | `/riftbound/app/collection` |
  | `/riftbound/deck`, `/riftbound/deck/view/<id>`, `/deck/view/<name>[/<seq>]` | `/riftbound/app/decks`, F5 deck route |
  | `/riftbound/profile` | `/riftbound/app/account/profile` |
  | `/riftbound/price` | `/riftbound/app/admin` |
- **F11-R8** Legacy JSON endpoints of the removed blueprints are deleted (D-F11-8); POST `/riftbound/logout`
  is removed (the app uses `POST /api/v1/auth/logout`).
- **F11-R9** Flask-Login sends HTML clients to `/riftbound/app/login?next=<absolute path>`; JSON clients keep
  the 401 envelope (API-8).
- **F11-R10** HTML error pages are standalone (no layout, no session write, no `Set-Cookie`), styled with the
  tokens, ES/EN by `Accept-Language`; JSON negotiation unchanged.
- **F11-R11** Removed: Jinja templates and static assets only they used (`style.css`, `csrf.js`, vendored
  ALTCHA if nothing else loads it; the Python `altcha` pin stays for the server), `legacy-routes.json`, the
  `legacy` nav status and its tests; `tests/test_authz_matrix.py` lists only live rules; a redirect-map test
  replaces `TestLegacyRoutes`. `AGENTS.md`/`README.md` lose the Jinja sections.
- **F11-R12** The installed PWA keeps working: legacy URLs opened inside the installed window land in the app
  (manifest scope `/riftbound/` covers the redirects).

### Accessibility
- **F11-R13** Browser E2E harness (D-F11-4): Playwright (Chromium) + `@axe-core/playwright` in a new CI job,
  against Flask with a seeded SQLite file database (`flask dev seed` style command, no network) and the
  production build; every route at 390 px and 1280 px, as user and admin, zero WCAG 2.2 A/AA violations.
- **F11-R14** Each item A1-A20 of design-handoff §7.4 has evidence (test name or manual note) in
  `docs/a11y-audit.md`; failures are fixed in this phase or listed as follow-ups with severity.
- **F11-R15** Manual checks (USER): keyboard-only main flows; screen readers (VoiceOver iOS, TalkBack
  Android, NVDA or Narrator); 200 % zoom and 320 px reflow; reduced motion; results recorded in the report.

### Performance
- **F11-R16** `check:dist` enforces bundle budgets (entry chunk and per-route chunks, gzip; numbers fixed
  from a measured baseline + 10 %) and fails on a regression.
- **F11-R17** Rendering: `@supports not (backdrop-filter)` fallback and fewer blurred layers on small screens
  (design-handoff §7.5-R10); `content-visibility: auto` or virtualization on lists > 200 rows; images with
  intrinsic size, lazy loading and the F2 derivatives.
- **F11-R18** Backend: query-count tests on the 10 busiest list endpoints; `EXPLAIN` review on PostgreSQL with
  any missing index added by a migration.
- **F11-R19** Lighthouse (mobile) recorded in `docs/frontend.md` for landing, login, home, catalog,
  collection, deck editor: Performance ≥ 85 (landing ≥ 90), Accessibility 100, Best Practices ≥ 95, SEO ≥ 90
  on the landing (D-F11-5).

### About, disclaimer, docs
- **F11-R20** Riot disclaimer (D-F11-6) on the landing footer, the login/register screens and
  `/riftbound/app/about`. English text verbatim plus a Spanish translation:
  "Rift Manager isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone
  officially involved in producing or managing Riot Games properties. Riot Games, and all associated
  properties are trademarks or registered trademarks of Riot Games, Inc." The owner checks the current
  wording of Riot's policy before merge (USER).
- **F11-R21** About page: app version (from `GET /health`), credits, data sources ("Precios: Cardmarket",
  "Catálogo: galería oficial"), font licences (OFL), generated third-party licence list (npm + pip, build
  time), link to the disclaimer.
- **F11-R22** Final docs: `README.md`, `AGENTS.md`, `docs/frontend.md`, `docs/knowledge/architecture.md`
  and `state.md` describe the system without Jinja; `docs/a11y-audit.md`; a short user help section in About
  (install, offline read-only, 2FA recovery = contact the admin).

## Data model changes

None required. Optional `00xx_legacy_cleanup` (D-F11-9): drop columns proven unused (candidates:
`rbcar_banned` after F2's ban table, legacy selling/playset columns if F3 replaced them, legacy deck fields
if F5 migrated them). Downgrade re-creates the columns empty, so it needs a backup and owner approval.
Indexes from F11-R18 come as their own small revision. Risk: item 1.

## API

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/riftbound/api/v1/public/feeds/{name}` | P | `news`, `events` (+ others kept by D-F11-2); cached. |
| GET | `/` | P | New landing (static entry). |
| GET | `/robots.txt` | P | Indexing rules. |
| GET | legacy page URLs (F11-R7) | P | Redirects. |

Removed: `/api/noticias`, `/api/discord`, `/api/torneos-online`, `/api/torneos-fisicos`, `/api/videos`,
`/api/decks`, `/frames/*`, every Jinja page and legacy JSON endpoint of the retired blueprints. No new error
codes.

## UI

| Screen | Mobile < 860 | Desktop ≥ 1240 | Wide ≥ 1600 |
|---|---|---|---|
| Landing `/` | Hero full-bleed over the map background, stacked CTAs, feature tiles 1 col, live blocks as horizontal scrollers | Hero 2 cols (text │ app screenshot), tiles 3 cols, live blocks 2 cols | Content max ≈ 1440 px, tiles 6 cols, live blocks 3 cols (events, news, decks) |
| About `/app/about` | One column of cards | 2 cols (about + credits │ licences list with search) | 3 cols (+ disclaimer and data sources) |
| Error pages | Centred card, brand, message, link home | same, larger | same |

States: live blocks with skeleton, hidden when empty or on error. i18n: namespaces `landing`, `about`
(ES/EN). Components: landing entry (`frontend/landing.html` + `src/landing/`), `InstallCta`, `FeedBlock`,
`AboutPage`, `LicencesList`, `Disclaimer`.

## Units

| ID | Title | Depends on | Size | Risk | Summary |
|---|---|---|---|---|---|
| F11-a | Public feeds API | F8-a | ~400 | Risk: item 3 (LAND-1 contract changes; landing consumers) | `/public/feeds/*`, placeholder removal, events feed from `rbevents`, spec LAND-1 updated. |
| F11-b | New landing | F11-a | ~600 | Risk: item 5 (second Vite entry, check-dist, Flask serving `/`) | Landing entry, install CTA + `?install=1`, disclaimer, SEO, robots, removal of old landing and frames. |
| F11-c | About + licences | F11-b | ~400 | Risk: item 5 (licence tooling at build time) | About page, generated licence list, disclaimer in auth screens, help section. |
| F11-d | Retire Jinja: user modules | F2-F9 flipped | ~550 | Risk: item 2 + item 3 (login redirect; bookmarks/installed apps) | Redirect map, `login_view` to the app, standalone error pages, removal of user-module templates/routes, matrix + tests. |
| F11-e | Retire Jinja: admin + leftovers | F10 done, F11-d | ~450 | Risk: item 3 (removing legacy endpoints) | Remove `price_bp`, `price.html`, base layout, static/vendor leftovers, `legacy` nav status, `legacy-routes.json`, docs. |
| F11-f | Legacy schema cleanup (optional) | F11-e, D-F11-9 | ~250 | Risk: item 1 (drops columns) | One reversible revision dropping columns proven unused; backup-first deploy. |
| F11-g | E2E + axe harness | F11-d | ~600 | Risk: item 5 (new CI job and dev dependencies) | Playwright + axe, seeded SQLite command, CI job, route matrix at 2 widths × 2 roles. |
| F11-h | a11y fixes + audit report | F11-g | ~500 | Risk: item 6 (screen-reader checks are manual) | Fixes from the harness and §7.4 checklist, `docs/a11y-audit.md`, owner manual passes. |
| F11-i | Performance pass | F11-e | ~500 | Risk: item 1 if indexes are added | Budgets in `check:dist`, rendering fixes, query-count tests, indexes, Lighthouse record. |
| F11-j | Final docs | all above | ~300 | Risk: none | README, AGENTS.md, frontend/architecture docs, state.md, roadmap closure. |

## Open decisions

| ID | Question | Options | Recommendation | Blocks |
|---|---|---|---|---|
| D-F11-1 | Landing technology | second Vite entry (static HTML + small script) / Jinja restyled / route inside the SPA | Second Vite entry served by Flask at `/`: shared tokens and fonts, no Jinja left, fast first paint | F11-b |
| D-F11-2 | Landing content | keep all six feeds / real sources only | Real sources only: official news (if parsing works), upcoming public events (F8), decks only with a real source; drop Discord/videos placeholders | F11-a |
| D-F11-3 | Redirect type and lifetime | 301 / 302; keep forever / remove after N months | 301, keep the map permanently (tiny) | F11-d |
| D-F11-4 | E2E stack | Playwright Chromium in CI / manual only | Playwright in CI, Chromium only, no network | F11-g |
| D-F11-5 | Lighthouse thresholds and automation | thresholds above, manual / LHCI in CI | Manual run recorded in docs with the thresholds above | F11-i |
| D-F11-6 | Disclaimer wording, placement, translation | English only / English + Spanish | English verbatim + Spanish translation, landing + auth + About | F11-b, F11-c |
| D-F11-7 | Scroll animation (81 frames, ~5.3 MB) | keep / short video / drop | Replace with one optimised hero image (or drop) | F11-b |
| D-F11-8 | Delete legacy JSON endpoints | delete / keep for scripts | Delete (only Jinja used them); the API key (F9) covers scripts | F11-d, F11-e |
| D-F11-9 | Drop obsolete columns | now / never | Optional unit after F11-e, owner approves the list | F11-f |
| D-F11-10 | Landing language | ES only / ES + EN by browser language with toggle | ES + EN (browser language, toggle stored locally) | F11-b |
| D-F11-11 | Landing design (design-handoff §10-13) | from tokens / commissioned | From tokens; owner reviews screenshots | F11-b |

## Risks and notes

- **Bookmarks and installed apps** still point at Jinja URLs; the redirect map must cover every GET page
  (test enumerates the old rules from a frozen list).
- **Install prompt scope**: the landing is outside the manifest/worker scope, so the CTA links into the app
  instead of calling the prompt on `/` (F11-R2).
- **CSP**: the landing becomes a second HTML entry; F12's enforcing CSP must cover it (keep it free of inline
  scripts).
- **Order**: F11-d needs every user module flipped to `spa` (F2-F9); F11-e needs F10. If a module slips, its
  Jinja page stays and F11-d skips it (listed as follow-up).
- **Licensing**: the About page lists licences; the legal review of Riot IP and other assets is F12.
