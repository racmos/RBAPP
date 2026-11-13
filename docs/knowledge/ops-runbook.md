# Ops runbook (dev)

Generic procedures. Host-specific values (paths, service name, URL, backup command, proxy host) live in
`ops.local.md` at the root of the **deployed checkout**. That file is git-ignored and never committed;
read it before running anything here. Never print `.env`, the database URL or any password.

There is no production yet (phase F12). Everything here is the development server.

## Working copies

- The **deployed checkout** stays on `main`. Gunicorn runs from it, and `spa_bp` reads `frontend/dist`
  from it on every request, so a frontend build there is live immediately. Never switch branches, build a
  feature branch or run `npm ci` for a feature there.
- Implement each unit in its own worktree:

  ```bash
  git -C <deployed checkout> fetch origin
  git -C <deployed checkout> worktree add ../RBAPP-<unit> -b feat/<branch> origin/main
  cd ../RBAPP-<unit>
  <deployed checkout>/venv/bin/python -m pytest -q          # backend, from the worktree root
  cd frontend && npm ci && npx vitest run                     # frontend
  ```

- After the PR is merged: `git worktree remove ../RBAPP-<unit>` and delete the local branch.

## Deploy after a merge

1. `cd <deployed checkout> && git pull --ff-only` (untracked owner files such as `.agents/`, `.claude/`,
   `skills-lock.json` or a modified `.atl/skill-registry.md` are expected: leave them alone).
2. See what changed: `git diff --stat ORIG_HEAD HEAD -- requirements.txt migrations/ frontend/ app/ config.py`.
3. `requirements.txt` changed → `venv/bin/pip install -r requirements.txt`.
4. `migrations/` changed → **backup first** (command in `ops.local.md`; dumps go to a private folder,
   mode 600), then `venv/bin/flask db upgrade` and `venv/bin/flask db check` (must report no drift).
5. `frontend/` changed → `cd frontend && npm ci && npm run build && npm run check:dist`.
6. Restart the service (command in `ops.local.md`). Python changes need it; a frontend-only change does
   not, but a restart is harmless.
7. Verify:
   - `curl -s -o /dev/null -w '%{http_code}\n' <URL>/riftbound/api/v1/health` → 200
   - `<URL>/riftbound/app/` → 200 `text/html`, `Cache-Control: no-cache`
   - `<URL>/riftbound/app/sw.js` → 200; `<URL>/riftbound/app/manifest.webmanifest` → 200
     `application/manifest+json`
   - the live checks listed in the unit's requirement
8. Report to the owner: what was deployed (commit), migration head, checks run and their result, and the
   manual checks left for them.

## Rollback

- Code: revert the PR on GitHub (new PR), merge, deploy again.
- Database: every revision is reversible: `venv/bin/flask db downgrade -1` (one step) — only with the
  owner's go-ahead. Last resort: restore the backup taken before the upgrade with `pg_restore` (owner
  decides; it overwrites data written since).
- PWA: a plain revert leaves the service worker installed on devices. Use the self-destroying build
  (`VITE_PWA_SELF_DESTROY=true npm run build && node scripts/check-dist.mjs --self-destroy dist`), deploy
  it, wait for clients, then deploy the fixed build. Details: `docs/frontend.md` → "Rolling back the PWA".

## Service operations

- Status and logs: `systemctl status <service>`, `journalctl -u <service> -n 200 --no-pager`.
- Users: `venv/bin/flask users list|promote|demote|block|unblock|unlock|set-password|reset-2fa <username>`
  (`reset-2fa`: see "Two-factor key (F9-d)").
- Schema snapshot (structure only): `venv/bin/flask schema snapshot`.
- Card bans per game mode (F2-a; the only way to change them until the F10 admin UI; a ban covers every
  printing of the name):
  - `venv/bin/flask bans list [--mode 1v1|2v2]`
  - `venv/bin/flask bans add "<card name>" --mode 1v1|2v2|all [--since YYYY-MM-DD] [--reason "<text>"] [--force]`
    (the name must exist in the catalog unless `--force`; running it again changes nothing)
  - `venv/bin/flask bans remove "<card name>" --mode 1v1|2v2|all`
- Nginx (public reverse proxy, TLS) runs on another host and is changed only by the owner. The template is
  `docs/nginx_config`.

## Nightly backup (dev, 2026-11-03)

`scripts/db_backup.py` writes `~/backups/rbapp/riftbound_nightly_<YYYYmmdd_HHMM>.dump` (`pg_dump -Fc -n riftbound`,
mode 600) and deletes `riftbound_nightly_*` files older than 14 days; the manual `riftbound_pre_*` dumps taken
before a migration are never touched. It reads `DATABASE_URL` from `.env` and never prints it. The timer
`riftbound-backup.timer` runs it at 03:30 Europe/Madrid (`Persistent=true`).

Install (sudo, same as the other timers) and rollback:

