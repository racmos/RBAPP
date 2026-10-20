# Rift Manager

Web application to manage the Riftbound trading card game: user accounts, card sets and cards, your collection, decks, Cardmarket prices, and a public landing page. Flask + PostgreSQL, with a JSON API (`/riftbound/api/v1`) for a future React client.

Developer and agent conventions live in [AGENTS.md](AGENTS.md); the migration runbook in [docs/migrations.md](docs/migrations.md).

## Setup

You need Python 3.12 and a PostgreSQL database (schema `riftbound`, created by the migrations).

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then edit it: DATABASE_URL and, optionally, SECRET_KEY
flask db upgrade              # creates the schema riftbound and every table
flask users promote <username> # after registering your first account in the browser
```

`.env` is git-ignored and is read only when `RB_ENV=development`. Never commit real values.

## Environment variables

Settings come from environment variables only (see [.env.example](.env.example), which lists every one with its default).

| Variable | Meaning |
|----------|---------|
| `RB_ENV` | `development`, `testing` or `production` (unset = production) |
| `SECRET_KEY` | 32+ random characters. Required outside development; weak or default keys are refused. In development a random one is generated per process |
| `DATABASE_URL` | `postgresql+psycopg://user:password@host:5432/riftbound` (required) |
| `RB_HOST`, `RB_PORT` | Bind address of `python run.py` (default `127.0.0.1:5000`) |
| `FLASK_DEBUG` | `1` enables the Werkzeug debugger; refused when `RB_ENV=production` |
| `RB_VERSION` | Version reported by `GET /riftbound/api/v1/health` (default `dev`) |
| `PROXY_FIX_X_FOR`, `PROXY_FIX_X_PROTO`, `PROXY_FIX_X_HOST` | Trusted reverse-proxy hops (default 1 each) |
| `SESSION_COOKIE_SECURE`, `REMEMBER_COOKIE_SECURE` | Secure flag of the cookies (default: on in production only) |
| `WTF_CSRF_ENABLED` | CSRF protection kill switch (default on) |
| `RATELIMIT_ENABLED`, `RATELIMIT_STORAGE_URI` | Per-IP rate limits and their storage (default on, `memory://`) |
| `CAPTCHA_PROVIDER` | `altcha` (default) or `none`; ALTCHA on the register form |
| `ALTCHA_HMAC_KEY`, `ALTCHA_EXPIRE_SECONDS`, `ALTCHA_MAX_NUMBER` | ALTCHA signing key, challenge lifetime and difficulty |
| `LOGIN_MAX_FAILURES`, `LOGIN_LOCK_BASE_MINUTES`, `LOGIN_LOCK_MAX_MINUTES` | Account lockout (5 failures, 15 minutes, doubling up to 24 hours) |
| `LANDING_CACHE_TTL` | Seconds the landing feeds are cached per worker (0 = off) |
| `CARDMARKET_ALLOWED_HOSTS` | Hosts the Cardmarket loader may download from |
| `RB_LEGACY_BACKUP_DIR` | Where migration 0002 saves the legacy tables (contains personal data, never commit) |
| `FRONTEND_DIST` | Directory with the built new app, served at `/riftbound/app/` (default `<project>/frontend/dist`; see [New app hosting](#new-app-hosting)) |

## Running

```bash
python run.py        # http://127.0.0.1:5000/riftbound (loopback only, debug off)
```

The landing page is at `/`; the application at `/riftbound`.

## Tests

```bash
pytest                                   # SQLite in memory, nothing else needed
pytest --cov=app --cov-report=term       # with coverage
```

The PostgreSQL tests (migrations on a real server) are skipped unless you point `TEST_POSTGRES_URL` at an empty database whose name contains `test`:

```bash
TEST_POSTGRES_URL=postgresql+psycopg://user:password@localhost:5432/riftbound_test pytest -m postgres
```

CI (GitHub Actions) runs the suite on Python 3.12 and the PostgreSQL tests on PostgreSQL 18.

## Frontend

The React app in `frontend/` needs Node 24 (`.nvmrc`):

```bash
cd frontend
nvm use                # Node 24
npm ci
npm run dev            # Vite dev server, proxies the API to Flask on 127.0.0.1:5000
npm run build          # production build in frontend/dist
```

`npm run lint`, `npm run typecheck` and `npx vitest run` are what CI runs besides the build.

## Database migrations

The schema is built and changed only by Alembic (`flask db ...`); see [docs/migrations.md](docs/migrations.md) for the full runbook, including how to back up first.

```bash
flask db upgrade                    # apply every pending revision
flask db check                      # must report no drift between models and migrations
flask db migrate -m "what changed"  # new revision: read the generated file before committing
flask db downgrade -1               # undo the last revision
```

## Admin CLI

The first admin can only be created from the server shell; no request can grant the role.

```bash
flask users promote <username>      # make admin (aliases: make-admin)
flask users demote <username>       # remove admin (alias: revoke-admin)
flask users block <username>        # refuse logins and drop the session
flask users unblock <username>
flask users set-password <username> # hidden prompt
flask users unlock <username>       # clear a login lockout
flask users list
```

## JSON API

`/riftbound/api/v1`: `GET /health`, `GET /meta/config`, `GET /auth/session`, `GET /auth/captcha`, `POST /auth/login`, `POST /auth/logout`, `POST /auth/register`, `GET /me/prefs`, `PATCH /me/prefs`. Responses are `{"success": true, "data": ...}` or `{"success": false, "error": "...", "message": "..."}`; an error may add a machine-readable `code` and `params`. Unsafe requests need the `X-CSRFToken` header; read the token from `GET /auth/session`, which also returns the signed-in user's `prefs` (interface preferences, `null` = Auto). `POST /auth/login` accepts `remember: true` to keep the session for 30 days. Details are in `AGENTS.md`.

## New app hosting

The React app (built from `frontend/`) is served by Flask itself at `/riftbound/app/`, from the directory in `FRONTEND_DIST` (default `frontend/dist`). Build it with:

```bash
cd frontend && npm ci && npm run build
```

Hashed files under `assets/` are cached for a year; `index.html`, `sw.js` and `manifest.webmanifest` always revalidate. A path without a file extension (a client route such as `/riftbound/app/account/interface`) gets `index.html`; a missing `.js`, `.css` or `.map` is a real 404. With no build, `/riftbound/app/` answers 503 and the rest of the application keeps working. Nginx needs no change. Build and deploy details: [docs/frontend.md](docs/frontend.md).

## Deployment

Production runs Gunicorn behind Nginx:

```bash
gunicorn --workers 3 --bind 0.0.0.0:8000 run:app
```

- systemd unit: [docs/riftbound.service](docs/riftbound.service). It reads the settings from `/etc/riftbound/riftbound.env` (mode 640, owner `root:www-data`) with at least `RB_ENV=production`, `SECRET_KEY` and `DATABASE_URL`.
- Nginx template: [docs/nginx_config](docs/nginx_config). One Flask app serves `/` (landing) and `/riftbound/`. The proxy must send `Host`, `X-Forwarded-For` and `X-Forwarded-Proto` and must not strip `Referer`; the app trusts exactly one proxy hop.
- Firewall port 8000 so only the Nginx host can reach Gunicorn.
- To upgrade: back up the database, `pip install -r requirements.txt`, `flask db upgrade`, `flask db check`, restart the service. Order matters; follow [docs/migrations.md](docs/migrations.md).
