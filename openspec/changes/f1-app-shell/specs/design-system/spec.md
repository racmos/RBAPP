# Delta for design-system

> Tags: `[a]`..`[g]` = delivery unit of change f1-app-shell. `[vitest]` = Vitest + Testing Library (jsdom). `[GH-CI]` = observable in GitHub Actions. `[MANUAL]` = visual/device review. Source of values: `openspec/design-handoff.md` (section numbers cited), except where this spec overrides them (DS-5). Dark mode only. Plain CSS tokens (layered) plus CSS Modules.

## ADDED Requirements

### Requirement: DS-1 Tokens [a]

The frontend MUST define the handoff tokens of section 1.1 as CSS custom properties on `:root` (plain CSS, `@layer`), including colours, `--panel*`, `--line*`, radii, `--gap`, `--pad`, `--row-h`, `--maxw` (1280px), `--maxw-wide` (1760px), fonts and shadows; the z-index scale (`--z-popover` 30, `--z-topbar` 40, `--z-botnav` 50, `--z-modal` 80, `--z-toast` 90); `color-scheme: dark`; `<meta name="theme-color" content="#06222c">`; and the scrollbar styling of section 1.3. Components MUST use tokens, not literal copies of token values.

#### Scenario: Token coverage
- GIVEN `tokens.css`
- WHEN a test parses it [vitest]
- THEN every token of handoff 1.1 exists with the documented value, `--maxw-wide` is `1760px`, and the five `--z-*` values match

#### Scenario: Colour scheme
- GIVEN the built `index.html` and `base.css`
- WHEN inspected
- THEN `color-scheme: dark` is declared and the `theme-color` meta is `#06222c`

### Requirement: DS-2 Accent rule [a]

`data-accent` on `<html>` (`cyan` or `orange`) MUST set `--accent`, `--accent-bright`, `--accent-dim` and `--accent-ink` (orange ink `#160d03`, cyan ink `#04222b`). Interactive states (primary buttons, focus ring, active nav, selected segment, links, slider) MUST derive from `--accent` (via `color-mix`) and MUST NOT hard-code the cyan `rgba(46,198,230,...)`. Cyan MUST remain the fixed information colour (field labels, data highlights). Success stays green and destructive stays red.

#### Scenario: Orange accent
- GIVEN `<html data-accent="orange">` [vitest]
- WHEN the CSS source of the accent tokens and of a primary Button is read (jsdom has no cascade)
- THEN its background resolves from `--accent` (orange), not cyan

#### Scenario: No hard-coded interactive cyan
- GIVEN the CSS of interactive primitives
- WHEN a scan searches for `46,198,230` and `#2ec6e6` [vitest]
- THEN none appear in interactive-state rules (only in info-colour rules or tokens)

### Requirement: DS-3 Density [a]

`data-density` on `<html>` MUST support `compact` and `comfy`; `regular` is the absence of the attribute. The values of handoff 1.2 MUST apply to `--gap`, `--pad`, `--row-h` and `--radius`. `--row-h` and `--radius-sm` MUST be consumed by the row, list and menu primitives and small controls that exist in F1.

#### Scenario: Density tokens
- GIVEN `data-density="compact"` [vitest]
- WHEN the stylesheet is parsed
- THEN `--gap` is 13px, `--pad` 13px, `--row-h` 44px and `--radius` 11px

#### Scenario: Regular
- GIVEN `<html>` without `data-density`
- WHEN computed
- THEN `--gap` is 20px and `--row-h` 54px

### Requirement: DS-4 Breakpoints [a]

`breakpoints.ts` MUST export `sm 680`, `md 860`, `lg 960`, `xl 1240` and `2xl 1600` and be the single source for `useMediaQuery`. Every `@media` width used in the app CSS MUST belong to this set; a Vitest scan MUST fail otherwise. Styles are mobile-first. At `md` and above the bottom nav is replaced by the top navigation; desktop layouts MUST show more data (extra columns/panels), not merely stretch.

#### Scenario: Scan passes
- GIVEN all `.css` files
- WHEN a test extracts `min-width`/`max-width` values from `@media` rules [vitest]
- THEN each value is one of 680, 860, 960, 1240, 1600 (or that value minus 0.02 for max-width ranges)

#### Scenario: Scan fails on strays
- GIVEN a stylesheet with `@media (max-width: 920px)`
- WHEN the scan runs
- THEN it fails naming the file and value

