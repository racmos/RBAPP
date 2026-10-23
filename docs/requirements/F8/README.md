# F8: Events — phase spec

Status: planned · Depends on: F4 (scheduler, Web Push, notification preferences), F5 (decks v2 ids for "deck played"); optional F9 (profile country for "near me") · Order (`docs/knowledge/roadmap.md`): after production (F12), after F15 (Rules app) and F5-k; the new landing (F11-a/F11-b) is built with it · Source: roadmap §5 (F8), design-handoff §3.1 (EventDTO), §3.8, §3.12, §5.6, §6-18/19/29, §7.2-V4, §7.3-D3, §7.6-L8, §9 F8, §10-5, product.md "Scope by phase"

## Goal

Users find Riftbound events, save the ones they will attend, add them to their calendar (ICS file, a
subscribable feed, Google Calendar link) and get push reminders. They can create their own events (private,
or public for every user) and record their result and the deck they played, which gives them per-deck
performance stats. Events imported by the scraper are always public.

## Current state

- **No events model.** Nothing in `app/models/` stores events, saves or results.
- **Landing feeds** (`app/services/scraper.py`, `app/routes/landing.py`, spec `openspec/specs/landing-feeds`
  LAND-1): `fetch_torneos_online()` returns **placeholder data only** (random slots and prices);
  `fetch_torneos_fisicos()` scrapes a store-locator page with generic CSS selectors, keeps only title and
  location (date `"TBD"`) and falls back to placeholders. Items are `TournamentItem(title, date, slots,
  price, location, url)` rendered as HTMX partials at `/api/torneos-*`, cached per worker (TTL 300 s).
  Nothing here is fit to import as real events: placeholders must never reach the database.
- **Decks**: `rbdecks` has `id`, `rbdck_user` (username), `rbdck_name`, `rbdck_seq` (versions as rows),
  `rbdck_mode`. F5 changes the format and adds private/public; F8 links to F5's ids.
- **Push / scheduler**: none yet; F4 adds the scheduled-job mechanism (CLI + systemd timer, documented in
  `docs/knowledge/ops-runbook.md` → "Scheduled jobs"), VAPID keys, push subscriptions, SW push handler and
  notification preferences.
- **Profile**: `rbusers` has no country/city (F9 adds them).
- **Frontend**: nav entry `events` is `planned` (icon `calendar`, placements `top`, `hub`). `lib/format.ts`
  formats dates with `es-ES`/`en-GB`.

## Scope

In:
- Events data (manual + scraped), saves ("my calendar"), results + deck played, per-deck stats.
- Manual events CRUD with visibility `private` / `public`; owner-only edits; `hidden` flag for admin moderation
  (the admin UI is F10).
- Scraper import job (`flask events import`) run by the F4 scheduler; first source: the upcoming-events
  calendar of the official site, behind an adapter; past events only when a source exists.
- ICS: one event, all saved events, subscribable feed with a revocable token; Google Calendar link.
- Push reminders for saved events (job + preference), reusing F4.
- Events UI: Upcoming, History, My calendar, add/edit dialog, result dialog, month view on desktop.

Out:
- Registration/payment for events, attendee lists, chat. Geolocation by distance (country/city only).
- Admin moderation screens (F10). The new public landing that shows events is F11-a/F11-b, built with the
  events work right after F8.
- Importing tournament standings/winners unless the chosen source provides them (D-F8-7).

## Decisions already taken

- Manual events: creator chooses private or public; scraper events are always public (product.md F8).
- Saved events, result + deck played, ICS, Google Calendar, push reminders (product.md F8, roadmap F8).
- Formats only `1v1` / `2v2` (product.md "Game modes"; design-handoff §0.2 "Formatos evento").
- ICS must fix the prototype bugs: `DTSTAMP`, UTC/`TZID`, escaping, 75-octet folding, real end time
  (design-handoff §5.6, §7.6-L8). Durations: 3 h skirmish/nexus/store/online, 8 h regional/national
  (design-handoff §0.2) as defaults, editable.
- Edits need a connection; offline is read-only (product.md "Offline").
- Push on iOS only with the PWA on the home screen, iOS 16.4+ (product.md "Platform notes").
- Scheduled work = Flask CLI + systemd timer, no Celery/Redis (cross-phase contract, F4).
- **D-F8-1** (owner, 2026-10-22): events come after production and after the Rules app (F15). F8 starts with
  an upcoming-events calendar scraped from the official site; past events are added when a source exists.
