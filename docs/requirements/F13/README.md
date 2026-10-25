# F13: Riot sync + catalog admin — phase spec

Status: planned · Depends on: F4-a (job runner + timers), M-c (no exception text in legacy endpoints), M-d (card images in a data directory outside the code tree) · Source: `docs/knowledge/decisions-2026-10-22.md` ("Riot sync", "Catalog admin", "Job runner", "Bans"), F10 phase spec (units F10-a, F10-e, F10-f moved here), product.md "Data" · Phase IDs are identifiers, not order; the order lives in `docs/knowledge/roadmap.md`.

## Goal

The owner keeps the card catalog up to date from a React admin panel without waiting for the rest of the
admin phase: they create each set by hand with its release date, edit sets and cards, and let a scheduled
Riot gallery sync insert new cards and follow card changes. Around a release the sync runs often and
applies changes by itself; afterwards it runs once a month and every change to an existing card waits in
an approval table (field, old value, new value) until the owner approves or rejects it. This phase also
lays the admin foundation (guarded admin API, audit log, admin layout) that F10 builds on.

## Current state

| Area | What exists today |
|---|---|
| Sets | `RbSet` (`rbset`, `app/models/set.py`): `rbset_id` TEXT PK (the set code, e.g. `OGN`), `rbset_name` NOT NULL, `rbset_ncard` SMALLINT, `rbset_outdat` DATE ("release date", nullable). Jinja `app/routes/domains/sets.py`: page `/riftbound/set` (U), `/add` and `/update/<id>` (A). Schemas `SetCreate`/`SetUpdate` in `app/schemas/validators.py` already accept `rbset_outdat`. |
| Cards | `RbCard` (`rbcards`, `app/models/card.py`): PK (`rbcar_rbset_id`, `rbcar_id`), FK to `rbset` ON UPDATE/DELETE CASCADE; text/number fields `rbcar_name`, `rbcar_domain`, `rbcar_type`, `rbcar_tags`, `rbcar_energy`, `rbcar_power`, `rbcar_might`, `rbcar_ability`, `rbcar_rarity`, `rbcar_artist`, `rbcar_banned` ('S'/'N'), `image_url`, `image`. `rbcollection` references cards with ON UPDATE/DELETE CASCADE; decks store card keys in their own data; `rbcm_product_card_map` and `rbcm_expansions.rbexp_rbset_id` are soft references (no FK). Jinja `app/routes/domains/cards.py`: page `/riftbound/card` (U); `/add`, `/update/<set>/<id>`, `/upload_image` (A), paths through `app/services/card_images.py` (IMG-2). |
| Riot scraper | `app/services/riot_scraper.py`: one GET of `https://riftbound.leagueoflegends.com/en-us/card-gallery/`, cards read from the `__NEXT_DATA__` JSON. `refresh_riot_sets()` lists the gallery's set filter. Since F13-c the fetch/parse helpers live in `riot_scraper.py` and the writes live in `app/services/riot_sync.py` (`sync`: insert new cards, auto-apply in active windows, propose to `rbcardchanges` otherwise; one transaction per set; never writes `rbcar_banned`). The gallery gives no release date. |
| Admin entry points | Jinja admin page `GET /riftbound/price` (`price_bp`, `before_request(require_admin)`) with the buttons `POST /refresh-riot-sets` and `POST /extract-riot-cards`; both run inside the HTTP request (Gunicorn default 30 s timeout). Their 500 handlers return exception text until M-c fixes it. |
| Jobs | None today. F4-a creates `rbjobs`, the kind registry `app/jobs/registry.py`, `flask jobs enqueue|run-pending|list` and the systemd timer templates; later phases only register kinds (decisions file, "Job runner"). |
| Admin API / UI | None. Frontend has the `requireAdmin` loader (`frontend/src/auth/guards.ts`); nav entries `price` and `admin` are `legacy` → `/riftbound/price`, `adminOnly: true`. No audit trail of admin writes. |
| Images | Written under `CARD_IMAGES_DIR/<folder>/` (data directory outside git since M-d). |

