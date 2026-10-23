# Open decisions

Product decisions still open, by phase. Each one has an ID, a recommendation and the full context in its
phase spec (`docs/requirements/F<n>/README.md` → "Open decisions"). The planner asks the ones that block the
next unit, in one batch, before writing that unit's requirement; the answer is recorded in the requirement
and later folded into the phase spec (and into `product.md` when it is a product rule).

Format: **ID** — question: *recommendation*.

Answered decisions leave this list. The answers of 2026-10-22 live in each phase spec, section "Decisions
already taken", and in `product.md`: F2 (D-F2-1, D-F2-2, D-F2-12), F3 (D-F3-1), F4 (D-F4-1, D-F4-2), F5
(D-F5-6), F8 (D-F8-1), F10 (D-F10-4, D-F10-6), F12 (D-F12-8).

The order of the sections follows the phase order of `roadmap.md`.

## F1 (before F1-close)

- **CONFIRM F1-g** — do F1-g before closing F1?: *yes (small, closes unit 7).*
- **CONFIRM sign-offs** — logo trace (1.39) and background default 100 with current blur/darkening (1.50, 5.41): *accept (owner said the logo is fine; only the zoom was wrong and it was fixed).*

## F4 Prices + Dashboard (F4-a/F4-b right after M-c)

- **D-F4-3** — movers noise floor. · **D-F4-4** — snapshots only for users with a collection: *yes.*
- **D-F4-5** — snapshot value uses the PRC-1 market price: *yes.* · **D-F4-6** — `pywebpush` + `importScripts`: *yes.*
- **D-F4-7** — price alerts on by default: *yes.* · **D-F4-8** — watchlist rule types. · **D-F4-9** — keep the Jinja dashboard until F11: *yes.*
- **D-F4-10** — where the auto-match review list lives: *the `daily_prices` job result (`rbjob_result`); a table only if it outgrows it.*

## F2 Catalog (F2-a after F4-a/F4-b; the rest after F13)

- **D-F2-3** — who can read the catalog API: *signed-in users; `/meta/game` public.*
- **D-F2-4** — base printing and tokens: *base = lowest numeric number; tokens excluded from deck search.*
- **D-F2-5** — prices shown on the card: *Mercado (with its source), Mín., Media 30 d, Mercado foil; no "High".*
- **D-F2-6** — history ranges: *30d / 90d (default) / 1y / all.*
- **D-F2-7** — offline strategy: *NetworkFirst (4 s) instead of stale-while-revalidate.*
- **D-F2-8** — offline scope: *what was already viewed; no full catalog snapshot.*
- **D-F2-9** — cache budgets: *as proposed in the spec.*
- **D-F2-10** — thumbnails with Pillow (optional unit F2-l): *yes.*
- **D-F2-11** — `sets` nav entry: *stays legacy until the catalog admin (F13, pulled forward from F10).*
- **D-F2-13** — catalog defaults: *grid, 48 per page, sort by number.*
- **D-F2-14** — topbar search: *from 1240 px.*

## F13 Riot sync + catalog admin

