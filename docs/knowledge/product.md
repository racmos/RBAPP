# Product: Rift Manager

Decisions agreed with the owner (2026-10-18 to 2026-10-22). They are binding for every phase unless the
owner changes them; a change is recorded here and in `state.md`.

## What it is

Rift Manager (repo `racmos/RBAPP`, formerly "Riftbound Manager") manages the Riftbound trading card game:
card catalog, personal collection, decks, Cardmarket prices, sales, events and stats.

- Installable PWA on mobile and desktop. On desktop the UI does **not** stretch: every module uses the
  extra width to show more data (more columns, side panels, 2-3 column layouts).
- Visual design comes from the hi-fi prototype "Rift Manager.zip" (design handoff). Its full inventory,
  tokens, screens, rules to port and gaps are in `openspec/design-handoff.md` (Spanish). The prototype
  code wins over its README when they disagree. The roadmap wins over the prototype.
- Multi-user. Only the owner is admin (`is_admin`). Open registration with protections
  (rate limits, ALTCHA proof of work, account lockout, admin can block accounts).
- There is **no production** yet. The current server and database are development. Production is phase F12.
  The Rules app (F15), the mulligan / opening hands section (F5-k) and events (F8) come after production,
  in that order (`roadmap.md`).

## Architecture decisions

| Topic | Decision |
|---|---|
| Backend | Flask stays, as a JSON API at `/riftbound/api/v1` with the envelope `{success, data, meta}`. Existing models, services (Cardmarket loader/matcher, Riot scraper) and Pydantic schemas are reused. |
| Frontend | React + TypeScript + Vite in `frontend/`, served by Flask at `/riftbound/app/` (not by Nginx). TanStack Query, React Router, react-i18next, CSS tokens + CSS Modules. |
| Auth | Same-origin session cookie (Flask-Login) + CSRF header. No JWT. Remember-me 30 days. |
| Migrations | Alembic (Flask-Migrate). The database is built only by migrations. |
| Jobs | One job runner, built once in F4-a: table `rbjobs` + `flask jobs run-pending`, run by a systemd timer. F10-d and every later phase only register job kinds. |
| Tests | The pre-existing suites were removed (M-a); only `tests/test_authz_matrix.py` and the startup smoke tests (backend + frontend) remain. Strict TDD continues: each unit writes its own tests and re-creates a removed guard when it touches its area. |
| Offline | Read-only: catalog, collection and decks viewable without network (from F2 on); every edit needs a connection. No API caching in F1. |
| Coexistence | Gradual: the PWA takes over one module per phase; modules not migrated stay in Jinja, linked from the app ("legacy" entries of the nav registry). Jinja is retired in F11. |
| Prices | Cardmarket only, EUR only. The prototype's provider/currency selector is hidden. |
| Languages | Spanish and English, real translations (`es` is the typed source catalog). |
| PWA | Manifest id/scope `/riftbound/`, start_url `/riftbound/app/`, service worker scope `/riftbound/app/`. Update prompt, never auto-reload. Rollback via a self-destroying service worker build. |

## Users, accounts and security

- No mail server: no password recovery by email. The admin resets passwords; Discord/Google OAuth login
  stays in F9 and is done just before production (F9-f); the owner creates the OAuth apps following a
  step-by-step guide.
- Secrets only through environment variables. Never in code, docs or commits.
- Private IPs and the dev domain are removed from tracked files only (unit M-c); the git history is not
  rewritten (no secret that is still valid was committed).
- `is_admin` / `is_blocked` change only through the CLI (`flask users ...`) until the F10 admin UI.
- Deck visibility from F5 on: private by default; the owner of a deck can mark it public or generate a
  read-only share link. Until F5 every signed-in user can see every deck (kept as is).

## Interface preferences (built in F1)

Stored per account in `rbuserprefs` (`NULL` = Auto): `lang`, `density`, `accent`, `bg_intensity`,
`collection_view`. Auto resolves by device: mobile (< 860 px) is compact + grid, desktop is regular +
table with more columns; orange accent on both; background intensity 100. Edited at
`/riftbound/app/account/interface`.

