# F10: Admin — phase spec

Status: planned · Depends on: F2 (ban table + read API + `flask bans`), F4 (scheduler, daily Cardmarket load), F8 (`hidden` events), **F9** (session revocation, 2FA reset) · Source: roadmap §5 (F10), §4, design-handoff §3.12, §6-2/36, §9 F10, §10-13, product.md "Users, accounts and security", "Scope by phase"

## Goal

The owner runs every admin task from a desktop-first React panel: sets and card editing, Riot gallery sync,
Cardmarket loads and product mappings, ignored products, users (block, unlock, reset password, reset 2FA,
end sessions), bans per mode and moderation of public events. Every admin write is audited. The Jinja admin
page stops being the place to work (it is deleted in F11).

## Current state

- **Admin Jinja page** `GET /riftbound/price` (`app/routes/domains/price.py`, template `price.html`, ~2,000
  lines) behind `price_bp.before_request(require_admin)` (ACL-3). Sections: price CSV generation
  (`POST /generate`, lines `set;name;id;N`), Riot gallery (`POST /refresh-riot-sets`,
  `POST /extract-riot-cards` → `app/services/riot_scraper.py`, writes `rbset`/`rbcards` and images under
  `app/static/images/cards/<folder>/`), Cardmarket load (`POST /cardmarket-load` with allow-listed URL
  overrides, ACL-7 → `CardmarketLoader.run`, history in `rbcm_load_history`), unmatched products
  (`GET /cardmarket-unmatched`), manual map/unmap (`/cardmarket-map`, `/cardmarket-unmap`), mappings browser
  (`GET /cardmarket-mappings`), conflicts, auto-match (`POST /cardmarket-auto-match`, selective
  `POST /auto-match/apply` → `app/services/cardmarket_matcher.py`), unmapped expansions
  (`GET /cardmarket-unmapped-expansions`, `POST /cardmarket-map-expansion`, may create an `rbset`), ignored
  products (`/ignored`, `/ignored/add`, `/ignored/restore`), card/product upserts
  (`/cardmarket-upsert-card`, `/cardmarket-upsert-product`, searches and details).
- **Sets / cards**: `app/routes/domains/sets.py` (`/riftbound/set` page `U`; `/add`, `/update/<id>` `A`),
  `app/routes/domains/cards.py` (`/riftbound/card` page `U`; `/add`, `/update/<set>/<id>`,
  `/upload_image` `A`, path safety in `app/services/card_images.py`, IMG-2). Bans: F2-a adds table
  `rbcardbans` (one row per normalized name `rbban_name_key` + mode, `since`, `reason`), `app/services/bans.py`,
  `flask bans list|add|remove` and `GET /bans`; with D-F2-2 (a) the Jinja card form stops editing
  `rbcar_banned`.
- **Response quality**: legacy endpoints answer `{success, ...}` without the v1 envelope, and several 500
  handlers return `str(e)` (`refresh_riot_sets`, `extract_riot_cards`, `cardmarket_load`,
  `upload_card_image`) — against the AGENTS.md rule "500 responses never include exception text".
- **Long requests**: the Cardmarket load and the Riot extraction run inside the HTTP request; Gunicorn runs
  with its default 30 s timeout (`docs/riftbound.service` has no `--timeout`).
- **Users**: only the CLI (`flask users list|promote|demote|block|unblock|unlock|set-password`,
  ACL-6, LOGIN-6). No audit trail of admin actions.
- **Frontend**: `requireAdmin` loader exists (`frontend/src/auth/guards.ts`); nav entries `price` (top, hub)
  and `admin` (more) are `legacy` → `/riftbound/price`, `adminOnly: true`.
- **Tests**: `tests/test_cardmarket*.py`, `test_access_control.py`, `test_authz_matrix.py`, `test_admin_cli.py`.

## Scope

In:
- Admin API under `/riftbound/api/v1/admin/` (v1 envelope, error codes, no exception text) porting every
  `price_bp`, `sets_bp` and `cards_bp` admin operation, plus users, bans, events moderation, jobs, audit.
- Background jobs for long operations (D-F10-4) using the F4 scheduler mechanism.
- React admin at `/riftbound/app/admin/*`, desktop-first, with defined mobile/desktop/wide layouts.
- Audit log of admin writes.
- Nav flip of `price`/`admin` to the new panel; the Jinja admin page shows a banner pointing to it.

