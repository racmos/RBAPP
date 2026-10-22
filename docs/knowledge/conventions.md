# Conventions: rules every change must follow

Each rule below was checked against the code, the tests, the CI files or the project documents.
"Enforced by" names the test or tool that fails when the rule is broken; a rule without one is a
convention held by review. Read `AGENTS.md` too: it is the project rulebook and this file does not
repeat everything in it. Architecture and file locations: `docs/knowledge/architecture.md`.

## 1. General

- Work in small units: one requirement document = one feature branch = one PR.
- Strict TDD on both lanes (`strict_tdd: true` in `openspec/config.yaml`, "Strict TDD" in `AGENTS.md`).
  See section 3.
- Documents, comments and commit messages are in English. UI text exists in Spanish AND English
  (section 5). Card names and abilities are data and are not translated.
- Do not add what was not asked: no new library, folder or feature outside the requirement. A new
  dependency is a decision for the owner (section 5, pins).
- A requirement that touches an existing contract (anything in `openspec/specs/`) must keep it or amend it
  explicitly. See `docs/knowledge/specs-index.md`.
- Preserve each file's line endings (section 8). New files use LF.
- Never write a secret, password, token, DSN, IP address or host name into code, tests, docs, commit
  messages or PR text. Refer to "the dev server".

## 2. Git, branches and pull requests

- Work in a git worktree created from an up-to-date `origin/main`; never switch branches in the deployed
  checkout (it serves the dev app; see `docs/knowledge/workflow.md` and `ops-runbook.md`). Never commit to or
  push `main`. The user merges; an agent never merges.
- Branch names used so far: `feat/f1a-frontend-toolchain`, `feat/f1b-spa-hosting`, `feat/f1c-api-prefs`,
  `feat/f1d-frontend-auth`, `feat/f1e-app-shell`, `feat/f1f-pwa`, `fix/f1-bg-portrait`, `docs/f1-planning`,
  `chore/f0-archive`. Pattern: `<type>/f<phase><unit letter>-<slug>` for unit work.
- Commits use Conventional Commits with a scope and the unit in the subject, for example
  `feat(frontend): installable PWA, icons, update prompt, offline shell (F1 unit f)`. Types seen: `feat`,
  `fix`, `docs`, `chore`, `test`. The body lists what changed and ends with the test counts
  ("vitest 1051 -> 1181; pytest 1634 -> 1640").
- Commit messages and PR descriptions end with the attribution lines the session supplies.
- Push and PR creation happen only when the user says so (`docs/requirements/TEMPLATE.md`, "Delivery").
- PR title: `<type>(<scope>): <summary> (F<n> unit <x>)`. PR body: summary, a map from each spec or
  requirement to the test that proves it (`S3 -> tests/test_x.py::TestY::test_z`), manual checks left for
  the user, rollback.
- Practice so far: a defect found after a unit merged is fixed in its own small PR (example:
  `fix/f1-bg-portrait`), not hidden in the next feature PR.

## 3. Test-driven development

- Write the failing test first and RUN it to see it fail for the right reason (RED) before writing the
  code (GREEN). Record the RED evidence in the PR (for example "4 failed in `src/test/pins.test.ts`").
- A step that cannot be RED (pure bootstrap such as the first toolchain files) is labelled as such in
  the PR; it is the exception.
- Characterisation tests ("CHAR") come first when a change touches legacy behaviour: pin what the code
  does today with a test that PASSES before the change, then change the code. Examples already in the repo:
  `tests/test_shell_coexistence.py::TestLandingIsUntouched` and `TestPagesList`, the table-driven price tests
  of `tests/test_pricing.py`. If an existing assertion must change, list it in the PR.
- A bug fix starts with a test that reproduces the bug.
- Existing tests are never deleted or weakened to make a change pass.
- Backend tests: pytest, SQLite in memory, nothing may reach the internet (the authz matrix test replaces
  `requests.Session.request` with a recorder that raises). Frontend tests: Vitest in jsdom, MSW with
  `onUnhandledFrame: 'error'` (an unmocked request fails the test).
- The Python lane never needs Node (HOST tests use a temporary dist: fixtures `spa_dist`, `spa_app`).
- Coverage by requirement: every MUST has a test or an explicit "manual" label with the check written down.

## 4. Backend

### Structure and style
- Routes are thin; logic goes in `app/services/` (no Flask request objects there). Read the patterns in
  `app/routes/domains/` and `app/services/` before writing.