## Scope

In:
- Admin foundation (from F10-a): admin blueprint under `/riftbound/api/v1/admin/` with
  `before_request(require_admin)`, sanitised errors, `rbadminaudit` + audit helper, partial
  `GET /admin/overview`, React `AdminLayout` + overview screen.
- Catalog admin API (from F10-e): sets (with release date entered by hand) and cards CRUD, image upload,
  in-use guards, audit.
- Riot sync: diff-based sync service, per-set schedule windows, job kind registered on the F4-a runner,
  timer templates, change-approval table with its API.
- Catalog admin UI (from F10-f): sets, cards, card editor + image upload, Riot sync panel with job status,
  change review screen.
- Read access to jobs (`GET /admin/jobs`, `GET /admin/jobs/{id}`) for the sync panel.

Out:
- Users admin, bans admin, events moderation, Cardmarket mappings and loads, audit UI (stay in F10).
- The job runner itself (F4-a); the daily Cardmarket load (F4-b).
- Bans (F2-a owns `rbcardbans`); Spanish enum names (F2).
- Removing Jinja pages or legacy routes (F11); dropping `rbcar_banned` (F10/F11).
- Riot gallery languages other than `en-us`.

## Decisions already taken

- Riot sync + catalog admin is pulled forward from F10 and does **not** wait for F9; it pulls F10-a,
  F10-e and F10-f. F10's user admin still waits for F9 (owner, 2026-10-22).
- The admin creates each set and enters its release date by hand; the set's name/code may change until
  the first card is revealed. The gallery provides no release date (owner, 2026-10-22).
- Sync schedule, per set, Europe/Madrid: from 21 days before the release date, card extraction at 08:00
  and 14:00; from the release date for 14 days, once a day; afterwards once a month (owner, 2026-10-22).
- New cards are always inserted. Changes to existing cards are applied automatically inside the active
  windows (pre-release and the 14 days after release); in the monthly run they go to an admin approval
  table showing field, old value and new value, with approve / reject (owner, 2026-10-22).
- The sync uses the F4-a job runner; F13 only registers job kinds (owner, 2026-10-22, "Job runner").
- The legacy `rbcar_banned` flag is not a ban source (the scraper resets it); bans are per card name and
  mode in F2-a (owner, 2026-10-22).
- Card images live outside git in a data directory (M-d runs before this phase) (owner, 2026-10-22).
- The catalog is maintained from the official gallery; the prototype CSV is not imported (product.md).
- Only the owner is admin; admin is desktop-first, React, `requireAdmin` (frontend) +
  `admin_required`/`require_admin` (backend); no exception text in error responses (product.md,
  AGENTS.md, F10 phase spec).
- Scheduled work = Flask CLI + systemd timers, no Celery/Redis (cross-phase contract).

## Requirements

### Admin foundation and security
- **F13-R1** Every admin endpoint lives on a blueprint under `/riftbound/api/v1/admin/` with
  `before_request(require_admin)`: anonymous → 401 JSON, non-admin → 403 JSON. Every rule is `A` in
  `tests/test_authz_matrix.py`; every frontend admin route uses `requireAdmin`. API keys (F9) never
  authenticate there. (F13-a)
- **F13-R2** Every admin write inserts an `rbadminaudit` row (actor, action, target, small JSON summary,
  time) in the same transaction. Changes applied by the scheduled sync are audited with a system actor
  (`actor_id` NULL, `actor_username` `system`). (F13-a, F13-c)
- **F13-R3** Error responses never include exception text. Job failures store a sanitised message (first
  line, ≤ 300 chars, no paths, no URLs with credentials) and log the full trace server-side. (F13-a, F13-c)

### Sets
- **F13-R4** `GET /admin/sets`: per set code, name, card count in `rbcards`, `rbset_ncard`, release date,
  current sync window (`pre_release`, `post_release`, `monthly`, `none`), next scheduled run, last sync job
  (id, status, finished at). (F13-b, F13-d)
