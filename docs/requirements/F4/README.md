# F4: Prices + Dashboard — phase spec
Status: planned · Depends on: F2 (pricing service, `price_summaries`, charts), F3 (collection lines, purchase price, wishlist) for F4-c..i; F4-a/F4-b need neither · Order (`docs/knowledge/roadmap.md`): F4-a and F4-b run early, right after M-c; F4-c runs with F3; F4-d..i are medium priority, before production · Source: roadmap §5 (F4), design-handoff §3.3, §3.12 (push), §3.13, §6 (5, 6), §7.5 R1, §9 (F4), `docs/knowledge/product.md` "Scope by phase", "Platform notes"

## Goal

Prices refresh by themselves every day; every user gets a daily snapshot of their collection value, sees
on a dashboard their KPIs, a 12-month value chart, the cards that rise and fall most (7/30 days) and their
alerts; they can watch cards and receive **push notifications** when a price crosses their threshold. F4
also builds the shared infrastructure later phases reuse: the job runner (`rbjobs` + systemd timers), Web
Push (VAPID, subscriptions, service-worker handler, notification preferences) and a notification log.

## Current state

| Area | What exists today |
|---|---|
| Cardmarket load | `app/services/cardmarket_loader.py::CardmarketLoader.run()` downloads singles, non-singles and the price guide (allow-listed URLs, SHA-256 change detection, `rbcm_load_history`), inserts `rbcm_products` / `rbcm_price` for `today` (UTC `YYYYMMDD`). Only run by an admin from the Jinja price page (`POST /riftbound/price/cardmarket-load`). Auto-match: `cardmarket_matcher.auto_match()` (admin button). |
| Prices | `rbcm_price` one row per product per loaded day; F2-b adds the `(product, date)` index, `price_summaries` with 7/30-day trends, `GET /cards/{set}/{id}/prices`. |
| Value history | None. Prototype series is synthetic (design-handoff §6-6). |
| Scheduler | None. No Celery/Redis; Gunicorn 3 workers; systemd unit in `docs/riftbound.service`; runbook has an empty "Scheduled jobs" section. |
| Push | None: no VAPID keys, no subscriptions, the service worker is Workbox `generateSW` (prompt mode) with no push handler. |
| Dashboard | Jinja `GET /riftbound/` (`main.dashboard`, U); nav entry `dashboard` is `legacy`. |
| Frontend | F2: `PriceChart`, `Sparkline`, card atoms, read cache; F1: `/account/interface`, `SettingsCard`, `Switch`, toasts. |

## Scope

In: job runner and timers; daily Cardmarket load (+ optional auto-match); daily value snapshot per user;
movers API; value-history API; dashboard API + UI; Web Push infrastructure; notification preferences;
watchlist with price alerts (including wishlist max price); price-freshness indicator.

Out: sales numbers (F7 fills `recent_sales`), event reminders (F8 adds its category), admin job UI (F10),
email notifications (no mail server).

## Decisions already taken

- Scheduled work = Flask CLI commands + systemd timers, no Celery/Redis (cross-phase contract).
- Job runner (owner, 2026-10-22): built once in F4-a (`rbjobs` + `flask jobs run-pending`, timer every
  minute); F10-d, F13 and every later phase only register job kinds; the daily Cardmarket load and the
  snapshot use the same path.
- **D-F4-1** (owner, 2026-10-22): the Cardmarket load runs every day at 06:30 Europe/Madrid, with a retry at
  08:00 Europe/Madrid if it failed. The job validates the load (files, rows, new products) and records the
  result.
- **D-F4-2** (owner, 2026-10-22): auto-match runs after every load, for clear cases only. Doubtful cases go to
  a review list; the planner analyses them to add matching criteria and automate as much as possible.
- Order (owner, 2026-10-22): F4-a and F4-b are planned right after M-c (before F2-a); F4-c runs together with
  F3; the rest of F4 is medium priority, before production.
- Tests (owner, 2026-10-22, unit M-a): each F4 unit writes its own tests and re-creates the removed guard of
  the area it touches (migration round-trip + drift test, error-code catalog test, pin check for new
  dependencies).
- Daily collection-value snapshot per user; history starts on the first snapshot (no backfill possible;
  "recopilando datos" empty state) (design-handoff §6-6).
- Top risers/fallers 7/30 days; watchlist with push alerts; KPIs + 12-month chart (product.md F4).
- Push on iOS only with the PWA on the home screen, iOS 16.4+ (product.md "Platform notes").
- Secrets (VAPID private key) only in environment variables.
- F4 owns push subscriptions and notification-preference categories (`price_alerts` here; F8 adds
  `event_reminders`), and a generic notification log that F8 uses to avoid duplicate reminders.
