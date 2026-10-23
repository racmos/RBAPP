# Project state

Single source of status. Every unit updates this file in its own PR (section "Units" and, when relevant,
"Pending checks", "Follow-ups" and "Known issues"). A unit is **done** when its PR is merged into `main`.

Last update: 2026-10-23 (M-a: test reset; only the authorization matrix and the smoke tests remain).

## Phases

| Phase | Status | Notes |
|---|---|---|
| F0 Foundation | **Done** (PRs #11-#16) | Archived in `openspec/changes/archive/2026-10-19-f0-foundation/`; contracts in `openspec/specs/`. |
| F1 App shell | **Done** (PRs #17-#24, #26, F1-close #27) | Archived in `openspec/changes/archive/2026-10-22-f1-app-shell/` (verify: 67 requirements, 64 PASS, 1 PASS manual, 2 DEFERRED, 0 FAIL); contracts merged into `openspec/specs/` (21 capabilities, 136 requirements). See "F1 detail". |
| F2 Catalog | Planned — next phase | `docs/requirements/F2/` (phase spec + unit drafts with CONFIRM items). |
| F3-F12 | Planned | Phase specs in `docs/requirements/F<n>/README.md`. |

## Plan change (2026-10-22)

The owner changed the order and answered several open decisions: see `decisions-2026-10-22.md` (it wins
over `product.md`, `roadmap.md` and `open-decisions.md` until M-b folds it in). M-a (test reset) is done;
next unit: **M-b** (plan docs). Order: M-a → M-b (plan docs) → M-c (hygiene) → F4-a/F4-b (jobs + daily prices) → F2-a (bans) →
M-d (images out of git) → Riot sync + catalog admin → F2 → F3 + F4-c → Products → medium priority →
production → Rules app → mulligan → events.

## Live on dev (2026-10-21)

- `main` at `492279b` (merge of PR #24) deployed: Jinja app at `/riftbound/`, React PWA at
  `/riftbound/app/`, JSON API at `/riftbound/api/v1`.
- Database at Alembic head `0006_user_prefs`. The app connects with a dedicated non-superuser role that
  owns only the `riftbound` schema.
- Tests after M-a: pytest 21 passed (authorization matrix + 2 smoke tests); vitest 1 (smoke test). The
  old suites live in baseline `902047c6579e5ee670e1fb4b103a941159b85c00`.
- Automated live PWA check (Playwright against the HTTPS dev URL, 2026-10-21): 19/19 — installable (no
  Chromium installability errors), manifest parsed, service worker scope `/riftbound/app/`, Jinja pages
  not controlled, precache has the shell, icons and backgrounds and nothing under `/riftbound/api` or
  `/riftbound/static`, offline deep link opens the shell with the offline banner, logout disabled offline,
  banner removed when back online, offline boot with/without the signed-in hint.

## F1 detail

| Unit | PR | Content |
|---|---|---|
| planning | #17 | `openspec/changes/archive/2026-10-22-f1-app-shell/` (exploration, proposal, 67 requirements, design D1-D26, 250 tasks). |
| a | #20 | Frontend toolchain, tokens, background, brand SVG, CI frontend job. |
| b | #18 | `spa_bp` serving `frontend/dist` at `/riftbound/app/`. |
| c | #19 | Migration `0006`, `GET`/`PATCH /me/prefs`, remember-me 30 days, API error codes. |
| fix | #21 | Portrait background (map rotated 90°). |
| d | #22 | API client, router, login/register with ALTCHA, i18n ES/EN. |
| e | #23 | App shell, navigation, "Más" sheet, Home hub, Interface preferences page, Jinja renamed "Rift Manager" + "Nueva app" link. |
| f | #24 | PWA: manifest, icons, service worker, update toast, install item + iOS dialog, offline banner/boot, self-destroying rollback build. |
| g | #26 | Hardening: `Content-Security-Policy-Report-Only` on the app document (`SPA_CSP=report-only\|off`), axe tests for every route and overlay, precache without duplicates (40 entries/33 unique → 33/33, enforced by `check:dist`), deterministic Toast test. Lighthouse pending (owner). |
| close | #27 | Tasks checked or DEFERRED, `verify-report.md`, delta specs merged into `openspec/specs/`, change archived → `docs/requirements/F1/F1-close.md`. |

## Pending checks (owner)

Only the owner checks still open (DEFERRED in `openspec/changes/archive/2026-10-22-f1-app-shell/tasks.md`). Results already
recorded (favicon, Android and desktop installs, remember-me, live PWA check, logo and background) are in
that file and in its `verify-report.md`.

| Check (F1 task) | Status |
|---|---|
| FAUTH-11 cross-app session (4.41): sign in in the app, open `/riftbound/` (Jinja), still signed in; sign out there, back in the app it shows the login screen | **Pending (owner).** |
| iPhone Safari install (6.28): "Más" → "Instalar app", follow the 3 steps; icon without black corners, name "Rift Manager", opens full screen | **Pending — to test later.** |
| macOS install (6.28b): Safari ("Añadir al Dock") or Chrome; own window, correct icon | **Pending — to test later.** |
| Lighthouse (6.26, 7.4): installability plus performance, accessibility and best-practices for `/riftbound/app/login` and `/riftbound/app/`; record in `docs/frontend.md` → "Lighthouse baseline" | **Pending (owner).** Chromium reports no installability errors (live, 2026-10-21). |
| Update prompt on a real device (6.32): at the next deploy of a new frontend build, toast "Nueva versión disponible." with "Actualizar"; no reload by itself | **Pending.** Verified locally in Chromium with two builds. |
| CSP report-only console review (7.5): browse every screen with the console open after the F1-g deploy; send any `[Report Only]` line to the planner | **Pending (owner).** |
| Rollback rehearsal on dev (6.34) | Not run on dev on purpose (it would uninstall the worker on the owner's devices); verified locally in Chromium. |

## Follow-ups

- F0 4.31: Nginx `limit_req` on the public proxy (template in `docs/nginx_config`) — owner action, or F12.
- F0 5.20: owner review of `README.md` / `AGENTS.md`.
- Riot fan-content disclaimer: F11. Licensing review (fonts, assets, Riot IP): before F12.
- Hygiene: `openspec/changes/archive/2026-10-19-f0-foundation/` mentions private IPs; `docs/nginx_config`
  contains the dev domain. Replace with placeholders (unit M-c).
- `docs/migrations.md` restarts `rbapp` while the repo unit file is `docs/riftbound.service`: align the naming.
- Legacy endpoints leak exception text: `cards.upload_card_image` and several `price.py` endpoints return
  `str(e)` in a 500, and the generic `except` of `validate_json` returns it in a 400. About 20 legacy places
  use `datetime.utcnow()` instead of `app/utils/clock.utcnow()`. Fix when the module is ported (F2/F10) or
  in a small hardening unit.
- Guards to re-create when their area is touched: see the test policy (AGENTS.md → Testing).
- OPAPP and DB tools on the owner's side use the rotated database superuser password (owner action, done
  or pending on their side; nothing in this repo).

## Known issues

- `frontend/src/assets/brand/mark.svg` and `wordmark.svg` are not byte-reproducible from
  `scripts/brand-trace.mjs` (a full run produces a heavier trace); do not regenerate them blindly.
- `dist/.vite/manifest.json` is publicly served (harmless; it lists chunk names only).
- The Riot scraper rewrites every field on update, so it resets `rbcar_banned` to `N` on each run (F2-a
  moves bans to their own table).
- The Jinja catalog SQL uses PostgreSQL-only constructs (`~`, `regexp_replace`, shimmed in SQLite tests).
- 376 card images under `app/static/images/cards/` are tracked in git despite the ignore rule (F12-g moves
  images out of the code tree).
- The landing feeds (`app/services/scraper.py`) serve placeholder news/tournaments; there is no real event
  source yet (F8 D-F8-1).
- `rbcollection` CHECK allows `rbcol_selling = 'S'` but the app writes only Y/N (F3 normalises it).
- The repo's systemd/Gunicorn docs use the default 30 s timeout while Cardmarket load and Riot extraction run
  inside the request (the dev server overrides it; F4/F10 move them to jobs).

## Units (from F1-close on)

| Unit | Status | Branch / PR | Notes |
|---|---|---|---|
| M-a | done | `chore/m-a-test-reset` / #TBD | Old suites removed; kept authz matrix + smoke tests; baseline `902047c6579e5ee670e1fb4b103a941159b85c00`. pytest 1694 passed / 41 skipped → 21 passed; vitest 1189 → 1. |
| F1-close | done | `chore/f1-close` / #27 | Verify report (67 requirements, 0 FAIL, no defects), 8 spec amendments, specs merged (62 ADDED + 5 MODIFIED), archive `2026-10-22-f1-app-shell`. Lanes on `c2a7fe7`: pytest 1694 passed / 41 skipped, vitest 1189. |
| F1-g | done | `feat/f1g-hardening` / #26 | CSP report-only + `SPA_CSP`, axe sweep, precache dedupe, Toast deflake. pytest 1640 → 1694; Lighthouse pending (owner). |
