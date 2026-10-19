# Tasks: F1 App Shell (roadmap F1 "Estructura app")

Mode: openspec · Strict TDD ON (RED then GREEN then REFACTOR, test task first) · Python lane `venv/bin/python -m pytest` (F0 baseline must stay green) · Frontend lane `cd frontend && npx vitest run`.
Seven units = seven PRs, branch `feat/f1-<unit>` from the updated `main`. Unit 0 is user prerequisites.
Order: a, b, c in parallel (separate branches or worktrees; they touch disjoint files except `AGENTS.md`/`README.md`, so rebase docs last) then d (needs a+b+c), e (needs d), f (needs a+b+e), g (optional, needs f).

**Legend**
- `RED` failing test first (run it, see it fail for the right reason) · `GREEN` minimal code, names the RED it turns green · `REFACTOR` · `CHAR` characterization test: pins current behaviour, MUST pass on unchanged code.
- `USER` only the user can do it · `[MANUAL]` device/browser/ops check · `[PG-CI]` runs in the `migrations-pg` job · `[GH-CI]` observable in GitHub Actions · `[P]` can run in parallel with the previous task (disjoint files).
- `(HOST-1)` = spec requirement · `D7` = design decision · `R3` = reconciliation item below.
- Bootstrap exception: tasks that only create tooling (1.2, 1.3) have no RED; the first RED of the frontend is 1.4.

## Reconciliation: orchestrator decisions (all design recommendations ACCEPTED, 2026-10-19)

| ID | Divergence | ORCHESTRATOR DECISION | Unit |
|---|---|---|---|
| R1 | PREF-6 "at most 860 px" vs DS-4 mobile-first | Phone = below 860 px everywhere (`down('md')`, max-width 859.98px). DS-4 wins; PREF-6 amended to "below 860 px" | a, e |
| R2 | FAUTH-7 scenario uses `/collection` (legacy, not an SPA route) | Scenario uses `/account/interface`, `next=%2Friftbound%2Fapp%2Faccount%2Finterface` (absolute) | d |
| R3 | SHELL-3 "four primary SPA destinations" | Bottom nav may hold legacy links: Inicio, Cartas, Colección, Mazos, Más; each flips to `spa` as its phase lands | e |
| R4 | `rb_prefs_v1` vs `rb_lang` | Keep both: mirror = copy of account prefs; `rb_lang` = device choice, written by the toggle and on logout. Order of D14/§4.5 | d, e |
| R5 | DS-5 `image-set` chooses by density | Width media query (`max-width: 859.98px` selects the 1280 px image); DS-5 amended | a |
| R6 | API-9 codes also touch legacy JSON endpoints | Codes added in `validate_json` and in the global CSRF/429/unauthorized handlers, additive keys only; record in archive notes | c |
| R7 | DS-2/DS-3 "computed styles" in jsdom | Assert on CSS source (postcss), not `getComputedStyle` | a |
| R8 | `.npmrc` location | `frontend/.npmrc` | a |
| R9 | CI-5 tagged `[e]` but placeholder test breaks in unit a | Guard removal + test rewrite in unit a; manifest check in unit f. CI-5 retagged `[a][f]` | a, f |
| R10 | FAUTH-8 non-admin 404 has no real admin route | `requireAdmin` tested on a test-only route; first real use in F10 | d |
| R11 | HOST-5 503 vs API-8 JSON and no `Set-Cookie` | `_spa_error`: JSON for JSON clients, minimal inline HTML otherwise; never Jinja templates | b |
| R12 | PREF-4 unknown fields | `PATCH /me/prefs` ignores unknown fields (`extra='ignore'`), never persisted, no 500 | c |

### Known test traps (each has an explicit task)
| Trap | Task |
|---|---|
| `tests/test_ci_workflows.py::TestFrontendPlaceholderJob` (asserts `frontend/package.json` absent) | 1.40, 1.43 |
| `tests/test_migrations.py` 0005 drift tests (`test_models_equal_the_schema_at_this_revision`, `test_round_trip_leaves_an_identical_schema`) and `TestRoundTrip` table count 15 to 16 | 3.6, 3.7 |
| `tests/test_authz_matrix.py`: `spa.*` public, `api_v1.get_me_prefs`/`patch_me_prefs` authenticated | 2.14, 3.32 |
| `tests/test_docs.py`: AGENTS.md names every route/table, README describes every env var | 1.47, 2.21, 2.22, 3.35, 5.37 |
| `tests/conftest.py` `CONFIG_ENV_NAMES` += `FRONTEND_DIST` | 2.5 |
| `tests/test_nginx_config_doc.py`: exactly 2 `proxy_pass` | 2.23 |
| Jinja register error text relies on `removeprefix('Value error, ')` | 3.3, 3.19 |
| "Riftbound Manager" strings in 9 templates + README + AGENTS | 5.36, 5.37 |

## Unit 0: Prerequisites (USER actions)

- [x] 0.1 (done 2026-10-19: Node 24.15.0 / npm 11.15.0 on the dev host, which is also the dev server) USER: Node 24 (`.nvmrc`) and npm available on the dev machine and on the dev server (needed for `npm ci && npm run build` in the rollout).
- [x] 0.2 (decided: planning artifacts committed first on branch `docs/f1-planning`; unit branches a/b/c start from it, each ticks only its own unit) USER: decide whether `openspec/changes/f1-app-shell/` (untracked) is committed with the unit PRs; `sdd-apply` ticks boxes in this file in the working tree.
- [x] 0.3 (done: copied byte-identical from the handoff zip to `openspec/changes/f1-app-shell/brand/new_rift.webp`; task 1.30 moves it to `frontend/assets-src/new_rift.webp`) USER: place the Summoner's Rift map `new_rift.webp` (1920x1079, from the design-handoff zip; it is not in the repository) at `frontend/assets-src/new_rift.webp` before task 1.30. The brand sources already sit in `openspec/changes/f1-app-shell/brand/`.
- [x] 0.4 (orchestrator creates one git worktree per parallel unit) USER: create one git worktree per parallel unit (a, b, c) if working in parallel.
- [ ] 0.5 USER (recommended): run the F0 pending manual checks (F0 1.24 etc.) as the first deploy smoke test after unit b/c reach dev.
- [ ] 0.6 USER: after each unit's PR is green, merge it; the next unit branches from the updated `main`.

## Unit 1 (a): Frontend toolchain, tokens, background, brand assets
Specs: DS-1..DS-10, CI-5 (job shape, R9), CI-9. Depends: none. Rollback: revert the PR; restore the guarded steps in `ci.yml` and `TestFrontendPlaceholderJob` together.