- Landing (owner, 2026-10-22): the current landing is a draft with placeholder content; it is rebuilt with
  the events work (F11-a/F11-b move next to F8).
- Job runner (owner, 2026-10-22): F8's import and reminder jobs register job kinds on the F4-a runner
  (`rbjobs` + `flask jobs run-pending`); F8 builds no runner of its own.
- Tests (owner, 2026-10-22, unit M-a): each F8 unit writes its own tests and re-creates the removed guard of
  the area it touches (migration round-trip + drift test, error-code catalog test, ES/EN parity).

## Requirements

### Data and visibility
- **F8-R1** An event has `source` (`manual`/`scraped`), `visibility` (`private`/`public`), owner (manual only),
  name, type, format, start/end (UTC) + IANA time zone, online flag, country (ISO 3166-1 alpha-2, NULL when
  online), city, venue, organizer, capacity, registered, fee (EUR), prize, URL (https only), status
  (`scheduled`/`cancelled`), `hidden` (moderation) and timestamps. CHECK: `scraped` ⇒ `public` and no owner.
- **F8-R2** A user sees: public events that are not hidden + their own events (hidden ones with a
  "Oculto por moderación" badge). Another user's private event → 404.
- **F8-R3** Only the owner edits or deletes a manual event; scraped events are read-only for everyone →
  409 `event_read_only`. Deleting asks for confirmation (design-handoff §7.3-D3) and removes saves/results of
  that event for all users (CASCADE) — the dialog says how many users saved it when public.
- **F8-R4** Validation (design-handoff §7.2-V4): name 3..120, start required and not more than 1 day in the
  past on create, end > start (default by type), capacity 1..10000, registered 0..capacity, fee 0..9999.99,
  URL https ≤ 500, city required unless online, text fields without HTML. Field errors use the existing
  `details[].code` (`required`, `too_long`, `out_of_range`, `invalid_format`).
- **F8-R5** Creating **public** events is rate-limited per user (10 per day, D-F8-11) → 429 `rate_limited`.

### Saves, results, stats
- **F8-R6** Save/unsave is idempotent (`PUT`/`DELETE`), per user, for any event the user can see.
- **F8-R7** One result per user per event: placement (≥ 1), players (≥ 2, ≥ placement), wins/losses/draws
  (0..50), deck id (an F5 deck **owned by the caller**, else 404), notes ≤ 500. Allowed only once the event
  has started (409 `event_not_started`). Deleting the deck keeps the result with the deck name snapshot.
- **F8-R8** `GET /events/stats` returns per deck: events, avg placement, best placement, W/L/D, win rate;
  per event type: events, avg placement; over `from`/`to`.

### Calendar
- **F8-R9** ICS output (own writer in `app/services/ics.py`, RFC 5545): `VERSION:2.0`,
  `PRODID:-//Rift Manager//Events//EN`, `CALSCALE:GREGORIAN`, per event `UID:evt-<id>@rift-manager`,
  `DTSTAMP` (UTC), `DTSTART`/`DTEND` in UTC (`…Z`), `SUMMARY`, `LOCATION`, `DESCRIPTION` (type, format,
  prize, organizer, link), `URL` when present, `STATUS:CANCELLED` when cancelled; escaping of `\ ; , \n`
  in every text field; CRLF; lines folded at 75 octets (UTF-8 safe). Unit tests cover each rule.
- **F8-R10** `GET /events/{id}.ics` (one event), `GET /me/calendar.ics` (all saved, future + last 30 days),
  and `GET /calendar/feed/<token>.ics` (same content, no session, token-authorised, `Cache-Control:
  private, max-age=900`). Token: 32 random bytes urlsafe, stored as sha256, one per user, rotate/revoke
  endpoints; an unknown token → 404.
- **F8-R11** Google Calendar link built client-side (pure, tested): template URL from design-handoff §5.6
  with UTC dates, `ctz` = event time zone, details incl. the event URL; opened with
  `target=_blank rel="noopener noreferrer"`.

### Scraper import
- **F8-R12** `flask events import [--source <key>] [--dry-run]` imports from adapters implementing
  `EventSource.fetch() -> list[ScrapedEvent]`; upsert by (`source_key`, `external_id`); never imports
  placeholder items (the landing placeholders are a different code path and stay untouched).
- **F8-R13** A future scraped event missing from 2 consecutive successful runs is marked `cancelled`, never
  deleted (saves/results reference it). A failed run changes nothing and exits non-zero (systemd shows it).
- **F8-R14** Adapter tests use recorded fixtures only (no network in tests, AGENTS.md); request timeout 10 s,
  identifying User-Agent, at most one run per hour; the runbook documents the timer (daily by default).

