# F10: Admin — phase spec

Status: planned · Depends on: F13 (admin foundation F13-a, catalog admin F13-b/F13-f — the former F10-a/e/f — and the jobs read API F13-e), F2 (ban table + read API + `flask bans`), F4 (job runner, daily Cardmarket load), **F9** (session revocation, 2FA reset); F8 (`hidden` events) for F10-j only · Order (`docs/knowledge/roadmap.md`): the rest of F10 is medium priority, before production; F10-j waits for F8 (after production) · Source: roadmap §5 (F10), §4, design-handoff §3.12, §6-2/36, §9 F10, §10-13, product.md "Users, accounts and security", "Scope by phase"

## Goal

The owner runs every admin task from a desktop-first React panel: Cardmarket loads and product mappings,
ignored products, users (block, unlock, reset password, reset 2FA, end sessions), bans per mode and
moderation of public events. Every admin write is audited. The admin foundation, sets and card editing and
the Riot gallery sync are built earlier by F13 (owner, 2026-10-22); F10 adds the remaining screens to that
panel. The Jinja admin page stops being the place to work (it is deleted in F11).

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
  `flask bans list|add|remove` and `GET /bans`; with F2-a the Jinja card form stops editing
  `rbcar_banned`.
- **Response quality**: legacy endpoints answer `{success, ...}` without the v1 envelope, and several 500
  handlers return `str(e)` (`refresh_riot_sets`, `extract_riot_cards`, `cardmarket_load`,
  `upload_card_image`) — against the AGENTS.md rule "500 responses never include exception text". Unit M-c
  fixes this before F10 (clear message + error code to the user, full detail logged and visible to the
  admin).
- **Long requests**: the Cardmarket load and the Riot extraction run inside the HTTP request; Gunicorn runs
  with its default 30 s timeout (`docs/riftbound.service` has no `--timeout`).
- **Users**: only the CLI (`flask users list|promote|demote|block|unblock|unlock|set-password`,
  ACL-6, LOGIN-6). No audit trail of admin actions.
- **Frontend**: `requireAdmin` loader exists (`frontend/src/auth/guards.ts`); nav entries `price` (top, hub)
  and `admin` (more) are `legacy` → `/riftbound/price`, `adminOnly: true`.
- **Tests**: since M-a only `tests/test_authz_matrix.py` and the startup smoke tests remain; the old
  `tests/test_cardmarket*.py`, `test_access_control.py` and `test_admin_cli.py` were removed (recover them
  from commit `902047c6579e5ee670e1fb4b103a941159b85c00` when a characterization test needs their fixtures).

## Scope

In:
- Admin API under `/riftbound/api/v1/admin/` (the blueprint, guard and audit built by F13; v1 envelope,
  error codes, no exception text) porting every remaining `price_bp` admin operation, plus users, bans,
  events moderation.
- Cardmarket job kinds for long operations, registered on the F4-a job runner.
- React admin screens at `/riftbound/app/admin/*` inside F13's admin layout, desktop-first, with defined
  mobile/desktop/wide layouts.