- PEP 8, type hints where useful. `db.session.commit()` after writes.
- New code gets time from `app.utils.clock.utcnow()` called through the module
  (`from app.utils import clock`), never `from ... import utcnow`, so tests can freeze it
  (`frozen_clock`). Older collection and deck routes still use `datetime.utcnow()`; do not copy that.
- Keep URLs under `/riftbound`; only the landing page and its partials (`/`, `/api/*`, `/frames/*`) live
  outside it. New JSON API routes go in the
  `api_v1` blueprint (`/riftbound/api/v1`); nothing may shadow `/riftbound/app/` (a test checks no existing
  rule lives under that prefix).

### Requests, responses, errors
- Every endpoint that receives JSON uses `@validate_json(Schema)` and reads `request.validated_data`. The
  schema goes in `app/schemas/validators.py`.
- API v1 answers with `ok(...)` / `fail(...)` from `app/api/responses.py`: `{success, data, meta}` or
  `{success: false, error, message, details?, code?, params?}`. Legacy endpoints keep their flat
  `{"success": true, ...}` shape; do not change an existing legacy response shape without a requirement.
- Error `code`s are a contract: add the `ErrorCode` / `DetailCode` value, the `code.<value>` (or
  `validation.<value>`) entry in BOTH `frontend/src/i18n/locales/{es,en}/errors.json`, and keep
  `tests/test_frontend_contracts.py` green. Enforced by that test.
- Codes are additive and lowercase snake_case; `params` are JSON scalars; no secrets, stack traces or
  internals in `message`, `code` or `params`.
- 500 responses never include exception text. Log the exception, return the generic message. (Some old
  admin endpoints still leak `str(e)`; do not copy them.)
- An error response must follow `wants_json()`: JSON for `/riftbound/api/` paths, JSON bodies and
  `Accept` preferring JSON; HTML otherwise.

### Authorization and data scope
- Classify every new URL rule as P, U or A in `tests/test_authz_matrix.py` (`MATRIX`). An unclassified rule
  fails the suite and names the rule. Enforced by that test.
- All routes except login, register, the landing page, the SPA host and the public API endpoints require
  login. Admin routes use `@admin_required` (or a blueprint `before_request(require_admin)`);
  anonymous callers are redirected to login or get a JSON 401, never 403; signed-in non-admins get 403.
- `is_admin` and `is_blocked` change only through `flask users ...`; never from request input, a migration or an
  environment variable.