### Requirement: DS-5 Background image, blur and slider [a]

The app background MUST be the Summoner's Rift map (`new_rift.webp`) on a fixed layer behind content, with the handoff dark overlay gradients kept. The image MUST be **slightly blurred and never brightened** so text and UI stay readable. `bgVars(percent)` MUST be a pure function that clamps `percent` to 0..100 and rounds to an integer, and returns CSS variables `--bg-image-opacity` and `--bg-image-filter` such that, for every integer value 0..100: the filter contains a blur greater than 0 px (start value 2 to 4 px, tuned visually); `brightness` is at most 1; `saturate` is at most 1; `opacity` is within 0..1 and non-decreasing in `percent`; `0` yields opacity 0 (no image); `100` yields opacity 1 (image fully visible, still blurred and darkened). The layer MUST be scaled/inset so blurred edges are not visible. A mobile variant of about 1280 px MUST be selected by a width media query below 860 px (not `image-set`) and a portrait variant by `orientation: portrait`; all variants MUST be precached. These rules replace the handoff 1.4 table. The default value is 100 unless the user decides otherwise in the PR screenshots.

#### Scenario: Slider bounds
- GIVEN `bgVars(0)` and `bgVars(100)` [vitest]
- WHEN evaluated
- THEN the first has opacity 0 and the second has opacity 1 and a blur greater than 0 px

#### Scenario: Never brighten
- GIVEN every integer from 0 to 100 [vitest]
- WHEN `bgVars` is evaluated
- THEN brightness <= 1 and saturate <= 1 in all cases and opacity never decreases as the value grows

#### Scenario: Clamping
- GIVEN inputs -10, 250 and 49.6 [vitest]
- WHEN evaluated
- THEN they behave as 0, 100 and 50 respectively

#### Scenario: Contrast over the extremes
- GIVEN the darkest (0) and the brightest (100) background states composed with the overlay gradients [vitest]
- WHEN the contrast of `--text` and `--muted` body text over them is computed
- THEN every pair is at least 4.5:1

#### Scenario: Visual review [MANUAL]
- GIVEN screenshots at 0, 50 and 100 on mobile and desktop
- WHEN the user reviews them
- THEN the image is visibly blurred and darkened and the default value is confirmed

### Requirement: DS-6 Self-hosted fonts [a]

Manrope and Space Grotesk MUST be self-hosted (variable fonts, `latin` and `latin-ext` subsets only, `font-display: swap`). The build output MUST NOT reference third-party font hosts, and the precache MUST include the latin fonts.

#### Scenario: No external fonts
- GIVEN the built CSS and `index.html`
- WHEN searched for `fonts.googleapis.com` and `fonts.gstatic.com`
- THEN there are no matches

### Requirement: DS-7 Accessibility and responsive baseline [a]

Following WCAG 2.2 AA: normal text MUST have contrast of at least 4.5:1 against its actual background (the handoff contrast fixes for `--muted-2` at 4.26:1, white on red at 4.14:1 and `--red` text at 3.98:1 MUST be applied to every token used by F1); a global `:focus-visible` ring using the accent MUST exist for all interactive elements; interactive targets MUST be at least 24x24 CSS px; visible text MUST NOT be smaller than 11 px; `prefers-reduced-motion: reduce` MUST disable non-essential animation; overlays MUST use native `<dialog>`; the viewport meta MUST include `viewport-fit=cover` with safe-area insets and `100dvh` where full height is needed; `backdrop-filter` MUST have a solid fallback.

#### Scenario: Token contrast
- GIVEN the text/background token pairs used by F1 components [vitest]
- WHEN contrast is computed
- THEN every normal-text pair is at least 4.5:1

#### Scenario: Focus visible
- GIVEN keyboard focus on a Button, a link and an Input [vitest]
- WHEN styles are read
- THEN each has a visible focus indicator that is not removed by `outline: none` without a replacement

#### Scenario: Reduced motion
- GIVEN `prefers-reduced-motion: reduce`
- WHEN the stylesheet is scanned
- THEN transitions and animations are disabled or shortened to a non-moving state

### Requirement: DS-8 Primitives [a][e]