- `GET /dashboard` has a `recent_sales` slot (null until F7) and `next_events` (null until F8).
- New tables reference `rbusers.id`; migrations take the next free revision numbers.

## Requirements

### Jobs
- **F4-R1** Table `rbjobs` (shape agreed with F10): `rbjob_id` BIGINT PK; `rbjob_kind` VARCHAR(32) NOT NULL CHECK IN the registered kinds; `rbjob_params` JSON; `rbjob_status` VARCHAR(10) CHECK IN ('queued','running','success','error'); `rbjob_requested_by` INT NULL FK `rbusers.id` ON DELETE SET NULL; `rbjob_requested_at`, `rbjob_started_at`, `rbjob_finished_at`; `rbjob_result` JSON; `rbjob_message` VARCHAR(300). Partial unique index on `kind` WHERE status IN ('queued','running') (one active job per kind). (F4-a)
- **F4-R2** `flask jobs enqueue <kind> [--param k=v]`, `flask jobs run-pending` (claims queued jobs one by one with a row lock/`UPDATE … WHERE status='queued'`, runs them, records result; a job running longer than its timeout is marked `error`), `flask jobs list [--limit]`. Job kinds register in `app/jobs/registry.py`. (F4-a)
- **F4-R3** systemd units documented in `docs/knowledge/ops-runbook.md` → "Scheduled jobs": `riftbound-jobs.timer` (every minute → `flask jobs run-pending`) and `riftbound-daily.timer` (daily 06:30 Europe/Madrid → `flask jobs enqueue daily_prices`) and a retry timer at 08:00 Europe/Madrid that enqueues `daily_prices` only when today's run did not succeed, with `journalctl` commands and how to run by hand. Templates in `docs/`. (F4-a timers, F4-b retry rule)

### Prices
- **F4-R4** Job `daily_prices`: runs `CardmarketLoader`; validates the load (expected files downloaded, row counts, new products) and records the outcome in the job result and `rbcm_load_history`; a failed validation is an `error` run (so the 08:00 retry fires). On success it always runs `auto_match` for clear cases only and stores the doubtful cases in a review list (D-F4-10), then enqueues `value_snapshot` and `price_alerts` once those kinds are registered (F4-c, F4-g land later). Skips (status success, message "unchanged") when the files' hashes did not change. (F4-b)
- **F4-R5** `GET /prices/movers?range=7d|30d&scope=all|mine&dir=up|down&limit=10` (U): cards ranked by `trend_*_pct` with a minimum market price (D-F4-3) to avoid noise; `scope=mine` limits to printings the user owns. (F4-d)
- **F4-R6** `GET /meta/game` `price.updated_on` drives a topbar indicator "Precios a dd/mm" (≥ 1240) and a stale warning when older than 2 days. (F4-h)

### Snapshots
- **F4-R7** Table `rbvaluesnaps`: `rbvsn_user_id` INT FK `rbusers.id` CASCADE, `rbvsn_date` DATE, `rbvsn_value` NUMERIC(12,2), `rbvsn_cost` NUMERIC(12,2) NULL (sum of purchase price × qty where set), `rbvsn_qty` INT, `rbvsn_unique` INT, `rbvsn_unpriced` INT; PK (user, date). Job `value_snapshot` writes today's row for every user with a collection (idempotent upsert). (F4-c)
- **F4-R8** `GET /collection/value-history?range=30d|90d|1y|all` (U) → `{points[{date, value, cost}], first_date}`. (F4-d)

### Dashboard
- **F4-R9** `GET /dashboard` (U): `{kpis: {value, value_delta_30d_pct, cards_total, cards_unique, decks_count, wishlist_count, selling: {lines, value}}, value_history (12 months, from snapshots), movers: {up[], down[]} (7 d, mine, 5 each), set_completion[{set_id, name, owned_unique, total}], alerts[] (latest 5 notifications), recent_sales: null, next_events: null, price_updated_on}`. (F4-e)