- Never trust ids from the client. Collection and deck queries are scoped to the signed-in user by
  `current_user.username` (collection rows use the helper `_get_owned_row`, which 404s on someone else's row).
  Deck name lookups only resolve the viewer's own decks; opening another user's deck is by id only.
- Every `POST`/`PUT`/`PATCH`/`DELETE` needs the CSRF token (`X-CSRFToken` header or `csrf_token` form
  field). There are no exemptions, the API included. Never exempt a view.
- Sensitive endpoints (login, register and any new one open to anonymous callers) get a Flask-Limiter limit;
  the Jinja form and the API of the same action share one `scope`.
- File uploads and image paths go through `app/services/card_images.py`. Outbound URLs chosen by a user or an
  admin go through an allow-list (`CARDMARKET_ALLOWED_HOSTS`, https only).
- Passwords: Werkzeug hashing, 8 to 128 characters, one rule everywhere (`PASSWORD_MIN_LENGTH`).

### Database and migrations
- Alembic is the only schema builder (`db.create_all()` is for tests only). Change the model and the
  migration in the same commit; `tests/test_migrations.py` fails when they disagree (drift guard).
- Workflow: `flask db migrate -m "..."`, READ and edit the generated file, `flask db upgrade`,
  `flask db check` (must say "No new upgrade operations detected."), `flask db downgrade -1`.
- Every revision is reversible and runs on SQLite and PostgreSQL: ALTERs through
  `op.batch_alter_table(..., schema='riftbound')`; PostgreSQL-only DDL behind
  `op.get_bind().dialect.name == 'postgresql'`.
- Revision ids are readable (`0007_<what>`), `down_revision` linked, constraints and indexes explicitly
  named (the models declare the same names).
- A revision that converts or deletes data validates first and aborts, changing nothing, with a message
  listing the offending rows (pattern: `0003`). Back up before upgrading a real database; never run a
  migration against the dev database without the backup step in `docs/migrations.md`.
- Naming: tables `rb<name>`, columns `rb<table>_<name>` (except `rbusers`), models `Rb<Name>` (the user model
  is `User`), schema `riftbound`, `__table_args__` carries `{"schema": "riftbound"}`; import new models in
  `app/models/__init__.py`. Quantities and money are numeric columns, never text.
- JSON columns use `JSON().with_variant(JSONB(), 'postgresql')`; `BigInteger` primary keys need a SQLite
  variant (see `rbcol_id`).
- The PostgreSQL tests (`pytest -m postgres`) need a database whose name contains `test`; they drop schema
  `riftbound` before and after each test. Never point them at dev data.
- Backups and dumps contain personal data (e-mails, password hashes): git-ignored, never committed or pasted.

### Dependencies
- Python packages are pinned with `==` in `requirements.txt`. If you change a backend pin, update the table in
  `AGENTS.md` (enforced by `tests/test_docs.py::TestAgentsVersions`).
- Security scan: `bandit -r app/ -ll` must stay clean (CI runs it on pushes to `main` and daily).

## 5. Frontend

### Dependencies and toolchain
- Node 24 (`.nvmrc`), npm. Dependencies are exact (no `^` or `~`); `frontend/.npmrc` sets `save-exact=true` and
  `engine-strict=true`; `package-lock.json` is committed. Enforced by `src/test/pins.test.ts`.
- Install with `npm install --save-exact --before=<date>`, where the date is the cutoff for "newest release
  published on or before that day". F1 used a cutoff about two weeks before the installation day (cutoff
  2026-10-05, verified 2026-10-19/21 with `npm view <pkg> time --json`) and refused newer releases that
  peer ranges or churn made risky (the "too new, do not pin" list in
  `openspec/changes/archive/2026-10-22-f1-app-shell/exploration.md`). The two-week gap is a practice, not a tool setting:
  `.npmrc` does not enforce it. Note npm reads the date as local midnight.
- A new dependency also goes into the REQUIRED set of `src/test/pins.test.ts` (transitive ones that must
  land on a version go into `LOCK_ONLY`). Record the chosen versions and publish dates in the PR.
- TypeScript stays at 6.0.3 (typescript-eslint peers); `altcha` in `package.json` must equal the Python pin
  (enforced by `tests/test_frontend_contracts.py::TestAltchaPin`).
- Prettier: single quotes, trailing commas, print width 100. Run `npm run lint` (ESLint + `prettier --check`).

### Code structure
- Only `src/api/client.ts` calls `fetch`. Every server call goes through `request()` / `src/api/endpoints.ts`
  with types in `src/api/types.ts`.
- The CSRF token lives only in the module variable of `src/api/csrf.ts`; never in `localStorage`,
  `sessionStorage` or a cookie. Browser storage goes through `src/lib/storage.ts` (it never throws) and holds
  only conveniences: `rb_lang`, `rb_prefs_v1`, `rb_was_signed_in`, `rb_chunk_reload`.
- Server state lives in TanStack Query (`['session']` is the account); do not add a second store for
  server data. Never persist passwords or tokens client-side.
- Folder boundaries are enforced by ESLint (`no-restricted-imports`): `lib` and `styles` are pure;
  `components/ui` imports only `lib` and the i18n hook; `api` imports only `lib`; features (`auth`, `prefs`,
  `i18n`, `pwa`) import other features only through their `index.ts` and never `shell`, `account` or `app`;
  `shell` and `account` never import `app`; only `app/` wires everything. Use the `@/` alias across
  folders, never `../`.
- Route modules load lazily (`lazy`). `altcha` is imported only by the register route (check-dist fails if it
  ends up in the entry chunk).
- Dev-only code is guarded by `import.meta.env.DEV` (the `/_kitchen` route) so the build drops it.
- No inline `<script>` in the SPA (the F1 design keeps the door open for a CSP) and no third-party font
  hosts (`check-dist` fails on `fonts.googleapis.com` / `fonts.gstatic.com`). Fonts are self-hosted.
  (The legacy Jinja `base.html` still loads Font Awesome from a CDN; that is not a pattern to copy.)
- Use the existing UI primitives in `src/components/ui/` (list in `architecture.md`, section 7.8) and extend
  them when a phase needs more; do not hand-roll a second button, field, modal, toast or empty state.