The library MUST provide, with typed props: Button, Field (label bound by `useId`, `aria-describedby` for hint/error), Input, Select, PasswordInput, Switch (`role="switch"`), SegmentedControl (radiogroup semantics), Slider (labelled, with visible value), Panel, PageHeader, Badge, Avatar, SettingsCard, Icon (SVG, `aria-hidden` by default; the 47 prototype icons plus `more`, `install`, `warning`, `offline`, `settings`, `info`, `external-link`, `check-circle`), Brand (mark and wordmark), Modal/Sheet/ConfirmDialog on native `<dialog>`, and Toast. Components deferred by the proposal (DomainPips, DataTable, Stepper, charts, etc.) MUST NOT be part of F1.

Overlays MUST close on Escape and on backdrop click (except ConfirmDialog backdrop), trap focus through the native modal behaviour and return focus to the opener. Toast MUST be announced through `aria-live`, support an action slot and auto-dismiss without removing items the user is interacting with.

#### Scenario: Field wiring
- GIVEN a Field with label, hint and error [vitest]
- WHEN rendered
- THEN the input is reachable by label text and `aria-describedby` references the hint and error ids

#### Scenario: Dialog focus
- GIVEN a Modal opened from a button [vitest]
- WHEN the user presses Escape
- THEN the dialog closes and focus returns to the button

#### Scenario: Segmented control
- GIVEN a SegmentedControl with three options [vitest]
- WHEN the user selects the second with keyboard arrows
- THEN `onChange` fires with that value and exactly one option is checked

#### Scenario: Toast action
- GIVEN a toast with an "Actualizar" action [vitest]
- WHEN it is shown
- THEN it is inside an `aria-live` region and the action is a focusable button

### Requirement: DS-9 Brand assets [a]

The originals supplied by the user MUST be copied to `frontend/assets-src/brand/`. The build MUST use, from `frontend/src/assets/brand/`: a clean SVG trace of the mark (fallback: white-to-transparent WebP/PNG) and a cropped transparent wordmark. Neither asset may show a white halo on `#06222c`. The wordmark, being an image, MUST expose the accessible name "Rift Manager" (`alt` or visually hidden text); the mark used alone MUST have the same name when it is the only brand element. The brand orange matches the default accent.

#### Scenario: Assets exist
- GIVEN the repository after unit a
- WHEN listed
- THEN the originals exist under `assets-src/brand/` and the derived files under `src/assets/brand/`

#### Scenario: Accessible name
- GIVEN the Brand component in wordmark and mark-only variants [vitest]
- WHEN queried by role/name
- THEN both resolve to the name "Rift Manager"

#### Scenario: No halo [MANUAL]
- GIVEN the assets rendered on `#06222c`
- WHEN reviewed at 1x and 2x
- THEN no white fringe is visible

### Requirement: DS-10 Toolchain and pins [a]

`frontend/` MUST be a Vite 8 + React 19 + TypeScript 6.0.3 project with exact versions (no `^` or `~`), `.npmrc` with `save-exact=true` and `engine-strict=true`, `engines.node >= 22.22`, and a committed `package-lock.json`. React Router 8 (data mode), TanStack Query 5, react-i18next, vite-plugin-pwa 1.3.0 (with workbox 7.4.1) and `altcha` 2.3.0 MUST be pinned at the versions of the proposal; the packages marked too new in the exploration MUST NOT be used. Scripts `dev`, `build` (`tsc -b && vite build`), `preview`, `lint` (ESLint flat + Prettier check), `typecheck`, `test` and `icons` MUST exist. The base path MUST default to `/riftbound/app/` and be configurable (`VITE_BASE`, `VITE_API_BASE`). The dev server MUST proxy `/riftbound/api` and `/riftbound/static` to Flask. The app MUST be built and tested with strict TDD (test before implementation).

#### Scenario: Exact pins
- GIVEN `frontend/package.json`
- WHEN a test reads dependency versions [vitest]
- THEN none starts with `^`, `~` or `>` and the pinned packages match the proposal table

#### Scenario: Scripts present
- GIVEN `package.json`
- WHEN scripts are listed
- THEN `dev`, `build`, `preview`, `lint`, `typecheck`, `test` and `icons` exist

#### Scenario: Clean install in CI [GH-CI]
- GIVEN a clean checkout
- WHEN `npm ci`, `npm run lint`, `npm run typecheck`, `npx vitest run` and `npm run build` run
- THEN all pass and `dist/index.html` exists