Background: the Summoner's Rift map, blurred and darkened, never brightened; portrait screens use the map
rotated 90 degrees. Body text keeps at least 4.5:1 contrast over it.

Brand: app name "Rift Manager"; orange swirl mark + "RIFT MANAGER" wordmark (sources in
`frontend/assets-src/brand/`); favicon is the simplified mark (approved 2026-10-21); app icon is the
swirl on teal `#06222c`.

## Game rules (single source of truth in the backend, served to the frontend by API)

- 1 Legend, 1 chosen Champion, **39 main-deck cards** (40 counting the chosen champion).
- Exactly **12 runes**, only of the legend's colours (domains).
- **3 distinct battlefields** (not counted in the deck).
- **Sideboard: 10 cards** (the prototype's 8 is obsolete).
- Max **3 copies per name** across main + sideboard + workbench + chosen champion. Different printings of
  the same name are the same card.
- Workbench: up to 100 distinct cards, excluded from the export.
- The champion must share a tag with the legend; changing the legend purges incompatible runes and champion.
- Game modes: **1v1 and 2v2 only** (no FFA). **Bans are per mode** and apply to the card **name** (all
  printings). A card can be banned in 1v1 and legal in 2v2. The UI says in which mode a card is banned and
  marks a deck **not legal** for its mode, explaining why. The single `rbcar_banned` column is not enough:
  a per-mode ban table is needed. Its initial data comes from the official ban list provided by the owner;
  the legacy `rbcar_banned` flag is not used as a source (the Riot scraper resets it).
- Opening hands / mulligan: a separate section after production (F5-k, split out of F5). It needs the
  official opening-hand and mulligan rules from the owner.
- Rule values live in one place in the backend and the frontend reads them from the API (never hardcoded).

## Data

- "Scraping" covers three sources: the official Riot card gallery (catalog); collection CSV import/export
  (F3); Cardmarket products, both singles and sealed (boxes, cases, sleeves, …).
- The card catalog (sets up to Vendetta) is maintained by the official gallery scraper
  (`app/services/riot_scraper.py` → `rbcards`). The prototype's CSV is **not** imported.
- Enum values (rarity, type, domain, …): the implementer reads the real values from the dev PostgreSQL
  database, read-only (the data there is real). The dev DB holds English values (the scraper reads
  `en-us`); the Spanish names come from the official Spanish card gallery (`es-es`), and the owner is asked
  only when a name is not there.
- **Riot sync** (F13, built with the catalog admin before the rest of the catalog): the admin creates the
  set and enters its release date by hand (the gallery provides no release date, and the set's name/code
  may change until the first card is revealed). From 21 days before the release date, card extraction runs
  at 08:00 and 14:00 Europe/Madrid; from the release date, once a day for 14 days; afterwards, once a
  month. New cards are always inserted. Changes to existing cards are applied automatically inside the
  active windows (pre-release and the 14 days after release); in the monthly run they go to an admin
  approval table (field, old value, new value; approve or reject).
- **Daily prices**: the Cardmarket load runs every day at 06:30 Europe/Madrid and retries at 08:00 if it
  failed. The job validates the load (files, rows, new products) and records the result. After every load
  the matcher links the clear cases automatically; doubtful cases go to a review list, which the planner
  analyses to add matching criteria and automate as much as possible.
- Card images: folder derived from the file-name prefix (`RbCard.image_src`). They move out of git into a
  data directory outside the code tree (unit M-d; copied first, because removing them from the index would
  delete them from the deployed checkout on the next pull).
- Price fallback chain (`app/services/pricing.py`): premium cards (rare, epic, showcase, or a foil copy) use
  `avg7_foil → avg7 → low_foil → low`; common non-foil uses `avg7 → avg7_foil → low → low_foil`; NULL and 0
  count as missing. Basic Runes have no foil slot.

## Scope by phase (owner decisions)

- **F3 Collection**: table + grid, add, bulk edit, server-side export, **CSV import wizard** (formats:
  own RBAPP, Cardmarket export, riftdecks.com, piltoverarchive.com, other apps; ask the owner for sample
  files when the phase starts), wishlist, optional **purchase price** per line.
  **Selling model**: on each line the owner marks in bulk how many copies to sell plus a selling switch;
  an expand arrow splits a card with several copies into sub-lines, each with its own price, condition and
  language (the synthetic `rbcol_id` rows already support this). The legacy `rbcol_selling = 'S'` value is
  evaluated and removed in F3.
  **Playset** (replaces the legacy `rbcol_playset`): a user profile setting "playset size", default 3,
  editable, and a per-card check "keep a playset" on each collection card. When a checked card's kept
  copies (counted per card name, all printings) fall below the profile value, the UI warns and highlights
  the line or tile in red. Nothing is blocked. The daily value snapshots (F4-c) are built with F3.
- **F4 Prices + Dashboard**: daily automatic Cardmarket load (job runner + timers, F4-a/F4-b, built right
  after M-c; schedule and auto-match under "Data"), daily collection-value snapshot per user (F4-c, with
  F3), top risers/fallers (7/30 days), watchlist with **push** alerts, KPIs + 12-month chart.
- **F5 Decks v2**: format v2 (legend, champion, main, runes, battlefields, sideboard, workbench), rules in
  Python + TS with shared test cases, **automatic migration** of existing decks (cards routed by type,
  keeping all versions), editor, text import/export (riftdecks/piltover formats), legality per mode,
  deck vs collection (missing cards + cost + wishlist), version diff, public read-only link. The
  opening-hand simulator / mulligan (F5-k) is split out and comes after production. Port the prototype's
  deck logic "as is" except where the rules above differ.
- **F6 Stats**: distribution by domain, rarity, type, set; top cards by value.
- **F7 Sales**: sales table, listings from lines on sale, selling deducts inventory, **real margin when a
  purchase price exists, otherwise comparison with that day's market price**, Cardmarket-compatible export.
- **F8 Events** (after production and after the Rules app): starts with an upcoming-events calendar scraped
  from the official site; past events when a source exists. Manual events (creator chooses private or
  public) + scraper events (always public), saved, result + deck played, ICS, Google Calendar, push
  reminders. The landing `/` is rebuilt with the events work: today's landing is a draft with placeholder
  content.
- **F9 Account**: extended profile + avatar, **TOTP 2FA**, sessions/devices (server-side session table),
  **Discord/Google login** (just before production), API key. No payments, no email recovery.
- **F10 Admin**: Cardmarket load, mappings, ignored, **users** (block, reset password; waits for F9),
  **bans per mode**. Desktop-first. Sets and card editing moved to F13. The legacy price CSV generator is
  dropped (it only listed `set;name;id;N` for every card, without prices); the Cardmarket sales export of
  F7 is a different feature and stays.
- **F11 Close**: retire Jinja, a11y audit, final docs, Riot fan-content disclaimer. The new landing with
  the install button moves to the events work (F8).
- **F12 Production**: deployment plan, final URL, HTTPS, new production secrets, production DB from
  Alembic, backups, monitoring, licensing review.
- **F13 Riot sync + catalog admin** (pulled forward from F10, without waiting for F9): admin foundation,
  sets with the release date, cards, Riot sync schedule and the change-approval table (see "Data").
- **F14 Products** (after F3): sealed Cardmarket products (boxes, cases, sleeves, …) with price and
  history, and the quantity owned. Their value is a separate "products" total, not added to the cards'
  collection value.
- **F15 Rules app** (after production, before events): the user selects cards that interact and the
  answer comes only from the official rule documents (Core Rules, Tournament Rules, FAQ). Previous queries
  are stored and returned when repeated. It needs an AI service (paid per query), semantic (vector) search
  and Obsidian-like linking. Specified when the phase starts.

## Platform notes

- Push on iOS only works with the PWA added to the home screen (iOS 16.4+).
- Store packaging later is possible with Capacitor without a rewrite.
