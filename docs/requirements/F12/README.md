# F12: Production — phase spec

Status: planned · Depends on: F11 (feature complete, Jinja retired), F1-g (CSP report-only data), the timers of F4/F8/F9/F10 · Source: roadmap §2 ("Despliegue"), §5 (F12), §8, product.md ("There is no production yet", F12 scope), F0 follow-up 4.31 (state.md), `docs/frontend.md` and `docs/nginx_config` (items deferred to F12)

This is an operations phase. Requirements are grouped by concern; code and documentation work is cut into
units for gentle-shell; steps that only the owner can do (accounts, DNS, servers, firewall, proxy, legal
texts, secrets) are marked **USER**. Nothing in the repo may contain the final domain, server addresses,
credentials or keys: documents use placeholders such as `<BASE_URL>`, `<SERVER>`, `<DB_NAME>`.

## Goal

Run Rift Manager in production for real users: a final URL over HTTPS, a production server and a production
database built from Alembic, new secrets, scheduled jobs, backups with a tested restore, monitoring and
alerting, sane logs, an enforcing Content Security Policy, a repeatable release and rollback procedure, and a
licensing/privacy review. Optionally carry over the owner's data and the curated Cardmarket mappings.

## Current state

- **No production exists**; the current server and database are development (product.md). The dev host
  layout: public Nginx with TLS on another host (changed only by the owner), Gunicorn from the deployed
  checkout, PostgreSQL with a dedicated non-superuser role owning schema `riftbound` (state.md).
- **Service template** `docs/riftbound.service`: `gunicorn --workers 3 --bind 0.0.0.0:8000 run:app`, default
  timeout (30 s), user `www-data`, `EnvironmentFile=/etc/riftbound/riftbound.env` (mode 640).
- **Proxy template** `docs/nginx_config`: HTTP→HTTPS redirect, `limit_req_zone rb_auth` (20 r/min, burst 10)
  for POSTs to login/register/API auth, `X-Frame-Options`, `nosniff`, proxy headers required by ProxyFix
  (1 hop) and the CSRF Referer check; HSTS and gzip only as comments. **It contains the real dev domain and
  certificate paths**, which AGENTS.md forbids in tracked files (fix in F12-f).
- **Config** (`config.py`, `.env.example`): `RB_ENV` defaults to production; `SECRET_KEY` (≥ 32, deny-list),
  `DATABASE_URL` required; DEBUG refused in production; cookies Secure in production; `RATELIMIT_STORAGE_URI`
  default `memory://` (per worker — the global limit is Nginx); `RB_VERSION` reported by `GET /health`
  (which runs `SELECT 1`, 503 without DB); `FRONTEND_DIST`; `CARDMARKET_ALLOWED_HOSTS`; ALTCHA key derived
  from `SECRET_KEY` when unset. Later phases add `SPA_CSP` (F1-g), VAPID keys (F4), `TOTP_ENCRYPTION_KEY`,
  `OAUTH_*`, `AVATAR_DIR` (F9).
- **Deploy** (`docs/knowledge/ops-runbook.md`, `docs/frontend.md`): `git pull`, pip, backup + `flask db
  upgrade`/`check`, `npm ci && npm run build` on the server (the build empties `dist`, so the app answers 503
  for a few seconds; atomic swap deferred to F12), restart. PWA rollback = self-destroying worker build.
- **CI** (`.github/workflows`): `ci.yml` (pytest, PostgreSQL 18 migrations round trip, frontend lint/
  typecheck/test/build/check + `frontend-dist` artifact kept 7 days), `security.yml` (bandit daily),
  `release.yml` (manual tag + GitHub release, no artifacts).
- **Logging**: Flask's default logger to stderr (journald); no request id, no structured format.
- **Data on disk**: card images under `app/static/images/cards/` inside the checkout (about 377 files tracked
  in git, more written by the Riot scraper); avatars under `AVATAR_DIR` (F9).
- **Open F0 follow-up 4.31**: live Nginx `limit_req` burst test and LOGIN-5 timing sample (state.md).

