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
`heartbeat` (diagnostic, 60 s timeout).

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
  history; owner's go-ahead only).

The daily timers (`riftbound-daily.timer` at 06:30 and `riftbound-daily-retry.timer` at 08:00, both
Europe/Madrid) are templates only: do not install them before F4-b registers the `daily_prices` kind.

## Never

- Commit or print `.env`, the database URL, passwords or keys. Write IPs, hostnames or domains in a
  tracked file.
- Run migrations without a backup. Edit the database by hand.
- Push to `main`, force-push, or merge PRs (the owner merges).
- Change the proxy, firewall or other hosts.
