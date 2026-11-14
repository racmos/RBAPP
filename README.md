# Rift Manager

Web application to manage the Riftbound trading card game: user accounts, card sets and cards, your collection, decks and Cardmarket prices. Flask + PostgreSQL serve a JSON API (`/riftbound/api/v1`) and the React app at `/riftbound/app/` (the old Jinja web was retired; its URLs redirect to the app).

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
| `CAPTCHA_PROVIDER` | `altcha` (default) or `none`; ALTCHA on register |
| `SPA_CSP` | `report-only` (default) or `off`: the `Content-Security-Policy-Report-Only` header of the new app (see `docs/frontend.md`) |
| `ALTCHA_HMAC_KEY`, `ALTCHA_EXPIRE_SECONDS`, `ALTCHA_MAX_NUMBER` | ALTCHA signing key, challenge lifetime and difficulty |
| `LOGIN_MAX_FAILURES`, `LOGIN_LOCK_BASE_MINUTES`, `LOGIN_LOCK_MAX_MINUTES` | Account lockout (5 failures, 15 minutes, doubling up to 24 hours) |
| `CARDMARKET_ALLOWED_HOSTS` | Hosts the Cardmarket loader may download from |
| `RB_LEGACY_BACKUP_DIR` | Where migration 0002 saves the legacy tables (contains personal data, never commit) |
| `FRONTEND_DIST` | Directory with the built new app, served at `/riftbound/app/` (default `<project>/frontend/dist`; see [New app hosting](#new-app-hosting)) |
| `CARD_IMAGES_DIR` | Absolute path of the card images data directory (`ogn/`, `ogs/`, ...), served at `/riftbound/media/cards/` and written by the admin upload and the Riot scraper (default `<project>/data/card-images`, git-ignored; a relative path stops the app). The images are not in git; `flask images import-legacy` copies the old `app/static/images/cards/` tree in |
| `PRODUCT_IMAGES_DIR` | Absolute path of the product images directory, served at `/riftbound/media/products/` and written by the admin upload (default `<project>/data/product-images`, git-ignored; a relative path stops the app) |
| `AVATAR_DIR` | Absolute path of the avatars directory: two WebP files per user (256 and 64 px), written by `POST /riftbound/api/v1/me/avatar` and served to signed-in users only (default `<project>/data/avatars`, git-ignored; a relative path stops the app; created on the first upload) |
| `TOTP_ENCRYPTION_KEY` | Fernet key (URL-safe base64 of 32 bytes) that encrypts the two-factor (TOTP) secrets. Required in production; in development unset means two-factor authentication is unavailable. Generate it with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`, keep it only in the service environment and back it up apart from the database dumps: losing it means every user's 2FA must be reset (see `docs/knowledge/ops-runbook.md`) |

## Running

```bash
python run.py        # http://127.0.0.1:5000/riftbound (loopback only, debug off)
```

The application is at `/riftbound/app/` (build it first, see [New app hosting](#new-app-hosting)); `/` and `/riftbound/` redirect there until the new landing page (F8).

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
npm run icons          # regenerate the committed PWA icons in frontend/public (only when the brand mark changes)
```

`npm run lint`, `npm run typecheck` and `npx vitest run` are what CI runs besides the build.

The app is an installable PWA called "Rift Manager" (service worker at `/riftbound/app/sw.js`, scope `/riftbound/app/`). Install, update, offline behaviour, the device checklist and how to roll the service worker back (`VITE_PWA_SELF_DESTROY=true`) are in [docs/frontend.md](docs/frontend.md).

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
flask users block <username>        # refuse logins and end every session
flask users unblock <username>
flask users set-password <username> # hidden prompt; ends every session of the user
flask users unlock <username>       # clear a login lockout
flask users list
flask users reset-2fa <username>    # remove two-factor authentication; ends every session of the user
flask sessions purge [--dry-run]    # delete the ended sign-in sessions (also a daily job)
```

## JSON API

`/riftbound/api/v1`: `GET /health`, `GET /meta/config`, `GET /auth/session`, `GET /auth/captcha`, `POST /auth/login`, `POST /auth/mfa`, `POST /auth/logout`, `POST /auth/register`, `GET /me/prefs`, `PATCH /me/prefs`. Responses are `{"success": true, "data": ...}` or `{"success": false, "error": "...", "message": "..."}`; an error may add a machine-readable `code` and `params`. Unsafe requests need the `X-CSRFToken` header; read the token from `GET /auth/session`, which also returns the signed-in user's `prefs` (interface preferences, `null` = Auto). `POST /auth/login` accepts `remember: true` to keep the session for 30 days; for an account with two-factor authentication on it answers `{"mfa_required": true, ...}` and `POST /auth/mfa` with a code finishes the sign-in. Details are in `AGENTS.md`.

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
- Nginx template: [docs/nginx_config](docs/nginx_config). One Flask app serves `/` (a redirect to the app for now) and `/riftbound/`. The proxy must send `Host`, `X-Forwarded-For` and `X-Forwarded-Proto` and must not strip `Referer`; the app trusts exactly one proxy hop.
- Firewall port 8000 so only the Nginx host can reach Gunicorn.
- To upgrade: back up the database, `pip install -r requirements.txt`, `flask db upgrade`, `flask db check`, restart the service. Order matters; follow [docs/migrations.md](docs/migrations.md).
