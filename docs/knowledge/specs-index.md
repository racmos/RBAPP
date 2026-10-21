# Specs index: the formal contracts of F0 and F1

`openspec/` was the spec-driven (SDD) workflow used for phases F0 (foundation) and F1 (app shell). From
now on new work is specified in `docs/requirements/` (a phase spec per phase plus one requirement document
per unit, template `docs/requirements/TEMPLATE.md`). The specs listed here stay as the REFERENCE CONTRACT:
a new requirement must not break them, or must say explicitly which requirement it amends and why.

How to read a spec file: `### Requirement: <ID> <Title> [unit]` followed by MUST/SHOULD/MAY text and
Given/When/Then scenarios. Unit tags `[a]`..`[g]` say which delivery unit built it. `[MANUAL]` = checked by a
person, `[PG-CI]` = runs in the PostgreSQL CI job, `[vitest]` = frontend test, `[build]` = asserted over the
production build, `[GH-CI]` = only visible in GitHub Actions.

Two groups:
1. `openspec/specs/<capability>/spec.md`: 14 capabilities from F0, archived 2026-10-19, authoritative.
   Archive of that change: `openspec/changes/archive/2026-10-19-f0-foundation/`.
2. `openspec/changes/f1-app-shell/specs/<capability>/spec.md`: 10 F1 delta specs (ADDED or MODIFIED
   requirements). Implemented by units a to f and merged to `main` (PRs 18 to 24; PR 21 is the background
   fix, not a unit); unit g (optional CSP hardening, no new requirements) is pending. They are merged into
   `openspec/specs/` only when F1 is archived, so until then BOTH locations must be read: where a delta
   MODIFIES a requirement, the delta text wins over the F0 text.

Companion documents: `openspec/roadmap.md` (phases F0 to F12, Spanish), `openspec/design-handoff.md`
(prototype inventory, Spanish), `openspec/changes/f1-app-shell/design.md` (decisions D1 to D26, reconciliations
R1 to R12), `proposal.md`, `exploration.md`, `tasks.md`.

---

## A. F0 specs (authoritative): `openspec/specs/`

### access-control (`access-control/spec.md`)
Who may do what. Adds the `is_admin` and `is_blocked` flags (changed only by CLI), the admin guard on
catalog writes and every price route, the rule that every URL rule is classified P/U/A in a test matrix, the
admin CLI, an allow-list for Cardmarket download URLs, and the `admin_client` / `other_user_client` fixtures.
- ACL-1 Admin and block flags: two boolean columns with server defaults; nobody becomes admin by migration, env or input
- ACL-2 Blocked accounts lose access: no login, session cut on next request, same answer as a wrong password
- ACL-3 Admin guard: anonymous gets login/401 (never 403), non-admin 403, admin passes; lists the guarded routes
- ACL-4 Catalog stays readable; admin UI hidden: Sets and Cards GET stay open; Add/Edit/Price controls only for admins
- ACL-5 Authorization matrix: every rule in `url_map` classified exactly once; unclassified fails the suite
- ACL-6 Admin CLI: `flask users promote|demote|block|unblock`, idempotent, works with no admin, unknown user exits non-zero
- ACL-7 Cardmarket URL allow-list: loader overrides must be https on an allowed host, else 400 and no request
- ACL-8 Test fixtures: `admin_client`, `other_user_client`; the 93 baseline tests keep passing

### api-v1 (`api-v1/spec.md`)
The JSON API foundation under `/riftbound/api/v1`: one envelope for success and error, health and config
endpoints, the session/login/logout/register endpoints, and the rule for JSON versus HTML answers.
F1 modifies API-1, API-4, API-5 and adds API-9 (see section B).
- API-1 Blueprint and envelope: prefix, no clash with `/api/*` landing routes, every error uses the envelope, no leaks in 500
- API-2 GET /health: public, `SELECT 1`, 503 envelope when the DB is down
- API-3 GET /meta/config: captcha provider and `required_for`, `registration_open`, `env`; no secrets
- API-4 GET /auth/session: anonymous vs signed-in payload plus CSRF token; blocked user is anonymous
- API-5 POST /auth/login: shared service, lockout and limits with the form; 401, 429 with Retry-After, 400
- API-6 POST /auth/logout: authenticated only, 200 `{}`; anonymous gets JSON 401
- API-7 POST /auth/register: 201 without a session, 400/409/429 cases, captcha and validation rules
- API-8 JSON vs HTML negotiation: path prefix, JSON body or Accept decides; no Accept header means HTML

