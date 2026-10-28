# Project state

Single source of status. Every unit updates this file in its own PR (section "Units" and, when relevant,
"Pending checks", "Follow-ups" and "Known issues"). A unit is **done** when its PR is merged into `main`.

Last update: 2026-10-28 (F3-e implemented, batch 1 unit 23; F3-c, F3-d done and deployed).

## Phases

| Phase | Status | Notes |
|---|---|---|
| F0 Foundation | **Done** (PRs #11-#16) | Archived in `openspec/changes/archive/2026-10-19-f0-foundation/`; contracts in `openspec/specs/`. |
| F1 App shell | **Done** (PRs #17-#24, #26, F1-close #27) | Archived in `openspec/changes/archive/2026-10-22-f1-app-shell/` (verify: 67 requirements, 64 PASS, 1 PASS manual, 2 DEFERRED, 0 FAIL); contracts merged into `openspec/specs/` (21 capabilities, 136 requirements). See "F1 detail". |
| M-a Test reset | **Done** (#29) | `docs/requirements/M/M-a-test-reset.md`. |
| M-b Plan update | **Done** (#30) | `docs/requirements/M/M-b-plan-update.md`. |
| M-c Hygiene | **Done** (#31) | `docs/requirements/M/M-c-hygiene.md`. |
| F4 Prices + Dashboard | In progress — F4-a done (#32), F4-b done (#33); the rest waits (F4-c with F3) | F4-a + F4-b (job runner, daily Cardmarket load) right after M-c; F4-c with F3; the rest in the medium-priority group. `docs/requirements/F4/README.md`. |
| F2 Catalog | In progress — F2-a…i done (#34, #45, #46, #47, #48, #49, #50, #51, #52); F2-k implemented (batch 1 unit 17) | `docs/requirements/F2/` (drafts adapted for batch 1 on 2026-10-25); F2-j (offline) and F2-l (thumbnails) in batch 2. |
| M-d Images out of git | In review (#37) — batch 1, unit 1 | `docs/requirements/M/M-d-card-images-out-of-git.md`. |
| F13 Riot sync + catalog admin | In progress — F13-g in review (#44), batch 1 unit 8 | `docs/requirements/F13/F13-{a..g}-*.md`. |
| F3 Collection | In progress — F3-a, b, c, d done (#55, #56, #59, #60), F3-e implemented (batch 1 unit 23); units 24-26 planned | `docs/requirements/F3/F3-{a,b,c,d,e,g,h,i}-*.md`; wishlist and offline in batch 2. |
| F14 Products | Planned — batch 1, units 27-32 | `docs/requirements/F14/F14-{a..f}-*.md`; offline in batch 2. |
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
| F2-a on the server (after merge): backup, `flask db upgrade` (`0009_card_bans`) + `flask db check`, restart; `flask bans list` shows the 25 seeded rows (12 names in 1v1 and 2v2, `Wuju Bladesman` in 2v2); signed-in `GET /riftbound/api/v1/bans` answers 200 and anonymous 401; ban a real card with `flask bans add "<name>" --mode 1v1 --reason test`, see `BANNED 1v1` on every printing in the Jinja catalog, then `flask bans remove "<name>" --mode 1v1` (`ops-runbook.md` → "Service operations") | **Pending (owner).** |
| M-d on the server (before or with the deploy that pulls it): **before pulling**, copy `<checkout>/app/static/images/cards/.` into the data directory (outside the checkout, owned by the service user); set `CARD_IMAGES_DIR` in `.env`, deploy, restart, run `flask images import-legacy` (copies 0 when the copy was done); live check: a Jinja catalog page loads its images from `/riftbound/media/cards/…` and `curl -sI` of one image answers 200 with `Cache-Control: public, max-age=604800` (`ops-runbook.md` → "Card images") | **Pending (owner).** |
| F4-b on the server (after merge): backup, `flask db upgrade` (`0008_jobs_daily_prices`) + `flask db check`, restart, install and enable `riftbound-daily.timer` and `riftbound-daily-retry.timer`, run `flask jobs enqueue daily_prices` once and read the result a few minutes later (`ops-runbook.md` → "Scheduled jobs" → "Daily Cardmarket load") | **Pending (owner).** |
| Rollback rehearsal on dev (6.34) | Not run on dev on purpose (it would uninstall the worker on the owner's devices); verified locally in Chromium. |
| F3-c + F3-d on the server (no migration) | **Done (2026-10-28).** Pulled at `c77d87c`, `dist` rebuilt, service restarted; anonymous `GET /collection/export` and `/collection` answer 401; the export built in process for the owner's collection gives 306 RBAPP rows and 14 Cardmarket rows (BOM, headers). Still to do by hand: download both files from `/riftbound/api/v1/collection/export?format=rbapp|cardmarket` while signed in and open them in a spreadsheet; upload the Cardmarket one to Cardmarket's stock import (no screen yet, F3-i). |
| F3-e on the server (after merge): **backup first**, `flask db upgrade` (`0018_import_previews`) + `flask db check`, restart | **Pending (owner).** |
| F4-c on the server (after merge): **backup first**, `flask db upgrade` (`0016_value_snapshots`, `0017_jobs_value_snapshot`) + `flask db check`, restart; `flask jobs enqueue value_snapshot`, then one row per user with a collection for today (runbook "Collection value snapshots"); the next 06:30 load shows `"queued": ["value_snapshot"]` | **Done (2026-10-28, deployed with F3-a and F3-b).** `0017` applied, `flask db check` clean; `flask jobs enqueue value_snapshot` stored 1 row (value 467.41, 891 copies, 264 printings, 1 unpriced) equal to the `GET /collection` totals. The next 06:30 load should show `"queued": ["value_snapshot"]` (not yet seen). |
| F3-a on the server (after merge): **backup first**, `flask db upgrade` (`0014_collection_selling`, `0015_playset`) + `flask db check`, restart; the upgrade log shows `rbcollection rows S->Y: 0`; the Jinja collection still lists, edits and exports (the CSV quantity equals what it was); `SELECT count(*) FROM riftbound.rbkeepplayset` is 1 on dev (`ops-runbook.md`) | **Done (2026-10-28).** Backup `riftbound_pre_f3a-f3b-f4c_20261028_1256.dump`, `0014` log `rows S->Y: 0`, `rbkeepplayset` 1 row, 14 `Y` rows with 40 copies for sale, no `sell_qty > quantity`. Still to look at by hand: the Jinja collection lists, edits and exports as before. |
| F2-b on the server (after merge): backup, `flask db upgrade` (`0013_price_product_date_idx`) + `flask db check`, restart; anonymous `GET /riftbound/api/v1/meta/game` answers 200 with `Cache-Control: no-cache` and a non-null `price.updated_on` | **Pending (owner).** |

## Follow-ups

- F0 4.31: Nginx `limit_req` on the public proxy (template in `docs/nginx_config`) — owner action, or F12.
- F0 5.20: owner review of `README.md` / `AGENTS.md`.
- Riot fan-content disclaimer: F11. Licensing review (fonts, assets, Riot IP): before F12.
- `docs/migrations.md` restarts `rbapp` while the repo unit file is `docs/riftbound.service`: align the naming.
- Guards to re-create when their area is touched: see the test policy (AGENTS.md → Testing).
- Card errata: the owner pointed to https://riftbound.gg/rules/errata/ (67 cards on 2026-10-24); where the current wording is stored and shown is not decided yet (F2 card detail or F13 sync).
- OPAPP and DB tools on the owner's side use the rotated database superuser password (owner action, done
  or pending on their side; nothing in this repo).

## Known issues

- `frontend/src/assets/brand/mark.svg` and `wordmark.svg` are not byte-reproducible from
  `scripts/brand-trace.mjs` (a full run produces a heavier trace); do not regenerate them blindly.
- `dist/.vite/manifest.json` is publicly served (harmless; it lists chunk names only).
The legacy scraper write path is gone (F13-c): the sync inserts new cards with `rbcar_banned = 'N'` and never rewrites it; bans still live in `rbcardbans`; F11 drops the column.
- The Jinja catalog SQL uses PostgreSQL-only constructs (`~`, `regexp_replace`, shimmed in SQLite tests).
- The landing feeds (`app/services/scraper.py`) serve placeholder news/tournaments; there is no real event
  source yet (F8 starts with the official upcoming-events calendar; the landing is rebuilt with F8).
- The repo's systemd/Gunicorn docs use the default 30 s timeout while Cardmarket load and Riot extraction run
  inside the request (the dev server overrides it; F4 and F13 move them to jobs).
- `cardmarket_matcher.auto_match` (also its dry run, used every day by `daily_prices`) reads every
  `rbcm_price` row of every date into memory; watch the job duration against its 1800 s timeout as the
  price history grows.
- `daily_prices` lists singles without an `idMetacard` as `no_candidates` (the matcher skips them).

## Units (from F1-close on)

| Unit | Status | Branch / PR | Notes |
|---|---|---|---|
| F2-fix | done (#54) | `fix/catalog-search-typing` / #54 | Typing bug in the catalog: inputs whose value lives in the URL (search, "text" facet, numeric ranges) lost letters when the URL answered a debounced commit (search) or on every keystroke (ranges). New `DebouncedInput` keeps local text and adopts the URL only for outside changes; single debounce. Vitest 288 → 291; pytest unchanged. |
| F3-e | in review (#61) | `feat/f3e-collection-import-api` / #61 | CSV import (S1-S7): table `rbimportpreviews` (migration `0018_import_previews`, JSON rows, 30 min, FK cascade), `POST /collection/import/preview` (format detection, 2 MB / 10 000 rows, row statuses and reason codes, expired previews purged, one preview per user) and `/commit` (`add` or `replace`, all or nothing, 410 `import_expired`); codes `import_expired`, `import_format_unknown`; `collection_write.add_row` is the shared merge rule. Export -> import with `replace` leaves the collection identical (test). pytest 1 107 → 1 192. Deviations L1-L5 in the requirement. Next unit: **F3-g**. |
| F3-d | done (#60) | `feat/f3d-collection-export-api` / #60 | CSV export (S1-S5): `GET /collection/export?format=rbapp|cardmarket` (+ list filters, `only_selling`), BOM, streamed, `X-Rows-Exported`, UTC file names; RBAPP format re-importable, Cardmarket byte-identical to the Jinja export (golden test), formula-injection prefix; `collection_read.export_lines`/`_load_lines` shared with the list, `pricing.product_names`. pytest 1 085 → 1 107. No migration. Next unit: **F3-e**. |
| F3-c | done (#59) | `feat/f3c-collection-write-api` / #59 | Collection write API (S1-S10): `POST /collection` (merge of identical lines in SQL, foil rule, selling defaults market x 1.05), `PATCH /collection/<id>` (stale guard by change time, `sell_qty` rules), `DELETE` (undo payload), `split` (new line or merge, source clamped), `bulk` (all or nothing, 1000 ids), `keep-playset`; `playset_size` in `/me/prefs` and the session (frontend `Prefs` gains it); new codes `foil_not_allowed`, `insufficient_quantity`, `stale_line`; service `app/services/collection_write.py`. pytest 930 → 1 085; vitest 291 → 301. No migration. Deviations L1-L6 in the requirement. Next unit: **F3-d**. |
| F4-c | done (#57) | `feat/f4c-value-snapshots` / #57 | Daily collection value snapshots (S1-S5): table `rbvaluesnaps` (migration `0016_value_snapshots`, PK user + date, FK cascade), `RbValueSnapshot`, `app/services/snapshots.py::take_snapshots(today)` (one row per user with a line, upsert per day, priced by `collection_read.user_value_summaries`, the F3-b code, fixed number of queries), job kind `value_snapshot` (migration `0017_jobs_value_snapshot`, 900 s, no params); `daily_prices` queues it as its last step (`queued` in its result, `JobAlreadyActive` ignored, queue failures never fail the load); runbook "Collection value snapshots". pytest 906 → 930. Next unit: **F3-c**. |
| F3-b | done (#56) | `feat/f3b-collection-read-api` / #56 | Collection read API (S1-S10): `GET /collection` (U, `api_v1.list_collection_groups`) via `CollectionListQuery`; `app/services/collection_read.py` (groups per printing and foil, `CollectionLine`/`CollectionGroup` contracts, market and P/L with half-up money, playset flag and short warning over all the user's lines of a name, totals over every matching line, disjunctive facets, 9 sorts with nulls last); `GET /meta/game` gains `conditions` and `languages`; card detail `my_lines` gain `purchase_price` and `sell_qty`; `card_list.parse_card`/`text_matches` and `pricing.price_as_of` are shared. At most 10 SQL statements (tested with 3 and 60 lines); S9 p95 ≈ 340 ms for 5 000 lines on SQLite in memory (target 300 ms, deviation L3 in the requirement). pytest 838 → 906; no migration. Next unit: **F4-c**. |
| F3-a | done (#55) | `feat/f3a-collection-data` / #55 | Collection data (S1-S7): migration `0014_collection_selling` (`rbcol_purchase_price` NUMERIC(10,2) NULL ≥ 0, `rbcol_sell_qty` 0..quantity back-filled by the old rules, legacy `S` → `Y` logged, `rbcollection_selling_chk` = Y/N) and `0015_playset` (`rbuserprefs.rbprf_playset_size` 1..9, NULL = 3; table `rbkeepplayset` seeded one row per user and `name_key` from rows with a playset); models `RbKeepPlayset`; `app/services/collection_rules.py` (`legacy_sell_qty`, `kept_copies`, `playset_size`, `sync_legacy_sell_qty`); the Jinja writes (`add`, `update_quantity`, `update_selling`, `update_playset`, `bulk_apply`, `import_csv`) keep `rbcol_sell_qty` coherent and `export_csv` reads it (byte-identical to the pre-F3-a fixture). Preflight on dev (2026-10-28): `rbcol_selling` Y 14 / N 292 (no `S`), 1 row with a playset, no `rbcol_quantity < 1`. `rbcol_playset` is deprecated (dropped in F11). pytest 787 → 838; PostgreSQL round trip left to CI `migrations-pg`. Next unit: **F3-b**. |
| F2-k | done (#53) | `feat/f2k-card-combobox` / #53 | Card combobox + topbar search (S1-S7): `CardCombobox` (ARIA 1.2, 2-char threshold, 250 ms debounce, abort, `filters` pass-through, option content, "more" row, loading/empty/error/offline states through a live region), `useCardSearch`, `cards:combobox.*` ES/EN, topbar "Buscar cartas" box at ≥ 1240 px with `/` shortcut and key hint, selection opens `/cards/<set>/<id>` with `{fromCatalog: true}`; `docs/frontend.md` "CardCombobox". Vitest 255 → 288; pytest 787 unchanged. Next unit: **F3-a**. |
| F2-i | done (#52) | `feat/f2i-catalog-desktop-wide` / #52 | Desktop sidebar, table view, wide preview (S1-S6): shared `CatalogFilters` (sheet/sidebar, collapsible, remembered), sticky sidebar layout, toolbar with per-page + table view, sortable 13/16-column table, `CatalogPreview` with 30d sparkline and `selected` param, delayed sidebar `aria-busy`, preview empty state; `docs/frontend.md` "Catalog" + storage keys. Vitest 226 → 255; pytest 787 unchanged. Next unit: **F2-k**. |
| F2-h | done (#51) | `feat/f2h-catalog-page` / #51 | Catalog page + nav flip (S1-S13): `requestWithMeta`, `getGameMeta`/`listCards` (envelope-level meta fix), params parse/serialize/round-trip, `CatalogPage` (toolbar, sheet, chips, grid/list, pagination, scroll restore), `FilterChip`/`Pagination` primitives, `cards` → spa; `docs/frontend.md` "Catalog", AGENTS.md. Vitest 184 → 226; pytest 787 unchanged. Next unit: **F2-i**. |
| F2-g | done (#50) | `feat/f2g-price-chart` / #50 | Price history chart + sparkline (S1-S7): `getCardPrices`/`useCardPrices` (keepPreviousData, 10-min stale), `scale.ts` (`linearScale` + `niceTicks`), `PriceChart` (measured SVG, keyboard, live region, table alternative), `CardPriceHistory` in the detail slot (`rb_price_range` remembered), `Sparkline`; `docs/frontend.md` "Charts". Vitest 148 → 184; pytest 787 unchanged. Next unit: **F2-h**. |
| F2-f | done (#49) | `feat/f2f-card-detail-screen` / #49 | Card detail screen (S1-S11): `CardDetail` types, `getCard`, `useCardDetail` (5-min stale, no 404 retry), `/cards` layout + `/:setId/:cardId` route (page/modal, prev/next, Esc close), 11 sections, 1/2/3-column layouts, `parseAbility`/`AbilityText`, `Modal` sizes, skeleton/404/retry states; `docs/frontend.md` "Catalog", AGENTS.md. Vitest 103 → 148; pytest 787 unchanged. Next unit: **F2-g**. |
| F2-e | done (#48) | `feat/f2e-card-ui-atoms` / #48 | Card UI atoms (S1-S14): `CardSummary` types, six fixtures, domain/rarity tokens + `domains.ts` (CSS=TS test), `shadeHex`, `formatPct`, `enums`+`cards` namespaces + `useEnumLabel`, `CardImage`/`CardArtPlaceholder`/`DomainPips`/`RarityDot`/`BanBadge`/`PriceTag`, ESLint card/charts boundary + type-only `@/api` test, kitchen entries, axe test; `docs/frontend.md` "Card components", AGENTS.md. Vitest 42 → 103; pytest 787 unchanged. Next unit: **F2-f**. |
| F2-d | done (#47) | `feat/f2d-card-detail-api` / #47 | Card detail + price history (S1-S9): `CardPricesQuery`, `app/services/card_detail.py` (CardDetail with ability/set/price_detail/printings/related/ban_info/my_lines/in_decks, prices with 30d/90d/1y/all windows and same-date foil), `GET /cards/<set>/<id>` + `…/prices` (U); ≤ 10/≤ 4 statements, detail p95 123 ms on dev (6 printings); `docs/api.md` "GET /cards/<set>/<id>", AGENTS.md. pytest 762 → 787. Next unit: **F2-e**. |
| F2-c | done (#46) | `feat/f2c-cards-list-api` / #46 | Cards list API (S1-S9): rewritten `validate_query` (lists via getlist, empty-drop, Pydantic coercion; bans moved onto it, `?mode=` now 200), `CardListQuery`, filters/facets/default sort/pagination in `app/services/card_list.py`, full sort keys with nulls-last + natural tiebreak, real `owned` counts, prices for all matches only with price sort/bounds, ≤ 8 statements with 200 cards; public `GET /cards` (U); S8 timings p95 default 177 / price_desc 415 (deviation L3) / q 185 / domains 174 ms; `docs/api.md` "GET /cards", AGENTS.md. pytest 706 → 762. Next unit: **F2-d**. |
| F2-b | done (#45) | `feat/f2b-game-meta-card-dto` / #45 | Game meta + card DTO (S1-S10): `game_domain` enums confirmed against the dev DB, `catalog.py` parsing/`card_summary`, `resolve_price_with_source` + batched `price_summaries` (2 SQL statements; 15-23 ms for 50 cards, ~170-230 ms for all 1298 dev cards), migration `0013_price_product_date_idx`, public `GET /meta/game` (P, `no-cache`), `docs/api.md` "API v1 reference" + "Data shapes". pytest 629 → 688. Next unit: **F2-c**. |
| F13-g | in review (#44) | `feat/f13g-change-review-ui` / #44 | Riot change review UI (S1-S9): ValueDiff, filters in URL, bulk select+confirm, detail panel ≥1600 px, cards <860 px, overview Riot band, admin nav count, Jinja hand-off notice. Vitest 30 → 42. Next unit: **F2-b**. |
| F13-f | in review (#43) | `feat/f13f-catalog-admin-ui` / #43 | Admin sets/cards/Riot screens: tables/cards lists, drawer + bottom-sheet editors, inline panel ≥1600 px, image upload, JobStatus polling, validation + translated errors, axe clean. No backend change. Vitest 12 → 30. Next unit: **F13-g**. |
| F13-e | in review (#42) | `feat/f13e-riot-sync-api` / #42 | Riot sync/read API (S1-S7): queue `riot_sync` (202/409), jobs list+detail, changes list/approve/reject/bulk (per-id transactions, stale/decided guards), overview `riot` block; new codes `job_running`/`change_stale`/`change_decided`; `docs/api.md` extended. No migration. Next unit: **F13-f**. |
| F13-d | in review (#41) | `feat/f13d-riot-sync-schedule` / #41 | `due_sets`/`next_run` (Madrid aware, DST tested), scheduled `riot_sync` requires `slot` (`nothing due` without fetch), `am`/`pm` timers with `SuccessExitStatus=1`, `window` + `next_run_at` on `GET /admin/sets`. No migration. Next unit: **F13-e**. |
| F13-c | in review (#40) | `feat/f13c-riot-sync-engine` / #40 | Sync engine `app/services/riot_sync.py`: fetch/parse split, window calculator (Madrid date), per-set savepoints, auto-apply in active windows else `rbcardchanges` proposals (migration `0011_card_changes`), `riot_sync` job kind (migration `0012_jobs_riot_sync`), legacy Jinja button queues the job. The old scraper write path is removed. pytest 522 → 570. Next unit: **F13-d**. |
| F13-b | in review (#39) | `feat/f13b-catalog-admin-api` / #39 | Admin sets/cards API (S2-S10): list/create/patch/delete with validation, in-use guards, image upload by magic bytes, every write audited in the same transaction; new codes `already_exists`/`set_in_use`/`card_in_use`; `docs/api.md` created. No migration. |
| F13-a | in review (#38) | `feat/f13a-admin-foundation` / #38 | Blueprint `api_admin` (`before_request(require_admin)`), `GET /admin/overview` (four catalog COUNTs), table `rbadminaudit` (migration `0010_admin_audit`, `record()` without commit), React admin area (`AdminLayout` + `OverviewPage`, nav `admin` → spa), `admin` i18n namespace + `common:offline.editDisabled`, re-created ES/EN parity test. pytest 436 → 469; vitest 1 → 12. Next unit: **F13-b**. |
| M-d | in review (#37) | `chore/m-d-card-images` / #37 | Setting `CARD_IMAGES_DIR` (absolute, default `<project>/data/card-images`, git-ignored `/data/`; a relative value is `ConfigError('CARD_IMAGES_DIR must be an absolute path')`; created on first write). `app/services/card_images.py` is the only module that knows the root: `images_root()`, `card_image_path(image, set_id=None)` (same refusals: separators, NUL, unsafe folder, symlink escape), `card_image_url()`; `RbCard.image_src` → `/riftbound/media/cards/<folder>/<image>`. Blueprint `media` (`app/routes/media.py`, `media.card_image`, P): letters-and-digits folder, plain file name, 404 otherwise, `Cache-Control: public, max-age=604800`, no `Set-Cookie`; the old `/riftbound/static/images/cards/…` URLs stop serving the images (D-Md-2). Admin upload and Riot scraper step 4 write through `card_image_path`. `deck.html` legend placeholder is an inline SVG. `flask images import-legacy [--source PATH]` copies, never overwrites (D-Md-3). The 376 tracked images are untracked (`.gitkeep` kept). Runbook "Card images". pytest 324 → 430. Next unit: **F13-a**. |
| F2-a | done | `feat/f2a-card-bans` / #34 | Table `rbcardbans` (migration `0009_card_bans`: one row per `name_key` and mode, CHECK built from `GAME_MODES` in the new `app/schemas/game_domain.py`; seeded with the official ban list read 2026-10-24, 25 rows: 12 names in 1v1 and 2v2, `Wuju Bladesman` in 2v2; `rbcar_banned` not read; downgrade drops the table and every ban). Service `app/services/bans.py` (`name_key`, `ban_map`, `card_bans`, `ban_info`, `list_bans`, `add_ban`, `remove_ban`), `flask bans list\|add\|remove` (name checked against the catalog unless `--force`), `GET /bans` (U) with printings per name. Jinja catalog: Banned column, badge (`BANNED 1v1, 2v2`) and `search_banned` read the ban table; the add/edit modals lose the banned field (the column keeps its value). PostgreSQL round trip left to CI `migrations-pg`. pytest 211 → 324. Next unit: **M-d**. |
| F4-b | done | `feat/f4b-daily-prices` / #33 | Job kind `daily_prices` (`app/jobs/daily_prices.py`, 1800 s; migration `0008_jobs_daily_prices` extends `ck_rbjobs_kind`, its downgrade refuses while such jobs exist): `CardmarketLoader().run()` with the default URLs, validation record from `rbcm_load_history`/`rbcm_price`/`rbcm_products`, clear-case linking from `auto_match(dry_run=True)` (one product + one free candidate card, confidence 0.7), review list in `rbjob_result` (≤ 200 + `review_total`), all in `app/services/daily_prices.py`; loader and matcher unchanged. `JobFailed` stores a handler message without the class name. `flask jobs enqueue <kind> --unless-succeeded-today` (UTC date) for the 08:00 retry; daily and retry systemd templates complete; runbook "Daily Cardmarket load". pytest 160 → 211. Next unit: **F2-a**. |
| F4-a | done | `feat/f4a-job-runner` / #32 | Table `rbjobs` (migration `0007_jobs`, one queued/running job per kind by partial unique index), registry `app/jobs/` with the `heartbeat` kind, runner service `app/services/jobs.py` (conditional-UPDATE claim, kind timeouts), `flask jobs enqueue\|run-pending\|list`, systemd templates in `docs/systemd/` (jobs timer every minute; daily 06:30 and retry 08:00 Europe/Madrid wait for F4-b), runbook "Scheduled jobs". PostgreSQL round trip left to CI `migrations-pg`. pytest 74 → 160. Next unit: **F4-b**. |
| M-c | done | `chore/m-c-hygiene` / #31 | Private IPs/dev domain replaced by placeholders (no history rewrite); legacy 500s and the generic `@validate_json` 400 return a clear message + `internal_error`/`bad_request`, detail only for admins, traceback logged; no `datetime.utcnow` under `app/` (guard test). |
| M-b | done | `docs/m-b-plan-update` / #30 | Decisions of 2026-10-22 folded into `product.md`, `roadmap.md`, `open-decisions.md`, phase specs F2-F12 and this file; new phase specs F13 (Riot sync + catalog admin), F14 (Products), F15 (Rules app). Documentation only. Next unit: **M-c**. |
| M-a | done | `chore/m-a-test-reset` / #29 | Old suites removed; kept authz matrix + smoke tests; baseline `902047c6579e5ee670e1fb4b103a941159b85c00`. pytest 1694 passed / 41 skipped → 21 passed; vitest 1189 → 1. |
| F1-close | done | `chore/f1-close` / #27 | Verify report (67 requirements, 0 FAIL, no defects), 8 spec amendments, specs merged (62 ADDED + 5 MODIFIED), archive `2026-10-22-f1-app-shell`. Lanes on `c2a7fe7`: pytest 1694 passed / 41 skipped, vitest 1189. |
| F1-g | done | `feat/f1g-hardening` / #26 | CSP report-only + `SPA_CSP`, axe sweep, precache dedupe, Toast deflake. pytest 1640 → 1694; Lighthouse pending (owner). |
