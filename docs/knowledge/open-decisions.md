# Open decisions

Product decisions still open, by phase. Each one has an ID, a recommendation and the full context in its
phase spec (`docs/requirements/F<n>/README.md` → "Open decisions"). The planner asks the ones that block the
next unit, in one batch, before writing that unit's requirement; the answer is recorded in the requirement
and later folded into the phase spec (and into `product.md` when it is a product rule).

Format: **ID** — question: *recommendation*.

**Answered on 2026-10-22** (see `decisions-2026-10-22.md`; unit M-b removes them from this list): D-F2-1,
D-F2-2, D-F2-12, D-F3-1, D-F4-1, D-F4-2, D-F5-6 (moved after production), D-F8-1 (moved after production),
D-F10-6.

## F1 (before F1-close)

- **CONFIRM F1-g** — do F1-g before closing F1?: *yes (small, closes unit 7).*
- **CONFIRM sign-offs** — logo trace (1.39) and background default 100 with current blur/darkening (1.50, 5.41): *accept (owner said the logo is fine; only the zoom was wrong and it was fixed).*

## F2 Catalog (next phase — ask first)

- **D-F2-1** — real enum values (rarity, type, domain…) in the dev DB: *the owner runs three read-only queries given in the spec.*
- **D-F2-2** — migrate `rbcar_banned`: *S/Y become banned in both 1v1 and 2v2; the Jinja catalog reads the new table.*
- **D-F2-3** — who can read the catalog API: *signed-in users; `/meta/game` public.*
- **D-F2-4** — base printing and tokens: *base = lowest numeric number; tokens excluded from deck search.*
- **D-F2-5** — prices shown on the card: *Mercado (with its source), Mín., Media 30 d, Mercado foil; no "High".*
- **D-F2-6** — history ranges: *30d / 90d (default) / 1y / all.*
- **D-F2-7** — offline strategy: *NetworkFirst (4 s) instead of stale-while-revalidate.*
- **D-F2-8** — offline scope: *what was already viewed; no full catalog snapshot.*
- **D-F2-9** — cache budgets: *as proposed in the spec.*
- **D-F2-10** — thumbnails with Pillow (optional unit F2-l): *yes.*
- **D-F2-11** — `sets` nav entry: *stays legacy until F10.*
- **D-F2-12** — enum names in Spanish: *Signature, Token, Showcase kept in English; card text not translated.*
- **D-F2-13** — catalog defaults: *grid, 48 per page, sort by number.*
- **D-F2-14** — topbar search: *from 1240 px.*

## F3 Collection

- **D-F3-1** — how legacy `rbcol_playset` maps to `sell_qty`.
- **D-F3-2** — import sample files (riftdecks, piltoverarchive, Cardmarket, others) and RBAPP CSV columns: *the owner provides samples.*
- **D-F3-3** — import previews: *stored in a DB table.*
- **D-F3-4** — language list.
- **D-F3-5** — merge identical lines on add: *yes.*
- **D-F3-6** — `rbcol_user` stays a username: *yes (new tables use `rbusers.id`).*
- **D-F3-7** — wishlist vs F4 watchlist: *separate concepts.*
- **D-F3-8** — undo window and bulk limits.

## F4 Prices + Dashboard

- **D-F4-1** — daily load time: *06:30 Europe/Madrid.* · **D-F4-2** — auto-match after each load: *yes.*
- **D-F4-3** — movers noise floor. · **D-F4-4** — snapshots only for users with a collection: *yes.*
- **D-F4-5** — snapshot value uses the PRC-1 market price: *yes.* · **D-F4-6** — `pywebpush` + `importScripts`: *yes.*
- **D-F4-7** — price alerts on by default: *yes.* · **D-F4-8** — watchlist rule types. · **D-F4-9** — keep the Jinja dashboard until F11: *yes.*

## F5 Decks v2

- **D-F5-1** — new head/version tables: *yes.* · **D-F5-2** — Jinja deck pages read-only after migration: *yes.*
- **D-F5-3** — when a new version is created. · **D-F5-4** — what a public link shows.
- **D-F5-5** — import sample files (riftdecks, piltover): *the owner provides them.*
- **D-F5-6** — official opening hand and mulligan rules: *the owner must give the values.*
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