- Module navigation comes from `src/shell/navRegistry.ts` (single list for topbar, bottom nav, "Más" sheet and
  hub); do not add a second list of modules. To port a module, flip its entry from `legacy` to `spa`, add the
  route, add `nav.json` labels (both languages). `legacy-routes.json` is checked against the Flask `url_map` by
  `tests/test_frontend_contracts.py::TestLegacyRoutes`; its key set must equal `LEGACY_ENDPOINTS` there.
- Edits are disabled while offline: use `useOffline()` from `@/auth`. Offline in F1 is shell only; do not add
  runtime caching of `/riftbound/api/*`, `/riftbound/static/*` or Jinja pages to the service worker without a
  requirement (PWA-3).
- Dates, numbers and money use `src/lib/format.ts` (`es-ES` / `en-GB`, EUR); money is EUR only.

### Internationalisation
- Every user-visible string goes through i18n, in BOTH `src/i18n/locales/es/*.json` and `.../en/*.json`.
  Spanish is the typed source (a missing key fails `npm run typecheck`).
- English must have the same keys, the same `{{placeholders}}` and the plural forms the language needs
  (`Intl.PluralRules`). Enforced by `src/i18n/parity.test.ts`.
- A new namespace is added in `src/i18n/resources.ts` (import both files, `NAMESPACES`, both `resources`
  objects). Existing: `common`, `nav`, `auth`, `errors`, `prefs`.
- `aria-label`s, `alt` text, toasts and `document.title` (via `useDocumentTitle`) are strings too.
- The product name "Rift Manager" is never translated.

### CSS, layout and accessibility
- CSS cascade layers: `@layer reset, tokens, base, layout, components, utilities`. Every `*.module.css` wraps
  ALL its rules in `@layer components { ... }` (unlayered CSS beats every layer). Enforced by
  `src/styles/layer-scan.test.ts`.
- `@media` widths come only from `src/lib/breakpoints.ts` (`sm` 680, `md` 860, `lg` 960, `xl` 1240, `2xl`
  1600, and each minus 0.02 for `max-width`). Enforced by `src/styles/media-scan.test.ts`. Mobile-first.
- Use design tokens (`var(--accent)`, `--panel`, `--gap`, `--row-h`, ...), not hard-coded colours; interactive
  tints derive from `--accent` with `color-mix`, never the literal cyan. Dark mode only.
- On desktop (`md` and above) a layout must show more data (extra columns, side panels, a second column), not
  just stretch the phone layout (DS-4). The Interface page adds its live preview from `xl` (1240 px).
- The background is never brightened, and body text keeps at least 4.5:1 contrast over it (worst-case tests in
  `src/lib/background-contrast.test.ts`). Text/background token pairs are tested in `src/lib/contrast.test.ts`;
  a new text/background pairing needs a row in that test.
- WCAG 2.2 AA baseline: visible text at least 11 px, interactive targets at least 24x24 CSS px, global
  `:focus-visible` ring on the accent, no bare `outline: none`, `backdrop-filter` always with a solid
  background fallback, `prefers-reduced-motion` honoured, `100dvh` and safe-area insets for full-height
  layouts. Enforced by `src/styles/a11y.test.ts`.
- Every screen gets a `vitest-axe` test with no violations. Today: login, register, the Interface page, and
  the shell at phone and desktop width with the "Más" sheet open (`src/shell/axe.test.tsx`); a new route adds
  its own (the audit of remaining gaps is task 7.3 of the pending unit g). Overlays use the native
  `<dialog>` primitives.
- Status text that appears dynamically is announced through `LiveAnnouncer` / `announce()` or a `role="status"`
  region; field errors are tied with `aria-describedby`; focus moves to the first invalid field after a failed
  submit.
- A page that throws must keep the topbar (it renders under `ShellError`); give new pages loading
  (`Skeleton`), empty (`EmptyState`) and error (`ErrorState` with retry) states.

### Build and PWA
- `npm run build` is `tsc -b && vite build`; `npm run check:dist` must pass on the result (manifest, icons,
  head tags, precache, `altcha` chunking, no third-party fonts, layer order).
- Touching `pwa-options.ts`, `vite.config.ts`, icons or the service worker also needs the self-destroying
  build to pass: `VITE_PWA_SELF_DESTROY=true npx vite build --outDir <tmp> --emptyOutDir` then
  `node scripts/check-dist.mjs --self-destroy <tmp>` (CI runs both).