```bash
sudo cp docs/systemd/riftbound-backup.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now riftbound-backup.timer
sudo systemctl start riftbound-backup.service      # one run now; then: ls -l ~/backups/rbapp
systemctl list-timers riftbound-backup.timer       # next run
# rollback
sudo systemctl disable --now riftbound-backup.timer && sudo rm /etc/systemd/system/riftbound-backup.{service,timer} && sudo systemctl daemon-reload
```

This is a safety net on the development server, not the production backup (F12-d: encrypted, copied off the host,
restore drill).

## Scheduled jobs (from F4)

Jobs are Flask CLI commands run by systemd timers on the dev server. Each phase that adds a job documents
here: the command, the unit/timer names, the schedule, the logs and how to run it by hand.

### Job runner (F4-a)

Background work is a row in `riftbound.rbjobs`. Something queues it (`flask jobs enqueue <kind>`, a timer,
later an admin endpoint); `riftbound-jobs.timer` starts `flask jobs run-pending` every minute, which marks
jobs running past their timeout as `error`, then claims each queued job, runs it and records `success` or
`error` with the result or the message. Only one job per kind can be queued or running. The runner exits 0
even when a job failed (the failure is on the job). Overlapping runs are safe: the unit wraps the runner
in `flock -n /run/riftbound/jobs.lock` and each job is claimed with a conditional `UPDATE`. Kinds today:
`heartbeat` (diagnostic, 60 s timeout), `daily_prices` (daily Cardmarket load, 1800 s timeout, F4-b below) and `value_snapshot` (F4-c below).
`price_alerts` (F4-g-2, "Wishlist price alerts" below): allowed by migration `0027_jobs_price_alerts`,
registered since F4-g-2, no timer: queued by `daily_prices`. Rollback: the 0027 downgrade refuses while
`price_alerts` jobs exist (`DELETE FROM riftbound.rbjobs WHERE rbjob_kind = 'price_alerts';`).

Templates: `docs/systemd/` (`riftbound-jobs.service` + `.timer`). They use the same user, working
directory and environment file as `docs/riftbound.service`; adapt them to the values in `ops.local.md`.

Upgrade order (first deploy of F4-a):

1. Backup (command in `ops.local.md`).
2. `venv/bin/flask db upgrade`, then `venv/bin/flask db check` (no drift).
3. Restart the service.
4. Install and enable the timer:

   ```bash
   sudo cp docs/systemd/riftbound-jobs.service docs/systemd/riftbound-jobs.timer /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now riftbound-jobs.timer
   systemctl list-timers riftbound-jobs.timer
   ```

5. Check: `venv/bin/flask jobs enqueue heartbeat` (`Queued job <id> (heartbeat).`), and a minute later
   `venv/bin/flask jobs list`: the job shows `success`.

Operations:

- Logs: `journalctl -u riftbound-jobs.service -n 200 --no-pager` (one line per job, then
  `Ran <n> job(s).`; `No pending jobs.` on idle minutes).
- Run by hand (as the service user, from the deployed checkout): `venv/bin/flask jobs run-pending`. Or
  start the unit once: `sudo systemctl start riftbound-jobs.service`.