### Push and notifications
- **F4-R10** Env vars `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` (`mailto:` or `https:` contact, no real address in the repo); push disabled (feature flag false in `/meta/config`) when unset; `.env.example` and README document them. `flask push generate-keys` prints a new key pair once. (F4-f)
- **F4-R11** Table `rbpushsubs`: id, user id FK CASCADE, `endpoint` TEXT UNIQUE, `p256dh`, `auth`, `user_agent` VARCHAR(200), `created_at`, `last_success_at`, `failure_count`. `GET /push/config` (U: public key, enabled), `POST /push/subscriptions`, `DELETE /push/subscriptions` (by endpoint). Endpoint host must be https; one user ≤ 10 subscriptions. (F4-f)
- **F4-R12** Table `rbnotifprefs` (user id, `category` CHECK IN registered categories, `enabled` bool; PK user+category; missing row = default per category). `GET/PATCH /me/notifications`. Categories: `price_alerts` (default on once push is enabled); F8 adds `event_reminders`. (F4-f)
- **F4-R13** Table `rbnotiflog` (id, user id, category, `ref` VARCHAR(100), title, body, url, `sent_at`, `delivered` count; UNIQUE (user, category, ref)) — the dedupe key for every sender (F8 reuses with `ref = event:<id>:24h`). (F4-f)
- **F4-R14** `send_push(user_id, category, ref, payload)` service: skips when the category is off or `ref` already logged; sends with `pywebpush` (pinned); deletes subscriptions answering 404/410; payload `{title, body, url, tag}` ≤ 3 KB, `url` always under `/riftbound/app/`. (F4-f)
- **F4-R15** Service worker push handler: `workbox.importScripts(['sw-push.js'])` (static file in `public/`) shows the notification and focuses/opens `url` on click; `check:dist` accepts exactly this import. (F4-f)

### Watchlist
- **F4-R16** Table `rbwatch` (id, user id, set/card or name key, foil, `rule` CHECK IN ('below','above','change_pct'), `threshold` NUMERIC, `active`, `last_triggered_at`); wishlist entries with `max_price` act as implicit `below` rules (D-F3-7). `GET/POST /watchlist`, `PATCH/DELETE /watchlist/{id}`; code `already_exists` on duplicates. (F4-g)
- **F4-R17** Job `price_alerts` after each load evaluates active rules against the new market prices and sends at most one push per rule per day (`ref = watch:<id>:<date>`), logging it. (F4-g)

### UI
- **F4-R18** `/dashboard` (nav `dashboard` → `spa`): mobile = KPI cards 2×2, value chart (12 m) with "recopilando datos" when < 2 points, movers (tabs Suben/Bajan, 7 d/30 d), alerts, set completion; desktop ≥ 1240 = chart 2/3 + rail 1/3 (alerts, movers, wishlist matches); wide ≥ 1600 = 3 columns (KPIs + chart | movers + watchlist | set completion + activity). Empty state for a new user (Importar CSV / Añadir primera carta). Fixes design-handoff R1. (F4-h)
- **F4-R19** `/account/notifications`: enable push (permission flow, iOS "add to home screen" hint when unsupported), per-category switches, list of this account's devices with "Quitar", test notification button. (F4-i)
- **F4-R20** Watchlist UI: `/prices/watchlist` (table/list, add rule from the card detail "Avisarme del precio"), alerts history from `rbnotiflog`. (F4-i)

### Offline / i18n / a11y / security
- **F4-R21** Dashboard and value history in the read cache (`rb-api-dashboard`, NetworkFirst); notification settings require a connection.
- **F4-R22** Namespaces `dashboard`, `notifications`; push titles/bodies rendered in the user's language (`rbuserprefs.lang`, fallback es).
- **F4-R23** Every new rule classified (all U; none public). Push endpoints validated; VAPID private key never logged or returned; job params never include secrets.

## Data model changes

| Table | Migration (next free numbers) | Risk |
|---|---|---|
| `rbjobs` | `00NN_jobs` | Medium: partial unique index (PostgreSQL and SQLite both support `WHERE`) |
| `rbvaluesnaps` | `00NN_value_snapshots` | Low |
| `rbpushsubs`, `rbnotifprefs`, `rbnotiflog` | `00NN_push` | Low |
| `rbwatch` | `00NN_watchlist` | Low |

All downgrades drop the tables (data loss documented). No change to existing tables.

## API

| Method | Path | Auth | Purpose | Unit |
|---|---|---|---|---|
| GET | `/prices/movers` | U | Risers/fallers 7/30 d, all or mine | F4-d |
| GET | `/collection/value-history` | U | Snapshot series | F4-d |
| GET | `/dashboard` | U | Dashboard payload | F4-e |
| GET | `/push/config` | U | `{enabled, public_key}` | F4-f |
| POST / DELETE | `/push/subscriptions` | U | Subscribe / unsubscribe this device | F4-f |
| GET / PATCH | `/me/notifications` | U | Categories on/off | F4-f |
| POST | `/push/test` | U | Send a test notification to the caller's devices (rate-limited 5/hour) | F4-f |
| GET / POST | `/watchlist` | U | List / create rules | F4-g |
| PATCH / DELETE | `/watchlist/{id}` | U | Edit / remove | F4-g |
| GET | `/notifications` | U | Latest 50 notifications of the user (from `rbnotiflog`) | F4-g |

New error codes: `push_disabled` (503, VAPID not configured), `push_subscription_invalid` (400, bad
endpoint/keys), `already_exists` (409, shared with F3/F5). Rate limit on `/push/test` uses `rate_limited`.

## UI