### app-config (`app-config/spec.md`)
Configuration comes only from environment variables and fails fast when unsafe. Covers `RB_ENV`, the
secret-key rules, when `.env` is read, engine options per database, `.env.example`, and the proxy hop count.
- CFG-1 No credentials in tracked code: `SECRET_KEY` and `DATABASE_URL` only from the environment
- CFG-2 Environment selection by RB_ENV: development, testing, production; unset means production
- CFG-3 Fail-fast validation after test overrides: weak or missing secret refuses to start; names variables, not values
- CFG-4 dotenv only in development: `.env` is read in development only
- CFG-5 Engine options follow the effective URI: `client_encoding=utf8` for PostgreSQL only, `pool_pre_ping` always
- CFG-6 .env.example and deployment docs: every variable listed with placeholders; the systemd unit uses `EnvironmentFile`
- CFG-7 Configurable proxy trust: `PROXY_FIX_X_FOR` and friends

### card-images (`card-images/spec.md`)
Where card images live on disk and how they are read and written safely.
- IMG-1 Folder derives from the filename prefix: `image_src` is `/riftbound/static/images/cards/<folder>/<image>`
- IMG-2 Upload cannot escape its folder: admin upload confined under `images/cards/`, letters and digits only
- IMG-3 Scraper writes where the UI reads: the Riot scraper uses the same folder rule

### ci-pipeline (`ci-pipeline/spec.md`)
The GitHub Actions contract. F1 MODIFIES CI-5 (the frontend job is no longer a placeholder) and adds CI-9.
- CI-1 No application secrets in CI: tests self-configure; no `DATABASE_URL` / `SECRET_KEY` in workflows
- CI-2 Single pinned Python and tooling: Python 3.12, `.python-version`, pinned bandit
- CI-3 Test job: install, `pytest` with coverage, on push to main and PRs
- CI-4 PostgreSQL migrations job: PostgreSQL service, upgrade, check, downgrade base, upgrade, seeded-data upgrade
- CI-5 Frontend placeholder job: (F0 text, hashFiles-guarded; superseded by the F1 delta)
- CI-6 Least-privilege permissions: `contents: read`, write only for the release job
- CI-7 Repository hygiene: stray root `package.json` and `diagnose.py` removed; `.gitignore` covers node and build output
- CI-8 Docs match reality: README and AGENTS state real versions, structure, commands

### collection-quantity (`collection-quantity/spec.md`)
`rbcol_quantity` as a real integer, and the collection write paths that depend on it.
- QTY-1 Integer storage via migration: text to integer 1..9999, aborts listing bad rows, CHECK `>= 1`
- QTY-2 Numeric ordering: sort by quantity is numeric
- QTY-3 Atomic merge on add: one SQL increment, no read-modify-write
- QTY-4 Validated CSV import: `set;card;foil;quantity` lines, invalid ones skipped and reported by line number

### csrf-protection (`csrf-protection/spec.md`)
CSRF on every unsafe method, with no exemptions.
- CSRF-1 Global protection of unsafe methods: header `X-CSRFToken` or form field, token valid for the session
- CSRF-2 Error format by client type: JSON envelope for API/JSON clients, HTML 400 for browsers
- CSRF-3 Forms and fetch calls carry the token: meta tag, `csrf.js`, hidden fields
- CSRF-4 Logout is POST-only: GET logout is 405; nav uses a form
- CSRF-5 Operator kill switch: `WTF_CSRF_ENABLED=false` for rollback; on by default outside testing

### db-migrations (`db-migrations/spec.md`)
Alembic through Flask-Migrate as the only schema builder, scoped to schema `riftbound`.
- MIG-1 Alembic via Flask-Migrate, schema-scoped: version table in `riftbound`, never touches `public`
- MIG-2 Baseline equals the dev snapshot: tables, constraints and indexes of the 2026-10-18 dev DB
- MIG-3 Stamp the existing dev database: adopt with `flask db stamp`, no DDL
- MIG-4 Legacy tables are backed up, then dropped: git-ignored SQL backup first; abort if it cannot be written
- MIG-5 rbdecks user FK repointed: to `rbusers(username)` before dropping; abort on orphans
- MIG-6 Models match the migrated schema (drift guard): `compare_metadata` empty; BigInteger/JSONB variants
- MIG-7 Both dialects, both directions: SQLite via batch operations, PostgreSQL-only DDL guarded
- MIG-8 Alembic is the only schema builder; legacy SQL archived: `run.py` no longer creates tables
- MIG-9 Pre-migration backup is documented: `pg_dump -n riftbound` and the restore path