### Reminders (push)
- **F8-R15** `flask events send-reminders` (timer every 15 min) sends one push per saved event and offset
  (24 h and 2 h before start, D-F8-3) to users whose notification preference "Eventos guardados" is on;
  idempotent through per-save sent markers; cancelled or hidden events send nothing.
- **F8-R16** Push payload: title = event name, body = relative start ("Empieza mañana a las 18:00" / "Starts
  tomorrow at 18:00") in the user's language, `url` = `/riftbound/app/events/<id>`; the SW handler from F4
  opens that URL.

### API, authz, i18n, a11y, offline
- **F8-R17** Every new URL rule classified in `tests/test_authz_matrix.py` (`U` except the feed: `P`,
  token-authorised); `@validate_json` on bodies; envelope + error codes.
- **F8-R18** Dates and relative chips ("Hoy", "Mañana", "en N días", "en 2 semanas") computed in the user's
  time zone with ICU plurals (design-handoff §5.6); `<html lang>` locale for formats.
- **F8-R19** Tabs are URLs; bookmark/save buttons have `aria-pressed`; type chips have text, not only
  colour (contrast fix for `nacional`/`nexus`, design-handoff §7.4-A10); month grid is a table with
  `aria-label` per day cell.
- **F8-R20** Offline: event lists SHOULD be readable from the F2 offline API cache (strategy D-F2-7; purged
  on logout, F2-R24) if D-F8-12 says so; create/edit/save/result disabled offline with the reason.
- **F8-R21** List endpoints: bounded queries (no N+1 for `saved`/`my_result` flags), indexes on start time.

## Data model changes

Revisions (next free numbers): `00xx_events` (F8-a), `00xx_event_results` (F8-e), `00xx_event_reminders`
(F8-h). All reversible; no backfill. Risk: item 1.

| Table | Columns (prefix) | Notes |
|---|---|---|
| `rbevents` (`rbevt_`) | `id` BIGINT PK; `source` VARCHAR(8) CHECK; `source_key` VARCHAR(32) NULL; `external_id` VARCHAR(120) NULL; `owner_id` INT NULL FK `rbusers.id` ON DELETE CASCADE; `visibility` VARCHAR(8) CHECK; `name` VARCHAR(120); `type` VARCHAR(16) CHECK (D-F8-2); `format` VARCHAR(4) NULL CHECK IN ('1v1','2v2'); `starts_at`, `ends_at` TIMESTAMP (UTC, naive like the rest of the app); `tz` VARCHAR(64); `online` BOOL; `country` CHAR(2) NULL; `city`, `venue`, `organizer` VARCHAR(120) NULL; `capacity`, `registered` INT NULL; `fee_eur` NUMERIC(8,2) NULL; `prize` VARCHAR(200) NULL; `url` VARCHAR(500) NULL; `status` VARCHAR(10) CHECK; `hidden` BOOL DEFAULT false; `hidden_reason` VARCHAR(200) NULL; `missing_runs` SMALLINT DEFAULT 0; `created_at`, `updated_at`, `last_seen_at` | UNIQUE (`source_key`,`external_id`); CHECK scraped ⇒ public AND owner NULL; indexes (`starts_at`), (`owner_id`), (`visibility`,`hidden`,`starts_at`) |
| `rbeventsaves` (`rbevs_`) | `user_id` FK CASCADE, `event_id` FK CASCADE, `saved_at`, `remind` BOOL DEFAULT true | PK (`user_id`,`event_id`) |
| `rbeventresults` (`rbevr_`) | `id` PK; `user_id` FK CASCADE; `event_id` FK CASCADE; `placement`, `players`, `wins`, `losses`, `draws` SMALLINT NULL; `deck_id` INT NULL FK `rbdecks.id` ON DELETE SET NULL (D-F8-4); `deck_name` VARCHAR(200) NULL snapshot; `notes` VARCHAR(500); timestamps | UNIQUE (`user_id`,`event_id`) |
| `rbcalfeeds` (`rbcfd_`) | `user_id` PK FK CASCADE; `token_hash` CHAR(64) UNIQUE; `created_at` | one feed per user |
| `rbeventsaves` + (F8-h) | `reminded_24h_at`, `reminded_2h_at` TIMESTAMP NULL | unless F4 ships a generic notification log (then use it) |

## API

Base `/riftbound/api/v1`.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/events` | U | `scope=upcoming\|past`, `type[]`, `format`, `country`, `online`, `from`, `to`, `min_players`, `mine`, `saved`, `source`, `page`, `per_page`; items = EventDTO (design-handoff §3.1) + `saved`, `my_result`, `is_owner`, `hidden`. |
| GET | `/events/{id}` | U | Detail (visibility rules F8-R2). |
| POST | `/events` | U | Create manual event (F8-R4/R5). 201. |
| PATCH | `/events/{id}` | U | Owner only; scraped → 409 `event_read_only`. |
| DELETE | `/events/{id}` | U | Owner only. |
| PUT / DELETE | `/events/{id}/save` | U | Save / unsave; body `{remind?}` on PUT. |
| GET | `/events/{id}.ics` | U | One-event ICS. |
| GET | `/me/calendar.ics` | U | Saved events ICS. |
| GET / POST / DELETE | `/me/calendar/feed` | U | Feed metadata / create-or-rotate (returns the URL once) / revoke. |
| GET | `/calendar/feed/<token>.ics` | P (token) | Subscribable feed. |
| PUT / DELETE | `/events/{id}/result` | U | Upsert / delete my result (F8-R7). |
| GET | `/events/stats` | U | Per deck / per type (F8-R8). |

New error codes: `event_read_only` (409), `event_not_started` (409). Meta: event types and countries served
by F2's `GET /meta/game` (additive keys `event_types`, `countries`; i18n `enums.event_type`, `enums.country`). CLI: `flask events import`,
`flask events send-reminders`.

## UI

Route `/riftbound/app/events` with tabs as URLs: `/events/upcoming` (default), `/events/history`,
`/events/calendar`; detail `/events/:id` (sheet on mobile, side panel on desktop, deep-linkable for push).

| Breakpoint | Layout |
|---|---|
| Mobile < 860 | Header + 3 stats (Próximos, Este mes, En mi calendario) in 2 cols. Tabs full width. Filters in a `Sheet` (type chips, format segmented, country select, "Solo guardados", "Solo míos"). One-column `EventCard` list (badges type/format/country/"Mío"/"Público·Privado", name, long date + relative chip, time + organizer, venue·city or Online, prize, capacity bar, fee/"Gratis", buttons Guardar (`aria-pressed`), Google Calendar, ICS). History = cards with "Mi resultado" and deck. My calendar = grouped by month + "Ya celebrados", feed card ("Suscribirse al calendario"). FAB-less: "Añadir evento" button in the header. |
| Desktop ≥ 1240 | Sticky filter panel left (≈ 280 px) + 2-column card grid; toggle List / Month (month grid with event dots, click → detail panel). History as table (date, event, type, format, country, players, my placement, record, deck, actions) + KPI band (events played, avg placement, best, win rate). |
| Wide ≥ 1600 | Three columns: filters / grid or month / right rail with "Mi próximo evento", upcoming reminders and per-deck performance (top 5 decks). |

Dialogs: add/edit event (`Modal`; fields of design-handoff §3.8 plus end time, time zone (default browser
zone), URL, visibility switch "Público para todos los usuarios" with explanation); result dialog (placement,
players, W/L/D steppers, deck `Select` of my F5 decks, notes); delete `ConfirmDialog`; feed dialog (URL with
`CopyButton`, "Regenerar" with warning that the old URL stops working). Empty states: "No hay eventos con
estos filtros", illustrated "Tu calendario está vacío" + CTA (design-handoff §3.8). Notification preference
toggle "Recordatorios de eventos guardados" lives in the F4 notification settings card.

i18n namespace `events` (≈ 120 keys) + `enums.event_type.*`, `enums.event_visibility.*`. Components:
`EventCard`, `EventFilters`, `EventTypeChip`, `MonthGrid`, `EventDetail`, `EventFormDialog`,
`ResultDialog`, `CalendarFeedCard`, `RelativeDayChip`, utils `gcalUrl()`, `relativeDay()`.

## Units

| ID | Title | Depends on | Size | Risk | Summary |
|---|---|---|---|---|---|
| F8-a | Events model + read API | F2-b (`/meta/game`) | ~450 | Risk: item 1 (new tables, CHECKs) | Migration `rbevents` + `rbeventsaves`, visibility rules, `GET /events`, `GET /events/{id}`, enums in meta, authz rows. |
| F8-b | Manual events + saves | F8-a | ~450 | Risk: item 2 (ownership and visibility checks) | `POST/PATCH/DELETE /events`, validation, per-user rate limit for public events, save/unsave, error code `event_read_only`. |
| F8-c | ICS + feed | F8-b | ~400 | Risk: item 2 (token-authorised public URL) | `services/ics.py`, `/events/{id}.ics`, `/me/calendar.ics`, feed table + token rotate/revoke + public feed route. |
| F8-d | Scraper import job | F8-a, F4 scheduler | ~450 | Risk: item 6 (live source format only testable with fixtures) | `EventSource` adapter for the official site's upcoming-events calendar, `flask events import`, missing-run cancellation, systemd unit/timer doc in the runbook. |
| F8-e | Results + stats API | F8-a, F5 decks | ~400 | Risk: item 3 (consumes F5 deck ids/ownership) | Migration `rbeventresults`, `PUT/DELETE /events/{id}/result`, `GET /events/stats`, `event_not_started`. |
| F8-f | Events UI: upcoming + forms | F8-b, F8-c | ~600 | Risk: none | Route + tabs, filters (sheet/panel), `EventCard`, save, GCal/ICS buttons, add/edit/delete dialogs, nav flip `events` → `spa`. |
| F8-g | Events UI: calendar, history, results | F8-e, F8-f | ~600 | Risk: none | My calendar (+ feed card), history list/table, result dialog, KPIs, month view, wide rail. |
| F8-h | Push reminders | F8-b, F4 push | ~350 | Risk: item 3 + item 4 (F4 push contract; duplicate sends from overlapping timer runs) | Sent markers, `flask events send-reminders` with a run lock, preference category, payload + SW deep link, runbook timer. |

## Open decisions

| ID | Question | Options | Recommendation | Blocks |
|---|---|---|---|---|
| D-F8-2 | Event types (design-handoff §10-5) | prototype 6 (`regional, national, skirmish, nexus, store, online`) / source categories | Prototype 6 with a mapping table from the source; unknown → `store` or `online` | F8-a |
| D-F8-3 | Reminder offsets and default | 24 h + 2 h, on by default for saved events / opt-in | 24 h + 2 h, on when the user enabled push | F8-h |
| D-F8-4 | "Deck played" target | F5 deck identity / a specific version | The id F5 exposes as stable deck id; snapshot the deck name (and version number if F5 keeps versions) | F8-e |
| D-F8-5 | Who sees public manual events, and the organizer label | all signed-in users + username / also anonymous landing | All signed-in users; creator's username (display name after F9) | F8-a |
| D-F8-6 | "Cerca de mí" | country filter only / profile country (F9) / browser geolocation | Country filter now; "near me" uses the profile country once F9 adds it (no geolocation) | F8-f |
| D-F8-7 | Tournament winner/standings column | drop / only if the source provides it | Drop unless the source provides it | F8-d, F8-g |
| D-F8-8 | Subscribable ICS feed with a token in the URL | yes / no | Yes, revocable; note tokens appear in proxy access logs (F12 log policy) | F8-c |
| D-F8-9 | Past manual events in History (the prototype hid them) | include / hide | Include | F8-g |
| D-F8-10 | Scraped events missing from the source | cancel after 2 runs / keep | Cancel after 2 consecutive successful runs (F8-R13) | F8-d |
| D-F8-11 | Public event creation limit | 10/day / none | 10 per user per day | F8-b |
| D-F8-12 | Offline reads for events | none / cached like the catalog | Cache `GET /events` with the F2 strategy (saved and upcoming help at the venue); product.md lists only catalog/collection/decks, so owner confirms | F8-f |

## Risks and notes

- **Placeholders**: the landing scraper invents tournaments. F8 must not reuse those functions for import;
  the new landing (F11-a/F11-b, built with F8) decides how it shows real `rbevents` (cross-phase).
- **Source terms**: F8-d checks the official site's terms and robots rules before the first live run; if they
  forbid scraping, F8 ships with manual events only and F8-d stays pending.
- **Time zones**: store UTC + IANA zone; `zoneinfo` needs the system tz database on the server (present on
  Linux; Windows dev would need `tzdata`). DST edge cases need tests (an event at 02:30 local on a DST day).
- **Push dependency**: if F4 slips, F8-a..g ship without reminders; F8-h waits.
- **Profile dependency**: F9 now lands before production, so before F8; "near me" can use the profile
  country from the start (D-F8-6).
- **Moderation**: F8 adds `hidden`; F10 adds the admin endpoints/UI. Until F10, the owner hides an event
  with SQL only in an emergency — add a tiny CLI `flask events hide <id> [--reason]` in F8-b if the owner
  wants it before F10 (cheap).
- **Feed tokens in logs**: Nginx access logs contain the feed path; F12 sets retention and access rules.
