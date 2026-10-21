# F1-g: Hardening — CSP report-only on the app, axe sweep, precache de-duplication, deflaked toast test

| Field | Value |
|---|---|
| Phase / unit | F1 / g |
| Branch | `feat/f1g-hardening` (from up-to-date `main`) |
| Depends on | PR #24 (F1-f) merged — done |
| Size forecast | ~300-450 authored lines (tests and docs included) |
| Risk | `Risk: item 2 (adds a security response header to the SPA; report-only, it cannot block anything)` |
| TDD | ON (strict). Runners: `venv/bin/pytest` (backend), `cd frontend && npx vitest run` (frontend) |
| Save as | `docs/requirements/F1/F1-g-hardening.md` (already in the repo) |

## Objective

Finish F1 with the optional hardening unit planned in `openspec/changes/f1-app-shell/tasks.md` (unit 7):
the React app gets a Content Security Policy in report-only mode (to learn what an enforcing policy would
break before F12), every app screen is covered by an automated accessibility check, the service worker
precache stops listing files twice, and a timing-flaky test becomes deterministic.

## Read first

- `AGENTS.md`, `docs/knowledge/conventions.md`, `docs/frontend.md` (sections on hosting and the PWA)
- `openspec/changes/f1-app-shell/tasks.md` unit 7 (7.1-7.7) and `design.md` §9, row "g"
- `app/routes/spa.py`, `config.py` (`validate_settings`, `ConfigError`, the env parsing helpers), `.env.example`
- `tests/test_spa_hosting.py` (fixtures `spa_dist` / `spa_app`)
- `frontend/pwa-options.ts` (`includeAssets`, `workbox.globPatterns`), `frontend/scripts/check-dist.mjs` and `check-dist.test.ts`
- `frontend/src/app/routes.tsx`, `frontend/src/shell/axe.test.tsx`, the existing axe tests in
  `src/auth/LoginPage.test.tsx`, `src/auth/RegisterPage.test.tsx`, `src/account/InterfacePage.test.tsx`
- `frontend/src/components/ui/Toast.test.tsx`

## Scope

In:
- `Content-Security-Policy-Report-Only` header on the SPA HTML responses, `SPA_CSP` setting.
- Axe coverage for every app route and overlay.
- Precache without duplicated URLs, enforced by `check:dist`.
- Deterministic toast-duration test.
- Docs.

Out:
- An enforcing CSP (F12). A `report-uri`/`report-to` endpoint. CSP on Jinja pages or on the API.
- Lighthouse automation in CI.

## Specs

S1. Every HTML response of `spa_bp` that serves `index.html` (the app root `/riftbound/app/` and every
    extension-less path that falls back to `index.html`) carries exactly this header when `SPA_CSP` is
    `report-only`:
    `Content-Security-Policy-Report-Only: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; worker-src 'self' blob: data:; connect-src 'self'; frame-ancestors 'self'; base-uri 'self'`
  - Example: `GET /riftbound/app/collection` (fallback) → 200 `text/html` with that header, byte for byte.
S2. Responses that are not `index.html` do not carry the header: `assets/*`, `sw.js`,
    `manifest.webmanifest`, icons, the 404 for a missing file with an extension, and the 503 "no build" page.
    No response carries an enforcing `Content-Security-Policy` header.
S3. Setting `SPA_CSP` (environment variable), values `report-only` (default when unset) and `off`.
  - `off` → no CSP header on any SPA response.
  - Any other value → the app refuses to start with `ConfigError` whose message contains
    `SPA_CSP must be report-only or off`. Parse it the same way `config.py` parses the other environment
    switches (the helpers that raise `{name} must be true or false`), so an invalid value fails exactly
    when an invalid boolean switch fails; verify how those helpers are called before adding the new one.
  - `.env.example` documents it next to the other kill switches: `# SPA_CSP=report-only   # report-only | off`.
S4. Accessibility: every route of `frontend/src/app/routes.tsx` and every overlay has a `vitest-axe` test with
    no violations: login, register (with the captcha widget mocked as in its current tests), shell at 390 px
    and 1280 px, "Más" sheet (member and admin), Interface page, 404, route error state (`RouteError`), iOS
    install dialog, update toast, offline banner. Reuse the existing tests where they already exist; add only
    the missing ones; fix any violation found in the component, not in the test.