- **F13-R5** `POST /admin/sets` creates a set (code, name, release date, optional `rbset_ncard`); a
  duplicate code → 409 `already_exists` (`params.field = "id"`). Whether the release date is mandatory is
  D-F13-3. (F13-b)
- **F13-R6** `PATCH /admin/sets/{id}` updates name, release date and `rbset_ncard`. The code (`rbset_id`)
  can change only while the set has no cards (the name/code may change until the first card is revealed);
  afterwards → 409 `set_in_use`. Changing the release date recomputes the set's window from the next run on.
  (F13-b)
- **F13-R7** `DELETE /admin/sets/{id}` only when no card references the set, else 409 `set_in_use`
  (D-F13-12). (F13-b)

### Cards
- **F13-R8** `GET /admin/cards`: filters (set, type, rarity, domain, missing image, text), sort, server-side
  pagination (50/100/200). (F13-b)
- **F13-R9** `POST /admin/cards` and `PATCH /admin/cards/{set}/{id}` create/update every catalog field
  **except** `rbcar_banned` (never writable from the admin API). Duplicate key → 409 `already_exists`.
  (F13-b)
- **F13-R10** `POST /admin/cards/{set}/{id}/image` uploads an image (multipart, ≤ 2 MB, jpg/png/webp)
  through `app/services/card_images.py` into the M-d data directory. (F13-b)
- **F13-R11** `DELETE /admin/cards/{set}/{id}` only when no collection line or deck uses the card, else
  409 `card_in_use` (`rbcollection` would cascade otherwise) (D-F13-12). (F13-b)

### Riot sync
- **F13-R12** One sync run fetches the `en-us` gallery once and reuses the existing parsing
  (`_parse_card`). A failed fetch or an unreadable page fails the run (job `error`, nothing written); a
  card that cannot be parsed is counted and skipped without aborting the run. The run never deletes cards
  (cards missing from the gallery: D-F13-9). (F13-c)
- **F13-R13** Sync windows are computed per set from its release date `R`, on Europe/Madrid local dates:
  `pre_release` = `R − 21` … `R − 1` (runs at 08:00 and 14:00); `post_release` = `R` … `R + 13` (one run
  a day, time D-F13-1); `monthly` = from `R + 14` (one run a month, day and time D-F13-2). A set without a
  release date follows D-F13-3. The window calculator is a pure function with tests for each boundary
  (`R − 22`, `R − 21`, `R − 1`, `R`, `R + 13`, `R + 14`) and for the daylight-saving changes. (F13-d)
- **F13-R14** New cards (key not in `rbcards`) are always inserted, in every window including the monthly
  run, and their image is downloaded into the data directory. Cards of a set code without an `rbset` row
  follow D-F13-4. (F13-c)
- **F13-R15** For existing cards the sync compares each synced field (`rbcar_name`, `rbcar_domain`,
  `rbcar_type`, `rbcar_tags`, `rbcar_energy`, `rbcar_power`, `rbcar_might`, `rbcar_ability`,
  `rbcar_rarity`, `rbcar_artist`, `image_url`, `image`; `rbcar_banned` per D-F13-10) with the stored value:
  - inside an active window (`pre_release`, `post_release`) a different value is applied at once, counted
    in the job result and audited with field, old and new value;
  - in the monthly run a different value is **not** applied: it creates one `pending` row in
    `rbcardchanges` (card, field, old value, new value). A field that already has a pending row updates
    that row's new value instead of adding another. (F13-c)
- **F13-R16** The sync never overwrites `rbset_ncard` or creates/renames sets except as decided in
  D-F13-4 and D-F13-18. (F13-c)
- **F13-R17** The job result records, per set: window, inserted, auto-applied changes, proposed changes,
  unchanged, images downloaded/existing/failed, unparsed cards, cards missing from the gallery, and the
  list of gallery set codes without an `rbset` row. (F13-c)