### deck-viewing (`deck-viewing/spec.md`)
Correct, private-by-lookup deck viewing (visibility itself stays "every signed-in user sees every deck" until F5).
- DECK-1 have/missing use the viewer's collection: never the owner's
- DECK-2 Name lookup is scoped to the viewer: `/view/<name>[/<seq>]` resolves only the viewer's decks; others by id
- DECK-3 versions endpoint works: the current user's versions, newest first, no 500
- DECK-4 Dead legacy routes removed: the two always-failing deck routes are gone

### landing-feeds (`landing-feeds/spec.md`)
The public landing partials do not hammer their upstream sources.
- LAND-1 Cached feed items: six feeds cached per feed and per worker for `LANDING_CACHE_TTL` (default 300 s)

### login-protection (`login-protection/spec.md`)
Defences around the login and register screens: lockout, rate limits, captcha, shared validation.
- LOGIN-1 Lockout columns: `failed_login_count`, `locked_until`, `last_login_at`
- LOGIN-2 Account lockout: 5th consecutive failure locks 15 minutes; locked attempts do not extend it
- LOGIN-3 Escalating lock: doubles up to 24 h
- LOGIN-4 Success resets state: counters cleared; a lock does not kill a live session
- LOGIN-5 No account oracle: unknown and blocked users answer like a wrong password, same hashing work
- LOGIN-6 Unlock CLI: `flask users unlock <username>`
- LOGIN-7 Rate limits: login `10/minute;50/hour`, register `5/hour` per IP, 429 with Retry-After
- LOGIN-8 ALTCHA on register: signed, expiring, single-use proof of work with a shared replay store
- LOGIN-9 Input validation shared by Jinja and API: one Pydantic schema for register; login only needs non-empty

### price-resolution (`price-resolution/spec.md`)
Which Cardmarket price column a card is worth. This is the authority for the chain, which is NOT one
single order: premium (rare, epic, showcase) or foil uses `avg7_foil -> avg7 -> low_foil -> low`; everything
else uses `avg7 -> avg7_foil -> low -> low_foil`; NULL and 0 are missing; no price gives `None`.
- PRC-1 Fallback chain: the two orders above, pinned by table-driven tests
- PRC-2 One shared implementation: `app/services/pricing.py` used by the collection and deck views

### session-security (`session-security/spec.md`)
Cookie flags, local-run safety and key rotation. F1 MODIFIES SESS-1 (remember cookie).
- SESS-1 Session and remember cookie flags: HttpOnly, SameSite=Lax, Secure in production
- SESS-2 Debug off by default; local bind: `run.py` binds loopback with debug off
- SESS-3 Key rotation invalidates sessions: a cookie signed with another key is anonymous

### user-profile (`user-profile/spec.md`)
The profile update endpoint behaves as a well-formed API.
- PROF-1 Duplicate email is a client error: 409 `Conflict`, case-insensitive, data unchanged
- PROF-2 Password change needs the current password: 400 otherwise; e-mail-only updates do not
- PROF-3 Profile update stays authenticated: anonymous denied; invalid e-mail rejected by the schema

---

## B. F1 delta specs (implemented in units a to f): `openspec/changes/f1-app-shell/specs/`

### api-v1 (MODIFIED API-1, API-4, API-5; ADDED API-9) - unit c
Makes the error envelope extensible (`code`, `params`), puts `prefs` in the session payload and adds the
`remember` flag to login. All additive: F0 fields, statuses and tests stay valid.
- API-1 (modified) Blueprint and envelope: errors may carry `code` and `params`
- API-4 (modified) GET /auth/session: signed-in payload includes the five-key `prefs`
- API-5 (modified) POST /auth/login: optional strict-boolean `remember`; true issues the 30-day remember cookie
- API-9 (added) Error codes for F1 endpoints: the `ErrorCode` / `DetailCode` set, where each is returned

### app-shell (ADDED) - unit e
The signed-in frame of the SPA: layout, topbar, bottom navigation, "Más" sheet, navigation registry, home hub,
Interface page, standard states, axe coverage, and coexistence with the Jinja pages.
- SHELL-1 Layout and landmarks: skip link, header, one `main`, width caps
- SHELL-2 Topbar and branding: sticky, wordmark at `md`+, mark below, nav, ES/EN toggle, avatar, logout
- SHELL-3 Bottom navigation: at most five items below `md`, "Más" last
- SHELL-4 "Más" sheet: native `<dialog>` with Interface, legacy modules, language, install, Admin, logout
- SHELL-5 Navigation registry: statuses `spa`, `legacy`, `planned`; tested legacy URLs; admin-only entries
- SHELL-6 Home hub: launcher to the modules following the registry
- SHELL-7 Interface page: density, accent, background slider, language, collection view; live preview from `xl`
- SHELL-8 Standard states: Skeleton, EmptyState, ErrorState, route error boundary, in-shell 404
- SHELL-9 Axe on the shell: no violations at phone and desktop widths, sheet open
- SHELL-10 Jinja coexistence and rename: "Nueva app" link, product name "Rift Manager", landing unchanged until F11

