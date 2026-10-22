# Project state

Single source of status. Every unit updates this file in its own PR (section "Units" and, when relevant,
"Pending checks", "Follow-ups" and "Known issues"). A unit is **done** when its PR is merged into `main`.

Last update: 2026-10-21 (handoff from the SDD workflow to Claude Project + gentle-shell).

## Phases

| Phase | Status | Notes |
|---|---|---|
| F0 Foundation | **Done** (PRs #11-#16) | Archived in `openspec/changes/archive/2026-10-19-f0-foundation/`; contracts in `openspec/specs/` (14 capabilities). |
| F1 App shell | **Units a-g done** (PRs #17-#24, #26); close pending | See "F1 detail". |
| F2 Catalog | Planned — next phase | `docs/requirements/F2/` (phase spec + unit drafts with CONFIRM items). |
| F3-F12 | Planned | Phase specs in `docs/requirements/F<n>/README.md`. |

## Live on dev (2026-10-21)

- `main` at `492279b` (merge of PR #24) deployed: Jinja app at `/riftbound/`, React PWA at
  `/riftbound/app/`, JSON API at `/riftbound/api/v1`.
- Database at Alembic head `0006_user_prefs`. The app connects with a dedicated non-superuser role that
  owns only the `riftbound` schema.
- Tests on `main`: pytest 1640 passed / 41 skipped (PostgreSQL-only tests skip on SQLite); vitest 1181.
- Automated live PWA check (Playwright against the HTTPS dev URL, 2026-10-21): 19/19 — installable (no
  Chromium installability errors), manifest parsed, service worker scope `/riftbound/app/`, Jinja pages
  not controlled, precache has the shell, icons and backgrounds and nothing under `/riftbound/api` or
  `/riftbound/static`, offline deep link opens the shell with the offline banner, logout disabled offline,
  banner removed when back online, offline boot with/without the signed-in hint.

## F1 detail

| Unit | PR | Content |
|---|---|---|
| planning | #17 | `openspec/changes/f1-app-shell/` (exploration, proposal, 67 requirements, design D1-D26, 250 tasks). |
| a | #20 | Frontend toolchain, tokens, background, brand SVG, CI frontend job. |
| b | #18 | `spa_bp` serving `frontend/dist` at `/riftbound/app/`. |
| c | #19 | Migration `0006`, `GET`/`PATCH /me/prefs`, remember-me 30 days, API error codes. |
| fix | #21 | Portrait background (map rotated 90°). |
| d | #22 | API client, router, login/register with ALTCHA, i18n ES/EN. |
| e | #23 | App shell, navigation, "Más" sheet, Home hub, Interface preferences page, Jinja renamed "Rift Manager" + "Nueva app" link. |
| f | #24 | PWA: manifest, icons, service worker, update toast, install item + iOS dialog, offline banner/boot, self-destroying rollback build. |
| g | #26 | Hardening: `Content-Security-Policy-Report-Only` on the app document (`SPA_CSP=report-only\|off`), axe tests for every route and overlay, precache without duplicates (40 entries/33 unique → 33/33, enforced by `check:dist`), deterministic Toast test. Lighthouse pending (owner). |
| close | — | Record manual results, verify against the F1 specs, archive into `openspec/specs/` → `docs/requirements/F1/F1-close.md`. |

## Pending checks (owner)

Results reported by the owner on 2026-10-21:

| Check (F1 task) | Result |
|---|---|
| Favicon, simplified mark (6.5) | Approved. |
| Maskable icon / Android launcher icon (6.8, 6.27) | Android Chrome install OK (name, icon, standalone). |
| Desktop install Chrome and Edge (6.29) | OK. |
| Remember-me survives closing the installed app until the next day (6.33) | OK. |
| iPhone Safari install (6.28) | **Pending — to test later.** |
| macOS install (Safari/Chrome) | **Pending — to test later.** |
| Lighthouse installability (6.26) | Pending (Chromium reports no installability errors). |
| Update prompt on a real device (6.32) | Pending: observe at the next deploy of a new build. Verified locally in Chromium with two builds. |
| Rollback rehearsal on dev (6.34) | Not run on dev (it would uninstall the worker on the owner's devices); verified locally in Chromium. |
| Lighthouse baseline (F1-g S8, 7.4) | **Pending (owner)**: Lighthouse is not installed on the server; record performance, accessibility and best-practices for `/riftbound/app/login` and `/riftbound/app/` in `docs/frontend.md` → "Lighthouse baseline". |
| CSP report-only console review (F1-g, 7.5) | **Pending (owner)** after the F1-g deploy: browse every screen with the console open and send any `[Report Only]` line to the planner. |
| Background default 100, blur, darkening (1.50, 5.41) and logo trace (1.39) | Owner said the logo is fine and only complained about the zoom, which was fixed; to confirm formally in F1-close. |

## Follow-ups

- F0 4.31: Nginx `limit_req` on the public proxy (template in `docs/nginx_config`) — owner action, or F12.
- F0 5.20: owner review of `README.md` / `AGENTS.md`.
- Riot fan-content disclaimer: F11. Licensing review (fonts, assets, Riot IP): before F12.
- Hygiene: `openspec/changes/archive/2026-10-19-f0-foundation/` mentions private IPs; `docs/nginx_config`,
  `tests/test_nginx_config_doc.py` and `tests/test_csrf.py` contain the dev domain. Replace with placeholders
  (small docs/test unit); `tests/test_docs.py` only scans `AGENTS.md` and `README.md`.
- `docs/migrations.md` restarts `rbapp` while the repo unit file is `docs/riftbound.service`: align the naming.
- Legacy endpoints leak exception text: `cards.upload_card_image` and several `price.py` endpoints return
  `str(e)` in a 500, and the generic `except` of `validate_json` returns it in a 400. About 20 legacy places
  use `datetime.utcnow()` instead of `app/utils/clock.utcnow()`. Fix when the module is ported (F2/F10) or
  in a small hardening unit.
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
| F1-close | not started | — | — |
| F1-g | done (PR pending merge) | `feat/f1g-hardening` / #26 | CSP report-only + `SPA_CSP`, axe sweep, precache dedupe, Toast deflake. pytest 1640 → 1694; Lighthouse pending (owner). |