### Schedule and jobs
- **F13-R18** Job kind `riot_sync` is registered in the F4-a registry (with the migration that extends
  the `rbjobs` kind CHECK if F4-a keeps one). Params: optional `sets` (codes) and `trigger`
  (`schedule` / `manual`). A scheduled run processes only the sets that are due at that time by their
  window; a manual run follows D-F13-5. At most one queued/running `riot_sync` (F4-a partial unique index);
  a manual request while one is active → 409 `job_running`. (F13-c, F13-d)
- **F13-R19** systemd timer template `riftbound-riot-sync.timer` (`OnCalendar` at 08:00 and 14:00
  Europe/Madrid → `flask jobs enqueue riot_sync --param trigger=schedule`), documented in
  `docs/knowledge/ops-runbook.md` "Scheduled jobs" with `journalctl` commands and how to run it by hand.
  A run with no set due finishes `success` with message "nothing due". (F13-d)
- **F13-R20** `POST /admin/riot/sync` queues a manual run (optional set codes, validated against
  `rbset`); `GET /admin/jobs` (filters kind, status; latest first) and `GET /admin/jobs/{id}` return job
  status and result for polling. The UI polls every 3 s while the job runs. (F13-e)

### Change approval
- **F13-R21** `GET /admin/riot/changes`: filters status (default `pending`), set, field, card text;
  each row = card (set, id, name, image), field, old value, new value, detected at, job id. (F13-e)
- **F13-R22** `POST /admin/riot/changes/{id}/approve` applies the new value only if the card's current
  value still equals the stored old value; otherwise 409 `change_stale` and nothing changes.
  `POST /admin/riot/changes/{id}/reject` marks it rejected. A change that is not `pending` → 409
  `change_decided`. Both are audited; approving an `image_url`/`image` change follows D-F13-8. (F13-e)
- **F13-R23** `POST /admin/riot/changes/bulk` `{ids[], action: approve|reject}` applies the R22 rule per
  row in one transaction per row and returns per-id outcomes (no all-or-nothing). (F13-e)
- **F13-R24** A rejected change is not proposed again while the gallery keeps the same new value
  (D-F13-7). (F13-c)

### Overview
- **F13-R25** `GET /admin/overview` (partial, F10 extends it): sets in an active window with their next
  run, pending changes count, last `riot_sync` job (status, finished at), sets without release date, cards
  without image, gallery set codes without an `rbset` row. (F13-a, F13-e)

### Legacy coexistence
- **F13-R26** After F13-c the legacy Jinja Riot buttons follow D-F13-11, so no code path writes cards
  outside the R13-R15 rules. (F13-c)

### UI, i18n, a11y, performance
- **F13-R27** Desktop-first, but every screen defines mobile, desktop and wide layouts (D-F13-15).
- **F13-R28** Namespace `admin` in both catalogs with the ES/EN parity test; confirmations with
  `ConfirmDialog` stating the effect ("Se aplicarán 12 cambios"). New error codes added to both
  `errors.json` files with the backend/frontend catalog test.
- **F13-R29** Tables: `<caption>`, `scope`, `aria-sort`, keyboard row actions, sticky header under the
  topbar.
- **F13-R30** List endpoints use bounded queries (query-count tests); tests use stored gallery JSON
  fixtures and never reach the internet.

## Data model changes