### ci-pipeline (MODIFIED CI-5; ADDED CI-9) - units a and f
The frontend CI job is real (no skipped steps), uploads the build artifact and checks the manifest; frontend
hygiene rules.
- CI-5 (modified) Frontend job: `npm ci`, lint, typecheck, vitest, build with Node from `.nvmrc`, none skipped; uploads `frontend-dist`; from unit f a manifest check that fails the job on a mismatch (the real job also runs `check:dist` and the self-destroy build, see PWA-5)
- CI-9 (added) Frontend repository hygiene: dist, node_modules, `.vite` ignored; lockfile committed; no source maps or `.env` in the artifact; Python lane needs no Node

### design-system (ADDED) - unit a (DS-8 also e)
Tokens, theming, breakpoints, background, fonts, accessibility baseline, primitives, brand assets and the
toolchain pins of the frontend.
- DS-1 Tokens: handoff colour, radius, spacing, z-index tokens as layered CSS custom properties
- DS-2 Accent rule: `data-accent` cyan or orange drives every interactive state
- DS-3 Density: `data-density` compact or comfy; regular is the absence of the attribute
- DS-4 Breakpoints: sm 680, md 860, lg 960, xl 1240, 2xl 1600; single source; mobile-first; desktop shows more data
- DS-5 Background image, blur and slider: map slightly blurred, never brightened; `bgVars`; 0 removes it
- DS-6 Self-hosted fonts: Manrope and Space Grotesk, latin and latin-ext only
- DS-7 Accessibility and responsive baseline: WCAG 2.2 AA contrast, focus ring, 24 px targets, 11 px text, reduced motion, native dialog
- DS-8 Primitives: typed Button, Field, Input, Select, Switch, SegmentedControl, Slider, Panel, Icon, Modal, Toast and the rest
- DS-9 Brand assets: originals in `assets-src/brand/`, traced SVGs shipped, accessible name "Rift Manager"
- DS-10 Toolchain and pins: Vite 8, React 19, TypeScript 6.0.3, exact versions, `.npmrc`, Node floor

### frontend-auth (ADDED) - unit d
Sign-in, registration and session handling in the SPA, sharing the session cookie with Jinja.
- FAUTH-1 Session boot: `GET /auth/session` before any guarded route; CSRF token in memory only
- FAUTH-2 Login flow: labelled fields, "Remember me" on by default, redirect through `safeNext`
- FAUTH-3 Register flow: config and captcha fetched; ALTCHA widget loaded lazily only here
- FAUTH-4 ALTCHA reset after any register error: new challenge and remount, payload is single-use
- FAUTH-5 Logout: 200 and 401 both sign out locally; other failures keep the user in with a toast
- FAUTH-6 CSRF retry once: refetch the session and repeat the request exactly once
- FAUTH-7 401 and 429 handling: 401 goes to `/login?next=...`; 429 shows a countdown from Retry-After
- FAUTH-8 Route guards: `requireAuth`, `requireAnon`, `requireAdmin` (UX only)
- FAUTH-9 safeNext: only same-origin paths under `/riftbound/`; router vs full-page navigation
- FAUTH-10 Auth screen accessibility: labels, autocomplete values, described errors, focus handling
- FAUTH-11 Shared session with Jinja: one session, logout in either ends both

### i18n (ADDED) - unit d (toggle UI unit e)
Spanish and English catalogs and everything that depends on the active language.
- I18N-1 Bundled catalogs with parity: namespaces `common`, `nav`, `auth`, `errors`, `prefs`; parity test
- I18N-2 Language resolution: account preference, `rb_lang`, browser language, `es`
- I18N-3 Document effects and formatting: `<html lang>`, title format, `es-ES` / `en-GB` Intl formatting
- I18N-4 Server errors translated by code: code, then API message, then generic text (implemented as the key `errors:code.<code>`; the spec text says `errors.<code>`)
- I18N-5 No missing keys at runtime: typed resources, fallback to `es`, never the raw key