S5. Precache: every URL appears once in the precache manifest of the generated `sw.js`.
  - RED first: `check-dist.test.ts` case "a precache URL listed twice fails" (the valid fixture with one
    entry duplicated must make `check-dist` exit 1 naming the URL).
  - GREEN: `check-dist.mjs` rejects duplicates; `pwa-options.ts` stops producing them (today
    `includeAssets` lists `favicon.svg`, `favicon.ico`, `apple-touch-icon-180x180.png` while
    `globPatterns` already matches them, and the plugin adds the manifest and its icons again: 40 entries,
    33 unique; duplicated today: `manifest.webmanifest`, `pwa-192x192.png`, `pwa-512x512.png`,
    `maskable-icon-512x512.png`, `apple-touch-icon-180x180.png`, `favicon.svg`, `favicon.ico`). After the fix: a real `npm run build` + `npm run check:dist` is clean and the entry count
    equals the unique count (record both numbers in the PR).
  - The icons, `favicon.*`, `index.html`, the three background images and the fonts stay precached
    (the existing `check-dist` rules keep passing).
S6. `src/components/ui/Toast.test.tsx` "removes a toast after its duration" is deterministic: fake timers
    (`vi.useFakeTimers()` + `vi.advanceTimersByTime`) or an equivalent that does not depend on wall-clock
    speed. Prove it by running that file 20 times in a row green (shell loop) and say so in the PR.
S7. Docs:
  - `docs/frontend.md` new section "Content Security Policy": the policy (S1 string), why report-only, how to
    read violations (browser console), how to turn it off (`SPA_CSP=off`), and the steps to move to
    enforcing later (collect violations, adjust, then switch the header name; planned for F12).
  - `AGENTS.md`: mention `SPA_CSP` in the SPA hosting paragraph; `README.md` config list if it lists the
    other kill switches. Keep CRLF in those files.
  - `docs/knowledge/state.md`: F1-g done (PR placeholder), Known issues: remove the precache duplicates and
    the flaky Toast entries.
S8. Lighthouse (best effort, not blocking): if Lighthouse can run headless on the server against the dev
    URL (`/riftbound/app/login` and, signed out, `/riftbound/app/`), record performance, accessibility and
    best-practices scores with the date in `docs/frontend.md` → "Lighthouse baseline". Lighthouse 12+ has no
    PWA category; installability is already covered by the live check. If it cannot run, write
    "pending (owner)" there and list it under manual checks.

## API / data contract

Response header only (S1-S3). No endpoint or schema change.

## UI

No visible change. Axe fixes (S4), if any, must keep the current look.

## Acceptance criteria

- [ ] AC1 `tests/test_spa_hosting.py::TestCsp` (RED first): header present on root and fallback, exact string; absent on assets, `sw.js`, manifest, icons, 404, 503; `off` removes it; invalid value raises `ConfigError` with the message (S1-S3).
- [ ] AC2 Axe tests for every route/overlay listed in S4, all without violations (S4).
- [ ] AC3 `check-dist.test.ts` duplicate case RED then GREEN; real build has no duplicate precache URL (S5).
- [ ] AC4 Toast test deterministic; 20 consecutive runs green (S6).
- [ ] AC5 Full lanes green: `venv/bin/pytest`; `cd frontend && npm run lint && npm run typecheck && npx vitest run && npm run build && npm run check:dist`.
- [ ] AC6 Docs and `docs/knowledge/state.md` updated (S7); Lighthouse recorded or marked pending (S8).

## Delivery

- Conventional Commits. Suggested slices: (1) CSP + config + docs, (2) axe sweep, (3) precache + toast.
- Push and PR when the owner says so. PR title: `feat(spa): CSP report-only, axe sweep, precache dedupe (F1 unit g)`.
  PR body: summary, S# → test map, precache counts before/after, manual checks, rollback (`SPA_CSP=off`).
- Never merge.

## After merge

- Deploy to dev with `docs/knowledge/ops-runbook.md` (frontend rebuild + restart; no migration).
- Live checks:
  - `curl -sI <URL>/riftbound/app/ | grep -i content-security-policy-report-only` → the S1 string.
  - `curl -sI <URL>/riftbound/app/sw.js | grep -ci content-security-policy` → `0`.
  - The PWA live check (see `ops.local.md`) still 19/19.
- Manual checks for the owner:
  1. Open the app with the browser console visible, sign in, browse every screen (home, Interface, "Más",
     install dialog), sign out, register page with the captcha. Copy any line that starts with
     "[Report Only]" and send it to the planner (planned follow-up: tune the policy or the code).
  2. This deploy is also the first real test of the update prompt (F1 6.32): on the installed app, reopen
     it; the toast "Nueva versión disponible." must appear with "Actualizar".

## Open questions

none