- Audit of every F10 admin write (F13's audit table and helper).
- The banner on the Jinja admin page pointing to the new panel; the `price` nav entry flip (F13-a flips
  `admin`).

Out:
- Changing `is_admin` from the UI (D-F10-1). Deleting user accounts (users delete their own, F9).
- Admin foundation, sets and cards admin, Riot sync and the jobs read API (F13: the former F10-a, F10-e,
  F10-f are F13-a, F13-b, F13-f).
- The legacy price CSV generator (dropped, see "Decisions already taken").
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
- Catalog admin (owner, 2026-10-22): built together with the Riot sync, before the rest of the catalog, in
  F13; it pulls F10-a (admin foundation), F10-e (catalog admin API) and F10-f (catalog admin UI) forward
  without waiting for F9. F10 user admin still waits for F9.
- **D-F10-6** (owner, 2026-10-22): drop the legacy price CSV (it only listed `set;name;id;N` for every card,
  without prices). The Cardmarket sales export of F7 is a different feature and stays.
- **D-F10-4** (owner, 2026-10-22, "Job runner"): the job runner is built once in F4-a (`rbjobs` +
  `flask jobs run-pending`); F10-d only registers job kinds.
- Bans (owner, 2026-10-22): the initial ban data comes from the official ban list (F2-a); `rbcar_banned` is
  never a source.
- Tests (owner, 2026-10-22, unit M-a): each F10 unit writes its own tests and re-creates the removed guard
  of the area it touches (migration round-trip + drift test, error-code catalog test, ES/EN parity).

## Requirements

### Security and authz
- **F10-R1** All admin endpoints live on the blueprint under `/riftbound/api/v1/admin/` that F13 creates, with
  `before_request(require_admin)`: anonymous → 401 JSON, non-admin → 403 JSON; API keys never authenticate
  there (F9-R24). Every rule is `A` in `tests/test_authz_matrix.py`; the frontend routes use `requireAdmin`.
- **F10-R2** Every admin write inserts an `rbadminaudit` row (actor, action, target, small JSON summary,
  time; table and helper from F13-a) in the same transaction. Secrets (temporary passwords, keys) are never written to the audit or logs.
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
- **F10-R8..R10** (sets, cards and Riot sync) moved to F13 with F10-e and F10-f (owner, 2026-10-22); see
  the F13 phase spec.

### Cardmarket
- **F10-R11** Load now (job) with optional overrides validated by the ACL-7 allow-list before queueing;
  load history from `rbcm_load_history` (date, file type, rows, status, message, loaded at).
- **F10-R12** Port, behaviour-preserving (characterization tests first on the legacy endpoints): unmatched
  products, manual map with foil (`N`/`S`/null), unmap, mappings browser with filters, conflict resolution,
  auto-match dry run + selective apply, ignored add/restore/list, unmapped expansions + map (optionally
  creating the set), product upsert/search (`rbproducts`), card upsert. The legacy price CSV generator
  (`POST /generate`, `set;name;id;N`) is **not** ported: it is dropped (owner, 2026-10-22) and disappears
  with the Jinja admin page (F11-e).

### Jobs
- **F10-R13** Long Cardmarket operations (load now, auto-match apply over N groups) are job kinds queued as
  `rbjobs` rows and executed by the F4-a `flask jobs run-pending` (timer every minute, with a run lock); F10
  builds no runner. At most one queued/running job per kind (409 `job_running`). F10-d adds
  `POST /admin/jobs` (queue a Cardmarket kind); polling uses F13-e's `GET /admin/jobs/{id}` and F13's
  `JobStatus` (every 3 s while a job runs). Riot sync is F13's single `riot_sync` kind (D-F13-17). The F4
  daily load uses the same code path.

### Bans and moderation
- **F10-R14** Bans (on F2's `rbcardbans`, through `app/services/bans.py` and its `name_key`): list per mode
  with card name, since, reason; add by card name for `1v1`, `2v2` or both (one row per mode, same
  validation as `flask bans add`); remove; audit (the table has no end date, so history lives in the audit). Consumers (catalog, legality) see the change
  on their next request; the UI warns that offline caches update within the SWR window.
- **F10-R15** Events: list public events (manual and scraped; filters upcoming/past, hidden, owner, source),
  hide with reason / unhide (F8 `hidden`, `hidden_reason`), delete a manual event with confirmation (shows
  how many users saved it); audit.

### Overview
- **F10-R16** `GET /admin/overview` (partial version from F13, completed here): users (total, new 7 d, blocked, locked, with 2FA), last Cardmarket load
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
| `00xx_admin_audit` (moved to F13 with F10-a; listed for reference) | `rbadminaudit` (`rbaud_`): `id` BIGINT PK; `actor_id` INT NULL FK `rbusers.id` ON DELETE SET NULL; `actor_username` VARCHAR(64); `action` VARCHAR(48); `target_type` VARCHAR(24); `target_id` VARCHAR(64); `details` JSON (JSONB on PostgreSQL); `created_at`. Indexes (`created_at` DESC), (`target_type`,`target_id`). | item 1 |
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
| POST | `/jobs` | Queue a Cardmarket job `{kind, params}` (F10-d). |
| GET | `/audit` | Audit log (filters actor, action, target, date). |

Built by F13 and reused here: the blueprint and guard, `/sets`, `/sets/{id}`, `/cards`, `/cards/{set}/{id}`,
`/cards/{set}/{id}/image`, `GET /jobs`, `GET /jobs/{id}` and the partial `/overview`.

New error codes: `self_action_forbidden` (409), `password_change_required` (403), `job_running` (409),
`set_in_use` (409), `card_in_use` (409), `already_exists` (409, `params.field`) — coordinate names with the
codes F2-F9 and F13 add (one registry, `app/api/error_codes.py`); `set_in_use` and `card_in_use` come with
the catalog admin in F13. No new CLI: `flask jobs run-pending` is F4-a's.

## UI

Routes `/riftbound/app/admin/*` inside F13's admin layout (own left navigation inside the app shell; F13
also owns `/admin/sets`, `/admin/cards` and `/admin/jobs/:id`): `/admin` (overview, completed here),
`/admin/users`, `/admin/users/:id`, `/admin/cardmarket/loads`, `/admin/cardmarket/mappings`, `/admin/cardmarket/expansions`,
`/admin/cardmarket/ignored`, `/admin/bans`, `/admin/events`, `/admin/audit`. Forced
password change screen `/account/password-required` (outside the admin area).

| Breakpoint | Layout |
|---|---|
| Mobile < 860 | Admin nav as a `Select`/sheet at the top; lists as cards with the 2-3 key fields and an actions menu; user actions and event moderation fully usable; mapping and card editors show "Más cómodo en escritorio" but stay usable in one column. |
| Desktop ≥ 1240 | Left admin nav (220 px) + dense `DataTable` (40 px rows, column chooser where > 8 columns) + detail drawer on the right (420 px) for user detail, card editor, mapping editor; overview as KPI band + two lists (recent jobs, recent audit). |
| Wide ≥ 1600 | Three panes: nav / table / persistent detail panel (no drawer); mappings screen shows unmatched products, candidate cards with images and the current mapping side by side; overview adds a third column (bans and moderation queue). |

Components (F13 provides `AdminLayout`, `AdminNav`, `JobStatus` and `CardEditor`): `UserTable`/`UserDetail`,
`TempPasswordDialog` (copy once, warning), `CardmarketLoadPanel` (load now + history with `JobStatus`),
`MappingWorkbench`, `AutoMatchReview` (checkbox list of pairings with confidence), `BanEditor` (card
combobox from F2, mode checkboxes, reason), `ModerationTable`, `AuditTable`. States: skeletons, empty,
error with retry, offline (all actions disabled; admin is online-only). Nav: F13-a flips `admin` to `spa`
(`/admin`, still `adminOnly`); F10-h flips `price` to `spa` (`/admin/cardmarket/loads`, still `adminOnly`).

## Units

| ID | Title | Depends on | Size | Risk | Summary |
|---|---|---|---|---|---|
| F10-b | Users admin API | F13-a (admin foundation, former F10-a), F9-a, F9-d | ~550 | Risk: item 2 + item 1 (account takeover surface; new column) | List/detail, block/unblock/unlock/revoke, reset 2FA, reset password + `must_change_password` enforcement. |
| F10-c | Users admin UI + forced change | F10-b | ~500 | Risk: none | Users table/cards, detail drawer, action dialogs, temp password dialog, `/account/password-required`. |
| F10-d | Cardmarket job kinds | F13-a, F13-e (jobs read API), F4-a | ~350 | Risk: item 4 (concurrent runs) | Kind `cardmarket_load` (load now with ACL-7 overrides) and the auto-match apply kind for large selections, on the F4-a runner (no runner code), `POST /admin/jobs`, load history API, audit. Riot sync is F13's `riot_sync` kind. |
| F10-g | Cardmarket mappings API | F13-a | ~550 | Risk: item 3 (port must keep matcher/loader behaviour) | Characterization tests on legacy endpoints, then v1 endpoints for unmatched, mappings, auto-match, ignored, expansions, products. |
| F10-h | Cardmarket mappings UI | F10-d, F10-g | ~600 | Risk: none | Cardmarket load panel with `JobStatus` (moved here from the former F10-f), mapping workbench, auto-match review (including the F4-b review list), expansions and ignored screens, `price` nav flip. |
| F10-i | Bans admin | F13-a, F2-a | ~450 | Risk: item 3 (consumes F2 `rbcardbans` + `services/bans.py`) | Write endpoints on F2's table + audit, `BanEditor` UI per mode (card combobox from F2). |
| F10-j | Events moderation (after production) | F13-a, F8-a | ~400 | Risk: item 3 (consumes F8 `hidden` contract) | Moderation endpoints + table, hide/unhide/delete dialogs. |
| F10-k | Audit UI + Jinja hand-off | F10-c, F10-h, F13-f (catalog admin UI, former F10-f) | ~350 | Risk: none | Audit screen, banner on the Jinja admin page linking to `/admin`, docs (AGENTS.md, runbook), overview completed. |

F10-a, F10-e and F10-f moved to F13 (now F13-a, F13-b, F13-f; owner, 2026-10-22).

## Open decisions

| ID | Question | Options | Recommendation | Blocks |
|---|---|---|---|---|
| D-F10-1 | Promote/demote admins from the UI? (product.md: flags change only through the CLI "until the F10 admin UI") | UI / CLI only | CLI only for `is_admin`; UI for block/unblock | F10-b |
| D-F10-2 | Password reset method | temporary password + forced change / admin types a password | Temporary password shown once + forced change | F10-b |
| D-F10-3 | Admin can reset 2FA | yes / no | Yes, audited, revokes sessions (only recovery path without e-mail) | F10-b |
| D-F10-7 | Legacy `rbcar_banned` column | drop in F10 / keep out of the editor, drop in F11 | Not editable anywhere (F2-a already drops it from the Jinja form); drop the column in F11-f | F13-b (former F10-e) |
| D-F10-10 | Where does the users' `sets` page go (nav `sets` is `legacy`, `U`)? | F2 catalog set view / admin only | F2 catalog (set filter/selector); admin keeps editing | F13-f (former F10-f; coordination with F2) |

D-F10-5, D-F10-8, D-F10-9 and D-F10-11 moved to F13 as D-F13-12..15 (they also cover the F10 screens).

## Risks and notes

- **Order**: user admin (F10-b/F10-c) needs F9 (session revocation, 2FA reset); the admin foundation and the
  catalog admin went to F13 without waiting for F9; F10-j needs F8, which comes after production.
- **Card images**: M-d moves them to a data directory outside the code tree before F13; the Riot sync (F13)
  writes there, and the job user must keep write access to it.
- **Matcher port**: `cardmarket_matcher.auto_match` and the loader are complex; keep them untouched and test
  the new endpoints against the fixtures of the removed `tests/test_cardmarket*.py` (recover them from commit
  `902047c6579e5ee670e1fb4b103a941159b85c00`).
- **Two admin UIs until F11**: the legacy endpoints keep `require_admin`; any fix to shared services applies
  to both. F11 deletes the Jinja admin.
- **SW caches**: ban/catalog changes reach offline caches only after revalidation (F2 SWR).
- **Self-lockout**: guard against blocking or resetting the last admin (F10-R3).