### pwa (ADDED) - unit f
Installable app, service worker, update prompt, rollback and offline shell.
- PWA-1 Manifest identity and scope: name, `id`/`scope` `/riftbound/`, `start_url` `/riftbound/app/`, `#06222c`
- PWA-2 Icons: 192, 512, maskable 512, apple touch 180, favicon; generated and committed
- PWA-3 Service worker scope and precache: `/riftbound/app/sw.js`, app shell only, navigation fallback allow/deny lists (the build precaches three background images; the text says "both variants")
- PWA-4 Prompt-based update: new worker waits; "Nueva versión" toast; hourly and on-visible checks
- PWA-5 Rollback by self-destroying SW: documented build mode; a plain revert is not a rollback
- PWA-6 Install entry: `beforeinstallprompt` item; iOS instructions dialog
- PWA-7 Offline shell and banner: shell opens from the precache; read-only offline; offline boot with the signed-in hint
- PWA-8 Session persistence in the installed app: "Remember me" keeps the user in for 30 days
- PWA-9 Installability verification: Lighthouse and device checks recorded in the PR (manual items)

### session-security (MODIFIED SESS-1) - unit c
- SESS-1 (modified) Session and remember cookie flags: the remember cookie is really issued when login sends `remember: true` (30 days, absolute) and never otherwise; the Jinja form never remembers

### spa-hosting (ADDED) - unit b
How Flask serves the built SPA at `/riftbound/app/`.
- HOST-1 Mount point and trailing-slash redirect: `FRONTEND_DIST`, `/riftbound/app` redirects, routes are public
- HOST-2 Cache rules: `assets/*` immutable; `index.html`, `sw.js`, `workbox-*.js`, manifest `no-cache` with ETag
- HOST-3 Extension-aware catch-all: no extension gets `index.html`; a missing file with an extension is a real 404
- HOST-4 Manifest mimetype: `application/manifest+json`
- HOST-5 Missing build returns 503: only `/riftbound/app/` is affected; the app still starts
- HOST-6 No secrets in the shell document: static `index.html`, no cookies on SPA responses
- HOST-7 Configuration and docs: `FRONTEND_DIST` documented; Nginx unchanged (two `proxy_pass` lines)

### ui-preferences (ADDED) - units c (PREF-1..5) and e (PREF-6..8)
Account-level interface preferences stored on the server (`NULL` = Auto) and applied by the SPA.
- PREF-1 Storage in rbuserprefs: table, columns, CHECKs, migration `0006_user_prefs`
- PREF-2 Allowed values: lang es|en; density compact|regular|comfy; accent cyan|orange; bg_intensity 0..100; collection_view table|grid
- PREF-3 GET /me/prefs: five keys, never creates a row, JSON 401 for anonymous
- PREF-4 PATCH /me/prefs semantics: absent = unchanged, `null` = Auto, invalid = 400, all-or-nothing, `{}` accepted
- PREF-5 Session carries prefs: `GET /auth/session` reflects the stored values
- PREF-6 Client defaults and Auto resolution: below 860 px compact and grid, else regular and table; orange; background 100
- PREF-7 Applied before first render: `rb_prefs_v1` mirror applied to `<html>` before React; server copy wins later
- PREF-8 Saving behaviour: optimistic, debounced slider, revert with a toast on failure

---

## C. Reading notes: where the specs and the code differ or have gone stale

- F0 `ci-pipeline` CI-5 still describes the hashFiles-guarded placeholder job; the real job is in the F1 delta
  and `.github/workflows/ci.yml`.
- F0 `api-v1` (API-1, API-4, API-5) and `session-security` (SESS-1) are superseded by their F1 deltas.
- I18N-4 names the catalog key `errors.<code>`; the code uses `errors:code.<code>` (namespace `errors`, group
  `code`). The catalogs and the contract test follow the code.
- PWA-3 says the precache holds "both" background images; the build precaches three (1280, 1920, portrait).
- `openspec/config.yaml` still carries F0-era context (93 baseline tests, "frontend not present yet").
- `openspec/changes/f1-app-shell/state.yaml` still says `apply: pending` (last updated 2026-10-19) although units
  a to f are merged; `tasks.md` names branches `feat/f1-a`..`feat/f1-g` while the real ones are
  `feat/f1a-frontend-toolchain` ... `feat/f1f-pwa`.
- Several F0/F1 spec scenarios are tagged `[MANUAL]` (rollback rehearsal, device installs, Lighthouse); they
  are not in any automated lane.
- Product decisions that are not specs yet (per-mode bans, deck formats v2, selling model, push alerts) live
  in `docs/knowledge/product.md` and will become phase specs under `docs/requirements/`.