| Route | Mobile < 860 | Desktop ≥ 1240 | Wide ≥ 1600 |
|---|---|---|---|
| `/dashboard` | KPIs 2×2, chart, movers tabs, alerts, set completion (stacked) | chart 2/3 + rail 1/3 | 3 columns |
| `/account/notifications` | single column of `SettingsCard`s | 2 columns (permission + categories / devices + history) | same |
| `/prices/watchlist` | list of rules with current price | table + card preview | + chart of the selected card |

New components: `ValueChart` (PriceChart generalized to a value series with cost line), `KpiCard`
(`StatCard` with delta + sparkline), `MoversList`, `NotificationPermission`. States: loading, empty
("Recopilando datos: vuelve mañana"), error, offline, push unsupported/denied.

## Units

| ID | Title | Depends on | Size | Risk | Summary |
|---|---|---|---|---|---|
| F4-a | Job runner + timers | M-c (order) | ~500 | items 1, 4, 5 | `rbjobs`, registry, `flask jobs …`, claim/timeout, runbook + unit templates (06:30 and 08:00 Europe/Madrid) |
| F4-b | Daily Cardmarket load job | F4-a | ~300 | items 3, 6 | `daily_prices` job (loader + validation record + auto-match of clear cases + review list), 08:00 retry rule, chaining, unchanged skip |
| F4-c | Value snapshots | F4-a, F3-b (runs with F3) | ~350 | item 1 | `rbvaluesnaps`, `value_snapshot` job, idempotent upsert |
| F4-d | Movers + value-history API | F4-c | ~400 | item 3 | `/prices/movers`, `/collection/value-history` |
| F4-e | Dashboard API | F4-d | ~350 | item 3 | `GET /dashboard` with the null slots for F7/F8 |
| F4-f | Web Push infrastructure | F4-a | ~600 | items 2, 5 | VAPID env, `pywebpush`, subscriptions, prefs, log, `send_push`, SW `importScripts`, `check:dist` |
| F4-g | Watchlist + price alerts | F4-b, F4-f, F3-f | ~500 | items 1, 4 | `rbwatch`, CRUD, `price_alerts` job, `/notifications` |
| F4-h | Dashboard UI + price freshness | F4-e | ~650 | none | `/dashboard` mobile/desktop/wide, `ValueChart`, `KpiCard`, nav flip, topbar indicator |
| F4-i | Notifications + watchlist UI | F4-f, F4-g | ~600 | item 6 | Permission flow, categories, devices, test push, watchlist screens, "Avisarme" in card detail |

## Open decisions

| ID | Question | Options | Recommendation | Blocks |
|---|---|---|---|---|
| D-F4-3 | Movers noise floor | — | Ignore cards whose market price is below 0.50 € on either date; ties by absolute change | F4-d |
| D-F4-4 | Snapshot for users without a collection | skip / zero rows | Skip; first snapshot the day after the first line exists | F4-c |
| D-F4-5 | Value used in snapshots | PRC-1 market per line | PRC-1 market (same as the collection screen) | F4-c |
| D-F4-6 | Push library and SW strategy | `pywebpush` + `importScripts` / switch to `injectManifest` | `pywebpush` pinned; keep `generateSW` and add `importScripts` (smaller change, rollback unchanged) | F4-f |
| D-F4-7 | Default for `price_alerts` | on / off | On as soon as the user enables push on a device | F4-f |
| D-F4-8 | Watchlist rule types | below / above / % change | All three; `change_pct` evaluated on the 7-day trend | F4-g |
| D-F4-9 | Keep the Jinja dashboard reachable? | yes / redirect | Yes until F11 (classic link) | F4-h |
| D-F4-10 | Where does the auto-match review list live? | job result JSON / new table | The `daily_prices` job result (`rbjob_result`: product id, candidate cards, reason), readable with `flask jobs list` and later in the F10 mapping screens; a table only if the list outgrows the job result | F4-b |

## Risks and notes

- **Overlapping runs**: the partial unique index + atomic claim prevent two workers or two timers from
  running the same kind; `run-pending` must also be safe if systemd starts it while the previous run is alive.
- **External dependency**: Cardmarket file URLs or format may change (item 6); the job reports an error,
  keeps the previous prices and never leaves half-loaded data (existing loader transactions). The 08:00 retry
  runs once; a second failure stays visible in the job list and `rbcm_load_history`.
- **Push on iOS** needs the installed PWA; the UI explains it instead of failing silently.
- **Service worker change** (F4-f) ships through the update prompt; the self-destroying rollback keeps working
  (`importScripts` file must be precached or served `no-cache`).
- The snapshot table grows by users × days (small); value history before F4 cannot be reconstructed.
- F7 fills `recent_sales`; F8 adds `event_reminders` and uses `rbnotiflog`; F10 reuses `rbjobs` and lists
  job runs.