Out:
- Changing `is_admin` from the UI (D-F10-1). Deleting user accounts (users delete their own, F9).
- Removing Jinja templates and legacy JSON routes (F11). Changes to matcher/loader algorithms (port only).
- User reports of events (no reporting flow in F10).

## Decisions already taken

- Only the owner is admin; open registration; the admin can block accounts (product.md, roadmap §4).
- Admin resets passwords because there is no e-mail recovery (product.md).
- Bans are per mode (1v1/2v2) and per card name; F2 owns the table, read API and CLI; F10 adds the admin UI
  (product.md "Game rules"; cross-phase contract).
- Admin is desktop-first, React, `requireAdmin` (frontend) + `admin_required`/`require_admin` (backend)
  (product.md F10; cross-phase contract). Admin screens have no prototype design: build from the tokens and
  review in each PR (design-handoff §3.12, §10-13).
- Cardmarket override URLs keep the allow-list (ACL-7). Scheduled work = CLI + systemd timer (F4).

## Requirements

### Security and authz
- **F10-R1** All admin endpoints live on a blueprint under `/riftbound/api/v1/admin/` with
  `before_request(require_admin)`: anonymous → 401 JSON, non-admin → 403 JSON; API keys never authenticate
  there (F9-R24). Every rule is `A` in `tests/test_authz_matrix.py`; the frontend routes use `requireAdmin`.
- **F10-R2** Every admin write inserts an `rbadminaudit` row (actor, action, target, small JSON summary,
  time) in the same transaction. Secrets (temporary passwords, keys) are never written to the audit or logs.
- **F10-R3** `is_admin` is not writable through any endpoint (test: a PATCH/POST with `is_admin` changes
  nothing). Actions on the caller's own account or on another admin (block, reset password, reset 2FA,
  revoke sessions) → 409 `self_action_forbidden`.
- **F10-R4** Error responses never include exception text; job failures store a sanitised message (first
  line, ≤ 300 chars, no paths or URLs with credentials) and log the full trace server-side.

### Users
- **F10-R5** `GET /admin/users`: search (username/e-mail substring), filters (admin, blocked, locked,
  2FA, OAuth, created range), sort, pagination; row = id, username, e-mail, created, last login, flags,
  collection lines, decks, active sessions.
- **F10-R6** Actions: block / unblock (block revokes all sessions, F9-R4), unlock (clears lockout,
  LOGIN-6 semantics), revoke sessions, reset 2FA (removes secret and recovery codes, revokes sessions),
  reset password (D-F10-2): server generates a 16-char temporary password, returns it once, sets
  `must_change_password`, clears the lockout and revokes sessions.
- **F10-R7** A user with `must_change_password` can sign in but every API call except `GET /auth/session`,
  `POST /me/password`, `POST /auth/logout` answers 403 `password_change_required`; the SPA routes to a
  forced change screen; the flag clears on success. The Jinja pages redirect to that screen.

### Catalog
- **F10-R8** Sets: list (cards count, mapped expansions), create, update (`rbset_name`, `rbset_ncard`,
  `rbset_outdat`); delete only when no card references it (409 `set_in_use`).
- **F10-R9** Cards: list with filters (set, type, rarity, domain, missing image, missing Cardmarket mapping,
  text), create, update every catalog field **except** `rbcar_banned` (bans are per mode), image upload
  through `card_image_path` (IMG-2, ≤ 2 MB, jpg/png/webp), delete only when no collection line or deck uses
  it (409 `card_in_use`; `rbcollection` would cascade otherwise). Duplicate keys → 409 `already_exists`.
- **F10-R10** Riot sync: refresh the set list and extract cards for selected sets as jobs (F10-R13); the
  result summary (steps, created/updated cards, images) is shown per job.

### Cardmarket
- **F10-R11** Load now (job) with optional overrides validated by the ACL-7 allow-list before queueing;
  load history from `rbcm_load_history` (date, file type, rows, status, message, loaded at).
- **F10-R12** Port, behaviour-preserving (characterization tests first on the legacy endpoints): unmatched
  products, manual map with foil (`N`/`S`/null), unmap, mappings browser with filters, conflict resolution,
  auto-match dry run + selective apply, ignored add/restore/list, unmapped expansions + map (optionally
  creating the set), product upsert/search (`rbproducts`), card upsert. The legacy price CSV generator is
  ported only if the owner still uses it (D-F10-6).

