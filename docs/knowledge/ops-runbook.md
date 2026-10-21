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

## Never

- Commit or print `.env`, the database URL, passwords or keys. Write IPs, hostnames or domains in a
  tracked file.
- Run migrations without a backup. Edit the database by hand.
- Push to `main`, force-push, or merge PRs (the owner merges).
- Change the proxy, firewall or other hosts.