| Revision (unit) | Change | Risk |
|---|---|---|
| `00xx_admin_audit` (F13-a) | `rbadminaudit` (`rbaud_`), shape from F10: `id` BIGINT PK; `actor_id` INT NULL FK `rbusers.id` ON DELETE SET NULL; `actor_username` VARCHAR(64); `action` VARCHAR(48); `target_type` VARCHAR(24); `target_id` VARCHAR(64); `details` JSON (JSONB on PostgreSQL); `created_at`. Indexes (`created_at` DESC), (`target_type`, `target_id`). | item 1 |
| `00xx_card_changes` (F13-c) | `rbcardchanges` (`rbchg_`): `id` BIGINT PK; `rbset_id`, `rbcar_id` TEXT NOT NULL, FK to `rbcards` ON UPDATE CASCADE ON DELETE CASCADE; `field` VARCHAR(32) CHECK IN the synced fields; `old_value` TEXT NULL; `new_value` TEXT NULL; `status` VARCHAR(10) CHECK IN ('pending','approved','rejected'); `job_id` BIGINT NULL FK `rbjobs` ON DELETE SET NULL; `detected_at`; `decided_at` NULL; `decided_by` INT NULL FK `rbusers.id` ON DELETE SET NULL. Partial unique index (`rbset_id`, `rbcar_id`, `field`) WHERE status = 'pending'. | item 1 |
| `00xx_jobs_riot_sync` (F13-c, only if F4-a's `rbjobs.kind` CHECK lists kinds) | Add `riot_sync` to the kind CHECK. | item 1 |

`rbset` needs no change: `rbset_outdat` is the release date. All revisions reversible with round-trip and
drift tests (`tests/migration_helpers.py`); downgrades drop the new tables (data loss documented). Deploy:
backup first.

## API

Base `/riftbound/api/v1/admin` (all `A`).

| Method | Path | Purpose | Unit |
|---|---|---|---|
| GET | `/overview` | Counters (F13-R25). | F13-a, F13-e |
| GET / POST | `/sets` | List with window state / create. | F13-b |
| PATCH / DELETE | `/sets/{id}` | Update (code only while empty) / delete unused. | F13-b |
| GET / POST | `/cards` | List with filters / create. | F13-b |
| PATCH / DELETE | `/cards/{set}/{id}` | Update / delete unused. | F13-b |
| POST | `/cards/{set}/{id}/image` | Upload image (multipart). | F13-b |
| POST | `/riot/sync` | Queue a manual `riot_sync` run. | F13-e |
| GET | `/jobs` · `/jobs/{id}` | Job list / status and result (read only). | F13-e |
| GET | `/riot/changes` | Change approval list. | F13-e |
| POST | `/riot/changes/{id}/approve` · `/riot/changes/{id}/reject` | Decide one change. | F13-e |
| POST | `/riot/changes/bulk` | Decide several changes. | F13-e |

New error codes (`app/api/error_codes.py`, both `errors.json`, contract test): `already_exists` (409,
`params.field`; introduced here if F13 runs before F3, which then reuses it), `set_in_use` (409),
`card_in_use` (409), `job_running` (409), `change_stale` (409), `change_decided` (409). CLI: none new
(`flask jobs …` comes from F4-a).

## UI

Routes `/riftbound/app/admin/*` with an admin layout (own left navigation inside the app shell):
`/admin` (overview), `/admin/sets`, `/admin/cards`, `/admin/riot` (schedule per set + "Sincronizar ahora"
+ recent runs), `/admin/riot/changes` (approval table), `/admin/jobs/:id`.

| Breakpoint | Layout |
|---|---|
| Mobile < 860 | Admin nav as a `Select`/sheet at the top; lists as cards with the 2-3 key fields and an actions menu; change review usable (approve/reject per row); card editor shows "Más cómodo en escritorio" but stays usable in one column. |
| Desktop ≥ 1240 | Left admin nav (220 px) + dense `DataTable` + detail drawer on the right (420 px) for the set and card editors; change review as a table (card, field, old → new, actions) with row selection and bulk actions; overview as KPI band + recent sync runs. |
| Wide ≥ 1600 | Three panes: nav / table / persistent detail panel; change review shows the card image and a side-by-side old/new text diff for long fields (`rbcar_ability`). |

Components: `AdminLayout`, `AdminNav`, `JobStatus` (polling, steps), `SetEditor` (release date picker,
window preview), `CardEditor` (form + image upload), `SyncPanel`, `ChangeReviewTable`, `ValueDiff`.
States: skeletons, empty ("Sin cambios pendientes"), error with retry, offline (all actions disabled;
admin is online-only). Nav: the `admin` entry becomes `spa` (`/admin`), still `adminOnly`; the `price`
entry stays `legacy` (Cardmarket tools stay in Jinja until F10).

## Units

| ID | Title | Depends on | Size | Risk | Summary |
|---|---|---|---|---|---|
| F13-a | Admin foundation | F1, M-c | ~550 | Risk: item 2 + item 1 (new admin surface; audit table) | Admin blueprint + guard + sanitised errors, `rbadminaudit` + audit helper, partial `GET /admin/overview`, React `AdminLayout` + overview, `admin` nav flip. Was F10-a. |
| F13-b | Catalog admin API | F13-a, M-d | ~500 | Risk: item 2 (file upload, catalog writes) | Sets (release date, code lock once cards exist) and cards CRUD, in-use guards, image upload via `card_images`, audit. Was F10-e. |
| F13-c | Riot sync engine + change table | F13-a, F4-a | ~600 | Risk: item 1 + item 6 (catalog writes from an external page; diff rules) | Sync service over the existing parser: insert new cards, field diff, auto-apply vs `rbcardchanges`, `riot_sync` job kind, result summary, legacy buttons per D-F13-11. |
| F13-d | Sync schedule | F13-c | ~300 | Risk: item 5 + item 4 (systemd timers; overlapping runs) | Window calculator (Europe/Madrid, boundary + DST tests), due-set selection, timer template, runbook "Scheduled jobs". |
| F13-e | Sync + approval API | F13-c | ~400 | Risk: item 1 (approved changes write cards) | Manual sync, jobs read endpoints, change list, approve/reject/bulk with the stale guard, overview counters. |
| F13-f | Catalog admin UI | F13-b, F13-e | ~600 | Risk: none | Sets table + `SetEditor`, cards table + `CardEditor` + image upload, `SyncPanel` with `JobStatus`. Was F10-f. |
| F13-g | Change review UI + hand-off | F13-f | ~400 | Risk: none | `ChangeReviewTable` with bulk actions and `ValueDiff`, overview completed, banner on the Jinja Riot section, docs (AGENTS.md, runbook, `docs/frontend.md`). |

## Open decisions

| ID | Question | Options | Recommendation | Blocks |
|---|---|---|---|---|
| D-F13-1 | Time of the once-a-day run in the 14 days after release | 08:00 / 14:00 / other | 08:00 Europe/Madrid (same timer as the pre-release morning run) | F13-d |
| D-F13-2 | Day and time of the monthly run | 1st of the month / release day-of-month / other | 1st of each month at 08:00 Europe/Madrid, all sets in `monthly` in one run | F13-d |
| D-F13-3 | Sets without a release date (legacy sets with `rbset_outdat` NULL, or a set created without it) | required on create / optional | Required when creating through the admin API; existing sets without a date are treated as `monthly` and listed on the overview | F13-b, F13-d |
| D-F13-4 | Gallery cards whose set code has no `rbset` row | auto-create a placeholder set / skip until the admin creates it | Auto-create the set (name = code, no release date) so new cards are always inserted, and flag it on the overview for the admin to name and date | F13-c |
| D-F13-5 | Rules of a manual "sync now" | per-set window rules / always auto-apply / always approval | Same per-set window rules as a scheduled run, but processing every requested set regardless of the time | F13-c, F13-e |
| D-F13-6 | Manual admin edits vs changes auto-applied inside a window | gallery wins / manual edit wins | Gallery wins inside the windows (the edit is visible in the audit with old and new value); outside the windows the change goes to approval as usual | F13-c |
| D-F13-7 | A rejected change seen again in a later monthly run | propose again / do not propose the same value | Do not propose it again while the gallery value equals the rejected new value; a different value creates a new pending row | F13-c |
| D-F13-8 | Image changes (`image_url` differs) | download and replace / record only | Treat `image_url` as a synced field; when applied or approved, download the new image over the same file name | F13-c, F13-e |
| D-F13-9 | Cards in the database that are no longer in the gallery | report only / delete / mark | Report only (job result + overview); never delete automatically | F13-c |
| D-F13-10 | `rbcar_banned` in the sync | keep writing `'N'` / stop writing it | Stop writing it (not a synced field); the column is dropped later with D-F10-7 | F13-c |
| D-F13-11 | Legacy Jinja buttons `POST /refresh-riot-sets` and `/extract-riot-cards` | keep as is / delegate to the F13 service / disable with a banner | `extract-riot-cards` delegates to the F13 sync service as a manual run (same rules, no second writer); `refresh-riot-sets` stays (read only); banner links to `/admin/riot` | F13-c, F13-g |
| D-F13-12 | Deleting sets and cards (was D-F10-5) | only unused / never | Only unused (the FK cascade would delete users' collection lines) | F13-b |
| D-F13-13 | Audit retention (was D-F10-8) | forever / 1 year | 1 year, purge job registered on the F4-a runner | F13-a |
| D-F13-14 | Admin design (was D-F10-11) | from tokens / commission a design | From tokens; owner reviews screenshots in each PR | F13-a, F13-f |
| D-F13-15 | Admin on mobile (was D-F10-9) | full / read + key actions | Read + approve/reject changes + "sync now"; editors desktop-preferred but usable | F13-f, F13-g |
| D-F13-16 | Telling the admin that changes are pending | overview only / nav badge / push | Overview counter + badge on the admin nav entry; push once F4-f exists, as a later addition | F13-g |
| D-F13-17 | Riot job kinds planned in F10-d (`riot_sets`, `riot_extract`) | keep them / replace with `riot_sync` | One `riot_sync` kind in F13; F10-d keeps only the Cardmarket kinds | F13-c (coordination with F10) |
| D-F13-18 | `rbset_ncard` written by the current scraper | sync overwrites it / admin-owned | Admin-owned: the sync reports the gallery count in the result and fills `rbset_ncard` only when it is NULL | F13-c |

## Risks and notes

- **External source** (item 6): the gallery is a Next.js page; a change in `__NEXT_DATA__` breaks parsing.
  The run fails cleanly (nothing written, sanitised message) and the overview shows the failed run. Tests
  use stored JSON fixtures; nothing reaches the internet.
- **Set code changes**: renaming `rbset_id` cascades to `rbcards` and `rbcollection`, but not to decks or
  the soft references in `rbcm_product_card_map` / `rbcm_expansions`; F13-R6 locks the code once the set
  has cards.
- **Two writers until F11**: the Jinja card form and the legacy Riot buttons write the same tables. D-F13-11
  routes the legacy extraction through the new service; the Jinja card form keeps writing (manual edits,
  audited only through the new API).
- **Timezone**: windows are local Europe/Madrid dates and the timers use `OnCalendar … Europe/Madrid`; the
  server clock may be UTC. The calculator is tested across both daylight-saving changes.
- **Overlapping runs**: the F4-a partial unique index + atomic claim keep one `riot_sync` at a time; the
  14:00 run on a slow day may find the 08:00 run still active and is then skipped (logged).
- **Images**: written to the M-d data directory as the service user; the folder must stay writable.
- **Ordering of error codes**: `already_exists` was planned to be introduced by F3; if F13 runs first it
  introduces it and F3 reuses it (cross-phase contract "Error codes").
- **Hand-over from F10**: F10-a, F10-e and F10-f move here; D-F10-5, D-F10-8, D-F10-9 and D-F10-11 are
  carried as D-F13-12 … D-F13-15. F10 keeps users, bans, moderation, Cardmarket and audit UI, and builds on
  `rbadminaudit` and `AdminLayout` from F13-a.
- **Spanish names**: the sync reads `en-us`, so the stored enum values (domain, type, rarity) stay English;
  their Spanish display names come from F2 (taken from the `es-es` gallery, owner 2026-10-22).
