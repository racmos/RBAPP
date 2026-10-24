# Project state

Single source of status. Every unit updates this file in its own PR (section "Units" and, when relevant,
"Pending checks", "Follow-ups" and "Known issues"). A unit is **done** when its PR is merged into `main`.

Last update: 2026-10-24 (F4-b: daily Cardmarket load job, PR #<PR>; next unit F2-a, bans).

## Phases

| Phase | Status | Notes |
|---|---|---|
| F0 Foundation | **Done** (PRs #11-#16) | Archived in `openspec/changes/archive/2026-10-19-f0-foundation/`; contracts in `openspec/specs/`. |
| F1 App shell | **Done** (PRs #17-#24, #26, F1-close #27) | Archived in `openspec/changes/archive/2026-10-22-f1-app-shell/` (verify: 67 requirements, 64 PASS, 1 PASS manual, 2 DEFERRED, 0 FAIL); contracts merged into `openspec/specs/` (21 capabilities, 136 requirements). See "F1 detail". |
| M-a Test reset | **Done** (#29) | `docs/requirements/M/M-a-test-reset.md`. |
| M-b Plan update | **Done** (#30) | `docs/requirements/M/M-b-plan-update.md`. |
| M-c Hygiene | **Done** (#31) | `docs/requirements/M/M-c-hygiene.md`. |
| F4 Prices + Dashboard | In progress — F4-a done (#32), F4-b in review (#<PR>); the rest waits (F4-c with F3) | F4-a + F4-b (job runner, daily Cardmarket load) right after M-c; F4-c with F3; the rest in the medium-priority group. `docs/requirements/F4/README.md`. |
| F2 Catalog | Planned — **next: F2-a** | F2-a (bans) after F4-a/F4-b; the rest after F13. `docs/requirements/F2/` (phase spec + unit drafts that need the planner's rewrite). |
| M-d Images out of git | Planned | After F2-a. Unit requirement still to write. |
| F13 Riot sync + catalog admin | Planned | `docs/requirements/F13/README.md`. |
| F3 Collection | Planned | With F4-c. `docs/requirements/F3/README.md`. |
| F14 Products | Planned | `docs/requirements/F14/README.md`. |
| F5, F6, F7, F10, F9, F11, F12 | Planned | Medium priority, then production. Phase specs in `docs/requirements/F<n>/README.md`. |
| F15 Rules app | Planned (after production) | `docs/requirements/F15/README.md` (outline). |
| F5-k Mulligan, F8 Events | Planned (after production, after F15) | F5-k in `docs/requirements/F5/README.md`; F8 with the new landing (F11-a/b). |

## Plan change (2026-10-22)

Order and phases: `roadmap.md` (folded in by M-b; record of the answers in `decisions-2026-10-22.md`).

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
| F4-a on the server (after merge): backup, `flask db upgrade` + `flask db check`, restart, install and enable `riftbound-jobs.timer`, then `flask jobs enqueue heartbeat` and `flask jobs list` a minute later (`ops-runbook.md` → "Scheduled jobs") | **Done** (deployed before F4-b). |
| F4-b on the server (after merge): backup, `flask db upgrade` (`0008_jobs_daily_prices`) + `flask db check`, restart, install and enable `riftbound-daily.timer` and `riftbound-daily-retry.timer`, run `flask jobs enqueue daily_prices` once and read the result a few minutes later (`ops-runbook.md` → "Scheduled jobs" → "Daily Cardmarket load") | **Pending (owner).** |
| Rollback rehearsal on dev (6.34) | Not run on dev on purpose (it would uninstall the worker on the owner's devices); verified locally in Chromium. |

## Follow-ups

- F0 4.31: Nginx `limit_req` on the public proxy (template in `docs/nginx_config`) — owner action, or F12.
- F0 5.20: owner review of `README.md` / `AGENTS.md`.
- Riot fan-content disclaimer: F11. Licensing review (fonts, assets, Riot IP): before F12.
- `docs/migrations.md` restarts `rbapp` while the repo unit file is `docs/riftbound.service`: align the naming.
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
- 376 card images under `app/static/images/cards/` are tracked in git despite the ignore rule (unit M-d
  moves them out of git into a data directory).
- The landing feeds (`app/services/scraper.py`) serve placeholder news/tournaments; there is no real event
  source yet (F8 starts with the official upcoming-events calendar; the landing is rebuilt with F8).
- `rbcollection` CHECK allows `rbcol_selling = 'S'` but the app writes only Y/N (F3 evaluates and removes it).
- The repo's systemd/Gunicorn docs use the default 30 s timeout while Cardmarket load and Riot extraction run
  inside the request (the dev server overrides it; F4 and F13 move them to jobs).
- `cardmarket_matcher.auto_match` (also its dry run, used every day by `daily_prices`) reads every
  `rbcm_price` row of every date into memory; watch the job duration against its 1800 s timeout as the
  price history grows.
- `daily_prices` lists singles without an `idMetacard` as `no_candidates` (the matcher skips them).

## Units (from F1-close on)

| Unit | Status | Branch / PR | Notes |
|---|---|---|---|
| F4-b | in review | `feat/f4b-daily-prices` / #<PR> | Job kind `daily_prices` (`app/jobs/daily_prices.py`, 1800 s; migration `0008_jobs_daily_prices` extends `ck_rbjobs_kind`, its downgrade refuses while such jobs exist): `CardmarketLoader().run()` with the default URLs, validation record from `rbcm_load_history`/`rbcm_price`/`rbcm_products`, clear-case linking from `auto_match(dry_run=True)` (one product + one free candidate card, confidence 0.7), review list in `rbjob_result` (≤ 200 + `review_total`), all in `app/services/daily_prices.py`; loader and matcher unchanged. `JobFailed` stores a handler message without the class name. `flask jobs enqueue <kind> --unless-succeeded-today` (UTC date) for the 08:00 retry; daily and retry systemd templates complete; runbook "Daily Cardmarket load". pytest 160 → 211. Next unit: **F2-a**. |
| F4-a | done | `feat/f4a-job-runner` / #32 | Table `rbjobs` (migration `0007_jobs`, one queued/running job per kind by partial unique index), registry `app/jobs/` with the `heartbeat` kind, runner service `app/services/jobs.py` (conditional-UPDATE claim, kind timeouts), `flask jobs enqueue\|run-pending\|list`, systemd templates in `docs/systemd/` (jobs timer every minute; daily 06:30 and retry 08:00 Europe/Madrid wait for F4-b), runbook "Scheduled jobs". PostgreSQL round trip left to CI `migrations-pg`. pytest 74 → 160. Next unit: **F4-b**. |
| M-c | done | `chore/m-c-hygiene` / #31 | Private IPs/dev domain replaced by placeholders (no history rewrite); legacy 500s and the generic `@validate_json` 400 return a clear message + `internal_error`/`bad_request`, detail only for admins, traceback logged; no `datetime.utcnow` under `app/` (guard test). |
| M-b | done | `docs/m-b-plan-update` / #30 | Decisions of 2026-10-22 folded into `product.md`, `roadmap.md`, `open-decisions.md`, phase specs F2-F12 and this file; new phase specs F13 (Riot sync + catalog admin), F14 (Products), F15 (Rules app). Documentation only. Next unit: **M-c**. |
| M-a | done | `chore/m-a-test-reset` / #29 | Old suites removed; kept authz matrix + smoke tests; baseline `902047c6579e5ee670e1fb4b103a941159b85c00`. pytest 1694 passed / 41 skipped → 21 passed; vitest 1189 → 1. |
| F1-close | done | `chore/f1-close` / #27 | Verify report (67 requirements, 0 FAIL, no defects), 8 spec amendments, specs merged (62 ADDED + 5 MODIFIED), archive `2026-10-22-f1-app-shell`. Lanes on `c2a7fe7`: pytest 1694 passed / 41 skipped, vitest 1189. |
| F1-g | done | `feat/f1g-hardening` / #26 | CSP report-only + `SPA_CSP`, axe sweep, precache dedupe, Toast deflake. pytest 1640 → 1694; Lighthouse pending (owner). |