## Scope

In: hosting plan and provisioning runbook; TLS; production Nginx template; Gunicorn and logging config;
secrets; production database and roles; scheduled jobs on the new host; backups and restore drill;
monitoring and alerting; CSP enforcing and security headers; rate-limit storage decision; release
artifacts and deploy script with atomic frontend swap; PWA/push/OAuth on the final origin; licensing and
privacy pages; optional data migration; go-live and rollback checklists.

Out: multi-server / high availability, containers or orchestration, CDN (possible later), paid
monitoring, e-mail delivery (no mail server, product.md), app store packaging.

## Decisions already taken

- Production is F12; HTTPS mandatory, certbot / Let's Encrypt (roadmap §2).
- New production secrets; production DB built only by Alembic (product.md F12; AGENTS.md "Database
  Changes"). Secrets only in environment variables, never in the repo or chats.
- Flask serves the SPA build, not Nginx (product.md "Architecture decisions"; F1 D1 — Nginx static serving
  of `assets/` was deferred to F12 as an option).
- Scheduled work = Flask CLI + systemd timers, no Celery/Redis (cross-phase contract, F4).
- PWA identity: manifest id/scope `/riftbound/`, start URL `/riftbound/app/`, worker scope `/riftbound/app/`,
  update prompt, rollback by self-destroying build (product.md "PWA").
- gentle-shell never changes the proxy, firewall or other hosts, never prints secrets (ops-runbook "Never").

## Requirements

### Hosting and network
- **F12-R1** The production host runs Linux LTS with Python 3.12, PostgreSQL 18, Nginx and systemd; Node 24
  only if the frontend is built there (D-F12-11). Sizing baseline: 2 vCPU, 4 GB RAM, 40 GB SSD (DB, card
  images, avatars, local backups) — D-F12-2.
- **F12-R2** Firewall: only 80/443 public; SSH key-only from restricted sources; PostgreSQL listens on
  localhost only; Gunicorn binds `127.0.0.1` or a unix socket when Nginx is on the same host (USER).
- **F12-R3** The app runs as a dedicated system user; the code tree is read-only for it; writable data
  directories are explicit (avatars, card images, frontend dist if built there, backups) — D-F12-8.

### TLS and proxy
- **F12-R4** Certificates by certbot with automatic renewal; TLS 1.2+; HTTP→HTTPS 301; HSTS
  `max-age=31536000` once every check passes (no preload at first) (USER applies, template in the repo).
- **F12-R5** `docs/nginx_config` becomes a generic production template with placeholders only (`<SERVER_NAME>`,
  certificate paths built from it): gzip for text/JS/CSS/JSON/SVG/manifest, `client_max_body_size 3m`
  (avatars/images ≤ 2 MB), `proxy_read_timeout 60s`, `limit_req` zones for auth POSTs (existing), OAuth
  start/callback, `POST /auth/mfa`, API-key requests and the ICS feed; a log format that drops query
  strings on `/riftbound/auth/oauth/` and masks the feed token path. `tests/test_nginx_config_doc.py` keeps
  checking the required directives.
- **F12-R6** The ProxyFix hop count matches the real topology (1 when Nginx is local); the proxy keeps
  `Host`, `X-Forwarded-For`, `X-Forwarded-Proto` and never strips `Referer` (CSRF check, AGENTS.md).

### Application server and logging
- **F12-R7** `gunicorn.conf.py` in the repo: workers (D-F12-17), `timeout 60`, `graceful_timeout 30`,
  `max_requests` with jitter, bind from env, access log off (Nginx logs access), error log to stderr. The
  systemd unit template uses it.
- **F12-R8** Application logs: one line per event with level, time (UTC), request id (`X-Request-ID` from
  Nginx or generated), method, path **without** query string, status, duration; never passwords, tokens,
  cookies, CSRF tokens, OAuth codes, API keys, TOTP codes or e-mail addresses. A test feeds a request with
  such values and asserts none reaches the log output.
- **F12-R9** Log retention: journald 30 days; Nginx logs rotated daily, kept 14 days (D-F12-12).

### Configuration and secrets
- **F12-R10** Production environment file (mode 640, owner root, group = service user) with **new** values
  (USER generates, never pasted anywhere): `SECRET_KEY`, `DATABASE_URL` (runtime role), `ALTCHA_HMAC_KEY`,
  `TOTP_ENCRYPTION_KEY`, VAPID public/private key + subject, `OAUTH_*` of the production OAuth apps,
  `RB_VERSION` (set by the deploy), `AVATAR_DIR`, `FRONTEND_DIST`, `SPA_CSP=enforce`, alert/heartbeat URLs.
- **F12-R11** `validate_settings` refuses to start in production when any secret a deployed feature needs is
  missing or weak (names only in the error): TOTP key valid, VAPID pair complete, each OAuth provider either
  fully configured or fully absent.
- **F12-R12** `.env.example` documents every variable added since F1 with safe defaults or empty values;
  `docs/production.md` lists which are required in production.

### Database
- **F12-R13** The production database is created empty and built with `flask db upgrade`; `flask db check`
  reports no drift; no dev dump is restored as a whole (D-F12-6).
- **F12-R14** Two roles (D-F12-13): a migration/owner role used only by the deploy for `flask db upgrade`,
  and a runtime role with DML on schema `riftbound` only; `pg_hba` allows local connections only.
- **F12-R15** PostgreSQL basics: `timezone=UTC`, `log_min_duration_statement` ≈ 500 ms, autovacuum on,
  connection limit ≥ workers × pool size + jobs + margin.

### Backups and restore
- **F12-R16** `scripts/backup.sh` (systemd service + timer, daily at night and before every migration):
  `pg_dump -Fc` of the database, plus the avatars and card-image directories; encrypted (D-F12-4); retention
  7 daily / 4 weekly / 6 monthly; copy off the host; heartbeat ping on success; non-zero exit and alert on
  failure. Backups never land inside the code tree.
- **F12-R17** `scripts/restore-check.sh` restores the newest backup into a scratch database whose name
  contains `restore_check`, runs `flask db check` against it, compares row counts of the main tables with
  production, prints a short report and drops the scratch DB. Quarterly restore drill (USER) recorded in
  `docs/production.md`.

### Monitoring and alerting
- **F12-R18** External uptime check of `GET /riftbound/api/v1/health` every 5 min (USER configures the
  service, D-F12-5).
- **F12-R19** Every scheduled job (Cardmarket load, value snapshot, push/watchlist, event import and
  reminders, sessions purge, account purge, jobs runner, backup, restore check) pings a heartbeat on success
  and its systemd unit has `OnFailure=` → an alert unit that posts job name, host alias and time to the alert
  webhook (no secrets, no log excerpts with personal data).
- **F12-R20** Daily checks with alerts: disk usage > 80 %, certificate expiry < 14 days, newest backup older
  than 26 h, Cardmarket load not successful today.

### Security headers and CSP
- **F12-R21** `SPA_CSP` accepts `enforce` (sends `Content-Security-Policy`) besides `report-only` and `off`;
  production uses `enforce` after a clean report-only period on dev (F1-g follow-up); the landing entry and
  the standalone error pages carry the same policy; the policy keeps `worker-src blob: data:` (ALTCHA) and
  allows nothing external.
- **F12-R22** All HTML responses: `X-Content-Type-Options: nosniff`, `Referrer-Policy:
  strict-origin-when-cross-origin`, `Permissions-Policy` (camera, microphone, geolocation off), framing
  denied via `frame-ancestors 'self'`; set once (app or Nginx, not both).

### Rate limits
- **F12-R23** Rate-limit storage per D-F12-3; whichever is chosen, the Nginx zones of F12-R5 are the global
  limit and the 4.31 burst test (25 POSTs → 429s) passes on production; LOGIN-5 timing sample recorded.

### Release and deploy
- **F12-R24** `release.yml` builds the frontend once, attaches `frontend-dist-<version>.tar.gz` and its
  SHA-256 to the GitHub release, and records the commit; versions are `vMAJOR.MINOR.PATCH`.
- **F12-R25** `scripts/deploy.sh <version>` (dry-run by default, `--apply` to act): checks out the tag,
  verifies the artifact checksum, installs Python deps, takes a backup if `migrations/` changed, runs
  `flask db upgrade` + `check` with the migration role, unpacks the build into a new directory and swaps it
  atomically (`mv`), sets `RB_VERSION`, restarts, runs smoke checks (`/health` version, app shell 200,
  `sw.js`, manifest type) and prints a summary. `--rollback <version>` redeploys a previous tag (no DB
  downgrade without the owner's go-ahead).
- **F12-R26** Dev remains the staging environment: every release is deployed to dev first and passes its live
  checks before production (D-F12-15).

### PWA, push, OAuth on the final origin
- **F12-R27** The final URL keeps the `/riftbound` base path (D-F12-1) so manifest, worker scope and every
  route stay unchanged; installs from the dev origin do not migrate (users install again; documented).
- **F12-R28** Production OAuth apps (or production redirect URIs) per `docs/oauth-setup.md` with `<BASE_URL>`
  = the final URL (USER, D-F12-9); VAPID keys generated for production (D-F12-10).

### Data and legal
- **F12-R29** Data carried from dev (D-F12-6) only through tested export/import commands: curated Cardmarket
  data (`rbcm_product_card_map`, `rbcm_ignored`, `rbcm_expansions`, `rbproducts`), and optionally the owner's
  collection, decks, sales and events. Catalog rebuilt by the Riot scraper job; prices by the Cardmarket job.
- **F12-R30** `docs/licensing.md`: fonts (OFL, licence files shipped with the build), third-party licences
  (from F11's generated list), Riot IP (card images, map background, names) under Riot's fan-content policy
  (free, no paywall, disclaimer from F11), Cardmarket price-guide terms, scraped sources and their terms,
  brand assets ownership, provenance of every image in `frontend/src/assets/` and the landing. Each line ends
  with "OK" or an action (USER reviews and signs off).
- **F12-R31** Privacy notice and terms pages in the app (`/riftbound/app/legal/privacy`, `/legal/terms`,
  public, ES/EN) with the owner's texts (D-F12-7): data stored (account, optional e-mail, approximate IP
  prefix in sessions, avatar, user content), purposes, retention, deletion (F9), contact; cookie notice:
  strictly necessary cookies only.

### Go-live
- **F12-R32** Go-live checklist executed and recorded in `state.md`: all units merged; dev staging green;
  production smoke checks; 4.31 burst test; PWA device checklist (Android, iOS, desktop) on the final URL;
  push test; OAuth sign-in with both providers; 2FA sign-in; restore drill done once; Lighthouse on the
  landing and the app; alerts tested by forcing one job failure.

## Data model changes

None planned. The production database is built by the existing revisions. Optional export/import commands
(F12-i) read and write existing tables only.

## Interfaces (instead of API)

| Kind | Name | Purpose |
|---|---|---|
| File | `gunicorn.conf.py` | Server settings (F12-R7). |
| File | `docs/nginx_config` | Generic production proxy template (F12-R5). |
| Files | `scripts/deploy.sh`, `scripts/backup.sh`, `scripts/restore-check.sh`, `scripts/check-host.sh` | Deploy, backup, restore drill, disk/cert/backup-age checks. |
| Units | `riftbound.service`, `riftbound-backup.{service,timer}`, `riftbound-restore-check.{service,timer}`, `riftbound-alert@.service`, the job timers of F4/F8/F9/F10 | systemd templates in `docs/systemd/`. |
| Env | `SPA_CSP=enforce`, `ALERT_WEBHOOK_URL`, `HEARTBEAT_URL_<JOB>`, `BACKUP_DIR`, `BACKUP_REMOTE`, `BACKUP_ENCRYPTION_RECIPIENT`, `RB_VERSION`, `CARD_IMAGES_DIR` (if D-F12-8) | Documented in `.env.example` / `docs/production.md`. |
| CLI | `flask data export` / `import` (F12-i, optional) | Carry curated/owner data from dev. |
| Pages | `/riftbound/app/legal/privacy`, `/riftbound/app/legal/terms` (P) | F12-R31. |

## Runbooks and checklists

`docs/production.md` (new) holds these, with placeholders only:

1. **Provisioning (USER)**: buy/choose domain and server (D-F12-1/2); DNS A/AAAA records; OS updates and
   unattended security upgrades; service user; firewall (F12-R2); PostgreSQL 18 install, database and two
   roles (F12-R14); Nginx + certbot (F12-R4/5); Python venv; directories and permissions (F12-R3).
2. **Secrets (USER)**: generate every value of F12-R10 on the server (commands in the doc, e.g.
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`), write the env file, never copy them to
   chats, tickets or the repo; store recovery copies in the owner's password manager.
3. **First deploy**: `scripts/deploy.sh <version> --apply` with an empty DB; create the owner account in the
   app; `flask users promote <owner>`; run the Riot sync and Cardmarket load jobs; import curated mappings
   (F12-R29); enable timers.
4. **Go-live** (F12-R32) and **rollback**: application rollback = `deploy.sh --rollback <prev>`; PWA rollback =
   self-destroying build (`docs/frontend.md`); database = restore from the pre-migration backup (owner decides).
5. **Restore drill** (quarterly) and **incident notes** (where logs are, how to read job status, who to
   contact).

## Units

| ID | Title | Depends on | Size | Risk | Summary |
|---|---|---|---|---|---|
| F12-a | Server config + logging | F11 | ~450 | Risk: item 5 + item 2 (runtime config; log redaction) | `gunicorn.conf.py`, request-id + redacted logging, security headers, `validate_settings` production checks, `.env.example`, unit template. |
| F12-b | CSP enforcing | F1-g, F11-b | ~300 | Risk: item 2 (a wrong policy breaks the app) | `SPA_CSP=enforce`, policy on landing and error pages, tests per entry, docs. |
| F12-c | Release artifacts + deploy script | F12-a | ~550 | Risk: item 5 (delivery pipeline) | `release.yml` artifact + checksum, `scripts/deploy.sh` (dry-run/apply/rollback, atomic swap, smoke checks), docs. |
| F12-d | Backups + restore check | F12-a | ~450 | Risk: item 1 + item 6 (data safety; off-site copy only testable live) | Backup/restore scripts, systemd templates, retention, encryption hook, docs. |
| F12-e | Monitoring + alerting | F12-d | ~400 | Risk: item 6 (alert delivery needs a live channel) | Heartbeats, `OnFailure` alert unit, `check-host.sh`, docs. |
| F12-f | Production proxy template + runbook | F12-a | ~400 | Risk: item 5 (proxy config consumed by the owner) | Generic `nginx_config` (no domain), zones, gzip, log masking, HSTS; `docs/production.md` provisioning/secrets/go-live sections. |
| F12-g | Data directories out of the code tree | F11, D-F12-8 | ~400 | Risk: item 1 + item 3 (moves files; image URLs used by the SW cache) | `CARD_IMAGES_DIR` (full images and F2-l thumbnails `app/static/images/card-thumbs/`), serving route or Nginx alias, scraper/upload/thumbnail writers use it, move script, stop tracking images in git (no history rewrite). |
| F12-h | Licensing + privacy pages | F11-c | ~400 | Risk: item 6 (legal review is human) | `docs/licensing.md`, legal pages (ES/EN, owner texts), font licence files in the build. |
| F12-i | Data export/import (optional) | F12-c, D-F12-6 | ~450 | Risk: item 1 (writes production data) | `flask data export` / `import` for curated Cardmarket tables and one user's data, idempotent, dry-run, tests on SQLite + PostgreSQL. |
| F12-j | Go-live record | all above + USER steps | ~150 | Risk: item 6 (live checks) | Run and record the go-live checklist, 4.31, PWA/push/OAuth checks; update `state.md`, `roadmap.md`. |

## Open decisions

| ID | Question | Options | Recommendation | Blocks |
|---|---|---|---|---|
| D-F12-1 | Final URL and base path | own domain + keep `/riftbound` / move the app to the domain root | Keep `/riftbound` (manifest id, worker scope and every route unchanged) | F12-f, F12-j |
| D-F12-2 | Server | self-hosted like dev / VPS | One VPS (or equivalent) running Nginx, app and PostgreSQL; size per F12-R1 | provisioning |
| D-F12-3 | Rate-limit storage | `memory://` + Nginx zones / local Valkey-Redis / memcached | `memory://` + Nginx zones; revisit if abuse is seen (no extra service) | F12-a, F12-f |
| D-F12-4 | Backup target, encryption, retention | off-site location; age/gpg; 7/4/6 | Encrypted (age) daily dumps, 7 daily/4 weekly/6 monthly, copy to a second location the owner controls | F12-d |
| D-F12-5 | Monitoring and alert channel | external uptime + heartbeat service / self-hosted; Discord webhook / phone push | Free external uptime + heartbeat service, alerts to a private Discord webhook | F12-e |
| D-F12-6 | Data from dev | fresh / curated Cardmarket data + owner's data / full copy | Fresh catalog and prices; carry curated Cardmarket mappings and, if wanted, the owner's data; no other dev accounts | F12-i |
| D-F12-7 | Privacy notice and terms | owner writes / planner drafts for approval | Planner drafts from the data inventory, owner approves; contact channel chosen by the owner | F12-h |
| D-F12-8 | Card images location (and committed images) | in the code tree (today) / data directory | Data directory outside the code tree; stop tracking images in git | F12-g |
| D-F12-9 | OAuth apps | separate production apps / add production redirect URIs to dev apps | Separate production apps (separate secrets) | F12-j |
| D-F12-10 | VAPID keys | new for production / reuse dev | New (subscriptions are per origin anyway) | F12-j |
| D-F12-11 | Where the frontend is built | CI release artifact / on the server | CI artifact (no Node on production) | F12-c |
| D-F12-12 | Log retention and IPs | 14 d Nginx, 30 d journald / other | As stated; IPs kept only in logs and as prefixes in sessions | F12-a, F12-f |
| D-F12-13 | Database roles | separate migration + runtime roles / one role | Separate roles | F12-c, provisioning |
| D-F12-14 | CSP violation reports | none / `report-to` endpoint | None (console during the dev report-only period); avoids a public write endpoint | F12-b |
| D-F12-15 | Staging | dev as staging / separate staging | Dev as staging | F12-c |
| D-F12-16 | Who runs host-level steps | owner by runbook / gentle-shell over SSH | Owner (gentle-shell prepares scripts and docs; runbook "Never" rules stand) | all USER steps |
| D-F12-17 | Gunicorn workers | `2×CPU+1` / fixed 3 | `2×CPU+1` capped by RAM (≈ 150 MB per worker) | F12-a |

## Risks and notes

- **Long requests**: F10 moves Cardmarket/Riot work to the job runner; if not, a 60 s timeout will cut them.
- **Per-worker limits**: with `memory://`, app limits multiply by the worker count; the Nginx zones are the
  real global limit (keep them stricter than the app's).
- **Secrets hygiene**: the dev git history contains old credentials that were rotated (F0); production uses
  new values only. Never reuse dev keys.
- **Tracked files with host data**: the dev Nginx template (`docs/nginx_config`) and the archived F0 tasks
  contain the dev domain; F12-f makes the template generic (the archive stays as history unless the owner
  wants it scrubbed).
- **PWA origin change**: dev installs keep pointing at dev; announce the new URL; consider the self-destroying
  build on dev once production is live if dev must stop being used by real users.
- **Legal**: Riot IP use is allowed only for free fan content with the disclaimer; any monetisation is out.