## F8 Events

- **D-F8-1** — real event source and its terms: *blocking for F8-d; no real source exists today (landing feeds are placeholders).*
- **D-F8-2** — event types (prototype's six + mapping). · **D-F8-3** — reminders 24 h and 2 h before.
- **D-F8-4** — "deck played" links deck identity or a version. · **D-F8-5** — public events visible to signed-in users only.
- **D-F8-6** — "near me" = country filter now, profile country after F9. · **D-F8-7** — drop the tournament-winner column.
- **D-F8-8** — subscribable ICS feed with a revocable token. · **D-F8-9** — past manual events in History.
- **D-F8-10** — scraped event missing in 2 runs → cancelled, never deleted. · **D-F8-11** — 10 public events per user per day.
- **D-F8-12** — offline cache for events (outside product.md).

## F9 Account

- **D-F9-1** — e-mail optional, unverified. · **D-F9-2** — account deletion with 10-day grace.
- **D-F9-3** — no public profile; drop social links. · **D-F9-4** — TOTP secrets encrypted at rest.
- **D-F9-5** — OAuth can create accounts; never auto-link by e-mail. · **D-F9-6** — 2FA also after OAuth sign-in.
- **D-F9-7** — username not editable. · **D-F9-8** — API key read-only.
- **D-F9-9** — non-remembered sessions expire after 12 h idle. · **D-F9-10** — new deps: Pillow, pyotp, segno, cryptography, Authlib.
- **D-F9-11** — store only an IP prefix for sessions. · **D-F9-12** — avatars visible to signed-in users only.

## F10 Admin

- **D-F10-1** — `is_admin` stays CLI-only: *yes.* · **D-F10-2** — password reset = temporary password + forced change.
- **D-F10-3** — admin can reset a user's 2FA. · **D-F10-4** — long operations through `rbjobs` (F4 runner): *yes.*
- **D-F10-5** — only unused sets/cards deletable. · **D-F10-6** — legacy price CSV generator: port or drop.
- **D-F10-7** — drop `rbcar_banned` in F11-f. · **D-F10-8** — audit retention 1 year.
- **D-F10-9** — admin on mobile: read + key actions. · **D-F10-10** — where the users' `sets` page goes: *F2 catalog.*
- **D-F10-11** — admin design built from tokens.

## F11 Close

- **D-F11-1** — landing as a second Vite entry. · **D-F11-2** — landing shows real feeds only.
- **D-F11-3** — permanent 301 redirects from Jinja URLs. · **D-F11-4** — Playwright E2E in CI.
- **D-F11-5** — Lighthouse manual with thresholds. · **D-F11-6** — Riot disclaimer: English verbatim + Spanish.
- **D-F11-7** — replace the 5.3 MB landing frame animation. · **D-F11-8** — delete legacy JSON endpoints.
- **D-F11-9** — drop obsolete columns (optional unit). · **D-F11-10** — landing ES + EN. · **D-F11-11** — landing design from tokens.

## F12 Production

- **D-F12-1** — final URL keeps `/riftbound`. · **D-F12-2** — one VPS for Nginx, app and DB.
- **D-F12-3** — in-memory rate limits + Nginx zones. · **D-F12-4** — encrypted daily backups 7/4/6 + off-site copy.
- **D-F12-5** — external uptime/heartbeat checks, alerts to a Discord webhook. · **D-F12-6** — fresh catalog; carry curated mappings and optionally the owner's data.
- **D-F12-7** — privacy/terms drafted by the planner, approved by the owner. · **D-F12-8** — card images in a data dir outside the code tree.
- **D-F12-9** — separate production OAuth apps. · **D-F12-10** — new VAPID keys. · **D-F12-11** — frontend built in CI as a release artifact.
- **D-F12-12** — log retention 14 d (Nginx) / 30 d (journald). · **D-F12-13** — separate DB roles for migrations and runtime.
- **D-F12-14** — no CSP report endpoint. · **D-F12-15** — dev serves as staging. · **D-F12-16** — the owner runs host-level steps.
- **D-F12-17** — Gunicorn workers 2×CPU+1, capped by RAM.