### Jobs (D-F10-4)
- **F10-R13** Long operations (Cardmarket load, Riot set refresh, Riot extraction, auto-match apply over
  N groups) are queued as `rbjobs` rows and executed by `flask jobs run-pending` (F4 timer, every minute,
  with a run lock). At most one queued/running job per kind (409 `job_running`). `GET /admin/jobs/{id}` for
  polling; the UI polls every 3 s while a job runs. The F4 daily load uses the same code path.

### Bans and moderation
- **F10-R14** Bans (on F2's `rbcardbans`, through `app/services/bans.py` and its `name_key`): list per mode
  with card name, since, reason; add by card name for `1v1`, `2v2` or both (one row per mode, same
  validation as `flask bans add`); remove; audit (the table has no end date, so history lives in the audit). Consumers (catalog, legality) see the change
  on their next request; the UI warns that offline caches update within the SWR window.
- **F10-R15** Events: list public events (manual and scraped; filters upcoming/past, hidden, owner, source),
  hide with reason / unhide (F8 `hidden`, `hidden_reason`), delete a manual event with confirmation (shows
  how many users saved it); audit.

### Overview
- **F10-R16** `GET /admin/overview`: users (total, new 7 d, blocked, locked, with 2FA), last Cardmarket load
  (date, status), unmatched products, unmapped expansions, cards without image or mapping, running/failed
  jobs, public events hidden/pending review, last runs of scheduled jobs if F4 records them.

### UI, i18n, a11y, performance
- **F10-R17** Desktop-first but every screen defines mobile (read + key actions), desktop and wide layouts.
- **F10-R18** Namespace `admin` (ES/EN parity, even though only the owner uses it); confirmations with
  `ConfirmDialog` stating the effect ("Se cerrarán 3 sesiones").
- **F10-R19** Tables: `<caption>`, `scope`, `aria-sort`, keyboard row actions, sticky header under the
  topbar; long lists paginated server-side (50/100/200).
- **F10-R20** List endpoints use bounded queries (query-count tests); mapping lists ≤ 1 s on the dev data set.

## Data model changes

| Revision (unit) | Change | Risk |
|---|---|---|
| `00xx_admin_audit` (F10-a) | `rbadminaudit` (`rbaud_`): `id` BIGINT PK; `actor_id` INT NULL FK `rbusers.id` ON DELETE SET NULL; `actor_username` VARCHAR(64); `action` VARCHAR(48); `target_type` VARCHAR(24); `target_id` VARCHAR(64); `details` JSON (JSONB on PostgreSQL); `created_at`. Indexes (`created_at` DESC), (`target_type`,`target_id`). | item 1 |
| `00xx_must_change_password` (F10-b) | `rbusers.must_change_password` BOOLEAN NOT NULL DEFAULT false (server default, existing rows false). | item 1 + 2 |
| `rbjobs` — created by F4-a (job runner); F10-d only adds job kinds | `rbjobs` (`rbjob_`): `id` BIGINT PK; `kind` VARCHAR(32) CHECK; `params` JSON; `status` VARCHAR(10) CHECK IN ('queued','running','success','error'); `requested_by` INT NULL FK SET NULL; `requested_at`, `started_at`, `finished_at`; `result` JSON; `message` VARCHAR(300). Partial unique index on `kind` WHERE status IN ('queued','running'). | item 1 + 4 |

All reversible; no backfill. Deploy: backup first. `rbcar_banned` is not dropped here (D-F10-7).

## API

Base `/riftbound/api/v1/admin` (all `A`).

| Method | Path | Purpose |
|---|---|---|
| GET | `/overview` | Counters (F10-R16). |
| GET | `/users` · `/users/{id}` | List / detail. |
| POST | `/users/{id}/block` · `/unblock` · `/unlock` · `/reset-password` · `/reset-2fa` | User actions (`reset-password` returns `{temp_password}` once). |
| DELETE | `/users/{id}/sessions` | Revoke all sessions of a user. |
| GET / POST | `/sets` | List / create. |
| PATCH / DELETE | `/sets/{id}` | Update / delete unused. |
| GET / POST | `/cards` | List with filters / create. |
| PATCH / DELETE | `/cards/{set}/{id}` | Update / delete unused. |
| POST | `/cards/{set}/{id}/image` | Upload image (multipart). |
| GET / POST | `/jobs` | List (kind, status) / queue `{kind, params}`. |
| GET | `/jobs/{id}` | Job status and result. |
| GET | `/cardmarket/loads` | Load history. |
| GET | `/cardmarket/unmatched` | Products without mapping. |
| GET / POST | `/cardmarket/mappings` | Browse / create-or-replace mapping. |
| DELETE | `/cardmarket/mappings/{id_product}` | Unmap. |
| POST | `/cardmarket/auto-match` · `/cardmarket/auto-match/apply` | Dry run / apply selected pairings (job when large). |
| GET / POST / DELETE | `/cardmarket/ignored` | List / ignore / restore. |
| GET / PATCH | `/cardmarket/expansions` · `/cardmarket/expansions/{id}` | Unmapped expansions / map to a set. |
| GET / PUT | `/cardmarket/products` · `/cardmarket/products/{set}/{id}` | Search / upsert `rbproducts`. |
| GET / POST / DELETE | `/bans` · `/bans/{id}` | Bans per mode (shape from F2). |
| GET | `/events` | Public events for moderation. |
| POST | `/events/{id}/hide` · `/events/{id}/unhide` | Moderation. |
| DELETE | `/events/{id}` | Delete a manual event. |
| GET | `/audit` | Audit log (filters actor, action, target, date). |

New error codes: `self_action_forbidden` (409), `password_change_required` (403), `job_running` (409),
`set_in_use` (409), `card_in_use` (409), `already_exists` (409, `params.field`) — coordinate names with the
codes F2-F9 add (one registry, `app/api/error_codes.py`). CLI: `flask jobs run-pending`.

## UI

Routes `/riftbound/app/admin/*` with an admin layout (own left navigation inside the app shell):
`/admin` (overview), `/admin/users`, `/admin/users/:id`, `/admin/sets`, `/admin/cards`,
`/admin/cardmarket/loads`, `/admin/cardmarket/mappings`, `/admin/cardmarket/expansions`,
`/admin/cardmarket/ignored`, `/admin/bans`, `/admin/events`, `/admin/audit`, `/admin/jobs/:id`. Forced
password change screen `/account/password-required` (outside the admin area).

| Breakpoint | Layout |
|---|---|
| Mobile < 860 | Admin nav as a `Select`/sheet at the top; lists as cards with the 2-3 key fields and an actions menu; user actions and event moderation fully usable; mapping and card editors show "Más cómodo en escritorio" but stay usable in one column. |
| Desktop ≥ 1240 | Left admin nav (220 px) + dense `DataTable` (40 px rows, column chooser where > 8 columns) + detail drawer on the right (420 px) for user detail, card editor, mapping editor; overview as KPI band + two lists (recent jobs, recent audit). |
| Wide ≥ 1600 | Three panes: nav / table / persistent detail panel (no drawer); mappings screen shows unmatched products, candidate cards with images and the current mapping side by side; overview adds a third column (bans and moderation queue). |

Components: `AdminLayout`, `AdminNav`, `JobStatus` (polling, progress steps), `UserTable`/`UserDetail`,
`TempPasswordDialog` (copy once, warning), `CardEditor` (form + image upload + Cardmarket mapping summary),
`MappingWorkbench`, `AutoMatchReview` (checkbox list of pairings with confidence), `BanEditor` (card
combobox from F2, mode checkboxes, reason), `ModerationTable`, `AuditTable`. States: skeletons, empty,
error with retry, offline (all actions disabled; admin is online-only). Nav: `price` and `admin` entries →
`spa` (`/admin`), still `adminOnly`.

## Units

| ID | Title | Depends on | Size | Risk | Summary |
|---|---|---|---|---|---|
| F10-a | Admin foundation | F1, F9-a | ~550 | Risk: item 2 + item 1 (new admin surface; audit table) | Admin blueprint + guard + sanitised errors, `rbadminaudit` + audit helper, `GET /admin/overview` (partial), React `AdminLayout` + overview, nav flip. |
| F10-b | Users admin API | F10-a, F9-a, F9-d | ~550 | Risk: item 2 + item 1 (account takeover surface; new column) | List/detail, block/unblock/unlock/revoke, reset 2FA, reset password + `must_change_password` enforcement. |
| F10-c | Users admin UI + forced change | F10-b | ~500 | Risk: none | Users table/cards, detail drawer, action dialogs, temp password dialog, `/account/password-required`. |
| F10-d | Jobs runner + Cardmarket/Riot jobs | F10-a, F4 scheduler | ~550 | Risk: item 4 + item 1 (concurrent runs; job table) | `rbjobs`, `flask jobs run-pending` with lock, kinds `cardmarket_load`, `riot_sets`, `riot_extract`, load history API, runbook timer. |
| F10-e | Catalog admin API | F10-a | ~500 | Risk: item 2 (file upload, catalog writes) | Sets and cards CRUD with in-use guards, image upload via `card_images`, audit. |
| F10-f | Catalog admin UI | F10-d, F10-e | ~600 | Risk: none | Sets table, cards table + editor + image upload, Riot sync and Cardmarket load panels with `JobStatus`. |
| F10-g | Cardmarket mappings API | F10-a | ~550 | Risk: item 3 (port must keep matcher/loader behaviour) | Characterization tests on legacy endpoints, then v1 endpoints for unmatched, mappings, auto-match, ignored, expansions, products. |
| F10-h | Cardmarket mappings UI | F10-g | ~600 | Risk: none | Mapping workbench, auto-match review, expansions and ignored screens. |
| F10-i | Bans admin | F10-a, F2-a | ~450 | Risk: item 3 (consumes F2 `rbcardbans` + `services/bans.py`) | Write endpoints on F2's table + audit, `BanEditor` UI per mode (card combobox from F2). |
| F10-j | Events moderation | F10-a, F8-a | ~400 | Risk: item 3 (consumes F8 `hidden` contract) | Moderation endpoints + table, hide/unhide/delete dialogs. |
| F10-k | Audit UI + Jinja hand-off | F10-c, F10-f, F10-h | ~350 | Risk: none | Audit screen, banner on the Jinja admin page linking to `/admin`, docs (AGENTS.md, runbook), overview completed. |

## Open decisions

| ID | Question | Options | Recommendation | Blocks |
|---|---|---|---|---|
| D-F10-1 | Promote/demote admins from the UI? (product.md: flags change only through the CLI "until the F10 admin UI") | UI / CLI only | CLI only for `is_admin`; UI for block/unblock | F10-b |
| D-F10-2 | Password reset method | temporary password + forced change / admin types a password | Temporary password shown once + forced change | F10-b |
| D-F10-3 | Admin can reset 2FA | yes / no | Yes, audited, revokes sessions (only recovery path without e-mail) | F10-b |
| D-F10-4 | Long operations | job table + 1-minute runner / synchronous with a longer Gunicorn timeout | Job table on the F4 timer mechanism; coordinate with F4 so its daily load uses the same runner | F10-d, F10-f |
| D-F10-5 | Deleting sets/cards | only unused / never | Only unused (FK cascade would delete users' collection lines) | F10-e |
| D-F10-6 | Legacy "price generation" CSV (`set;name;id;N`) | port / drop | Ask the owner; drop if unused | F10-g |
| D-F10-7 | Legacy `rbcar_banned` column | drop in F10 / keep out of the editor, drop in F11 | Not editable anywhere (F2 D-F2-2 already drops it from the Jinja form); drop the column in F11-f | F10-e |
| D-F10-8 | Audit retention | forever / 1 year | 1 year, purge job | F10-a |
| D-F10-9 | Admin on mobile | full / read + key actions | Read + user actions + moderation; heavy tools desktop-preferred | F10-c, F10-h |
| D-F10-10 | Where does the users' `sets` page go (nav `sets` is `legacy`, `U`)? | F2 catalog set view / admin only | F2 catalog (set filter/selector); admin keeps editing | F10-f (coordination with F2) |
| D-F10-11 | Admin design (design-handoff §10-13) | from tokens / commission a design | From tokens, owner reviews screenshots in each PR | F10-a |

## Risks and notes

- **Order**: F10 needs F9 (session revocation, 2FA reset). The roadmap lists F2, F4, F8 only — add F9.
- **Riot extraction** writes card images into `app/static/images/cards/` inside the deployed checkout; jobs
  run as the service user, so that folder must stay writable (F12 may move it to a data directory).
- **Matcher port**: `cardmarket_matcher.auto_match` and the loader are complex; keep them untouched and test
  the new endpoints against the same fixtures as `tests/test_cardmarket*.py`.
- **Two admin UIs until F11**: the legacy endpoints keep `require_admin`; any fix to shared services applies
  to both. F11 deletes the Jinja admin.
- **SW caches**: ban/catalog changes reach offline caches only after revalidation (F2 SWR).
- **Self-lockout**: guard against blocking or resetting the last admin (F10-R3).