- **D-F13-1** — time of the once-a-day run in the 14 days after release: *08:00 Europe/Madrid (same timer as the pre-release morning run).*
- **D-F13-2** — day and time of the monthly run: *1st of each month at 08:00 Europe/Madrid, all sets in `monthly` in one run.*
- **D-F13-3** — sets without a release date (legacy sets with `rbset_outdat` NULL, or a set created without it): *Required when creating through the admin API; existing sets without a date are treated as `monthly` and listed on the overview.*
- **D-F13-4** — gallery cards whose set code has no `rbset` row: *Auto-create the set (name = code, no release date) so new cards are always inserted, and flag it on the overview for the admin to name and date.*
- **D-F13-5** — rules of a manual "sync now": *Same per-set window rules as a scheduled run, but processing every requested set regardless of the time.*
- **D-F13-6** — manual admin edits vs changes auto-applied inside a window: *Gallery wins inside the windows (the edit is visible in the audit with old and new value); outside the windows the change goes to approval as usual.*
- **D-F13-7** — a rejected change seen again in a later monthly run: *Do not propose it again while the gallery value equals the rejected new value; a different value creates a new pending row.*
- **D-F13-8** — image changes (`image_url` differs): *Treat `image_url` as a synced field; when applied or approved, download the new image over the same file name.*
- **D-F13-9** — cards in the database that are no longer in the gallery: *Report only (job result + overview); never delete automatically.*
- **D-F13-10** — `rbcar_banned` in the sync: *Stop writing it (not a synced field); the column is dropped later with D-F10-7.*
- **D-F13-11** — legacy Jinja buttons `POST /refresh-riot-sets` and `/extract-riot-cards`: *`extract-riot-cards` delegates to the F13 sync service as a manual run (same rules, no second writer); `refresh-riot-sets` stays (read only); banner links to `/admin/riot`.*
- **D-F13-12** — deleting sets and cards (was D-F10-5): *Only unused (the FK cascade would delete users' collection lines).*
- **D-F13-13** — audit retention (was D-F10-8): *1 year, purge job registered on the F4-a runner.*
- **D-F13-14** — admin design (was D-F10-11): *From tokens; owner reviews screenshots in each PR.*
- **D-F13-15** — admin on mobile (was D-F10-9): *Read + approve/reject changes + "sync now"; editors desktop-preferred but usable.*
- **D-F13-16** — telling the admin that changes are pending: *Overview counter + badge on the admin nav entry; push once F4-f exists, as a later addition.*
- **D-F13-17** — riot job kinds planned in F10-d (`riot_sets`, `riot_extract`): *One `riot_sync` kind in F13; F10-d keeps only the Cardmarket kinds.*
- **D-F13-18** — `rbset_ncard` written by the current scraper: *Admin-owned: the sync reports the gallery count in the result and fills `rbset_ncard` only when it is NULL.*

## F3 Collection

- **D-F3-2** — import sample files (riftdecks, piltoverarchive, Cardmarket, others) and RBAPP CSV columns: *the owner provides samples.*
- **D-F3-3** — import previews: *stored in a DB table.*
- **D-F3-4** — language list.
- **D-F3-5** — merge identical lines on add: *yes.*
- **D-F3-6** — `rbcol_user` stays a username: *yes (new tables use `rbusers.id`).*
- **D-F3-7** — wishlist vs F4 watchlist: *separate concepts.*
- **D-F3-8** — undo window and bulk limits.
- **D-F3-9** — where the "playset size" setting is stored: *`rbuserprefs` column (`NULL` = default 3), through `/me/prefs`.*
- **D-F3-10** — "keep a playset" stored per what, and what counts as kept: *per user + card name; kept = sum of `qty − sell_qty` over the name's lines.*
- **D-F3-11** — what the legacy `rbcol_selling = 'S'` becomes: *decide from the F3-a evaluation of the dev data; if it means "surplus for sale", `S` → `Y`.*
- **D-F3-12** — do lines with a legacy `rbcol_playset` turn on "keep a playset" for their name: *yes, once in the F3-a migration.*

## F14 Products

- **D-F14-1** — where the product catalog lives: *Reuse `rbproducts`, keyed by Cardmarket id, filled from the non-singles data after each load; `rbcm_products` stays the raw daily copy.*
- **D-F14-2** — which products count (sleeves and accessories may not be in the Riftbound non-singles file): *Every non-single product of the Riftbound file; the admin hides what does not belong; products outside the file wait until a source exists.*
- **D-F14-3** — product type list: *Fixed list (`booster`, `box`, `case`, `bundle`, `starter`, `sleeves`, `accessory`, `other`) mapped from the Cardmarket category, admin can override.*
- **D-F14-4** — price used for a sealed product: *Chain `avg7 → trend → low` (no foil fields); NULL and 0 count as missing, like PRC-1. The implementer checks which fields the price guide fills for non-singles on the dev database (read only).*
- **D-F14-5** — fields of an owned line and duplicates: *Quantity + optional purchase price + note; several lines per product allowed when the purchase price differs (same rule as F3-R6), otherwise adding merges the quantity.*
- **D-F14-6** — history of the products total: *Nullable `rbvsn_products_value` in the daily snapshot, shown as its own series (never summed with the cards).*
- **D-F14-7** — products total on the dashboard (F4-e): *Yes, as its own KPI next to the collection value, clearly labelled.*
- **D-F14-8** — product images: *Admin upload or image URL stored in the data directory (same safety rules as card images); placeholder per type when missing.*
- **D-F14-9** — wishlist and price alerts for products: *Later (after F4-g watchlist exists); out of F14.*
- **D-F14-10** — selling products (F7): *Later, outside F7's card contract.*
- **D-F14-11** — who sees the product catalog: *Signed-in users (`U`), like the card catalog.*
- **D-F14-12** — products offline: *Read cache `rb-api-products` (NetworkFirst, purged on logout), extending the offline list in product.md, which needs the owner's yes.*
- **D-F14-13** — existing `rbproducts` rows of type `single` written from the Jinja admin: *Keep them out of the products catalog (filter `nonsingle`); review on the dev database before the migration.*

## F5 Decks v2

- **D-F5-1** — new head/version tables: *yes.* · **D-F5-2** — Jinja deck pages read-only after migration: *yes.*
- **D-F5-3** — when a new version is created. · **D-F5-4** — what a public link shows.
- **D-F5-5** — import sample files (riftdecks, piltover): *the owner provides them.*
- **D-F5-7** — name collation. · **D-F5-8** — where the shared Python/TS rule cases live.
- **D-F5-9** — decks become owner-only (amends contract DECK-1): *yes, per product.md.*

## F6 Stats

- **D-F6-1** — unpriced lines. · **D-F6-2** — tokens and Basic Runes in set completion. · **D-F6-3** — promo sets in completion.
- **D-F6-4** — P/L reference. · **D-F6-5** — F6 and F7 can swap order.

## F7 Sales

- **D-F7-1** — revenue counts shipped sales only. · **D-F7-2** — cancelling asks to return copies (default yes); only cancelled sales can be deleted.
- **D-F7-3** — one optional `fees` field. · **D-F7-4** — Cardmarket export byte-identical to today's.
- **D-F7-5** — "real margin" and "vs market" never summed. · **D-F7-6** — optional channel enum.
- **D-F7-7** — sale date as the user's local date. · **D-F7-8** — export quantity follows F3's "copies to sell".
- **D-F7-9** — no offline for sales. · **D-F7-10** — conditions/languages from `/meta/game`. · **D-F7-11** — only lines on sale can be sold.

## F10 Admin

D-F10-5, D-F10-8, D-F10-9 and D-F10-11 moved to F13 (D-F13-12 to D-F13-15): the admin foundation is built there.

- **D-F10-1** — `is_admin` stays CLI-only: *yes.* · **D-F10-2** — password reset = temporary password + forced change.
- **D-F10-3** — admin can reset a user's 2FA.
- **D-F10-7** — drop `rbcar_banned` in F11-f. · **D-F10-10** — where the users' `sets` page goes: *F2 catalog.*

## F9 Account

- **D-F9-1** — e-mail optional, unverified. · **D-F9-2** — account deletion with 10-day grace.
- **D-F9-3** — no public profile; drop social links. · **D-F9-4** — TOTP secrets encrypted at rest.
- **D-F9-5** — OAuth can create accounts; never auto-link by e-mail. · **D-F9-6** — 2FA also after OAuth sign-in.
- **D-F9-7** — username not editable. · **D-F9-8** — API key read-only.
- **D-F9-9** — non-remembered sessions expire after 12 h idle. · **D-F9-10** — new deps: Pillow, pyotp, segno, cryptography, Authlib.
- **D-F9-11** — store only an IP prefix for sessions. · **D-F9-12** — avatars visible to signed-in users only.

## F11 Close

The landing decisions (D-F11-1, D-F11-2, D-F11-7, D-F11-10, D-F11-11) are asked when the landing is rebuilt
with F8, after production.

- **D-F11-1** — landing as a second Vite entry. · **D-F11-2** — landing shows real feeds only.
- **D-F11-3** — permanent 301 redirects from Jinja URLs. · **D-F11-4** — Playwright E2E in CI.
- **D-F11-5** — Lighthouse manual with thresholds. · **D-F11-6** — Riot disclaimer: English verbatim + Spanish.
- **D-F11-7** — replace the 5.3 MB landing frame animation. · **D-F11-8** — delete legacy JSON endpoints.
- **D-F11-9** — drop obsolete columns (optional unit). · **D-F11-10** — landing ES + EN. · **D-F11-11** — landing design from tokens.
- **D-F11-12** — what `/` shows between go-live and the new landing (F11-b): *hide the placeholder blocks with fabricated items (small change in F11-d or F12); full rebuild with F8.*

## F12 Production

- **D-F12-1** — final URL keeps `/riftbound`. · **D-F12-2** — one VPS for Nginx, app and DB.
- **D-F12-3** — in-memory rate limits + Nginx zones. · **D-F12-4** — encrypted daily backups 7/4/6 + off-site copy.
- **D-F12-5** — external uptime/heartbeat checks, alerts to a Discord webhook. · **D-F12-6** — fresh catalog; carry curated mappings and optionally the owner's data.
- **D-F12-7** — privacy/terms drafted by the planner, approved by the owner.
- **D-F12-9** — separate production OAuth apps. · **D-F12-10** — new VAPID keys. · **D-F12-11** — frontend built in CI as a release artifact.
- **D-F12-12** — log retention 14 d (Nginx) / 30 d (journald). · **D-F12-13** — separate DB roles for migrations and runtime.
- **D-F12-14** — no CSP report endpoint. · **D-F12-15** — dev serves as staging. · **D-F12-16** — the owner runs host-level steps.
- **D-F12-17** — Gunicorn workers 2×CPU+1, capped by RAM.

## F15 Rules app (after production)

- **D-F15-1** — aI service: *A hosted API with per-query billing, chosen when the phase starts by cost and quality on a sample of real rule questions.*
- **D-F15-2** — vector store: *`pgvector` in PostgreSQL (no new server; backups already cover it).*
- **D-F15-3** — cost control: *Per-user daily limit plus a global monthly budget with a kill switch; stored answers do not count.*
- **D-F15-4** — who can use it: *Admin only during a trial, then every signed-in user.*
- **D-F15-5** — when two queries are "the same": *Exact match on the sorted card set and the normalised question; semantic matches shown as "preguntas parecidas", not reused silently.*
- **D-F15-6** — languages: *Answers in the user's language (es/en) with quotes of the English source text.*
- **D-F15-7** — meaning of "Obsidian-like linking": *Backlinks and a list of related items first; a graph view only if the owner asks for it.*
- **D-F15-8** — how the official documents arrive and are updated: *Owner provides the files; the admin ingests a new version from the admin panel.*
- **D-F15-9** — stored answers after a new rules version: *Mark them outdated and recompute on the next request.*

## F8 Events (after production and after F15)

- **D-F8-2** — event types (prototype's six + mapping). · **D-F8-3** — reminders 24 h and 2 h before.
- **D-F8-4** — "deck played" links deck identity or a version. · **D-F8-5** — public events visible to signed-in users only.
- **D-F8-6** — "near me" = country filter now, profile country after F9. · **D-F8-7** — drop the tournament-winner column.
- **D-F8-8** — subscribable ICS feed with a revocable token. · **D-F8-9** — past manual events in History.
- **D-F8-10** — scraped event missing in 2 runs → cancelled, never deleted. · **D-F8-11** — 10 public events per user per day.
- **D-F8-12** — offline cache for events (outside product.md).