- PWA icons in `frontend/public/` and the traced brand SVGs are committed; CI only checks them. Regenerate with
  `npm run icons` / `npm run brand:trace` only when the brand mark changes.
- A plain revert of the frontend is NOT a PWA rollback. Use the self-destroying build first
  (`docs/frontend.md`, "Rolling back the PWA").

## 6. Documentation

- Update `AGENTS.md` when the structure, commands, endpoints, tables or conventions change. `tests/test_docs.py`
  checks that: stated backend versions equal `requirements.txt`; every path in the "Project Structure" tree
  exists; every table and blueprint is named; key commands are present; no private IP address appears in
  `AGENTS.md` or `README.md`.
- `README.md` must mention every variable of `.env.example` (`tests/test_docs.py::TestReadme`). A new setting goes
  in `config.py`, `.env.example` and the README together.
- `docs/frontend.md` carries the frontend runbook; `tests/test_frontend_contracts.py::TestDocs` pins the
  rollback, service-worker and checklist sections. `docs/migrations.md` carries the migration runbook.
- `docs/nginx_config` keeps exactly two `proxy_pass` lines and the headers CSRF and ProxyFix need
  (`tests/test_nginx_config_doc.py`).
- Each unit updates `docs/knowledge/state.md` in its own PR (what changed, PR number placeholder, new
  follow-ups, known issues). Deploy and rollback steps live in `docs/knowledge/ops-runbook.md`; owner decisions
  in `docs/knowledge/product.md` (a change to a decision is recorded there and in `state.md`).
- Requirements for new work live in `docs/requirements/F<n>/` (template `docs/requirements/TEMPLATE.md`, cycle in
  `docs/knowledge/workflow.md`); `openspec/specs/` stays the contract that new requirements must not break.

## 7. Security and secrets

- Settings come only from environment variables (`config.py`). `.env` is git-ignored and read only when
  `RB_ENV=development`. Never commit, print, paste or log `.env` or any value from it.
- No credential, DSN, IP address or host name in code or docs. Examples in documents use placeholders such as
  `postgresql+psycopg://user:password@host:5432/riftbound`.
- CI never receives application secrets: no `DATABASE_URL`, `SECRET_KEY` or `FLASK_ENV` in any workflow, and
  no `secrets.*` for them (`tests/test_ci_workflows.py`). The PostgreSQL job uses `RB_ENV=development` so the
  process generates a random key.
- The kill switches (`WTF_CSRF_ENABLED`, `RATELIMIT_ENABLED`, `CAPTCHA_PROVIDER=none`) exist for rollback only;
  never turn them off to make a test or a feature pass. Tests that need a protection use `csrf_app`,
  `limited_app` or `altcha_app`.
- Anything that grants admin goes through the CLI. There is no password recovery by e-mail; the admin resets
  passwords with `flask users set-password`.
- Cookies stay HttpOnly and SameSite=Lax; `Secure` in production. Do not weaken `Referrer-Policy:
  strict-origin-when-cross-origin` on SPA responses (the CSRF Referer check needs it) and never send
  `no-referrer` from the client.

## 8. Line endings

53 tracked files are CRLF and `.gitignore` has mixed endings; everything else is LF. There is no
`.gitattributes` and no `core.autocrlf`, so the files are stored as they are.

Preserve each file's line endings. Editing tools and scripts may silently convert them, which turns a
3-line change into a whole-file diff. After editing a CRLF file, check that the diff shows only your lines
(`git diff --stat`) and `git ls-files --eol <file>` still says `crlf`.

List them with `git ls-files --eol | grep -E 'i/(crlf|mixed)'`. The CRLF set today:
- root: `.env.example`, `AGENTS.md`, `README.md`, `config.py`, `pytest.ini`, `run.py`, `wsgi.py`
  (`.gitignore` is mixed);
- docs and SQL: `docs/nginx_config`, `docs/riftbound.service`, `migrations/legacy_sql/database_setup.sql`;
- app Python: `app/__init__.py`, `app/errors.py`, `app/models/{__init__,card,collection,market,set,user}.py`,
  `app/routes/{auth,routes}.py`, `app/routes/domains/{__init__,cards,profile,sets}.py`,
  `app/schemas/{__init__,validation}.py`;
- templates: `base`, `cards`, `deck`, `deck_view`, `login`, `profile`, `register`, `sets`, `errors/*`,
  `landing/components/*`; static: `app/static/css/style.css`, `app/static/landing/js/camera-scroll.js`;
