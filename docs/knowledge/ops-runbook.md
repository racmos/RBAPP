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
- Users: `venv/bin/flask users list|promote|demote|block|unblock|unlock|set-password <username>`.
- Schema snapshot (structure only): `venv/bin/flask schema snapshot`.
- Card bans per game mode (F2-a; the only way to change them until the F10 admin UI; a ban covers every
  printing of the name):
  - `venv/bin/flask bans list [--mode 1v1|2v2]`
  - `venv/bin/flask bans add "<card name>" --mode 1v1|2v2|all [--since YYYY-MM-DD] [--reason "<text>"] [--force]`
    (the name must exist in the catalog unless `--force`; running it again changes nothing)
  - `venv/bin/flask bans remove "<card name>" --mode 1v1|2v2|all`
- Nginx (public reverse proxy, TLS) runs on another host and is changed only by the owner. The template is
  `docs/nginx_config`.

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
`heartbeat` (diagnostic, 60 s timeout) and `daily_prices` (daily Cardmarket load, 1800 s timeout, F4-b below).

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

The legacy Jinja button "Extraer cartas Riot" now only queues the job
(`POST /riftbound/price/extract-riot-cards` → `{"success": true, "job_id": n, …}`; 409
`{"success": false, "message": "Ya hay una sincronización en curso."}` when one is active);
"refresh Riot sets" stays read only.

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
table and its history. downgrading the migrations (owner's go-ahead only) drops the change
table and its history. The 0012 downgrade refuses while `riot_sync` jobs exist, so delete them first
(`DELETE FROM riftbound.rbjobs WHERE rbjob_kind = 'riot_sync';`), then
`venv/bin/flask db downgrade 0011_card_changes` (runs the 0012 and 0011 downgrades).

## Card images (from M-d)

Card images are not in git and not in the code tree. They live in the data directory set by
`CARD_IMAGES_DIR=<data dir>` in `.env` (absolute path, outside the checkout, owned by the service user; the
host value is in `ops.local.md`). Unset, the app uses `<project>/data/card-images` (git-ignored; dev and
tests only). Flask serves the directory at `/riftbound/media/cards/<folder>/<file>` (public, cached a
week); the admin upload and the Riot scraper write there. The old `/riftbound/static/images/cards/...`
URLs no longer serve the images. The Nginx template proxies every `/riftbound/` URL to Flask, so the
proxy needs no change.

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
3. Live check: open a Jinja catalog page; its images load from `/riftbound/media/cards/…`;
   `curl -sI <URL>/riftbound/media/cards/ogn/ogn_1.png` → 200 with `Cache-Control: public, max-age=604800`.

Rollback: revert the PR and redeploy; the revert puts the tracked images back in the checkout and the
pages read `/riftbound/static/images/cards/...` again. Images added after the deploy exist only in the data
directory: copy them back first (`cp -a <data dir>/. <checkout>/app/static/images/cards/`). Leave the data
directory in place.

## Never

- Commit or print `.env`, the database URL, passwords or keys. Write IPs, hostnames or domains in a
  tracked file.
- Run migrations without a backup. Edit the database by hand.
- Push to `main`, force-push, or merge PRs (the owner merges).
- Change the proxy, firewall or other hosts.
