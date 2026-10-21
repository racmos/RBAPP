# Product: Rift Manager

Decisions agreed with the owner (2026-10-18 to 2026-10-21). They are binding for every phase unless the
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

## Architecture decisions

| Topic | Decision |
|---|---|
| Backend | Flask stays, as a JSON API at `/riftbound/api/v1` with the envelope `{success, data, meta}`. Existing models, services (Cardmarket loader/matcher, Riot scraper), Pydantic schemas and tests are reused. |
| Frontend | React + TypeScript + Vite in `frontend/`, served by Flask at `/riftbound/app/` (not by Nginx). TanStack Query, React Router, react-i18next, CSS tokens + CSS Modules. |
| Auth | Same-origin session cookie (Flask-Login) + CSRF header. No JWT. Remember-me 30 days. |
| Migrations | Alembic (Flask-Migrate). The database is built only by migrations. |
| Offline | Read-only: catalog, collection and decks viewable without network (from F2 on); every edit needs a connection. No API caching in F1. |
| Coexistence | Gradual: the PWA takes over one module per phase; modules not migrated stay in Jinja, linked from the app ("legacy" entries of the nav registry). Jinja is retired in F11. |
| Prices | Cardmarket only, EUR only. The prototype's provider/currency selector is hidden. |
| Languages | Spanish and English, real translations (`es` is the typed source catalog). |
| PWA | Manifest id/scope `/riftbound/`, start_url `/riftbound/app/`, service worker scope `/riftbound/app/`. Update prompt, never auto-reload. Rollback via a self-destroying service worker build. |

## Users, accounts and security

- No mail server: no password recovery by email. The admin resets passwords; Discord/Google OAuth login
  comes in F9 (the owner must be guided step by step to create the OAuth apps).
- Secrets only through environment variables. Never in code, docs or commits.
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
  a per-mode ban table is needed.
- Rule values live in one place in the backend and the frontend reads them from the API (never hardcoded).

## Data

- The card catalog (sets up to Vendetta) is maintained by the official gallery scraper
  (`app/services/riot_scraper.py` → `rbcards`). The prototype's CSV is **not** imported.
- Card images: folder derived from the file-name prefix (`RbCard.image_src`).
- Price fallback chain (`app/services/pricing.py`): premium cards (rare, epic, showcase, or a foil copy) use
  `avg7_foil → avg7 → low_foil → low`; common non-foil uses `avg7 → avg7_foil → low → low_foil`; NULL and 0
  count as missing. Basic Runes have no foil slot.

## Scope by phase (owner decisions)

- **F3 Collection**: table + grid, add, bulk edit, server-side export, **CSV import wizard** (formats:
  own RBAPP, Cardmarket export, riftdecks.com, piltoverarchive.com, other apps; ask the owner for sample
  files when the phase starts), wishlist, optional **purchase price** per line.
  **Selling model**: on each line the owner marks in bulk how many copies to sell plus a selling switch;
  an expand arrow splits a card with several copies into sub-lines, each with its own price, condition and
  language (the synthetic `rbcol_id` rows already support this). How the legacy `rbcol_playset` (copies
  kept) maps onto it is confirmed at the start of F3.
- **F4 Prices + Dashboard**: daily automatic Cardmarket load (timer), daily collection-value snapshot per
  user, top risers/fallers (7/30 days), watchlist with **push** alerts, KPIs + 12-month chart.
- **F5 Decks v2**: format v2 (legend, champion, main, runes, battlefields, sideboard, workbench), rules in
  Python + TS with shared test cases, **automatic migration** of existing decks (cards routed by type,
  keeping all versions), editor, text import/export (riftdecks/piltover formats), legality per mode,
  deck vs collection (missing cards + cost + wishlist), version diff, public read-only link, opening-hand
  simulator. Port the prototype's deck logic "as is" except where the rules above differ.
- **F6 Stats**: distribution by domain, rarity, type, set; top cards by value.
- **F7 Sales**: sales table, listings from lines on sale, selling deducts inventory, **real margin when a
  purchase price exists, otherwise comparison with that day's market price**, Cardmarket-compatible export.
- **F8 Events**: manual events (creator chooses private or public) + scraper events (always public),
  saved, result + deck played, ICS, Google Calendar, push reminders.
- **F9 Account**: extended profile + avatar, **TOTP 2FA**, sessions/devices (server-side session table),
  **Discord/Google login**, API key. No payments, no email recovery.
- **F10 Admin**: sets, card editing, Cardmarket load, mappings, ignored, **users** (block, reset password),
  **bans per mode**. Desktop-first.
- **F11 Close**: landing `/` restyled + install button, retire Jinja, a11y audit, final docs,
  Riot fan-content disclaimer.
- **F12 Production**: deployment plan, final URL, HTTPS, new production secrets, production DB from
  Alembic, backups, monitoring, licensing review.

## Platform notes

- Push on iOS only works with the PWA added to the home screen (iOS 16.4+).
- Store packaging later is possible with Capacitor without a rewrite.