### 1.A Pins and bootstrap
- [ ] 1.1 Verify pins: `npm view <pkg>@<ver> time --json` for every row of exploration §3.6 (react, react-dom, vite, @vitejs/plugin-react, vite-plugin-pwa, workbox-build/window, react-router, typescript, @tanstack/react-query). For unlisted packages (vitest, jsdom, @testing-library/*, eslint + plugins, prettier, postcss, sharp, potrace, svgo, @fontsource-variable/*) choose the newest release published on or before 2026-10-05 whose peer ranges accept TS 6.0.3 and Vite 8.3.2. Record the table in the PR.
- [ ] 1.2 Create `frontend/.npmrc` (`save-exact=true`, `engine-strict=true`; R8), `frontend/package.json` skeleton (private, `type: module`, `engines.node >=22.22`, scripts `dev`, `build` = `tsc -b && vite build`, `preview`, `lint`, `typecheck`, `test`, `icons` (placeholder until 6.9), `brand:trace`, `check:dist`), `frontend/.prettierrc.json`. Confirm root `.nvmrc` is `24`.
- [ ] 1.3 Bootstrap (no RED possible): install exact `vitest`, `jsdom`, `typescript`, `postcss`, `@types/node` with `--before=2026-10-05`; add `tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json` (no `baseUrl`, `paths` `@/*`), minimal `vite.config.ts` (alias `@/`, `test` block: jsdom, `src/test/setup.ts`), `src/test/setup.ts`. `npx vitest run --passWithNoTests` exits 0.
- [ ] 1.4 RED `frontend/src/test/pins.test.ts` (DS-10): no dependency starts with `^`, `~` or `>`; `.npmrc` has `save-exact` and `engine-strict`; `engines.node`; scripts list present; `package-lock.json` exists; REQUIRED now: react 19.3.0, react-dom 19.3.0, vite 8.3.2, @vitejs/plugin-react 6.1.1, typescript 6.0.3, both fontsource packages; expected-if-present map (react-router 8.4.0, @tanstack/react-query, vite-plugin-pwa 1.3.0, workbox-window 7.4.1, altcha 2.3.0) equals when installed. Fails on the missing dependencies.
- [ ] 1.5 GREEN `npm install --save-exact --before=2026-10-05`: react, react-dom, `@fontsource-variable/manrope`, `@fontsource-variable/space-grotesk`; dev: vite, @vitejs/plugin-react, @types/react*, eslint stack (typescript-eslint, react-hooks, jsx-a11y), prettier, @testing-library/{react,user-event,jest-dom}, sharp, potrace, svgo. Commit `package-lock.json`. Turns 1.4 green.
- [ ] 1.6 `frontend/index.html` (`<title>Rift Manager</title>`, viewport with `viewport-fit=cover`, `theme-color #06222c`, `color-scheme` dark, inline `<style>html{background:#06222c;color-scheme:dark}</style>`; no Google Fonts, no inline script; D18), placeholder `src/main.tsx`, full `vite.config.ts` (`base` from `VITE_BASE` default `/riftbound/app/`, `VITE_API_BASE`, `build.sourcemap:false`, `emptyOutDir`, dev proxy `/riftbound/api` and `/riftbound/static` to `VITE_DEV_PROXY` default `http://127.0.0.1:5000`).
- [ ] 1.7 `frontend/eslint.config.js` (flat; typescript-eslint, react-hooks, jsx-a11y, Prettier check in `npm run lint`) with the D10 `no-restricted-imports` overrides per folder (`lib`, `components/ui`, `api`, features). `npm run lint`, `npm run typecheck`, `npm run build` pass on the placeholder.
- [ ] 1.8 RED [P] `frontend/src/test/eslint-boundaries.test.ts`: ESLint `Linter` on sample sources reports an error for `src/lib/x.ts` importing `@/api`, `src/components/ui/x.tsx` importing `@/auth`, `src/api/x.ts` importing `@/shell`. GREEN: adjust 1.7 overrides.

### 1.B Test infrastructure
- [ ] 1.9 RED `src/test/viewport.test.ts`: `setViewport(390)` makes `matchMedia('(max-width: 859.98px)')` match and `(min-width: 860px)` not; changing the width fires `change` listeners. GREEN `src/test/viewport.ts` (matchMedia mock evaluating min/max-width) and register it in `src/test/setup.ts`.
- [ ] 1.10 RED `src/test/css.test.ts`: helper reads a CSS file with postcss; `mediaWidths(css)` returns the `@media` widths; `declsFor(css, selector)` returns declarations; glob of all `src/**/*.css`. GREEN `src/test/css.ts`.

### 1.C Breakpoints (DS-4, R1)
- [ ] 1.11 RED `src/lib/breakpoints.test.ts`: exports `sm 680, md 860, lg 960, xl 1240, 2xl 1600`; `up('md') === '(min-width: 860px)'`; `down('md') === '(max-width: 859.98px)'`; `useMediaQuery(down('md'))` returns true at 859 and false at 860 and re-renders when the viewport changes.
- [ ] 1.12 GREEN `src/lib/breakpoints.ts`, `src/lib/useMediaQuery.ts` (`useSyncExternalStore`). Turns 1.11 green.
- [ ] 1.13 RED `src/styles/media-scan.test.ts` (DS-4): every `@media` width in `src/**/*.css` is in the set or the set minus 0.02; the scan function fails naming file and value for a fixture string with `max-width: 920px`. GREEN: scan function in `src/test/css.ts`; passes on the real tree.

### 1.D Tokens, accent, density (DS-1/2/3/7, R7)
- [ ] 1.14 RED `src/styles/tokens.test.ts` (DS-1): expected table transcribed from `openspec/design-handoff.md` §1.1 (colours, `--panel*`, `--line*`, radii, `--gap`, `--pad`, `--row-h`, `--maxw` 1280px, `--maxw-wide` 1760px, fonts, shadows), the five `--z-*` (-2 bg, 30, 40, 50, 80, 90 including `--z-bg`), `color-scheme: dark`, scrollbar rules of §1.3, and the contrast-fixed values for `--muted-2`, white-on-red and `--red` text. Fails: no CSS yet.
- [ ] 1.15 GREEN `src/styles/{tokens,reset,fonts,base,utilities,index}.css`. `index.css` declares `@layer reset, tokens, base, layout, components, utilities` (D15). `fonts.css` imports only the `latin` and `latin-ext` subsets with `font-display: swap`. Turns 1.14 green.
- [ ] 1.16 RED `src/styles/accent.test.ts` (DS-2, CSS source): `[data-accent=orange|cyan]` each define `--accent`, `--accent-bright`, `--accent-dim`, `--accent-ink` (orange ink `#160d03`, cyan ink `#04222b`); `--accent-soft/-ring/-glow` use `color-mix(in srgb, var(--accent) 16%/45%/50%, transparent)`; a scan finds no `46,198,230` or `#2ec6e6` in any CSS outside token definitions of the info colour.
- [ ] 1.17 GREEN accent blocks in `tokens.css`. Turns 1.16 green.
- [ ] 1.18 RED `src/styles/density.test.ts` (DS-3): `[data-density=compact]` gives `--gap` 13px, `--pad` 13px, `--row-h` 44px, `--radius` 11px; `comfy` per handoff §1.2; `:root` (regular) `--gap` 20px, `--row-h` 54px; no `[data-density=regular]` rule exists. GREEN density blocks.

### 1.E Contrast and a11y baseline (DS-7)
- [ ] 1.19 RED `src/lib/contrast.test.ts`: `contrast('#fff','#000') === 21`; hex, `rgb()` and alpha parsing; alpha compositing over a base; relative luminance; token pairs used by F1 (`--text`/`--bg-0`, `--text`/`--panel`, `--muted`/`--panel`, `--muted-2`/`--panel`, accent-ink on accent, white on red, `--red` on `--panel`) each at least 4.5:1, read from `tokens.css`.
- [ ] 1.20 GREEN `src/lib/contrast.ts`; fix token values with the handoff contrast fixes if a pair fails. Turns 1.19 green.
- [ ] 1.21 RED `src/styles/a11y.test.ts` (DS-7): a global `:focus-visible` rule uses the accent; no `outline: none/0` without a replacement on the same selector; a `prefers-reduced-motion: reduce` block disables transitions and animations; no `font-size` below 11px anywhere; every `backdrop-filter` rule has a solid `background` in the same rule; safe-area `env(safe-area-inset-*)` and `100dvh` present in base.
- [ ] 1.22 GREEN `base.css` / `utilities.css` adjustments. Turns 1.21 green.

### 1.F Formatting
- [ ] 1.23 RED `src/lib/format.test.ts`: `formatMoney(1234.5,'es')` follows `es-ES` EUR (decimal comma), `en` follows `en-GB`; `formatNumber`, `formatDate` use `es-ES`/`en-GB`, not the browser locale. GREEN `src/lib/format.ts`.

### 1.G Background layer (DS-5, R5)
- [ ] 1.24 RED `src/lib/background.test.ts` invariants: for every integer 0..100 blur above 0px, brightness at most 1, saturate at most 1, `contrast(` never present in the filter, opacity within 0..1 and non-decreasing, opacity 0 at p=0 and 1 at p=100, `bg` is `off` only at 0.
- [ ] 1.25 RED same file: clamping and rounding (-10 gives 0, 250 gives 100, 49.6 gives 50, NaN gives 100) and a golden table for 0, 50, 100 (documented as deliberately updated when constants are tuned).
- [ ] 1.26 GREEN `src/lib/background.ts`: `BG_BLUR_PX = 3`, `BG_OVERLAYS` (data: two radial gradients and one linear, with the cyan glow, from the handoff), `bgVars(p)` as in design §4.6. Turns 1.24 and 1.25 green.
- [ ] 1.27 RED `src/lib/background-contrast.test.ts`: assume a pure-white image pixel times the maximum brightness for p at that opacity over `--bg-0`; sample `BG_OVERLAYS` on a 24x24 grid for 390x844 and 1440x900; for p in {0,10,...,100} the contrast of `--text` and of `--muted` is at least 4.5:1 (`--muted-2` excluded).
- [ ] 1.28 GREEN: tune `BG_OVERLAYS` and the brightness/saturate ranges until 1.27 passes (never brighten).
- [ ] 1.29 RED `src/styles/background.test.ts`: `background.css` has a fixed `::before` layer with `inset: -3%`, `z-index: var(--z-bg)`, `filter: var(--bg-image-filter)`, `opacity: var(--bg-image-opacity)`; `html[data-bg="off"]` hides it (`display:none`); the 1280 image is chosen inside `@media (max-width: 859.98px)` and 1920 otherwise; no `image-set`-only selection (R5).
- [ ] 1.30 GREEN: copy `frontend/assets-src/new_rift.webp` (task 0.3) to `src/assets/bg/new_rift-1920.webp`; produce `new_rift-1280.webp` with sharp (one-off script `scripts/make-bg.mjs`, documented in `assets-src/README.md`, outputs committed); `src/styles/background.css`. Turns 1.29 green.

### 1.H Brand asset pipeline (DS-9, D20)
- [ ] 1.31 Move (plain `mv`, files are untracked) `openspec/changes/f1-app-shell/brand/rift-manager-{mark,wordmark}.webp` to `frontend/assets-src/brand/`; write `assets-src/brand/README.md` (provenance, trace parameters, regeneration command, "never shipped").
- [ ] 1.32 RED `src/assets/brand/brand-assets.test.ts` (DS-9 "Assets exist"): originals exist; `mark.svg` and `wordmark.svg` exist, parse as SVG, have a `viewBox`, contain no `<image>`, `<script>` or base64 raster, no fill whose luminance is above 0.95 (white halo proxy), and the wordmark viewBox is cropped to its glyphs (aspect ratio wider than 2:1).
- [ ] 1.33 GREEN `scripts/brand-trace.mjs` part 1 (mark): sharp builds a silhouette by distance from white, `potrace` traces it, `svgo` cleans it, a diagonal `linearGradient` `#fbb20b` to `#f5500a` is re-applied (colours re-sampled from the original), viewBox cropped to the bounding box. Output `src/assets/brand/mark.svg`.
- [ ] 1.34 GREEN `scripts/brand-trace.mjs` part 2 (wordmark): same pipeline for the letters with a vertical gradient `#f2a90f` to `#e85d07`, cropped transparent viewBox. Output `src/assets/brand/wordmark.svg`. Turns 1.32 green.
- [ ] 1.35 Hand review of both SVGs (path count, swirl tips, gradient direction); render on `#06222c` at 1x and 2x to a temp folder with a one-off sharp call.
- [ ] 1.36 Conditional, only if 1.35 is not acceptable: fallback colour-to-alpha against white (`alpha = max_c(255-c)/255`, `c' = (c-(1-alpha)*255)/alpha`) into WebP/PNG in `src/assets/brand/`; adapt 1.32 and 1.37 to the raster files.
- [ ] 1.37 RED `src/components/ui/Brand.test.tsx` (DS-9): `<Brand variant="wordmark"/>` and `<Brand variant="mark"/>` are found by role `img` and name "Rift Manager". GREEN `Brand.tsx` + `Brand.module.css` (rules inside `@layer components`).
- [ ] 1.38 RED `src/styles/layer-scan.test.ts` (D15): every `*.module.css` wraps all its rules in `@layer components { }`. GREEN: passes with `Brand.module.css`; fix any stray unlayered rule.
- [ ] 1.39 USER [MANUAL]: no-halo review of the assets on `#06222c` at 1x and 2x (DS-9); approve the trace or ask for the fallback of 1.36.

### 1.I CI, check-dist, tests (CI-5, CI-9, R9)
- [ ] 1.40 RED `tests/test_ci_workflows.py`: rewrite `TestFrontendPlaceholderJob` into `TestFrontendJob`: `frontend/package.json` and `frontend/package-lock.json` exist; no step has a `hashFiles('frontend/package.json')` `if`; step order is checkout, setup-node (`node-version-file: .nvmrc`, npm cache with `frontend/package-lock.json`), `npm ci`, `npm run lint`, `npm run typecheck`, `npx vitest run`, `npm run build`, `npm run check:dist`, `actions/upload-artifact@v4` (`name: frontend-dist`, `path: frontend/dist`, `if-no-files-found: error`, `retention-days: 7`); every step uses `working-directory: frontend` where needed; workflow permissions stay `contents: read`. Delete `test_the_workflow_does_not_need_a_frontend_directory`; keep the `.nvmrc` major test.
- [ ] 1.41 RED `frontend/scripts/check-dist.test.ts` (spawns `node scripts/check-dist.mjs <dir>` against tmp fixtures): passes with only `index.html`; fails on a `.map` file, on `.env`, on a `fonts.googleapis.com` or `fonts.gstatic.com` reference in html/css/js, and on a missing `index.html`.
- [ ] 1.42 GREEN `frontend/scripts/check-dist.mjs` (Node built-ins only) and `npm run check:dist`. Turns 1.41 green.
- [ ] 1.43 GREEN `.github/workflows/ci.yml`: remove the `hashFiles` guards, set the steps of 1.40, add the artifact upload; keep job id `frontend`. Turns 1.40 green; the rest of `test_ci_workflows.py` stays green.
- [ ] 1.44 RED+GREEN `tests/test_ci_workflows.py` CI-9: `.gitignore` still has `frontend/dist/`, `node_modules/`, `.vite/` (existing test) and `frontend/package-lock.json` exists; `git check-ignore frontend/dist` exits 0 (subprocess).

### 1.J Placeholder app and docs
- [ ] 1.45 `src/main.tsx` placeholder: apply `bgVars(100)` to `<html>`, render `<Brand>` and, only when `import.meta.env.DEV`, a range input (0..100) driving `bgVars` live. This is the screenshot harness; replaced in unit d/e.
- [ ] 1.46 REFACTOR: run `npm run lint`, `typecheck`, `vitest run`, `build`; remove duplication in `src/test/*`; confirm no `^`/`~` in `package.json`.
- [ ] 1.47 `AGENTS.md` (tree adds only `frontend/` paths that exist, stack row for the frontend) and `README.md` (frontend dev commands: `nvm use`, `npm ci`, `npm run dev`, `npm run build`); run `venv/bin/python -m pytest tests/test_docs.py`.

### 1.K Verify and PR checkpoint
- [ ] 1.48 Clean-install proof: delete `node_modules`, run `npm ci && npm run lint && npm run typecheck && npx vitest run && npm run build && npm run check:dist`; `dist/index.html` exists.
- [ ] 1.49 Full pytest green (F0 baseline + rewritten CI test).
- [ ] 1.50 USER [MANUAL]: screenshots of the placeholder background at 0, 50, 100 on a phone and a desktop attached to the PR; the user confirms the default value (100 or other) and blur. Update constants and the golden table if the user changes them.
- [ ] 1.51 [GH-CI] The `frontend` job runs unskipped and green; artifact `frontend-dist` contains `index.html`.
- [ ] 1.52 PR checkpoint (`feat/f1-a`): scenarios DS-1..10, CI-5 shape, CI-9 mapped to tests; PR lists the pins table (1.1) and the traps handled. USER merges (0.6).

## Unit 2 (b): SPA hosting
Specs: HOST-1..7. Depends: none (needs unit a only for a real dist at dev rollout). Rollback: revert the PR or stop registering `spa_bp`; Jinja unaffected.

### 2.A Baseline and config
- [x] 2.1 (done 2026-10-19: baseline 1182 passed, 30 skipped; `TestExistingRoutes::test_no_existing_rule_lives_under_the_spa_prefix` pins that no non-spa rule starts with `/riftbound/app`) Suite green on updated `main`; assert in the PR that no rule in `app.url_map` starts with `/riftbound/app` today.
- [x] 2.2 (done 2026-10-19: `TestExistingRoutes` (5 tests) passed before `spa_bp` was registered) CHAR `tests/test_spa_hosting.py::TestExistingRoutes` (HOST-1): `GET /riftbound/login`, `GET /riftbound/api/v1/health` and an existing `/riftbound/static/...` file respond with the same status and content type as before (pin before registering `spa_bp`).
- [x] 2.3 (done 2026-10-19: RED seen (KeyError FRONTEND_DIST), `tests/test_config.py::TestFrontendDist`) RED `tests/test_config.py`: `load_settings` returns `FRONTEND_DIST` = env value when set, else `<repo>/frontend/dist`; `create_app` copies it into `app.config`; empty string counts as unset.
- [x] 2.4 (done 2026-10-19: `config.py` `DEFAULT_FRONTEND_DIST` + `load_settings`; `create_app` needs no change because it already copies `load_settings`) GREEN `config.py` (`load_settings`) and `app/__init__.py` config pass-through. Turns 2.3 green.
- [x] 2.5 (done 2026-10-19: `FRONTEND_DIST` added to `CONFIG_ENV_NAMES`) `tests/conftest.py`: add `FRONTEND_DIST` to `CONFIG_ENV_NAMES` (trap); suite stays green.
- [x] 2.6 (done 2026-10-19: `spa_dist` / `spa_app` fixtures in `tests/conftest.py`) Fixtures in `tests/conftest.py`: `spa_dist` (tmp dir with `index.html`, `assets/app-abc123.js`, `sw.js`, `manifest.webmanifest`, `pwa-192x192.png`, plus a `secret.txt` beside, not inside, the dist) and `spa_app` (app whose `FRONTEND_DIST` points at it; read per request, D1).

### 2.B RED (one task per requirement group)
- [x] 2.7 (done 2026-10-19: `TestMountAndRedirect`) RED HOST-1: `/riftbound/app` gives a redirect whose `Location` ends `/riftbound/app/`; `/riftbound/app/` gives 200 `text/html` and the exact `index.html` body for an anonymous client.
- [x] 2.8 (done 2026-10-19: `TestCacheControlHelper`, `TestCacheRules`) RED HOST-2: `assets/app-abc123.js` has `Cache-Control` containing `public`, `max-age=31536000`, `immutable`; `index.html`, `sw.js`, `manifest.webmanifest` have `no-cache` and no `immutable`; `pwa-192x192.png` is not `immutable`; repeat `sw.js` with `If-None-Match: <etag>` gives 304.
- [x] 2.9 (done 2026-10-19: `TestFileLikeHelper`, `TestCacheControlHelper`) RED HOST-3 pure: `_is_file_like` classifies `a/b.js`, `x.woff2`, `x.map` as file-like and `account/interface`, `cards` as routes (D2); `_cache_control(path)` per D3.
- [x] 2.10 (done 2026-10-19: `TestExtensionAwareCatchAll`) RED HOST-3 routes: deep link `/riftbound/app/account/interface` gives 200 with the `index.html` body and `no-cache`; `assets/missing.js`, `missing.css`, `missing.woff2`, `missing.js.map` give 404 and a body that is not `index.html`; traversal `/riftbound/app/..%2Fsecret.txt` and `/riftbound/app/../secret.txt` never return the content.
- [x] 2.11 (done 2026-10-19: `TestMimetypes`) RED HOST-4 / D4: `manifest.webmanifest` starts with `application/manifest+json`; `.woff2` `font/woff2`, `.webp` `image/webp`, `.js` `text/javascript`, `.svg` `image/svg+xml`.
- [x] 2.12 (done 2026-10-19: `TestMissingBuild` (missing dir and dir without index.html)) RED HOST-5 / R11: with `FRONTEND_DIST` nonexistent and with a dir lacking `index.html`, `/riftbound/app/` and `/riftbound/app/assets/x.js` give 503 with a non-empty message; browser `Accept` gets minimal HTML (no `base.html` markup, no CSRF cookie), `Accept: */*` / JSON gets the `json_error` envelope; `Cache-Control: no-store`; `create_app` starts; `/riftbound/api/v1/health` is 200 `status:"ok"`.
- [x] 2.13 (done 2026-10-19: `TestNoSecretsInTheShell`) RED HOST-6 / D3: `GET /riftbound/app/` and an asset have no `Set-Cookie`; every SPA response has `X-Content-Type-Options: nosniff` and `Referrer-Policy: strict-origin-when-cross-origin`; `index.html` contains no `csrf` string (fixture check).
- [x] 2.14 (done 2026-10-19: `TestSpaIsPublic` + `spa.*` in MATRIX) RED `tests/test_authz_matrix.py`: add `'spa.*': 'P'` and a probe that an anonymous client gets 200 on `/riftbound/app/` (fails until registered).

### 2.C GREEN
- [x] 2.15 (done 2026-10-19: `app/routes/spa.py` helpers) GREEN `app/routes/spa.py` pure helpers: `SPA_MIMETYPES`, `FILE_LIKE`, `_is_file_like`, `_cache_control`. Turns 2.9 and 2.11 (unit part) green.
- [x] 2.16 (done 2026-10-19: `_spa_error` + 503 guard in `_serve`) GREEN `_spa_error(status, message)` (R11, D5) and the 503 guard (`dist/index.html` missing). Turns 2.12 green.
- [x] 2.17 (done 2026-10-19: `index()` / `asset()` via `_send`) GREEN routes `index()` and `asset(path)` with `send_from_directory(... mimetype from map, conditional=True)`, headers of D3, no use of `session`/`current_user`. Turns 2.7, 2.8, 2.10, 2.13 green.
- [x] 2.18 (done 2026-10-19: registered in `create_app` after the domain blueprints; full suite 1303 passed, 30 skipped) GREEN register `spa_bp` in `create_app` after the domain blueprints (`app/__init__.py`). Turns 2.14 and 2.2 green; full suite green.
- [x] 2.19 (done 2026-10-19: single `_serve(path)` written from the start, suite green) REFACTOR `spa.py` (single `_serve(path)` used by both routes); suite green.

### 2.D Docs
- [x] 2.20 (done 2026-10-19: `docs/frontend.md`) `docs/frontend.md`: build (`npm ci && npm run build`), `FRONTEND_DIST`, deploy options (build on server with Node 24, or unpack the `frontend-dist` artifact), the short 503 window during rebuild and the optional atomic swap, "Nginx needs no change in F1", rollout order, smoke checklist.
- [x] 2.21 (done 2026-10-19: `.env.example` (commented `FRONTEND_DIST`) + README table row and "New app hosting" section) `.env.example`: `FRONTEND_DIST` as a commented variable. README describes it (HOST-7).
- [x] 2.22 (done 2026-10-19: `AGENTS.md` tree entry + "SPA hosting (`spa_bp`)" subsection; `test_docs.py` green) `AGENTS.md`: tree entry `app/routes/spa.py`, blueprint `spa_bp` named. Run `tests/test_docs.py` (trap).
- [x] 2.23 (done 2026-10-19: `docs/nginx_config` comment notes only; `test_nginx_config_doc.py` green (2 proxy_pass)) `docs/nginx_config`: optional notes (gzip, HSTS) without any new `proxy_pass`; run `tests/test_nginx_config_doc.py` (still exactly two).

### 2.E Verify and PR checkpoint
- [x] 2.24 (done 2026-10-19: full pytest 1303 passed, 30 skipped (no `frontend/` directory exists in this branch and no test spawns node or reads the real dist)) Full pytest green; confirm the tests run with no Node installed (CI-9 "No Node in pytest").
- [ ] 2.25 USER [MANUAL] dev rollout (after unit a merged): `cd frontend && npm ci && npm run build`, restart the service. Smoke (HOST-7): `/riftbound/app/` loads, a deep link reloads, `/riftbound/app` redirects, F0 pending manual checks pass.
- [ ] 2.26 PR checkpoint (`feat/f1-b`): HOST-1..7 mapped to tests or 2.25; docs updated; USER merges.

## Unit 3 (c): Preferences API, error codes, remember cookie
Specs: PREF-1..5, API-1, API-4, API-5, API-9, SESS-1. Depends: none. Rollback: `flask db downgrade 0005_login_protection`, then revert; every API change is additive.

### 3.A Baseline
- [ ] 3.1 Suite green on updated `main`.
- [ ] 3.2 CHAR `tests/test_error_codes.py::TestAdditive` (R6): pin the exact keys of today's bodies for a legacy JSON validation 400 (`success`, `error`, `message`, `details[].field/message/type`), the API 404, 401 and CSRF 400; they must still pass after the codes land (the new keys are added, none removed).
- [ ] 3.3 CHAR `tests/test_login_protection.py` / new: the Jinja register error text for a bad password and bad email today (pins the `removeprefix('Value error, ')` path before 3.19).
- [ ] 3.4 CHAR login never sets `remember_token` today (documents the defect; superseded by 3.23, delete this CHAR in 3.25).

### 3.B Migration 0006 (PREF-1)
- [ ] 3.5 RED `tests/test_migrations.py::TestUserPrefs0006`: from `0005_login_protection` upgrade creates `riftbound.rbuserprefs` with columns and types of design §5.2, PK `rbuserprefs_pkey`, FK `rbuserprefs_user_fk` with ON DELETE CASCADE, named CHECKs, all preference columns nullable; inserts of `bg_intensity=101` and `density='huge'` raise `IntegrityError` while NULL passes; downgrade drops the table; up, down, up round trip.
- [ ] 3.6 Trap: change the two 0005-level drift tests (`test_models_equal_the_schema_at_this_revision`, `test_round_trip_leaves_an_identical_schema`) to compare against metadata without `rbuserprefs` (or to run at head); list the edit in the PR. Done in the same commit as 3.8.
- [ ] 3.7 Trap: update `TestRoundTrip` table count 15 to 16 and add `rbuserprefs` to the expected table list.
- [ ] 3.8 GREEN `app/schemas/prefs_domain.py` (domain tuples), `app/models/prefs.py` (`RbUserPrefs`, same CHECK names, `{"schema":"riftbound"}`) imported in `app/models/__init__.py`.
- [ ] 3.9 GREEN `migrations/versions/0006_user_prefs.py` (`down_revision = '0005_login_protection'`, `op.create_table` with named constraints, `server_default=sa.func.now()`, downgrade `op.drop_table`). Turns 3.5 and the drift tests green (`compare_metadata` returns `[]` at head).
- [ ] 3.10 RED+GREEN [PG-CI] `tests/test_migrations_pg.py`: up, down, up from 0005; CHECK rejections; cascade delete removes the prefs row; `flask db check` clean at head. Run locally if `TEST_POSTGRES_URL` exists, else record "verified in CI migrations-pg" in the PR.

### 3.C Schema and service (PREF-2, PREF-4)
- [ ] 3.11 RED `tests/test_prefs_api.py::TestPrefsUpdateSchema`: every allowed value passes and one invalid value per field fails; `bg_intensity` rejects `True`, `50.5`, `"50"`; `None` allowed per field; `{}` valid; unknown keys ignored (R12); `model_fields_set` reflects only the present keys. Parity: the same values against the model CHECKs through the DB (PREF-2).
- [ ] 3.12 GREEN `PrefsUpdate` in `app/schemas/validators.py` built from `prefs_domain` (`extra='ignore'`, `StrictInt` + `Field(ge=0, le=100)`). Turns 3.11 green.
- [ ] 3.13 RED `tests/test_prefs_api.py::TestPrefsService`: `get_prefs` returns five keys, all `None` for a user without a row, and inserts nothing; `update_prefs` creates the row on first write, updates only given keys, `None` resets, refreshes `rbprf_updated_at` (use `frozen_clock`), and retries once as UPDATE when the first INSERT raises `IntegrityError` (monkeypatched).
- [ ] 3.14 GREEN `app/services/prefs.py` (`PREF_KEYS`, `get_prefs`, `update_prefs`; D7 upsert). Turns 3.13 green.

### 3.D Error codes (API-1, API-9, R6)
- [ ] 3.15 RED `tests/test_error_codes.py::TestHelpers`: `ErrorCode` StrEnum has the nine values of D9; `json_error`/`fail` accept keyword-only `code` and `params` and add them to the body only when set; codeless output is byte-identical to F0.
- [ ] 3.16 GREEN `app/api/error_codes.py`, `app/api/responses.py` (keyword-only `code=None, params=None`).
- [ ] 3.17 RED `tests/test_error_codes.py::TestValidationMapping` (pure): the §5.3 table: `missing` gives `required`; `string_too_short`/`too_short` gives `too_short` with `params.min`; `string_too_long`/`too_long` with `max`; `greater_than_equal`... gives `out_of_range` with `min`/`max`; `invalid_format` custom; `literal_error`, `bool_type`, `int_from_float` give `invalid_value`.
- [ ] 3.18 RED `tests/test_error_codes.py::TestValidateJson`: 400 body has `code:"validation_error"` and each detail keeps `field`, `message`, `type` plus `code`/`params`; register with a 3-character password and a malformed email returns `password` (`too_short`, `params.min`) and `email` (`invalid_format`).
- [ ] 3.19 GREEN `app/schemas/validation.py` mapping and top-level code; `RegisterRequest` validators raise `PydanticCustomError('invalid_format', ...)` in `app/schemas/validators.py`. Re-run 3.3 (Jinja register text unchanged) and 3.2.
- [ ] 3.20 RED `tests/test_error_codes.py::TestEndpointCodes`: login 401 `invalid_credentials`; five failures then the sixth is 429 `locked` with `params.retry_after` equal to the `Retry-After` header; limiter 429 `rate_limited` with `retry_after` (use `limited_app`); register 409 `username_taken` then `email_taken`; register without payload on `altcha_app` gives 400 `error:"Captcha Error"` `code:"captcha_failed"`; CSRF failure 400 `csrf_invalid` (API and a legacy JSON endpoint); anonymous `POST /auth/logout` and `GET /me/prefs` give 401 `unauthenticated`; the unknown path 404 stays codeless (API-1 "Codeless errors unchanged").
- [ ] 3.21 GREEN `app/api/v1/auth.py` codes on login and register; `app/errors.py` global CSRF and 429 handlers; `app/__init__.py` `unauthorized_handler` code. Turns 3.20 green.
- [ ] 3.22 Run the whole suite; any F0 test that compares a full error body with `==` is loosened to a subset check and listed in the PR (additive contract).

### 3.E Remember cookie (API-5, SESS-1)
- [ ] 3.23 RED `tests/test_remember_cookie.py`: production config over `https://localhost`: `remember:true` sets `remember_token` with `HttpOnly`, `SameSite=Lax`, `Secure` and `Max-Age`/`Expires` within one minute of 30 days; `remember:false` and absent set none; `"yes"` and `1` give 400 with `details` naming `remember` and no session; development login has no `Secure`; `REMEMBER_COOKIE_HTTPONLY/SAMESITE/SECURE/DURATION` config values (30 days); Jinja form login still issues no remember cookie.
- [ ] 3.24 RED same file: a client with `remember_token` only (drops `session`) gets `authenticated:true`; `POST /auth/logout` expires `remember_token` and the next `/auth/session` is anonymous; a user blocked after login is anonymous with a valid remember cookie.
- [ ] 3.25 GREEN `config.py` `_session_settings`: `REMEMBER_COOKIE_DURATION = timedelta(days=30)` (constant, no env var; D8); `LoginRequest.remember: StrictBool = False` and `login_user(user, remember=data.remember)` in `app/api/v1/auth.py`. Update `tests/test_session_cookies.py` only where it pins the old config shape. If the blocked-user test of 3.24 fails, fix the `user_loader`.

### 3.F Endpoints and session payload (PREF-3, PREF-4, PREF-5, API-4)
- [ ] 3.26 RED `tests/test_prefs_api.py::TestGetPrefs`: defaults (five `null`, no row created), anonymous 401 JSON with `code:"unauthenticated"`, per-user isolation.
- [ ] 3.27 RED `tests/test_prefs_api.py::TestPatchPrefs`: partial update keeps others; `null` resets to Auto; invalid values `101`, `"purple"`, `50.5`, `true` give 400 naming the field with stored prefs unchanged; all-or-nothing (`{"lang":"en","density":"huge"}`); `{}` gives 200 and creates no row; unknown fields not persisted and no 500; non-JSON body 400; success returns the full five-key prefs and refreshed `updated_at`.
- [ ] 3.28 RED `tests/test_prefs_api.py::TestPatchCsrf` (`csrf_app`): no token gives 400 `csrf_invalid`; anonymous with token gives 401 JSON.
- [ ] 3.29 RED `tests/test_api_v1.py` or `test_prefs_api.py::TestSessionPrefs`: anonymous session has no `prefs` key; logged-in `user` has exactly `id, username, email, is_admin`; prefs without a row are five `null`s and no row exists afterwards; stored `lang:"en"`, `bg_intensity:40` come back; after `PATCH {"accent":"cyan"}` the session shows `accent == "cyan"` (PREF-5).
- [ ] 3.30 GREEN `app/api/v1/me.py` (`GET`/`PATCH /me/prefs`; `@login_required`, `@validate_json(PrefsUpdate)`, `model_dump(include=model_fields_set)`) and import in `app/api/v1/__init__.py`. Turns 3.26..3.28 green.
- [ ] 3.31 GREEN `auth_session` adds `data['prefs'] = get_prefs(current_user.id)` only when authenticated. Turns 3.29 green.
- [ ] 3.32 RED+GREEN `tests/test_authz_matrix.py` (trap): add `api_v1.get_me_prefs` and `api_v1.patch_me_prefs` as `'U'`; the matrix fails for unclassified endpoints until added.
- [ ] 3.33 REFACTOR: shared helpers in `tests/auth_helpers.py` for "login with remember"; remove duplicated fixtures; suite green.

### 3.G Docs
- [ ] 3.34 `docs/migrations.md`: section for `0006_user_prefs` (what it adds, rollback `flask db downgrade 0005_login_protection`).
- [ ] 3.35 `AGENTS.md`: name `rbuserprefs`, `RbUserPrefs`, `app/api/v1/me.py`, `app/services/prefs.py`, `app/api/error_codes.py`; grep `README.md` and `docs/` for the `/auth/session` and login payload descriptions and add `prefs`, `remember` and `code`/`params`. Run `tests/test_docs.py` (`test_every_table_is_named`).

### 3.H Verify and PR checkpoint
- [ ] 3.36 Full pytest green; list in the PR every F0 test edited (3.6, 3.7, 3.22, 3.25).
- [ ] 3.37 [GH-CI] `migrations-pg` job green with the 0006 PG tests; `flask db check` clean at head.
- [ ] 3.38 USER [MANUAL] dev rollout, in this order: (1) `pg_dump -n riftbound -Fc` to a path outside the repo and `pg_restore -l` check; (2) update the working tree; (3) `cd frontend && npm ci && npm run build` (skip if unit a/b is not merged yet); (4) `flask db upgrade` to `0006_user_prefs`, then `flask db check`; (5) restart the service. Smoke: API login with `remember:true` shows a ~30-day `remember_token`; `PATCH /me/prefs` then `GET /auth/session` shows the value; F0 pending checks (0.5).
- [ ] 3.39 PR checkpoint (`feat/f1-c`): PREF-1..5, API-1/4/5/9, SESS-1 mapped; PR notes R6 (additive keys on legacy JSON endpoints). USER merges.

## Unit 4 (d): API client, router, auth screens, i18n
Specs: FAUTH-1..11, I18N-1..5, plus contract tests (D25). Depends: a + b + c merged. Rollback: revert; the Jinja login still works.

### 4.A Dependencies and test infrastructure
- [ ] 4.1 `npm view <pkg> time --json` for react-router 8.4.0, @tanstack/react-query, i18next, react-i18next, msw, vitest-axe, altcha 2.3.0; pick the newest release on or before 2026-10-05 (i18next 26.5.2 and react-i18next 17.1.0 are too new per exploration); record in the PR.
- [ ] 4.2 RED `tests/test_frontend_contracts.py::TestAltchaPin` (D25, FAUTH-4): `frontend/package.json` and `frontend/package-lock.json` altcha version equals the pin in `requirements.txt`. Fails: no altcha dependency yet.
- [ ] 4.3 GREEN `npm install --save-exact --before=2026-10-05`: react-router, @tanstack/react-query, i18next, react-i18next, altcha 2.3.0; dev: msw, vitest-axe, jsdom helpers; extend the required-present set of `src/test/pins.test.ts`. Turns 4.2 green.
- [ ] 4.4 Spike: read the `altcha` 2.3.0 typings and source for the `statechange` event (`detail.state`, `detail.payload`), `challengejson`, `auto`, `hidelogo`, `strings`; write the findings as a header comment in `src/auth/altcha.d.ts` and a PR note.
- [ ] 4.5 `src/test/msw/{server.ts,handlers.ts}` (default handlers for session, login, logout, register, captcha, meta/config, me/prefs), `src/test/renderApp.tsx` (router + providers + viewport), `setup.ts` with `onUnhandledRequest:'error'`, `vitest-axe` matcher, a `HTMLDialogElement.showModal/close` polyfill for jsdom.

### 4.B API client (D11, D12, FAUTH-1, FAUTH-6)
- [ ] 4.6 RED `src/api/errors.test.ts`: `ApiError` kinds `http|network|timeout|parse`; `code` normalised as `body.code ?? deriveCode(error, status)` (F0 bodies without codes map: 401 login, 409 messages, 429); `retryAfter` from the `Retry-After` header else `params.retry_after`.
- [ ] 4.7 RED `src/api/client.test.ts` (MSW): `request<T>` unwraps `{success,data}`; sends `Accept: application/json`, `credentials: 'same-origin'`; 15 s timeout (fake timers) gives kind `timeout`; malformed JSON gives `parse`; `X-CSRFToken` only on POST/PATCH/PUT/DELETE; fetches the session first when no token is held; never sets `Referrer-Policy: no-referrer`; the token is never written to `localStorage` or `sessionStorage` (FAUTH-1).
- [ ] 4.8 RED same file, FAUTH-6: first POST 400 `csrf_invalid` then refreshed token accepted gives exactly two POSTs and one session GET; both POSTs failing gives no third POST; 401 on any path except `/auth/login` and `/auth/logout` calls `onUnauthorized` once.
- [ ] 4.9 GREEN `src/api/{errors,csrf,client,endpoints,types}.ts`. Turns 4.6..4.8 green.

### 4.C Session, guards, router (FAUTH-1, 7, 8, 9)
- [ ] 4.10 RED `src/auth/safeNext.test.ts` (FAUTH-9): the table `/riftbound/app/collection` (router) and `/riftbound/collection` (document) accepted; `https://evil.example`, `//evil.example`, `/\evil`, `javascript:alert(1)`, `/riftbound/../etc`, `%2f%2fevil.example`, `/other`, empty, `null`, double-encoded variants all return home.
- [ ] 4.11 GREEN `src/auth/safeNext.ts` (decode at most twice; D13). Turns 4.10 green.
- [ ] 4.12 RED `src/auth/session.test.ts`: `sessionQuery` caches `{authenticated,user,prefs}`; sets the CSRF token; sets the "was signed in" hint on authenticated and clears it on anonymous (non-sensitive key); `staleTime` 5 min; refetch on focus; no retry on 4xx, one on network error.
- [ ] 4.13 GREEN `src/auth/{session,hint}.ts`, `src/app/queryClient.ts`. Turns 4.12 green.
- [ ] 4.14 RED `src/auth/guards.test.tsx`: signed-in boot shows loading then home and never renders the login form; anonymous at a guarded route lands on `/login?next=<absolute>`; `requireAnon` redirects an authenticated user to `safeNext(next)` or home; `requireAdmin` renders the 404 view for a non-admin on a test-only route (R10) and the page for an admin.
- [ ] 4.15 RED `src/app/unauthorized.test.tsx` (FAUTH-7, R2): a 401 from an API call made on `/account/interface` clears the cache, sets the session anonymous, clears the hint and navigates to `/login?next=%2Friftbound%2Fapp%2Faccount%2Finterface`; concurrent 401s navigate once.
- [ ] 4.16 GREEN `src/auth/guards.ts`, `src/app/{router,routes,AppProviders,RouteError}.tsx` (basename `/riftbound/app`, lazy routes, `HydrateFallback`, `onUnauthorized` hook with the `handling` flag; `/` renders a temporary `HomePlaceholder` with a logout button until unit e). Turns 4.14 and 4.15 green.
- [ ] 4.17 RED+GREEN `src/app/chunk-reload.test.ts` (D24): `vite:preloadError` reloads once (`sessionStorage` `rb_chunk_reload` guard) and not twice; `RouteError` offers "Recargar" for a dynamic-import failure.

### 4.D i18n (I18N-1..5, D14)
- [ ] 4.18 RED `src/i18n/parity.test.ts` (I18N-1): parity function fails on fixtures with a missing key (names key and language), mismatched `{{placeholders}}` (`{{count}}` vs `{{n}}`), and a missing plural form per `Intl.PluralRules(lang).resolvedOptions().pluralCategories`; the same function passes on the real catalogs; unused keys are reported as a warning list.
- [ ] 4.19 RED `src/i18n/resolveLang.test.ts` (I18N-2): account `en` with browser `es-ES` gives `en`; `rb_lang` before the session; `navigator.languages = ["fr-FR","en-US"]` gives `en`; `["fr-FR"]` gives `es`; unsupported stored values ignored.
- [ ] 4.20 RED `src/i18n/translateError.test.ts` (I18N-4): `username_taken` in `es` gives the catalog text, not `message`; `locked` with `retry_after: 30` interpolates; unknown code `brand_new_code` with `message` shows the message; no code and no message gives `errors:status.<n>` then `errors:unknown`; network/timeout gives `errors:network`; field details use `errors:validation.<field>.<code>`, then `validation.<code>` with params (`{min:8}`), then `detail.message`.
- [ ] 4.21 RED `src/i18n/i18n.test.tsx` (I18N-3, I18N-5): switching ES to EN updates `document.documentElement.lang`, labels and `document.title` (`<page> · Rift Manager`, root `Rift Manager`); a missing key falls back to the `es` text and never renders the raw key; typed resources: a `// @ts-expect-error` line calls `t('auth:does.not.exist')`, so `npm run typecheck` fails if typing is lost.
- [ ] 4.22 GREEN catalogs `src/i18n/locales/{es,en}/{common,nav,auth,errors,prefs}.json` (auth, login, register, validation, `errors:code.*` for every `ErrorCode`, `status.*`, `network`, `unknown`), `i18n/{index,resolveLang,translateError}.ts`, `i18next.d.ts` (`CustomTypeOptions.resources = typeof es`), a `useDocumentTitle` hook. Turns 4.18..4.21 green.
- [ ] 4.23 RED+GREEN `tests/test_frontend_contracts.py::TestErrorCodeCatalogs` (D25): every `ErrorCode` value has `code.<value>` in `frontend/src/i18n/locales/{es,en}/errors.json`.

### 4.E Primitives used by d (DS-8 subset)
- [ ] 4.24 RED+GREEN `Button` (variants, `pending` disables and sets `aria-busy`) with `Button.module.css` in `@layer components`.
- [ ] 4.25 RED `Field.test.tsx` (DS-8): the input is reachable by label text; `aria-describedby` references the hint and error ids (`useId`). GREEN `Field.tsx`, `Input.tsx`.
- [ ] 4.26 RED+GREEN `PasswordInput`: show/hide control with an accessible name, `autocomplete` pass-through.
- [ ] 4.27 RED+GREEN `LiveAnnouncer` (always mounted, visually hidden, `aria-live="polite"`) and `Toast` store/stack (`popover="manual"` re-shown on push; `position: fixed; z-index: var(--z-toast)` fallback; action slot is a focusable button; item under pointer or focus is not auto-dismissed).
- [ ] 4.28 RED+GREEN `Skeleton` (`aria-busy` region), `ErrorState` (message + retry action), minimal `Icon` set needed by d (`eye`, `eye-off`, `warning`, `check-circle`).

### 4.F Auth screens
- [ ] 4.29 RED `src/auth/LoginPage.test.tsx` (FAUTH-2, 7, 10): labelled fields with `autocomplete` `username`/`current-password`; "Remember me" checked by default and `remember:true` in the body; unchecked gives `remember:false`; success refetches the session then navigates home; `next=/riftbound/app/account/interface` navigates to `/account/interface`; a legacy `next` does a full navigation; 401 shows a translated generic message, keeps the username, clears the password, focuses the password, no redirect; 400 `details` map to field errors with focus on the first invalid field; submit disabled while pending.
- [ ] 4.30 RED same: 429 with `Retry-After: 30` starts a countdown near 30 s, disables submit, announces at start and at 0 (not every second), re-enables at 0 (fake timers); wordmark has the name "Rift Manager"; `vitest-axe` clean including the error state.
- [ ] 4.31 GREEN `src/auth/{AuthLayout,LoginPage,useAuth}.tsx` + `useRetryCountdown`; `AuthLayout` has a language toggle that writes only `rb_lang` (signed-in persistence arrives in unit e). Turns 4.29 and 4.30 green.
- [ ] 4.32 RED `src/auth/RegisterPage.test.tsx` (FAUTH-3, 4, 10): provider `none` or null challenge renders no widget and sends no `altcha`; provider `altcha` with a custom-element stub that fires `statechange` keeps submit disabled until verified, then sends `altcha`; 201 navigates to `/login` with a success toast and an anonymous session; 409 `username_taken` shows the translated message on the username field and focuses it (also `email_taken`); `captcha_failed`.
- [ ] 4.33 RED same: after any error (400, 409, 429, 5xx, network) a new `GET /auth/captcha` is made, the widget remounts with a new key and submit is disabled until re-verified; client checks (`^[A-Za-z0-9_.-]{3,32}$`, email shape, password 8..128); invalid email focuses the email field with `aria-describedby`; `autocomplete` `new-password`, `email`; axe clean.
- [ ] 4.34 GREEN `src/auth/{RegisterPage,AltchaWidget}.tsx`, `altcha.d.ts`; `altcha` imported only in the lazy register route module (D22). Turns 4.32 and 4.33 green.
- [ ] 4.35 RED+GREEN logout (FAUTH-5): 200 and 401 both clear the query cache, the hint, write the current language to `rb_lang`, set the session anonymous and navigate to `/login`; 500 stays in the shell with an error toast.
- [ ] 4.36 `src/main.tsx`: read `rb_lang`, `i18n.init`, register the `vite:preloadError` listener, render `RouterProvider`. (Prefs bootstrap arrives in unit e.)
- [ ] 4.37 Build with `build.manifest: true` and confirm in `dist/.vite/manifest.json` that `altcha` is only reachable through a dynamic import (FAUTH-3 "Lazy loading"); record in the PR (automated in 6.13).
- [ ] 4.38 REFACTOR: extract shared form helpers; `npm run lint`, `typecheck`, full vitest, build.

### 4.G Docs and PR checkpoint
- [ ] 4.39 `docs/frontend.md`: auth/CSRF flow, error-code catalogs, how to add an error code (backend enum + both catalogs + contract test); `AGENTS.md` frontend structure; `test_docs.py` green.
- [ ] 4.40 Full lanes green: vitest, lint, typecheck, build, `check:dist`, pytest including `test_frontend_contracts.py`.
- [ ] 4.41 USER [MANUAL] dev rollout (rebuild only): `npm ci && npm run build`, restart; FAUTH-11 cross-app session: log in in the SPA, open `/riftbound/`, log out there, reload `/riftbound/app/` and see the login screen.
- [ ] 4.42 PR checkpoint (`feat/f1-d`): FAUTH-1..11, I18N-1..5 mapped to tests or 4.41. USER merges.

## Unit 5 (e): App shell, preferences UI, Jinja rename
Specs: SHELL-1..10, PREF-6..8, DS-8 (rest), DS-3 consumption. Depends: d. Rollback: revert (removes the "Nueva app" link and the rename).

### 5.A Baseline
- [ ] 5.1 `git grep -n "Riftbound Manager" -- app tests README.md AGENTS.md` and list the hits (9 templates + README + AGENTS; none expected in tests). Paste the list in the PR.

### 5.B Remaining primitives (DS-8)
- [ ] 5.2 RED+GREEN `Icon` full set: the 47 prototype icons plus `more`, `install`, `warning`, `offline`, `settings`, `info`, `external-link`, `check-circle` exist in `icons.ts`; `aria-hidden="true"` by default; optional `title` makes it `role="img"`.
- [ ] 5.3 RED+GREEN `Select` and `Switch` (`role="switch"`, keyboard toggle).
- [ ] 5.4 RED `SegmentedControl.test.tsx` (DS-8): radiogroup semantics; arrow keys move selection, `onChange` fires with the second value and exactly one option is checked. GREEN.
- [ ] 5.5 RED+GREEN `Slider`: labelled, visible value, keyboard step, `onChange` while dragging and `onCommit` on pointerup/blur.
- [ ] 5.6 RED+GREEN `Panel`, `PageHeader`, `Badge`, `Avatar` (initials), `SettingsCard`, `EmptyState`.
- [ ] 5.7 RED `Modal.test.tsx` (DS-8, D17): opens with `showModal()`; Escape closes and focus returns to the opener; backdrop closes only when both `pointerdown` and `pointerup` land on the dialog element; `ConfirmDialog` backdrop does not close; scroll lock rule `html:has(dialog[open])` exists in CSS.
- [ ] 5.8 GREEN `Modal`, `Sheet`, `ConfirmDialog` on native `<dialog>`; toast stack stays above an open dialog (re-show). Turns 5.7 green.
- [ ] 5.9 RED `src/styles/density-consumption.test.ts` (DS-3): the row, list and menu primitive CSS use `var(--row-h)` and small controls use `var(--radius-sm)`. GREEN: adjust module CSS.
- [ ] 5.10 `src/dev/KitchenSink.tsx` (route `/_kitchen` only when `import.meta.env.DEV`); RED+GREEN test that the production route table has no `/_kitchen`.
- [ ] 5.11 REFACTOR: shared focus-ring and target-size (24px minimum) helpers; layer-scan (1.38) still green.

### 5.C Preferences core (PREF-6, PREF-7, R1, R4)
- [ ] 5.12 RED `src/prefs/domain.test.ts` and `storage.test.ts`: domains of PREF-2; `rb_prefs_v1` mirror keeps `null`, contains only the five fields, ignores missing, corrupt (`"{not json"`) and out-of-domain values without throwing.
- [ ] 5.13 RED `src/prefs/resolve.test.ts`: Auto density `compact` at 859 px and `regular` at 860 px (R1); Auto view `grid`/`table` likewise; accent null gives `orange`; `bg_intensity` null gives 100; explicit `comfy` at 390 px wins.
- [ ] 5.14 RED `src/prefs/apply.test.ts`: `applyPrefs` sets `data-accent`, removes `data-density` for `regular`, sets `lang`, `data-bg`, and the `bgVars` variables on `<html>`.
- [ ] 5.15 GREEN `src/prefs/{types,domain,storage,resolve,apply}.ts`. Turns 5.12..5.14 green.
- [ ] 5.16 RED `src/prefs/bootstrap.test.tsx` (PREF-6/7): mirror `{accent:"cyan"}` is applied to `<html>` before the session response arrives; 390 px with all null gives `data-density="compact"`; 1280 px gives no `data-density` and `data-accent="orange"`; a server session with `accent:"orange"` replaces the mirror and the DOM; crossing 860 px re-resolves Auto values.
- [ ] 5.17 GREEN `PrefsProvider.tsx`, `usePrefs.ts`, and the `main.tsx` bootstrap before `createRoot().render()` (D18); session prefs feed `resolveLang` and `i18n.changeLanguage` (R4). Turns 5.16 green.
- [ ] 5.18 RED `src/prefs/sync.test.ts` (PREF-8): accent Cyan applies at once and sends exactly one PATCH `{"accent":"cyan"}`; a 500 reverts the value and shows an error toast with "Reintentar"; ten slider values within 400 ms send one PATCH with the last value (also flushes on pointerup, blur, pagehide); choosing Auto sends `{"density":null}`; one request in flight, changes made meanwhile are merged into the next; only changed fields are sent; 401 goes to the global handler.
- [ ] 5.19 RED same: anonymous language toggle writes only `rb_lang` (no PATCH); signed-in toggle writes `rb_lang` and sends `{"lang":...}`.
- [ ] 5.20 GREEN `src/prefs/sync.ts` and a `LanguageToggle` shared by `AuthLayout`, `Topbar` and the sheet. Turns 5.18 and 5.19 green.

### 5.D Navigation registry, hub, shell (SHELL-1..6, 8, R3)
- [ ] 5.21 Read the Flask `url_map` for the real legacy URLs (dashboard, sets, cards, collection, decks, profile, price) before writing the JSON.
- [ ] 5.22 RED `tests/test_frontend_contracts.py::TestLegacyRoutes` (SHELL-5): every URL in `frontend/src/shell/legacy-routes.json` matches a GET rule via `app.url_map.bind('localhost').match`. GREEN `src/shell/legacy-routes.json` and `legacyRoutes.ts`.
- [ ] 5.23 RED `src/shell/navRegistry.test.tsx`: statuses `spa|legacy|planned`; `planned` not rendered; admin-only hidden for non-admins; a `legacy` Collection entry is a plain `<a href="/riftbound/collection">` and not a router link; bottom nav set is Inicio, Cartas, Colección, Mazos, Más (R3). GREEN `src/shell/navRegistry.ts`.
- [ ] 5.24 RED `src/shell/HomeHub.test.tsx` (SHELL-6): non-admin sees six launcher links (Dashboard, Sets, Cards, Collection, Decks, Profile) and no Price; an admin also sees Price. GREEN `HomeHub.tsx`.
- [ ] 5.25 RED `src/shell/AppShell.test.tsx` at 1280 px (SHELL-1/2): exactly one `main` and one `banner`, one `navigation`; first tab stop is "skip to content"; no bottom nav in the DOM; no bottom padding class; wordmark shown and mark-only not; nav list, ES/EN toggle, avatar with initials and a logout button named "Cerrar sesión"; the active entry has `aria-current="page"`.
- [ ] 5.26 RED same at 390 px (SHELL-2/3): mark-only shown, no full nav list, bottom nav with at most 5 items, last "Más", active item `aria-current="page"`; hidden at 1024 px; logout name resolvable at both widths.
- [ ] 5.27 RED `src/shell/shell-css.test.ts`: topbar sticky 64px (56px below `sm`); content capped at `var(--maxw)` and `var(--maxw-wide)` from `2xl`; bottom-nav labels at least 11px; safe-area insets on bottom nav; bottom padding only inside the below-`md` rule.
- [ ] 5.28 GREEN `AppShell.tsx`, `Topbar.tsx`, `BottomNav.tsx` (mounted via `useMediaQuery(up('md'))`, D16) with CSS modules in `@layer components`, skip link. Turns 5.25..5.27 green.
- [ ] 5.29 RED `src/shell/MoreSheet.test.tsx` (SHELL-4): non-admin sheet lists Interface, legacy modules, language and logout and no Admin; admin sees Admin (legacy `/riftbound/price`); Escape closes and focus returns to "Más"; activating an entry closes the sheet. GREEN `MoreSheet.tsx` (leaves a slot for the install item of unit f).
- [ ] 5.30 RED `src/shell/states.test.tsx` (SHELL-8): unknown route `/riftbound/app/does-not-exist` shows the 404 view inside the shell with a link home; a throwing route component shows `ErrorState` while the topbar stays usable; the retry action refetches the failed query. GREEN `NotFound.tsx`, per-layout `errorElement`, wire `*` route and replace `HomePlaceholder` with `HomeHub` in `routes.tsx`.

### 5.E Interface page (SHELL-7, SHELL-9)
- [ ] 5.31 RED `src/account/InterfacePage.test.tsx`: five labelled controls with options (density Auto/Compact/Regular/Comfy, accent Cyan/Orange, slider 0..100 with value, language ES/EN/Auto, view Auto/Table/Grid); moving the slider to 0 sets `--bg-image-opacity` to 0 immediately; the preview component is rendered at 1280 px (`xl`) and absent at 390 px.
- [ ] 5.32 GREEN `src/account/{InterfacePage,BackgroundPreview}.tsx`; `/account` redirects to `/account/interface`; strings in `prefs` and `nav` catalogs (ES/EN parity test stays green). Turns 5.31 green.
- [ ] 5.33 RED+GREEN `vitest-axe` sweeps (SHELL-9, SHELL-7): shell at 390 px and 1280 px, with the "Más" sheet open, and the Interface page; fix violations.

### 5.F Jinja coexistence and rename (SHELL-10)
- [ ] 5.34 CHAR `tests/test_shell_coexistence.py`: the landing `GET /` body is pinned (stable marker strings) so it proves it stays unchanged; Jinja pages list: login, register, dashboard, set, card, collection, deck, price (admin), profile.
- [ ] 5.35 RED same file: authenticated `GET /riftbound/` contains an anchor to `/riftbound/app/` with text "Nueva app"; each listed page's `<title>` and brand text contain "Rift Manager" and not "Riftbound Manager".
- [ ] 5.36 GREEN `app/templates/base.html` (link "Nueva app", title, brand, footer) and the other templates with the old name (list from 5.1). Turns 5.35 green; the landing CHAR (5.34) stays green.
- [ ] 5.37 Rename the product name in `README.md` and `AGENTS.md` prose (not repo or path names); run `tests/test_docs.py`.
- [ ] 5.38 Full pytest suite green (SHELL-10 "Full suite"); any assertion edited only for the renamed string is listed in the PR.

### 5.G Docs and PR checkpoint
- [ ] 5.39 `docs/frontend.md`: shell anatomy, nav registry (how to flip an entry from `legacy` to `spa`), prefs model and sync, how to add a catalog namespace; AGENTS tree for `shell/`, `prefs/`, `account/`.
- [ ] 5.40 Full lanes green: vitest, lint, typecheck, build, `check:dist`, pytest.
- [ ] 5.41 USER [MANUAL]: screenshots of the real app at slider 0, 50, 100 on a phone and a desktop attached to the PR; confirm the default (100 or other), blur and darkening; tune `background.ts` constants and the golden table if changed.
- [ ] 5.42 USER [MANUAL] dev rollout (rebuild + restart); check Jinja pages show the new title and the "Nueva app" link, and the SPA shell at phone and desktop widths.
- [ ] 5.43 PR checkpoint (`feat/f1-e`): SHELL-1..10, PREF-6..8 mapped; PR amends PREF-6 and SHELL-3 text (R1, R3). USER merges.

## Unit 6 (f): PWA
Specs: PWA-1..9, CI-5 manifest check (R9), D20 `mark-simple`, D21 icons. Depends: a + b + e. Rollback: build with `VITE_PWA_SELF_DESTROY=true`, deploy, wait for clients, then revert (a plain revert leaves the SW installed).

### 6.A Dependencies
- [ ] 6.1 `npm view` for vite-plugin-pwa 1.3.0, workbox-window 7.4.1 (lock must resolve workbox-build 7.4.1), `@vite-pwa/assets-generator` (newest on or before 2026-10-05 compatible with the plugin).
- [ ] 6.2 `npm install --save-exact --before=2026-10-05` those packages; extend the required-present set of `pins.test.ts` (RED first by adding the expectation, then install).

### 6.B Favicon mark and icons (PWA-2, D20, D21)
- [ ] 6.3 RED `src/assets/brand/brand-assets.test.ts`: `mark-simple.svg` exists, is valid SVG without raster, and its path count is lower than or equal to the mark.
- [ ] 6.4 GREEN `scripts/brand-trace.mjs` part 3: morphological dilation of about 2 % and higher `turdSize` produce `src/assets/brand/mark-simple.svg`. Turns 6.3 green.
- [ ] 6.5 USER [MANUAL]: favicon sign-off at 16, 32 and 48 px (simplified mark acceptable or not).
- [ ] 6.6 RED `frontend/scripts/check-dist.test.ts` icon cases: icon files exist and the PNG IHDR width/height equal the sizes declared in the manifest fixture; one 512 icon has purpose `maskable`; apple-touch 180 exists.
- [ ] 6.7 GREEN `pwa-assets.config.ts` (presets: transparent 64/192/512 on `#06222c` with 10 % padding; maskable 512 full-bleed with 30 % padding; apple 180 with 20 % padding; `favicon.ico` 48 from `mark-simple`, plus `favicon.svg`); run `npm run icons`; commit the outputs in `frontend/public/`.
- [ ] 6.8 USER [MANUAL]: maskable preview shows the mark inside the 80 % safe zone (PWA-2).
- [ ] 6.9 Wire the `icons` script to the assets generator (replaces the placeholder of 1.2).

### 6.C Manifest, SW and head (PWA-1, PWA-3, PWA-5, D23)
- [ ] 6.10 RED `frontend/pwa-options.test.ts` on the pure options module `pwa-options.ts`: `registerType:'prompt'`, `injectRegister:false`, `strategies:'generateSW'`, `devOptions.enabled:false`; manifest `name`/`short_name` "Rift Manager", `id` and `scope` `/riftbound/`, `start_url` `/riftbound/app/` inside the scope, `display` `standalone`, `theme_color`/`background_color` `#06222c`, `categories` has `games`; workbox: `navigateFallback` `/riftbound/app/index.html`, allowlist matches only `/riftbound/app/...`, denylist matches `/riftbound/api/x`, `/riftbound/static/x`, `/riftbound/app/a.js` and not `/riftbound/app/account`; `skipWaiting` and `clientsClaim` false; `cleanupOutdatedCaches`; no `runtimeCaching`; `maximumFileSizeToCacheInBytes` 3 MiB; Fontsource non-latin subsets in `globIgnores`; `selfDestroying` follows `VITE_PWA_SELF_DESTROY`.
- [ ] 6.11 GREEN `pwa-options.ts` and `VitePWA` in `vite.config.ts`; `index.html` meta (`apple-mobile-web-app-capable`, `mobile-web-app-capable`, status bar style, `apple-mobile-web-app-title=Rift Manager`, apple-touch-icon, `favicon.svg`, `favicon.ico`). Turns 6.10 green.
- [ ] 6.12 RED `check-dist.test.ts` manifest/head/SW cases (CI-5 "Manifest check", PWA-1, PWA-3): a manifest named "Riftbound Manager" fails; correct values pass; `start_url` outside `scope` fails; `index.html` lacks manifest link, `theme-color` `#06222c`, title or apple tags fails; `sw.js` missing or precache without `index.html` or either background image fails; a precache URL under `/riftbound/api` fails; a registered route for `/riftbound/api` fails.
- [ ] 6.13 GREEN extend `scripts/check-dist.mjs` for 6.6 and 6.12 and the FAUTH-3 rule (`dist/.vite/manifest.json`: `altcha` absent from the entry chunk static imports). Real build + `npm run check:dist` green. Turns 6.6 and 6.12 green.
- [ ] 6.14 RED+GREEN self-destroying build (PWA-5): `check-dist.mjs --self-destroy <dir>` asserts `sw.js` contains unregister/cache-clearing logic and no precache manifest; add a CI step that builds with `VITE_PWA_SELF_DESTROY=true --outDir` to a path outside the uploaded artifact and runs that check; extend `TestFrontendJob` to expect the step.

### 6.D Update prompt (PWA-4)
- [ ] 6.15 RED `src/pwa/useUpdatePrompt.test.tsx` (mock `virtual:pwa-register/react`, vitest alias): `needRefresh` shows the "Nueva versión" toast with an "Actualizar" action and no reload; activating it calls `updateServiceWorker(true)` once; dismissing keeps a half-filled form's values and does not reload; update checks run every 60 min (fake timers) and on `visibilitychange` to visible, only when online.
- [ ] 6.16 GREEN `src/pwa/{useUpdatePrompt.ts,UpdateToast.tsx}` mounted in `AppProviders`; ES/EN strings in `common`. Turns 6.15 green.

### 6.E Install entry (PWA-6)
- [ ] 6.17 RED `src/pwa/useInstall.test.tsx`: a captured `beforeinstallprompt` is `preventDefault`ed and activating "Install" calls the saved `prompt()`; `appinstalled` clears it; iOS Safari UA (iPhone, iPad, MacIntel with touch) without the event shows the item and opens `IosInstallDialog` with the Share and Add to Home Screen steps; `display-mode: standalone` or `navigator.standalone` hides the item; no install path hides it.
- [ ] 6.18 GREEN `src/pwa/{installPrompt.ts,useInstall.ts,IosInstallDialog.tsx}`; start `installPrompt.listen()` in `main.tsx` before React; add the item to `MoreSheet` and an equivalent entry in the desktop `Topbar` menu. Turns 6.17 green and the 5.29 tests stay green.

### 6.F Offline (PWA-7)
- [ ] 6.19 RED `src/pwa/offline.test.tsx`: session request network error with the hint boots the shell with the `OfflineBanner` (`role="status"`, translated); without the hint an `ErrorState` with retry; a 401 always goes to login; the `online` event removes the banner; Interface-page controls and logout are disabled while offline and no PATCH is sent.
- [ ] 6.20 GREEN `src/lib/useOnline.ts`, `src/components/ui/OfflineBanner.tsx`, offline branch in `requireAuth` and `AppShell`, disabled state in `prefs/sync.ts` consumers. Turns 6.19 green.

### 6.G Docs and CI
- [ ] 6.21 RED `tests/test_frontend_contracts.py::TestDocs`: `docs/frontend.md` contains "self-destroying" and the rollback steps (PWA-5 "Documented"). GREEN: runbook (build with `VITE_PWA_SELF_DESTROY=true`, deploy, wait, revert), icon regeneration, SW scope notes, device checklist.
- [ ] 6.22 RED+GREEN `tests/test_ci_workflows.py`: the frontend job runs `npm run check:dist` after the build and before the upload (manifest check, CI-5); the self-destroy step of 6.14 exists.
- [ ] 6.23 `AGENTS.md` / `README.md`: `pwa/` folder, icons command; `tests/test_docs.py` green.

### 6.H Verify, device checks and PR checkpoint
- [ ] 6.24 Full lanes green: vitest, lint, typecheck, build, `check:dist` (manifest, icons, SW), pytest.
- [ ] 6.25 [GH-CI] `frontend` job green with the manifest check; deliberately failing manifest rehearsed locally (6.12).
- [ ] 6.26 USER [MANUAL] dev rollout (rebuild + restart over HTTPS). Lighthouse installability passes for `/riftbound/app/` (PWA-9).
- [ ] 6.27 USER [MANUAL] Android Chrome: install, launched window name and icon "Rift Manager".
- [ ] 6.28 USER [MANUAL] iOS Safari: Add to Home Screen via the dialog steps; icon and name correct.
- [ ] 6.29 USER [MANUAL] desktop Chrome/Edge: install entry, standalone window.
- [ ] 6.30 USER [MANUAL] SW scope is `/riftbound/app/` and a Jinja page is not controlled (PWA-3).
- [ ] 6.31 USER [MANUAL] offline: airplane mode opens the shell with the banner (PWA-7); back online removes it.
- [ ] 6.32 USER [MANUAL] update flow: deploy a second build, reopen the installed app, the prompt appears and accepting loads the new version (PWA-4).
- [ ] 6.33 USER [MANUAL] sign in with Remember me on, close the installed app completely, reopen the next day and still be signed in (PWA-8).
- [ ] 6.34 USER [MANUAL] rollback rehearsal on dev: deploy the self-destroying build, confirm the SW unregisters and caches clear, then redeploy the normal build.
- [ ] 6.35 PR checkpoint (`feat/f1-f`): PWA-1..9 mapped to tests or manual items 6.26..6.34 with results recorded; favicon sign-off (6.5) quoted. USER merges.

## Unit 7 (g): Hardening (optional)
Specs: no new requirements (hardens HOST-6, DS-7). Depends: f. Rollback: `SPA_CSP=off`.

- [ ] 7.1 RED `tests/test_spa_hosting.py::TestCsp`: `index.html` (and the fallback) carry `Content-Security-Policy-Report-Only` with the directives of design §9 unit g; assets do not; `SPA_CSP=off` removes it; default is `report-only`; an invalid value fails `validate_settings` with a clear message.
- [ ] 7.2 GREEN `config.py` (`SPA_CSP`), `.env.example`, README, `app/routes/spa.py` header. Turns 7.1 green; `tests/test_docs.py` green.
- [ ] 7.3 Axe sweep: list every route in `routes.tsx` and ensure each has a `vitest-axe` test (login, register, shell both widths, sheet, Interface, 404, error state); fix gaps.
- [ ] 7.4 USER [MANUAL]: run Lighthouse (performance, accessibility, best practices, PWA) on `/riftbound/app/` and `/riftbound/app/login`; record scores and actions in `docs/frontend.md`.
- [ ] 7.5 USER [MANUAL]: browse the app with the console open; list CSP report-only violations; tune the policy or the code.
- [ ] 7.6 Docs: CSP policy, how to turn it off, how to move to enforcing mode later; `AGENTS.md`.
- [ ] 7.7 Verify + PR checkpoint (`feat/f1-g`); full lanes green. USER merges.

## Summary

| Unit | Name | Tasks | Specs | PR |
|---|---|---|---|---|
| 0 | Prerequisites (USER) | 6 | n/a | none |
| 1 (a) | frontend-toolchain + brand | 52 | DS-1..10, CI-5 shape, CI-9 | `feat/f1-a` |
| 2 (b) | spa-hosting | 26 | HOST-1..7 | `feat/f1-b` |
| 3 (c) | api-prefs-session | 39 | PREF-1..5, API-1/4/5/9, SESS-1 | `feat/f1-c` |
| 4 (d) | frontend-auth-i18n | 42 | FAUTH-1..11, I18N-1..5 | `feat/f1-d` |
| 5 (e) | app-shell-prefs | 43 | SHELL-1..10, PREF-6..8, DS-8 | `feat/f1-e` |
| 6 (f) | pwa | 35 | PWA-1..9, CI-5 manifest | `feat/f1-f` |
| 7 (g) | hardening (optional) | 7 | hardens HOST-6, DS-7 | `feat/f1-g` |
| Total | | 250 | | 7 PRs |

Parallelism: a, b, c on separate branches or worktrees; d needs a+b+c; e needs d; f needs a+b+e; g needs f. Dev rollout order (3.38): backup, update tree, `npm ci && npm run build`, `flask db upgrade` (0006), restart service.