- History: `venv/bin/flask jobs list [--limit N]` (newest first, default 20).
- Queue a job: `venv/bin/flask jobs enqueue <kind> [--param key=value]...`.
- Disable (rollback): `sudo systemctl disable --now riftbound-jobs.timer`. Queued jobs stay queued until
  the timer is enabled again. Removing the table is `flask db downgrade 0006_user_prefs` (drops the job
  history; owner's go-ahead only; with F4-b deployed, first follow its rollback below).

### Daily Cardmarket load (F4-b)

`riftbound-daily.timer` (06:30 Europe/Madrid) starts `riftbound-daily.service`, which runs
`flask jobs enqueue daily_prices`; the job runner picks it up within a minute. The job loads the three
Cardmarket files (price guide, singles, non-singles) from the default allow-listed URLs, validates the load,
links the clear auto-match cases and lists the doubtful ones for review. It ends `error` (and links nothing)
when the loader fails or the validation fails (`Validation failed: no price rows for <date>`,
`Validation failed: <file> missing for <date>`). `riftbound-daily-retry.timer` (08:00 Europe/Madrid) starts
`riftbound-daily-retry.service`: `flask jobs enqueue daily_prices --unless-succeeded-today` prints
`Skipped: a 'daily_prices' job already succeeded today (job <id>).` and exits 0 when a run succeeded on the
current UTC date, and queues the job again otherwise. Both services use the same user, paths and
environment file as `riftbound-jobs.service`.

Install (after the F4-b deploy: backup, `venv/bin/flask db upgrade` to `0008_jobs_daily_prices`,
`venv/bin/flask db check`, restart; `riftbound-jobs.timer` must already be enabled):

```bash
sudo cp docs/systemd/riftbound-daily.service docs/systemd/riftbound-daily.timer \
        docs/systemd/riftbound-daily-retry.service docs/systemd/riftbound-daily-retry.timer \
        /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now riftbound-daily.timer riftbound-daily-retry.timer
systemctl list-timers 'riftbound-daily*'
```

Check: run it once by hand with `venv/bin/flask jobs enqueue daily_prices`, then a few minutes later
`venv/bin/flask jobs list`: the `daily_prices` row shows `success` (or `error` and its message). Logs:
`journalctl -u riftbound-daily.service -u riftbound-daily-retry.service -u riftbound-jobs.service -n 200 --no-pager`.

Read the result (there is no `flask jobs` command for it; this prints the latest `daily_prices` job):

```bash
venv/bin/flask shell <<< "import json; from app.models import RbJob; j = RbJob.query.filter_by(rbjob_kind='daily_prices').order_by(RbJob.rbjob_id.desc()).first(); print(j.rbjob_id, j.rbjob_status, j.rbjob_message); print(json.dumps(j.rbjob_result, indent=2, ensure_ascii=False))"
```

`rbjob_result` holds:

- `validation`: the loader date, per file the status of its last `rbcm_load_history` row of that date
  (`success`, or `skipped` when the product file was unchanged) and its rows, `price_rows`,
  `products_today` and `new_products` (products of that date never seen on an earlier date).
- `auto_match`: `linked` (written by this run: one unmapped product and one free candidate card in its
  metacard group, `match_type='auto'`, confidence 0.7), `proposed` (pairs the matcher would make) and
  `review` (how many products need a human). The loader's exact-name rule still links its own cases first.
- `review` (at most 200 items) and `review_total`: the unmapped singles of the load date that were not
  linked, each with `product_id`, `name`, `expansion_id`, candidate cards and a `reason`:
  `no_candidates` (no card with that name), `ambiguous` (several products or several candidate cards in
  the group), `conflict` (the card slot is already taken or proposed for two products) or `ignored_pair`
  (ignored in the mappings browser). Link them by hand in the admin mappings screens; the planner uses the
  list to add matching rules.

Rollback: `sudo systemctl disable --now riftbound-daily.timer riftbound-daily-retry.timer` (the job kind
stays registered and can still be queued by hand). Downgrading the migration (owner's go-ahead only)
needs the `daily_prices` rows gone first, otherwise it stops with a clear message:
`DELETE FROM riftbound.rbjobs WHERE rbjob_kind = 'daily_prices';` then
`venv/bin/flask db downgrade 0007_jobs`.

### Riot sync (F13-c)

The `riot_sync` job (timeout 1800 s) keeps the catalog in line with the official gallery: it always
inserts new cards, auto-applies differences around a release (21 days before until 13 days after) and
records anything else in `rbcardchanges` for the admin. Manual runs queue
`venv/bin/flask jobs enqueue riot_sync [--param trigger=schedule] [--param sets=OGN,OGS]` (no `sets` =
every gallery set); the F13-d timers queue the schedule. Unknown set codes fail the job
(`riot_sync: unknown set(s): …`).

Run by hand (as the service user, from the deployed checkout): the command above, then a minute later
`venv/bin/flask jobs list`. Read the result with the one-liner below (it prints the latest `riot_sync`
job): `validation`-style summary per set (`window`, `inserted`, `applied`, `proposed`, `unchanged`,
`missing_from_gallery`, `images`, `error`).

```bash
venv/bin/flask shell <<< "import json; from app.models import RbJob; j = RbJob.query.filter_by(rbjob_kind='riot_sync').order_by(RbJob.rbjob_id.desc()).first(); print(j.rbjob_id, j.rbjob_status, j.rbjob_message); print(json.dumps(j.rbjob_result, indent=2, ensure_ascii=False))"
```

Manual runs come from the app (Admin → Riot, `POST /riftbound/api/v1/admin/riot/sync`); the old Jinja
button went with the Jinja web (PR 3/3 of its retirement).

The `am` job runs every day at 08:00 Europe/Madrid (pre-release, post-release and, on the 1st of
the month, `monthly` sets); the `pm` job runs at 14:00 (pre-release only). A scheduled run with no
due set ends `success` with `{"message": "nothing due", "sets": []}` and fetches nothing.

Install (after the F13-c deploy: backup, `venv/bin/flask db upgrade` to `0012_jobs_riot_sync`,
`venv/bin/flask db check`, restart):

```bash
sudo cp docs/systemd/riftbound-riot-sync-am.service docs/systemd/riftbound-riot-sync-am.timer \
        docs/systemd/riftbound-riot-sync-pm.service docs/systemd/riftbound-riot-sync-pm.timer \
        /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now riftbound-riot-sync-am.timer riftbound-riot-sync-pm.timer
systemctl list-timers 'riftbound-riot-sync*' --no-pager
```

An exit 1 from a timer unit (`SuccessExitStatus=1`) means a sync was already queued or running:
the run is skipped, nothing failed.

Rollback: disable both timers (`sudo systemctl disable --now riftbound-riot-sync-am.timer
riftbound-riot-sync-pm.timer`); downgrading the migrations (owner's go-ahead only) drops the change
table and its history. The 0012 downgrade refuses while `riot_sync` jobs exist, so delete them first
(`DELETE FROM riftbound.rbjobs WHERE rbjob_kind = 'riot_sync';`), then
`venv/bin/flask db downgrade 0011_card_changes` (runs the 0012 and 0011 downgrades).

How to review Riot changes (F13-g): after a monthly-window load, open `/riftbound/app/admin/riot/changes`
as an admin. Each row shows the card, the field and the old vs new value; approve or reject it there
(single or in bulk with the checkbox selection). A change whose card no longer matches is reported as
stale and stays undecided. Approving an `image_url` change re-downloads the image over the card's file.

Comparison rules (owner feedback 2026-10-29): the gallery sends `name` and `subtitle` apart; a
non-Legend, non-Signature card stores "Name, Subtitle" ("Ahri, Alluring"), Legends keep the bare
name. The gallery's "Champion Legend" is stored as "Legend". In a set with `rbset_ncard` (the card
count the owner sets by hand in `rbset`; VEN = 166) a card numbered above it is Showcase, and at or
below it a gallery "Showcase" never replaces the stored rarity; a set without a count compares the
rarity as before. Image URLs that differ only in the query string (`?accountingTag=RB`) are the same
image: no proposal, no write.

Recheck pending proposals after a rule change (S17). Proposals made before the rules above stay
pending until rechecked; the recheck re-evaluates every pending row against the stored card with the
same rules (no network) and marks the ones that are no longer a change `obsolete` (`decided_at` =
now, `decided_by` NULL, one `riot.recheck` audit row); nothing is deleted. Needs migration
`0023_card_changes_obsolete`. **Take a `pg_dump` first** (owner's go-ahead), then look at the dry run:

```bash
pg_dump -h <host> -U <user> -d <database> -n riftbound -Fc -f ~/backups/rbapp/riftbound_pre_recheck_$(date +%Y%m%d_%H%M).dump
venv/bin/flask db upgrade                       # to 0023_card_changes_obsolete, then restart
venv/bin/flask riot recheck-pending --dry-run   # counts per set and field, changes nothing
venv/bin/flask riot recheck-pending
```

Output: `Checked N pending proposals: X obsolete, Y still pending.` then one `  SET field: n` line per
set and field made obsolete. A second run reports 0 obsolete. Obsolete rows leave the pending list and
the bulk actions (they answer `decided`), are listed with `?status=obsolete`, and never block a later
proposal of the same value (only `rejected` does). Undo for one batch: restore the dump, or
`UPDATE riftbound.rbcardchanges SET rbchg_status = 'pending', rbchg_decided_at = NULL WHERE
rbchg_status = 'obsolete' AND rbchg_decided_at = '<the run's time>'`. The `0023` downgrade refuses
while obsolete rows exist (set their status first).

### Collection value snapshots (F4-c)

The `value_snapshot` job (timeout 900 s, no params) stores, for every user with at least one collection
line, today's collection value in `rbvaluesnaps` (value, cost, copies, distinct printings, lines without a
price), priced by the same code as `GET /collection`. When `daily_prices` succeeds, its last step queues it
and the job runner (which keeps claiming queued jobs) runs it right after the load; `daily_prices` shows
`"queued": ["value_snapshot", "products_refresh", "price_alerts"]` in its result (F14-a, F4-g-2). A snapshot that cannot be queued never
fails the price load.
A second run the same day replaces that day's rows; the history cannot be rebuilt later, so do not delete rows.

Since F14-c (migration `0022_snapshot_products_value`) each row also stores `rbvsn_products_value`: the value
of the user's sealed products (`rbuserproducts`, sum of price x quantity over the priced lines, priced like
`GET /me/products`), kept apart and never added to `rbvsn_value`. It is NULL for a user without product lines
and for every row taken before 0022. A user with product lines but no collection lines now gets a row too,
with the cards at 0 (`rbvsn_value` 0, `rbvsn_cost` NULL, qty, unique and unpriced 0); a user with neither gets
no row. The job result adds `products_value` (the sum over all users). Rollback: the 0022 downgrade drops the
column and its values, and the 0021 downgrade drops `rbuserproducts` with every user's products, so back up
first and only with the owner's go-ahead.

By hand: `venv/bin/flask jobs enqueue value_snapshot`, then `venv/bin/flask jobs list`. Read today's rows:

```bash
venv/bin/flask shell <<< "from app.models import RbValueSnapshot as S; from app.utils import clock; [print(r.rbvsn_user_id, r.rbvsn_date, r.rbvsn_value, r.rbvsn_cost, r.rbvsn_qty, r.rbvsn_unique, r.rbvsn_unpriced) for r in S.query.filter_by(rbvsn_date=clock.utcnow().date())]"
```

Install (after the F4-c deploy: backup, `venv/bin/flask db upgrade` to `0017_jobs_value_snapshot` (runs
`0016_value_snapshots` and `0017`), `venv/bin/flask db check`, restart the service). No new timer. Rollback:
the 0017 downgrade refuses while `value_snapshot` jobs exist (`DELETE FROM riftbound.rbjobs WHERE
rbjob_kind = 'value_snapshot';`), and the 0016 downgrade drops `rbvaluesnaps` with every snapshot taken, so
only with the owner's go-ahead.

### Product catalog refresh (F14-a)

The `products_refresh` job (timeout 600 s, optional param `date=YYYYMMDD`, default the latest
`rbcm_products` date) brings the product catalog `rbproducts` in step with the non-single Cardmarket
products of that date: new ids are inserted (name, category, kind, set of the mapped expansion), existing ones
get name, category and `listed = true`, and kind / set unless `rbpdt_kind_locked` / `rbpdt_set_locked`;
`nonsingle` products missing from the date get `listed = false`. Rows are never deleted. `daily_prices`
queues it after `value_snapshot` (each on its own: one active or failing does not stop the other). A date
without non-single products is an error and changes nothing; so is an unknown param or a bad date.

By hand: `venv/bin/flask jobs enqueue products_refresh [--param date=YYYYMMDD]`, then
`venv/bin/flask jobs list`. Read the counts (`date`, `new`, `updated`, `not_listed`, `total`) of the latest job:

```bash
venv/bin/flask shell <<< "from app.models import RbJob as J; j = J.query.filter_by(rbjob_kind='products_refresh').order_by(J.rbjob_id.desc()).first(); print(j.rbjob_id, j.rbjob_status, j.rbjob_result or j.rbjob_message)"
```

Install (after the F14-a deploy): backup first, `venv/bin/flask db upgrade` to `0020_jobs_products_refresh`
(runs `0019_products_catalog`, which moves the `rbproducts` key to the product id and refuses while a
product id is in more than one row, and `0020`), `venv/bin/flask db check`, restart the service, then
`venv/bin/flask jobs enqueue products_refresh` and read the counts. No new timer. Rollback: the 0020
downgrade refuses while `products_refresh` jobs exist (`DELETE FROM riftbound.rbjobs WHERE rbjob_kind =
'products_refresh';`); the 0019 downgrade refuses while a product has no set (`rbpdt_id_set IS NULL`; set it
or delete those rows) and drops the new columns (category, kind, locks, hidden, listed), so only with the
owner's go-ahead.

### Wishlist price alerts (F4-g-2)

The `price_alerts` job (timeout 900 s, no params) raises the wishlist price alerts of the latest Cardmarket
price load (`rbwishlistalerts`; rule in `docs/api.md` → "Wishlist alerts (F4-g-2)"): for every user, one
alert per card target and price date when any wishlist line of that target with a max price is at or below
it. `daily_prices` queues it last, after `value_snapshot` and `products_refresh` (each on its own: one
active or failing does not stop the others, and none can fail the price load). The price date is the newest
`rbcm_price` date, so a second run on the same load creates nothing (`alerts_created: 0`); the next load
raises the alerts again while the prices stay low. No price load at all is an error (`price_alerts: no
Cardmarket prices loaded`); any param is an error.

By hand (for example to check the job after a deploy): `venv/bin/flask jobs enqueue price_alerts`, then
`venv/bin/flask jobs list`. Read the counts of the latest job (`price_date`, `lines_checked` = lines with a max
price, `cards_checked` = user + card targets, `alerts_created`, `skipped_no_price` = targets without a price):

```bash
venv/bin/flask shell <<< "from app.models import RbJob as J; j = J.query.filter_by(rbjob_kind='price_alerts').order_by(J.rbjob_id.desc()).first(); print(j.rbjob_id, j.rbjob_status, j.rbjob_result or j.rbjob_message)"
```

Expected: `success`, `price_date` = the date of the last load, and on a second run the same day
`alerts_created: 0`. Install: no migration (`0027_jobs_price_alerts` must already be applied), restart the
service and rebuild the frontend; the first alerts come with the next `daily_prices` run. Rollback: revert the
code; the alerts already raised stay in `rbwishlistalerts` (harmless; the 0026 downgrade would drop them with
the wishlists, so only with the owner's go-ahead).

### Session purge (F9-a)

Every sign-in is a row of `rbsessions` (F9-a). Ended rows stay until they are purged: revoked ones (logout,
"sign out" of a device, a password change, `flask users block|set-password`), remembered ones past their
30 days and the others idle for 12 hours. The `sessions_purge` job (timeout 300 s, no params) deletes them
and returns `{purged: n}`; active sessions are never touched. `riftbound-sessions-purge.timer` starts
`riftbound-sessions-purge.service` every day at 04:15 Europe/Madrid (`Persistent=true`), which queues it
with `flask jobs enqueue sessions_purge --unless-succeeded-today`; the job runner (`riftbound-jobs.timer`)
runs it.

Install (sudo, after migration `0029_sessions` is applied) and check:

```bash
sudo cp docs/systemd/riftbound-sessions-purge.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now riftbound-sessions-purge.timer
systemctl list-timers riftbound-sessions-purge.timer          # next run
venv/bin/flask sessions purge --dry-run                       # "Would purge <n> session(s)", deletes nothing
venv/bin/flask jobs enqueue sessions_purge                    # one run now, then:
venv/bin/flask jobs list                                      # sessions_purge success, result {purged: n}
```

`venv/bin/flask sessions purge` runs the same purge at once without the job runner.

Rollback: `sudo systemctl disable --now riftbound-sessions-purge.timer && sudo rm
/etc/systemd/system/riftbound-sessions-purge.{service,timer} && sudo systemctl daemon-reload`. Before a
downgrade of `0029_sessions` delete the jobs of this kind
(`DELETE FROM riftbound.rbjobs WHERE rbjob_kind = 'sessions_purge'`; the downgrade refuses while they
exist), then `venv/bin/flask db downgrade 0028_legacy_schema_cleanup` and redeploy the previous commit:
the downgrade drops every session, so every user signs in again once more.

## Server-side sessions (F9-a, migration 0029)

Revision `0029_sessions` adds `rbsessions` and the `sessions_purge` job kind. The identity in the session
and remember cookies changes from a plain user id to `s:<token>`, so **every user signs in again once**
after the deploy (old cookies load as anonymous; the app shows its login screen, then stays signed in).
Announce it to the users before the deploy. Order, with the owner's go-ahead:

```bash
venv/bin/python scripts/db_backup.py          # pg_dump first; check the new file in ~/backups/rbapp
git pull --ff-only                            # the F9-a code
venv/bin/flask db upgrade                     # 0029_sessions
venv/bin/flask db check                       # "No new upgrade operations detected."
# restart the service at once (command in ops.local.md): the new code reads rbsessions
```

Then install the purge timer ("Session purge (F9-a)" above) and run the live checks of
`docs/requirements/F9/F9-a-sessions.md`. Rollback: as in "Session purge (F9-a)".

## Legacy schema cleanup (F11-f, migration 0028)

The decks v2 copy (F5-c, `flask decks migrate`) is history: the command, the `RbDeck` model and the
copy service were removed in F11-f, and revision `0028_legacy_schema_cleanup` drops `rbdecks`, the
provenance columns `rbdkh_legacy_name` / `rbdkv_legacy_id`, `rbcol_playset`, `rbcar_banned` and
`rbprf_lang` (D-F11-9). **Data loss**: those rows and values are gone (dev had 3 `rbdecks` rows, all
copied to v2; a production data reset follows); the downgrade re-creates the structure only. The
previous code reads the dropped columns, so restart right after the upgrade. Order, with the owner's
go-ahead:

```bash
venv/bin/python scripts/db_backup.py          # pg_dump first; check the new file in ~/backups/rbapp
git pull --ff-only                            # the F11-f code
venv/bin/flask db upgrade                     # 0028_legacy_schema_cleanup
venv/bin/flask db check                       # "No new upgrade operations detected."
# restart the service at once (command in ops.local.md): the old code reads the dropped columns
cd frontend && npm ci && npm run build && npm run check:dist   # the frontend changed too
```

Rollback: check out the previous code, `venv/bin/flask db downgrade 0027_jobs_price_alerts` (structure
back, empty), restart; the values come back only by restoring the dump.

## Card images (from M-d)

Card images are not in git and not in the code tree. They live in the data directory set by
`CARD_IMAGES_DIR=<data dir>` in `.env` (absolute path, outside the checkout, owned by the service user; the
host value is in `ops.local.md`). Unset, the app uses `<project>/data/card-images` (git-ignored; dev and
tests only). Flask serves the directory at `/riftbound/media/cards/<folder>/<file>` (public, cached a
week); the admin upload and the Riot scraper write there. The app has no `/riftbound/static/` route
(Jinja retirement, PR 3/3): those URLs are 404. The Nginx template proxies every `/riftbound/` URL to
Flask, so the proxy needs no change.

- Backup: the data directory is the only copy of the scraped and uploaded images. Copy it with the
  database backup (`tar -C <data dir> -czf <backup folder>/card-images-<date>.tar.gz .`, private folder);
  F12 schedules it.
- Copy images from elsewhere: `venv/bin/flask images import-legacy [--source PATH]` copies every
  `<folder>/<file>` of `PATH` (default `app/static/images/cards`) into the data directory. It never
  overwrites a file and never deletes the source, so it can run any number of times; it prints
  `Copied <n>, skipped <m> existing, ignored <k>.`

### Deploy of M-d (before or together with the deploy that pulls the M-d commit)

The M-d commit removes the tracked images from git, so the next `git pull` deletes them from the
checkout. Copy first.

1. **Before pulling**: create the data directory (outside the checkout), owned by the service user, and
   copy the images: `cp -a <checkout>/app/static/images/cards/. <data dir>/`. If the pull already
   happened, the files are gone from the checkout: restore them from the previous commit with
   `git -C <checkout> archive <old sha> app/static/images/cards | tar -x -C /tmp/cards-restore` and run
   `venv/bin/flask images import-legacy --source /tmp/cards-restore/app/static/images/cards`.
2. Set `CARD_IMAGES_DIR=<data dir>` in `.env`, deploy, restart, then run `venv/bin/flask images
   import-legacy` (copies 0 if step 1 was done; it also picks up the untracked images the Riot scraper
   left in the checkout).
3. Live check: open the app's Cards page; its images load from `/riftbound/media/cards/…`;
   `curl -sI <URL>/riftbound/media/cards/ogn/ogn_1.png` → 200 with `Cache-Control: public, max-age=604800`.

Rollback: revert the PR and redeploy; the revert puts the tracked images back in the checkout and the
pages read `/riftbound/static/images/cards/...` again. Images added after the deploy exist only in the data
directory: copy them back first (`cp -a <data dir>/. <checkout>/app/static/images/cards/`). Leave the data
directory in place.

### Product images (F14-d)

Product images follow the card image rules: not in git, not in the code tree. They live in
`PRODUCT_IMAGES_DIR=<data dir>` in `.env` (absolute path, outside the checkout, owned by the service
user, a different directory from `CARD_IMAGES_DIR`; the host value is in `ops.local.md`). Unset, the app
uses `<project>/data/product-images` (git-ignored; dev and tests only); a relative path stops the app
(`PRODUCT_IMAGES_DIR must be an absolute path`). The files sit directly in the directory as
`<product id>.<png|jpg|webp>`, written only by the admin upload (`POST /admin/products/<id>/image`);
Flask serves them at `/riftbound/media/products/<file>` (public, cached a week). No proxy change.

- Install (with the F14-d deploy): create the directory, owned by the service user, set
  `PRODUCT_IMAGES_DIR` in `.env`, restart. The app creates the directory on the first upload if it is
  missing, but only with the right owner if the parent allows it, so create it first.
- Backup and copies: same rules as the card images. Copy the directory with the database backup
  (`tar -C <data dir> -czf <backup folder>/product-images-<date>.tar.gz .`); when moving it, copy
  without overwriting (`cp -an <old dir>/. <new dir>/`) and never delete the source. A file copied in by
  hand is not shown until the product's `rbpdt_image` names it: add new images through the admin upload.
- Live check: upload an image on a product in the admin; `curl -sI <URL>/riftbound/media/products/<id>.png`
  → 200 with `Cache-Control: public, max-age=604800`.

## Avatars (F9-c)

Profile photos are user data: not in git, not in the code tree, never public. They live in
`AVATAR_DIR=<data dir>` in `.env` (absolute path, outside the checkout, owned by the service user, a
different directory from `CARD_IMAGES_DIR` and `PRODUCT_IMAGES_DIR`; the host value is in
`ops.local.md`). Unset, the app uses `<project>/data/avatars` (git-ignored; dev and tests only); a
relative path stops the app (`AVATAR_DIR must be an absolute path`). Each avatar is two files
directly in the directory, `<user id>-<version>-256.webp` and `<user id>-<version>-64.webp`, written
only by `POST /riftbound/api/v1/me/avatar` (mode 600, through a temporary `.upload-*.tmp` name in the
same directory and `os.replace`) and served by Flask only to signed-in users at
`/riftbound/api/v1/users/<id>/avatar` (private cache). Nginx never serves the directory: no proxy
change, and do not add an alias for it.

- Install (with the F9-c deploy): `venv/bin/pip install -r requirements.txt` (adds Pillow) **before**
  the restart, otherwise the app does not start (`ModuleNotFoundError: PIL`). Create the directory,
  owned by the service user and writable by it, not readable by others
  (`install -d -m 700 -o <service user> -g <service group> <data dir>`), set `AVATAR_DIR` in `.env`
  (or keep the default), restart. The app creates the directory on the first upload if it is missing,
  but only with the right owner if the parent allows it, so create it first. No migration.
- Permissions: the service user needs read, write and delete in the directory (an upload replaces the
  previous version's files; a failed delete is only logged, `could not delete avatar file ...`, and
  leaves a stale file that nothing serves).
- Backup: the nightly backup (`scripts/db_backup.py`) dumps the database only; it does **not** copy
  `AVATAR_DIR`. The directory is the only copy of the photos: copy it with the database backup
  (`tar -C <data dir> -czf <backup folder>/avatars-<date>.tar.gz .`, private folder, personal data);
  F12 schedules it with the image directories. Restoring files without the matching database rows (or
  the reverse) only shows no avatar (404) for those users; nothing breaks.
- Stray files: `.upload-*.tmp` files are left only if the process dies mid-write; they and files of
  versions no row names can be deleted at any time.
- Live check (after the deploy): `POST /riftbound/api/v1/me/avatar` with a phone photo → 200
  `{avatar_url}`; that URL answers `image/webp` 256x256 to a second signed-in account; a private window
  gets 401.
- Rollback: revert the PR, redeploy (Pillow can stay installed). Uploaded files stay in `AVATAR_DIR`,
  harmless; the profile rows keep the stem and version (the reverted code ignores them).

## Two-factor key (F9-d)

TOTP secrets (`rbusermfa.rbmfa_secret_enc`) are stored only encrypted with the Fernet key
`TOTP_ENCRYPTION_KEY`. The database alone cannot produce a code; the key alone holds no secret. Keep
them apart.

- Generate the key once, on the server, printed to the terminal only (never to a file in the checkout,
  never pasted into chat, an issue or git):

  ```bash
  venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```

  It is 44 characters of URL-safe base64 (32 bytes).
- Put it only in the service environment file (the file the systemd unit's `EnvironmentFile` names, or
  the environment file of the deployed checkout on the dev server; `ops.local.md` says which), as
  `TOTP_ENCRYPTION_KEY=<key>`, mode 600/640 owned by root or the service user, **before** the restart
  that brings the F9-d code. Every process that runs the app needs the same value (gunicorn and the
  `flask` CLI and timers use the same file).
- Startup: in production a missing key stops the app with `ConfigError` "TOTP_ENCRYPTION_KEY is
  missing", an invalid one with "TOTP_ENCRYPTION_KEY is not a valid key" (the value is never printed).
  In development a missing key only logs a warning and two-factor authentication is unavailable
  (`GET /riftbound/api/v1/me` → `security.mfa.available: false`; the `/me/2fa/*` routes answer 503); an
  invalid one stops the app too.
- Backup: copy the key to the owner's password manager (or another offline place) **apart from** the
  database dumps; a dump and the key together are enough to read every user's TOTP secret. The nightly
  backup does not copy it.
- Lost or changed key: every stored secret becomes unreadable. Signed-in users with 2FA get 503
  "Two-factor authentication is not available" on the 2FA routes and on `POST /me/reauth` with a code
  (logged as `The TOTP secret of user <id> cannot be decrypted`, never the secret). Recovery: set a new
  key, restart, then remove each affected user's 2FA with `venv/bin/flask users reset-2fa <username>`
  (it also ends all their sessions); users set 2FA up again. A user can also turn it off with one of
  their recovery codes, which does not need the key. There is no key rotation tool yet.
- Admin reset (lost phone and codes): `venv/bin/flask users reset-2fa <username>` →
  `Two-factor authentication removed for '<username>'; <n> session(s) ended` (`'<username>' has no
  two-factor authentication` when it is off; nothing changes then). Until F10 this is the only way.
- Live check (after the deploy): `GET /riftbound/api/v1/me` → `security.mfa.available: true`; with an
  authenticator app: setup → enable with a code → 10 recovery codes; disable with a recovery code.
- Rollback: revert the PR and `venv/bin/flask db downgrade -1` (drops `rbusermfa` and
  `rbrecoverycodes`: every user's 2FA is lost; owner's go-ahead). The key can stay in the environment
  (the reverted code ignores it). The packages can stay installed.

## Jinja retirement (PR 3/3)

The Jinja web (landing, dashboard, auth forms, sets, cards, collection, decks, price tools, profile,
templates, static assets) is removed; `/`, `/riftbound`, `/riftbound/` and the old page URLs answer a 302 to
the app (table in AGENTS.md → "Old URLs"). No migration, no data change; the legacy tables stay until F11.

- Deploy: the usual "Deploy after a merge" (`requirements.txt` changed only by dropping `beautifulsoup4`, so
  `pip install` changes nothing; no frontend rebuild is needed: only the dev proxy line of
  `frontend/vite.config.ts` changed), then restart.
- `.env`: `LANDING_CACHE_TTL` is no longer read; remove it if present (harmless otherwise).
- Nginx: **no change needed** when it proxies `/` and `/riftbound/` whole to Flask, as `docs/nginx_config`
  does. Only a proxy that serves `/riftbound/static/` from disk, or keeps a separate landing app at `/`, needs
  that block removed (check `ops.local.md`). The `limit_req` line for `POST /riftbound/(login|register)` of
  older copies of the template is now dead (those URLs answer 405) and may stay.
- Live checks:
  - `curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' <URL>/` → `302 <URL>/riftbound/app/`
  - the same for `<URL>/riftbound/` → `/riftbound/app/`, `<URL>/riftbound/collection` →
    `/riftbound/app/collection`, `<URL>/riftbound/login?next=%2Friftbound%2Fcollection` →
    `/riftbound/app/login?next=%2Friftbound%2Fcollection`
  - `<URL>/riftbound/nope` → 404 with the small "Back to the app" page; `<URL>/riftbound/static/css/style.css`
    → 404
  - sign in through the app, open a bookmark of an old page: it lands on the matching app screen.
- Rollback: revert the PR and deploy again (no data to restore).

## Never

- Commit or print `.env`, the database URL, passwords or keys. Write IPs, hostnames or domains in a
  tracked file.
- Run migrations without a backup. Edit the database by hand.
- Push to `main`, force-push, or merge PRs (the owner merges).
- Change the proxy, firewall or other hosts.