- tests: `tests/__init__.py`, `tests/conftest.py`, `tests/test_routes.py`.

LF (do not convert): all of `frontend/`, `app/api/`, `app/cli/`, `app/services/`, `app/utils/`,
`app/schemas/{validators,prefs_domain}.py`, the newer models (`deck`, `cardmarket`, `captcha`, `prefs`),
`app/routes/{landing,spa}.py`, `app/routes/domains/{collection,deck,price}.py`, `migrations/versions/`, the other
`docs/*.md`, `openspec/`, `.github/`, and every test file except the three above.

## 9. Known traps

Verified in the code or tests:
- `admin_client` and `other_user_client` log in through the real form: request them BEFORE `csrf_app`, or the
  login needs a token (comment in `tests/conftest.py`).
- `login_as` is a plain function in `tests/conftest.py`, not a fixture: `from tests.conftest import login_as`.
- The PostgreSQL tests refuse a database whose name lacks `test` and are skipped without `TEST_POSTGRES_URL`;
  41 tests are skipped in a normal run for that reason.
- A raw psycopg connection from a script needs `client_encoding=utf8`; the app sets it itself in
  `config.engine_options` (PostgreSQL only; SQLite rejects the option).
- SQLite does not enforce the `ON DELETE CASCADE` of `rbuserprefs` (the app never turns on foreign keys there);
  the cascade is tested on PostgreSQL only.
- `rbcol_selling` allows `'S'` in the database CHECK but the application accepts only `'Y'` and `'N'`;
  `rbcar_banned` is a single `'N'`/`'S'` flag for the card, not per game mode.
- `validate_json` turns any non-validation exception while reading the body into a 400 "Bad Request" with the
  exception text; and a non-JSON content type is a 400 without a `code`.
- `tests/test_authz_matrix.py` asserts `price.*` has exactly 23 rules; adding a price route means updating that
  count together with the classification.
- The built `dist/.vite/manifest.json` (from `build.manifest: true`) is public and harmless: it lists chunks.
- `vite-plugin-pwa` writes seven entries twice into the precache of `sw.js` (the manifest and six icon or
  favicon files: once from the glob, once from `includeAssets`). Harmless; `state.md` plans to clean it in F1-g.
- The frontend build empties `frontend/dist` first, so `/riftbound/app/` answers 503 for a few seconds during a
  rebuild on the server (build into a temp dir and `mv` to avoid it).
- `VITE_PWA_SELF_DESTROY` is a build-time variable; a normal `npm run build` never produces the rollback worker.

Recorded as known issues in `docs/knowledge/state.md`, not asserted by a test (re-check before relying on them):
- The Vitest toast test "removes a toast after its duration" (`src/components/ui/Toast.test.tsx`, fake timers
  with `shouldAdvanceTime`) can be timing-flaky under heavy machine load; re-run it before assuming a regression.
- `frontend/src/assets/brand/mark.svg` and `wordmark.svg` are not byte-reproducible from `brand-trace.mjs`
  (the script output needs a human review and the committed files are the reviewed ones). Do not regenerate
  them as a side effect.

## 10. Definition of done

A unit is done when ALL of this is true:
1. Every requirement in the unit's document has a test (or a written manual check) and each test was seen RED
   before GREEN.
2. Backend lane green: `venv/bin/pytest` (SQLite). With a migration also: `flask db upgrade`,
   `flask db check`, `flask db downgrade -1` and upgrade again on a throw-away database; if you can, run
   `TEST_POSTGRES_URL=... venv/bin/pytest -m postgres` against a database whose name contains `test`.
3. Frontend lane green, from `frontend/`: `npm run lint && npm run typecheck && npx vitest run && npm run build &&
   npm run check:dist`. When PWA files changed, also the self-destroying build and its check (section 5).
4. Docs updated: `AGENTS.md` (tree, tables, endpoints, conventions as needed), `docs/frontend.md` or
   `docs/migrations.md` when their subject changed, `.env.example` and `README.md` for a new setting, the
   authz matrix for a new route, both i18n catalogs for new text.
5. `docs/knowledge/state.md` updated.
6. No secret, IP address or host name was added; `git status` shows no `.env`, backup, `dist` or build output.
7. The diff for each CRLF file contains only the intended lines.
8. Commits follow section 2; the PR has the spec-to-test map, manual checks for the user and a rollback line.
   The user merges.
