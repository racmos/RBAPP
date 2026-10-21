# Roadmap

Master plan. Supersedes `openspec/roadmap.md` (Spanish, 2026-10-18), which stays for history. Status
lives in `state.md`; owner decisions in `product.md`; each phase's detail in
`docs/requirements/F<n>/README.md`.

## Phases

| Phase | Goal | Depends on | Status |
|---|---|---|---|
| F0 Foundation | Secrets in env, admin role, CSRF, login protection, Alembic baseline, API v1 skeleton, CI. | — | Done |
| F1 App shell | React PWA shell: toolchain, tokens, background, brand, auth screens, i18n, prefs, nav, PWA. | F0 | a-f done; g optional; close pending |
| F2 Catalog | Cards API with filters/facets, catalog UI, card detail with real price history, my copies, related cards, **bans per mode**, offline catalog. | F1 | Next |
| F3 Collection | Table + grid, add, bulk edit, server export, CSV import wizard, wishlist, purchase price, selling model with sub-lines. | F2 | Planned |
| F4 Prices + Dashboard | Daily Cardmarket load, daily value snapshot, movers 7/30 d, watchlist + push alerts, KPIs + 12-month chart. | F3 | Planned |
| F5 Decks v2 | Deck format v2, shared rules Python/TS, migration of existing decks, editor, import/export, legality per mode, deck vs collection, versions diff, share link, hand simulator. | F2 (bans), F3 (collection) | Planned |
| F6 Stats | Distributions by domain/rarity/type/set, top value, value over time. | F4 (snapshots) | Planned |
| F7 Sales | Sales table, listings from lines on sale, margin, Cardmarket export. | F3, F4 | Planned |
| F8 Events | Manual (private/public) + scraped (public) events, results + deck played, ICS/GCal, push reminders. | F4 (push, scheduler), F5 (decks) | Planned |
| F9 Account | Profile + avatar, TOTP 2FA, server-side sessions/devices, Discord/Google login, API key. | F1 | Planned |
| F10 Admin | React admin: sets, cards, Cardmarket tools, users, bans per mode, event moderation. | F2, F4, F8, F9 | Planned |
| F11 Close | Restyled landing with install CTA, retire Jinja, a11y audit, performance, final docs, Riot disclaimer. | F2-F10 | Planned |
| F12 Production | Final URL/server, HTTPS, new secrets, production DB from Alembic, backups, monitoring, CSP enforcing, licensing. | F11 | Planned |

Order: F1-g (optional) → F1-close → F2 → F3 → F4 → F5 → F6 → F7 → F8 → F9 → F10 → F11 → F12.
F9 depends only on F1 and may be moved earlier if the owner wants 2FA/OAuth sooner; F6 and F7 can swap.

## Cross-phase contracts

Decisions that make the phases fit together. A phase spec that needs to break one says so and the owner
decides.

- **Bans per mode** — F2 creates the ban table (1v1/2v2, by card name), its read API and a `flask bans …`
  CLI. F5 uses it for deck legality. F10 adds the admin UI.
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
  the daily collection-value snapshot; F10-d adds admin-triggered kinds (`cardmarket_load`, `riot_sets`,
  `riot_extract`); F8 uses it for scraper imports and reminders; F9-k for scheduled account deletion.
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
  `params.index`), `already_exists` (F3 wishlist, reused by F4 watchlist and F5 deck names),
  `import_format_unknown` (F3, reused by F5). Each phase spec lists its new codes; F2 adds none.
- **Shared UI** — F2 builds the card atoms, `CardCombobox`, price chart and sparkline; F4 builds `ValueChart`
  and `KpiCard`; F5 builds `Donut` and `MiniCurve` (if F6 runs before F5 they move to F6-b).
- **Migrations** — F2 uses `0007_card_bans` and `0008_price_product_date_idx`; later phases take the next
  free revision number at implementation time.
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
| F1 | g (optional), close | `docs/requirements/F1/`. Recommended: F1-g, then F1-close. |
| F2 Catalog | a bans · b game meta + card DTO · c cards list API · d card detail API · e card UI atoms · f card detail screen · g price chart · h catalog page (nav flip) · i catalog desktop/wide · j offline cache · k card combobox + topbar search · l WebP thumbnails (optional, Pillow) | a→k in order (f before h so tiles never link to a missing route); l any time after b. Unit drafts written. |
| F3 Collection | a data (purchase price, sell_qty, playset mapping) · b read API · c write API · d export · e import · f wishlist data/API · g UI mobile (nav flip) · h UI desktop/wide · i import wizard + export dialog · j wishlist UI · k offline | API units before UI. Needs import sample files from the owner (D-F3-2). |
| F4 Prices + Dashboard | a job runner + timers · b daily Cardmarket load · c value snapshots · d movers + value history API · e dashboard API · f Web Push · g watchlist + alerts · h dashboard UI · i notifications + watchlist UI | a first (everything scheduled depends on it). |
| F5 Decks v2 | a rules engine (Python) + rule values in meta · b rules library (TS, shared cases) · c v2 tables + migration of existing decks · d decks API · e import/export API · f deck vs collection · g share link · h UI mobile · i UI desktop/wide + analysis · j import/export + versions UI · k public page + hand simulator · l offline | Owner must give official opening-hand/mulligan rules (D-F5-6). Decks become owner-only (amends DECK-1). |
| F6 Stats | a stats API · b chart components · c stats page (nav flip, offline) | Can swap with F7. |
| F7 Sales | a sales table + create API · b lifecycle · c listings + summary API · d export · e UI listings + sell · f UI history, export, wide rail | Export stays byte-identical to today's Cardmarket export (D-F7-4). |
| F8 Events | a model + read API · b manual events + saves · c ICS + feed · d scraper import job · e results + stats API · f UI upcoming + forms · g UI calendar/history/results · h push reminders | F8-d blocked until the owner picks a real event source (D-F8-1): today's landing feeds are placeholders. |
| F9 Account | a server-side sessions · b profile + password + re-auth API · c avatar · d TOTP enrolment · e 2FA at sign-in · f OAuth backend + owner guide · g OAuth UI · h API key · i account shell + profile UI · j security + API UI · k scheduled account deletion | New deps to approve (D-F9-10). |
| F10 Admin | a foundation (guarded blueprint, audit table, layout) · b users API · c users UI + forced password change · d jobs kinds + Cardmarket/Riot jobs · e catalog admin API · f catalog admin UI · g mappings API port · h mappings UI · i bans admin · j events moderation · k audit UI + Jinja admin hand-off | Desktop-first. |
| F11 Close | a public feeds API · b new landing · c about + licences · d retire Jinja (user modules) · e retire Jinja (admin + leftovers) · f legacy schema cleanup (optional) · g E2E + axe harness · h a11y fixes + audit · i performance · j final docs | |
| F12 Production | a server config + logging · b CSP enforcing · c release artifact + deploy script · d backups + restore check · e monitoring + alerting · f production Nginx template + runbook · g data dirs out of the code tree · h licensing + privacy pages · i data export/import (optional) · j go-live record | Many USER steps (host level). |

Open decisions per phase: `open-decisions.md`.

