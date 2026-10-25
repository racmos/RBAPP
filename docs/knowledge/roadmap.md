# Roadmap

Master plan. Supersedes `openspec/roadmap.md` (Spanish, 2026-10-18), which stays for history. Status
lives in `state.md`; owner decisions in `product.md`; each phase's detail in
`docs/requirements/F<n>/README.md`; maintenance units outside the phases in `docs/requirements/M/`. Phase
IDs are identifiers, not order: the order is the table below and the "Order" list. The owner set this order
on 2026-10-22 (`decisions-2026-10-22.md`).

## Phases

Rows follow the agreed order (first unit of each phase). A phase split across the order says so in "Goal".

| Phase | Goal | Depends on | Status |
|---|---|---|---|
| F0 Foundation | Secrets in env, admin role, CSRF, login protection, Alembic baseline, API v1 skeleton, CI. | — | Done |
| F1 App shell | React PWA shell: toolchain, tokens, background, brand, auth screens, i18n, prefs, nav, PWA. | F0 | Done (a-g, close; archived 2026-10-22) |
| M-a Test reset | Remove the old suites; keep the authorization matrix; add startup smoke tests. | F1 | Done (#29) |
| M-b Plan update | Fold the owner decisions of 2026-10-22 into the plan documents; add the F13, F14, F15 phase specs. | M-a | Done (#30) |
| M-c Hygiene | Private IPs and the dev domain out of tracked files (no history rewrite); legacy endpoints stop returning exception text (clear message + error code to the user, full detail logged and visible to the admin); `datetime.utcnow()` → `app/utils/clock.utcnow()`. | M-b | Next |
| F4 Prices + Dashboard | **F4-a + F4-b first** (job runner + timers, daily Cardmarket load at 06:30 Europe/Madrid with retry at 08:00, validation record, auto-match of clear cases). F4-c (daily value snapshots) with F3; the rest (movers, watchlist + push alerts, KPIs + 12-month chart) in the medium-priority group. | M-c (F4-a/b); F3-b (F4-c) | Planned |
| F2 Catalog | **F2-a first** (bans per mode, by card name, initial data from the official ban list). The rest after F13: cards API with filters/facets, catalog UI, card detail with real price history, my copies, related cards, offline catalog. | F1; F2-a → F13 → rest | Planned |
| M-d Images out of git | Card images out of git into a data directory outside the code tree (copy first: removing them from the index would delete them from the deployed checkout on the next pull). | F2-a | In review (#37) |
| F13 Riot sync + catalog admin | Admin foundation, sets with release date entered by hand, cards, Riot sync schedule, change-approval table. Pulled forward from F10 (F10-a, F10-e, F10-f) without waiting for F9. | F4-a (job runner), M-d | Planned |
| F3 Collection | Table + grid, add, bulk edit, server export, CSV import wizard, wishlist, purchase price, selling model with sub-lines, playset setting + "keep a playset" warning. Built together with F4-c. | F2 | Planned |
| F14 Products | Sealed Cardmarket products (boxes, cases, sleeves, …): price and history, quantity owned, a separate "products" total (not added to the collection value). | F3 | Planned |
| F5 Decks v2 | Deck format v2, shared rules Python/TS, migration of existing decks, editor, import/export, legality per mode, deck vs collection, versions diff, share link. **Without** the hand simulator / mulligan (F5-k, after production). | F2 (bans), F3 (collection) | Planned |
| F6 Stats | Distributions by domain/rarity/type/set, top value, value over time. | F4-c (snapshots) | Planned |
| F7 Sales | Sales table, listings from lines on sale, margin, Cardmarket export. | F3, F4 | Planned |
| F10 Admin | React admin (rest): users, Cardmarket tools and mappings, bans per mode, audit, event moderation. Catalog admin and Riot sync moved to F13; the legacy price CSV is dropped. | F13 (foundation), F9 (users), F2-a (bans), F4 | Planned |
| F9 Account | Profile + avatar, TOTP 2FA, server-side sessions/devices, API key; **Google/Discord login (F9-f) just before production**. | F1 | Planned |
| F11 Close | Retire Jinja, a11y audit, performance, final docs, Riot disclaimer. **Without** the new landing (F11-a/b move with F8). | F2-F7, F9, F10 | Planned |
| F12 Production | Final URL/server, HTTPS, new secrets, production DB from Alembic, backups, monitoring, CSP enforcing, licensing. | F11 | Planned |
| F15 Rules app | After production, before events: select cards that interact; answers only from the official Core Rules, Tournament Rules and FAQ; stored queries returned when repeated. Specified when the phase starts. | F12 | Planned |
| F5-k Mulligan / opening hands | Split out of F5: opening-hand simulator and mulligan. Needs the official rules from the owner. | F12, F15, F5 | Planned |
| F8 Events | Upcoming-events calendar scraped from the official site first; past events when a source exists; manual (private/public) events, results + deck played, ICS/GCal, push reminders. With the **new landing** (F11-a/b). | F12, F15, F4 (push, job runner), F5 (decks) | Planned |

Order (owner, 2026-10-22):

1. M-a test reset (done) → M-b plan update → M-c hygiene.
2. F4-a + F4-b (job runner + timers, daily Cardmarket load).
3. F2-a (bans per mode; the owner provides the official ban list).
4. M-d (card images out of git).
5. F13 Riot sync + catalog admin.
6. F2 rest (catalog).
7. F3 collection + F4-c daily value snapshots.
8. F14 Products.
9. Medium priority: rest of F4, F5 without the hand simulator, F6, F7, rest of F10, F9, F11 without the new
   landing, then F12 production. Inside the group the unit dependencies decide: F10 users admin (F10-b/c)
   waits for F9; F9-f (Google/Discord login) and its UI F9-g are done just before F12; F6 and F7 can swap.
10. After production: F15 Rules app → F5-k mulligan / opening hands → F8 events + new landing (F11-a/b).

## Cross-phase contracts

Decisions that make the phases fit together. A phase spec that needs to break one says so and the owner
decides.

- **Bans per mode** — F2-a creates the ban table (1v1/2v2, by card name), its read API and a `flask bans …`
  CLI; the initial data comes from the official ban list provided by the owner (the legacy `rbcar_banned`
  flag is not a source: the Riot scraper resets it). F5 uses it for deck legality. F10 adds the admin UI.
- **Admin foundation** — F13 builds the guarded admin blueprint, audit table and layout (F10-a, pulled
  forward) without waiting for F9. F10 builds the rest of the admin on it; F10 users admin still waits for F9.
- **Meta endpoint** — F2 fixes the shape of the meta/enums endpoint (sets, enums, rule values); F5 adds the
  deck rule values to it. Rule values are never hardcoded in the frontend.
- **Offline read cache** — F2-j adds service-worker runtime caching: read-only API GETs use **NetworkFirst**
  (4 s timeout, then cache; stale-while-revalidate was rejected because the refetch after an edit would show
  old data), caches named `rb-api-catalog`, `rb-api-collection`, `rb-api-decks`, `rb-api-dashboard`,
  `rb-api-stats`; images cache-first with an LRU/size limit; TanStack queries that must work offline use
  `networkMode: 'offlineFirst'`; API caches are purged on logout and when the signed-in user changes. This
  amends F1 PWA-1 ("no runtime caching") and the `check:dist` rule. F3, F5, F4 and F6 extend it. Offline
  covers what was already viewed (no full catalog snapshot). Edits always need a connection. Offline for
  sales or events is outside `product.md` and needs the owner (D-F7-9, D-F8-12).
- **Collection data** — F3 owns purchase price, the selling model (bulk sell count + switch + sub-lines
  with price/condition/language) and the wishlist. F7 builds sales on top.
- **Jobs, snapshots and push** — F4-a creates the job runner: table `rbjobs` + `flask jobs run-pending`
  (lock, run by a systemd timer every minute; no Celery/Redis). F4 uses it for the daily Cardmarket load and
  the daily collection-value snapshot; F13 registers the Riot sync kinds; F10-d adds the admin-triggered
  Cardmarket kinds. Every later phase only registers job kinds, never a second runner. F8 uses it for scraper imports and reminders; F9-k for scheduled account deletion.
  F4-f adds Web Push (VAPID keys in env vars, subscriptions table, service-worker push handler via
  `importScripts`, notification-preference categories; F8 adds "event reminders") and a `recent_sales`
  dashboard slot that F7 fills. F6 reads the snapshots.
- **Collection contract for sales** — F3 provides per line `purchase_price` (EUR per unit, nullable), the
  `selling` switch, `sell_qty`, `sell_price`, sub-lines as separate `rbcol_id` rows and
  `PATCH /collection/{id}`; condition and language enums in `/meta/game`. F7 relies on exactly this.
- **Identity in new tables** — new tables reference `rbusers.id` (like `rbuserprefs`); the legacy
  `rbcollection` and `rbdecks` keep the username reference (D-F3-6). F9-k's account purge must list every
  table that references a user, across all phases.
- **Error codes** — each code is introduced once and reused: `insufficient_quantity` (F3-c; F7 adds
  `params.index`), `already_exists` (F13 duplicate set/card, which runs first; reused by F3 wishlist, F4 watchlist and F5 deck names),
  `import_format_unknown` (F3, reused by F5). Each phase spec lists its new codes; F2 adds none.
- **Shared UI** — F2 builds the card atoms, `CardCombobox`, price chart and sparkline; F4 builds `ValueChart`
  and `KpiCard`; F5 builds `Donut` and `MiniCurve` (if F6 runs before F5 they move to F6-b).
- **Migrations** — every unit takes the next free revision number at implementation time. F4-a now runs
  before F2-a, so the names drafted in F2 (`0007_card_bans`, `0008_price_product_date_idx`) are renumbered
  then.
- **Decks** — F5 makes decks private by default with public share links; F8 links "deck played" to an F5 deck.
- **Sessions and identity** — F9 introduces the server-side session table, TOTP, OAuth and API keys.
- **Jinja retirement** — each phase flips its module's nav registry entry from `legacy` to `spa` and keeps
  the Jinja page reachable until F11 removes Jinja.
- **Layouts** — every new screen defines mobile (< 860 px), desktop (≥ 1240 px) and wide (≥ 1600 px)
  layouts; desktop shows more data.

## Units per phase

Unit tables (ID, title, dependencies, size, risk) are in each phase spec. Summary:

| Phase | Units | Order and notes |
|---|---|---|
| F1 | g (optional), close | `docs/requirements/F1/`. Done. |
| M (maintenance) | a test reset · b plan update · c hygiene · d card images out of git | `docs/requirements/M/`. a and b done; c next; d after F2-a. |
| F2 Catalog | a bans · b game meta + card DTO · c cards list API · d card detail API · e card UI atoms · f card detail screen · g price chart · h catalog page (nav flip) · i catalog desktop/wide · j offline cache · k card combobox + topbar search · l WebP thumbnails (optional, Pillow) | a right after F4-a/b (initial ban data from the official list); b→k after F13, in order (f before h so tiles never link to a missing route); l any time after b. Unit drafts written; they need the planner's rewrite before hand-over. |
| F3 Collection | a data (purchase price, sell_qty, playset setting) · b read API · c write API · d export · e import · f wishlist data/API · g UI mobile (nav flip) · h UI desktop/wide · i import wizard + export dialog · j wishlist UI · k offline | API units before UI. F4-c is built with F3. The owner provides CSV samples at the start of F3 (F3-e). The legacy `rbcol_selling = 'S'` value is evaluated and removed in F3. |
| F4 Prices + Dashboard | a job runner + timers · b daily Cardmarket load · c value snapshots · d movers + value history API · e dashboard API · f Web Push · g watchlist + alerts · h dashboard UI · i notifications + watchlist UI | a and b right after M-c (a first: everything scheduled depends on it); c with F3; d-i in the medium-priority group. |
| F13 Riot sync + catalog admin | a admin foundation (from F10-a) · b catalog admin API (from F10-e) · c Riot sync engine + change table · d sync schedule · e sync + approval API · f catalog admin UI (from F10-f) · g change review UI + hand-off | `docs/requirements/F13/README.md`. Uses the F4-a job runner; does not wait for F9. |
| F14 Products | sealed products, price and history, quantity owned, "products" total | `docs/requirements/F14/README.md`. After F3. |
| F5 Decks v2 | a rules engine (Python) + rule values in meta · b rules library (TS, shared cases) · c v2 tables + migration of existing decks · d decks API · e import/export API · f deck vs collection · g share link · h UI mobile · i UI desktop/wide + analysis · j import/export + versions UI · k hand simulator / mulligan (split out, after production) · l offline · m public deck page | The owner provides deck export samples at the start of F5 (F5-e) and the official opening-hand/mulligan rules before F5-k. Decks become owner-only (amends DECK-1). |
| F6 Stats | a stats API · b chart components · c stats page (nav flip, offline) | Can swap with F7. |
| F7 Sales | a sales table + create API · b lifecycle · c listings + summary API · d export · e UI listings + sell · f UI history, export, wide rail | Export stays byte-identical to today's Cardmarket export (D-F7-4). |
| F10 Admin | b users API · c users UI + forced password change · d Cardmarket job kinds · g mappings API port · h mappings UI · i bans admin · j events moderation · k audit UI + Jinja admin hand-off | a, e and f moved to F13. Users admin (b, c) waits for F9. j needs F8-a, so it waits for F8. The legacy price CSV generator is dropped. Desktop-first. |
| F9 Account | a server-side sessions · b profile + password + re-auth API · c avatar · d TOTP enrolment · e 2FA at sign-in · f OAuth backend + owner guide · g OAuth UI · h API key · i account shell + profile UI · j security + API UI · k scheduled account deletion | f and g just before F12 (the owner creates the OAuth apps following the guide). New deps to approve (D-F9-10). |
| F11 Close | c about + licences · d retire Jinja (user modules) · e retire Jinja (admin + leftovers) · f legacy schema cleanup (optional) · g E2E + axe harness · h a11y fixes + audit · i performance · j final docs | a (public feeds API) and b (new landing) move with F8, after production. |
| F12 Production | a server config + logging · b CSP enforcing · c release artifact + deploy script · d backups + restore check · e monitoring + alerting · f production Nginx template + runbook · h licensing + privacy pages · i data export/import (optional) · j go-live record | g (card images out of the code tree) moved to unit M-d. b depended on F11-b (new landing), now after production: see the F12 spec. Many USER steps (host level). |
| F15 Rules app | outline only | `docs/requirements/F15/README.md`. Specified when the phase starts. |
| F8 Events | a model + read API · b manual events + saves · c ICS + feed · d scraper import job · e results + stats API · f UI upcoming + forms · g UI calendar/history/results · h push reminders | After F15 and F5-k, with F11-a/b. The scraper starts with the upcoming-events calendar of the official site; past events when a source exists. |

Open decisions per phase: `open-decisions.md`.

