# Riftbound - Agent Instructions

## Workflow (read first)

This file is the single source of instructions for every AI agent on this repository (Claude Code, gentle-shell, Codex, Gemini, Copilot and others). `CLAUDE.md` only imports it; never put rules in an agent-specific file.

Work arrives as a unit requirement in `docs/requirements/F<n>/F<n>-<x>-<slug>.md` (format: `docs/requirements/TEMPLATE.md`), written by the planner (a Claude Project) from the phase spec `docs/requirements/F<n>/README.md`. The full cycle, roles and rules are in `docs/knowledge/workflow.md`.

- Before changing anything read `docs/knowledge/state.md` (status), `docs/knowledge/conventions.md` (rules) and the requirement's "Read first" list. `docs/knowledge/product.md` holds the owner's binding decisions.
- One requirement = one branch from up-to-date `origin/main` = one PR. Work in a git worktree, never in the deployed checkout (it serves the dev app; see `docs/knowledge/ops-runbook.md`).
- Strict TDD: observe the failing test before the code. Finish with every lane green (`pytest`; `cd frontend && npm run lint && npm run typecheck && npx vitest run && npm run build && npm run check:dist`).
- Update `docs/knowledge/state.md` in the same PR, plus this file and `docs/*.md` when structure, commands, endpoints or conventions change.
- Push, PR creation and merge are the owner's decisions; the owner merges. Deploy to dev only when asked, following `docs/knowledge/ops-runbook.md` and the local `ops.local.md` (git-ignored, never committed).
- A requirement that contradicts the code, `openspec/specs/` or `product.md`: stop and report instead of guessing.

## Project Overview

**Rift Manager** is a web application to manage the Riftbound trading card game:
- Authentication, profiles and roles (user / admin)
- Card sets and individual cards
- Personal collection tracking (quantities, foil, playsets, selling)
- Deck building and deck viewing
- Cardmarket prices (admin tools) and price resolution
- A public landing page (news, tournaments, videos, decks)
- A JSON API (`/riftbound/api/v1`) for the future React client

## Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.12 |
| Backend | Flask 3.1.0 |
| Database | PostgreSQL (schema `riftbound`); SQLite in memory for the tests |
| ORM | SQLAlchemy 2.0.36 + Flask-SQLAlchemy 3.1.1 (driver: psycopg 3.2.13) |
| Migrations | Alembic 1.20.0 through Flask-Migrate 4.1.0 |
| Auth | Flask-Login 0.6.3 |
| CSRF | Flask-WTF 1.3.0 |
| Rate limits | Flask-Limiter 4.1.1 (in-memory, per worker) |
| Captcha | altcha 2.3.0 (proof of work, vendored widget) |
| Validation | Pydantic 2.10.5 |
| Testing | pytest 8.3.4, pytest-cov 6.0.0 |
| Server | Gunicorn 23.0.0 behind Nginx |
| Frontend | React 19.3.0 + TypeScript 6.0.3 + Vite 8.3.2 in `frontend/` (Node 24, exact pins in `frontend/package.json`); tests with Vitest 5.0.3 |

The exact pins live in `requirements.txt`; if you change one, update this table (a unit that touches the pins re-creates the pin check, see Testing).

## Project Structure

```
riftbound/
├── app/
│   ├── __init__.py          # App factory, extensions (db, migrate, login, csrf, limiter), blueprints
│   ├── errors.py            # Error handlers + wants_json() (JSON or HTML negotiation)
│   ├── security.py          # admin_required / require_admin
│   ├── db_schema.py         # Schema name + Alembic options shared by the app and migrations/env.py
│   ├── api/                 # JSON API
│   │   ├── error_codes.py   # ErrorCode / DetailCode: machine-readable error `code`s
│   │   ├── responses.py     # ok() / fail() envelopes
│   │   └── v1/              # Blueprint api_v1 at /riftbound/api/v1
│   │       ├── __init__.py
│   │       ├── auth.py      # session, captcha, login, logout, register
│   │       ├── bans.py      # GET /bans (card bans per game mode)
│   │       ├── me.py        # GET/PATCH /me/prefs (interface preferences)
│   │       └── meta.py      # health, meta/config
│   ├── cli/                 # Flask CLI groups
│   │   ├── bans.py          # flask bans list|add|remove (card bans per game mode)
│   │   ├── jobs.py          # flask jobs enqueue|run-pending|list
│   │   ├── schema.py        # flask schema snapshot
│   │   └── users.py         # flask users promote|demote|block|unblock|set-password|list|unlock
│   ├── jobs/                # Background job kinds; the package is the single import point (create_app)
│   │   ├── registry.py      # JobKind(name, handler, timeout_seconds), register / get / names, JobFailed
│   │   ├── daily_prices.py  # daily_prices: Cardmarket load, validation, clear auto-match, review list (1800 s)
│   │   └── heartbeat.py     # heartbeat: diagnostic kind (60 s)
│   ├── models/              # SQLAlchemy models (Rb prefix)
│   │   ├── ban.py           # RbCardBan (rbcardbans): bans by card name and game mode
│   │   ├── user.py          # User (rbusers)
│   │   ├── set.py           # RbSet (rbset)
│   │   ├── card.py          # RbCard (rbcards)
│   │   ├── collection.py    # RbCollection (rbcollection)
│   │   ├── deck.py          # RbDeck (rbdecks)
│   │   ├── market.py        # RbCardMarket (rbcardmarket)
│   │   ├── cardmarket.py    # Rbcm* models (rbcm_* tables, Cardmarket loader) and RbProducts (rbproducts)
│   │   ├── captcha.py       # RbCaptchaUsed (rbcaptcha_used)
│   │   ├── job.py           # RbJob (rbjobs): job queue and results, one active job per kind
│   │   └── prefs.py         # RbUserPrefs (rbuserprefs): interface preferences, NULL = Auto
│   ├── routes/
│   │   ├── auth.py          # Login / register / logout (Jinja forms)
│   │   ├── card_images.py   # card_images_bp: serves CARD_IMAGES_DIR at /riftbound/static/images/cards/
│   │   ├── landing.py       # Public landing page and its HTMX partials (/ and /api/*)
│   │   ├── spa.py           # spa_bp: serves the React build from FRONTEND_DIST at /riftbound/app/
│   │   ├── routes.py        # Dashboard + domain blueprint imports
│   │   └── domains/         # Domain routes
│   │       ├── sets.py      # Sets
│   │       ├── cards.py     # Cards + image upload
│   │       ├── collection.py # Collection management, import/export
│   │       ├── deck.py      # Decks
│   │       ├── price.py     # Cardmarket loading and matching (admin only)
│   │       └── profile.py   # Profile updates
│   ├── services/            # Business logic, no Flask request objects
│   │   ├── auth.py          # authenticate (lockout), register_user, unlock_user
│   │   ├── bans.py          # name_key, ban_map, card_bans, ban_info, list_bans, add_ban, remove_ban
│   │   ├── captcha.py       # none / altcha providers, replay store
│   │   ├── daily_prices.py  # validate_load, match_clear_cases (daily_prices job, F4-b)
│   │   ├── jobs.py          # enqueue, claim_next, expire_stale, run_pending, list_jobs, last_success_today (job runner)
│   │   ├── prefs.py         # get_prefs / update_prefs (interface preferences)
│   │   ├── pricing.py       # resolve_price, latest_price_for_card
│   │   ├── card_images.py   # card_image_path: safe write paths under CARD_IMAGES_DIR
│   │   ├── cardmarket_loader.py
│   │   ├── cardmarket_matcher.py
│   │   ├── riot_scraper.py
│   │   └── scraper.py       # Landing feeds with a TTL cache
│   ├── schemas/             # Pydantic
│   │   ├── game_domain.py   # Game enumerations (GAME_MODES), the single source for schemas and CHECKs
│   │   ├── prefs_domain.py  # Value domains of the interface preferences (schema + model CHECKs)
│   │   ├── validators.py    # Request schemas
│   │   └── validation.py    # @validate_json decorator
│   ├── utils/
│   │   └── clock.py         # utcnow() (patched in tests)
│   ├── templates/           # Jinja2 templates; errors/ and landing/ inside
│   └── static/              # Static files
│       ├── css/
│       ├── js/
│       │   └── csrf.js      # fetch wrapper that adds X-CSRFToken
│       ├── vendor/
│       │   └── altcha/      # Vendored ALTCHA widget (pinned version)
│       ├── landing/         # Landing page assets
│       └── images/
├── migrations/              # Alembic
│   ├── env.py
│   ├── versions/            # 0001_baseline ... one file per revision
│   └── legacy_sql/          # Frozen pre-Alembic SQL (reference only)
├── frontend/                # React app (F1); see "Frontend" below
│   ├── package.json         # Exact pins, scripts (dev, build, lint, typecheck, test, check:dist)
│   ├── assets-src/          # Brand and background sources (never shipped)
│   ├── public/              # Committed icons and favicons (generated by `npm run icons`)
│   ├── pwa-options.ts       # vite-plugin-pwa options (manifest, Workbox, self-destroying switch)
│   ├── pwa-assets.config.ts # Icon presets for `npm run icons`
│   ├── scripts/             # brand-trace.mjs, make-bg.mjs, icons.mjs, check-dist.mjs
│   └── src/
│       ├── app/             # Router, route table, providers, bootstrap (wires everything)
│       ├── api/             # Typed fetch client, CSRF token, ApiError, endpoints
│       ├── auth/            # Session query, guards, safeNext, login and register screens
│       ├── i18n/            # es/en catalogs, resolveLang, translateError, parity check
│       ├── prefs/           # Preferences: bootstrap, resolve, apply, mirror, optimistic sync, provider
│       ├── pwa/             # Update toast, install prompt and iOS dialog (the service worker comes from vite-plugin-pwa)
│       ├── account/         # Interface settings page and its live preview
│       ├── shell/           # AppShell, Topbar, BottomNav, MoreSheet, HomeHub, nav registry, NotFound
│       ├── components/ui/   # Primitives (Brand, Button, Field, Input, Toast, ...)
│       ├── lib/             # breakpoints, contrast, format, background, storage
│       ├── styles/          # Layered tokens, base, background, fonts
│       └── test/            # Vitest setup, MSW server, renderApp, viewport mock, CSS helpers
├── tests/
│   ├── conftest.py          # Fixtures (see Testing)
│   └── test_*.py
├── docs/
│   ├── knowledge/           # Product, architecture, conventions, state, roadmap, workflow, ops runbook
│   ├── requirements/        # Phase specs (F<n>/README.md) and unit requirements for gentle-shell
│   ├── migrations.md        # Migration runbook
│   ├── nginx_config         # Nginx template
│   ├── systemd/             # systemd templates: job runner timer (F4-a), daily load timers (F4-b)
│   └── riftbound.service    # systemd unit
├── openspec/                # Spec-driven development artifacts (SDD)
├── .github/
│   └── workflows/           # ci.yml, security.yml, release.yml
├── config.py                # Settings from environment variables
├── run.py                   # Local entry point (python run.py)
├── wsgi.py                  # WSGI entry point
├── pytest.ini
├── requirements.txt
├── .env.example
└── README.md
```

## Configuration

Settings come only from environment variables (`config.py`). A git-ignored `.env` is read **only** when `RB_ENV=development`.

| Variable | Meaning |
|----------|---------|
| `RB_ENV` | `development`, `testing` or `production` (unset = production) |
| `SECRET_KEY` | 32+ random characters; the app refuses weak or default keys outside development |
| `DATABASE_URL` | `postgresql+psycopg://user:password@host:5432/riftbound` |
| `CARD_IMAGES_DIR` | Absolute path of the card images root (`ogn/`, `ogs/`, ...); unset = `app/static/images/cards`; a relative path stops the app with `ConfigError`. The images are not in git (M-d) |

The rest (cookies, kill switches, lockout, captcha, proxy hops) is documented in `.env.example`. Never commit real values and never write a credential, IP address or hostname into code or docs.

## Conventions

### Database Naming
- Tables: `rbusers`, `rbset`, `rbcards`, `rbcollection`, `rbdecks`, `rbcardmarket`, `rbproducts`, `rbcaptcha_used`, `rbuserprefs`, `rbjobs`, `rbcardbans`, and the Cardmarket loader tables `rbcm_categories`, `rbcm_expansions`, `rbcm_ignored`, `rbcm_load_history`, `rbcm_price`, `rbcm_product_card_map`, `rbcm_products`
- Schema: `riftbound`
- Model classes use the `Rb` prefix (the user model is `User`, table `rbusers`)

### Column Naming
- snake_case with the table prefix: `rbcar_name`, `rbcol_quantity`, `rbdck_snapshot`
- `rbusers` is the exception: `username`, `email`, `is_admin`, `is_blocked`, ...
- `rbcol_quantity` is an integer (1..9999); never store numbers as text.

### URL Routes
- Every route uses the `/riftbound` prefix (Nginx reverse proxy); the landing page lives at `/`.
- Legacy JSON endpoints stay flat (`{"success": true, ...}`); the API v1 uses the envelope below.

### Blueprints
`landing_bp`, `card_images_bp`, `main_bp` (dashboard), `auth_bp`, `sets_bp`, `cards_bp`, `collection_bp`, `deck_bp`, `price_bp`, `profile_bp` and `api_v1` (JSON API).

### SPA hosting (`spa_bp`)
`app/routes/spa.py` serves the frontend build (`FRONTEND_DIST`, default `frontend/dist`, read per request) at `/riftbound/app/`. Public, never touches the session, so no `Set-Cookie`. `assets/*` are immutable; everything else is `no-cache`. A path without a file extension gets `index.html`; a missing file with an extension is a real 404; no build is a 503 (JSON for JSON clients, a minimal inline page otherwise, never the Jinja error templates). The `index.html` responses carry `Content-Security-Policy-Report-Only` (`SPA_CSP=report-only`, the default, or `off`; any other value stops the app with `ConfigError`); no other response gets a CSP. It is registered after the domain blueprints; Tests get a temporary dist from the `spa_dist` / `spa_app` fixtures, no Node needed. See `docs/frontend.md`.

### Card images (`card_images_bp`)
`app/routes/card_images.py` serves `CARD_IMAGES_DIR` at `/riftbound/static/images/cards/<path>` (endpoint `card_images.serve`, public). The rule is more specific than Flask's `static` rule, so it wins for that prefix; every other `/riftbound/static/...` URL still comes from `app/static/`. `RbCard.image_src` and the URLs are unchanged. `..`, absolute paths, symlinks resolving outside the root, folders and missing files are 404; caching is Flask's static one (conditional requests, `SEND_FILE_MAX_AGE_DEFAULT`). The images live outside git in a data directory per host (`docs/knowledge/ops-runbook.md` → "Card images"). Tests point `app.config['CARD_IMAGES_DIR']` at a temporary directory and never touch the repo's images.

### Color Scheme (Dark Teal Theme)
| Element | Color | Hex |
|---------|-------|-----|
| Background | Dark Teal | #013951 |
| Hover | Deep Teal | #1a4c62 |
| Accent (buttons) | Cyan | #00b2cf |
| Active/Hover | Orange | #ef7d21 |
| Menu | Black | #111111 |

## Roles and Authorization

Every URL rule is **public (P)**, **authenticated (U)** or **admin (A)**. `tests/test_authz_matrix.py` lists them all and fails, naming the rule, when a new route is not classified: add it there.

- Admin routes use `@admin_required` (`app/security.py`); the whole `price_bp` is guarded by `before_request(require_admin)`. Anonymous callers are sent to login, plain users get 403.
- `is_admin` and `is_blocked` are changed only by the CLI (`flask users promote|demote|block|unblock <username>`), never by request input. A blocked user is rejected exactly like a wrong password.
- Card bans (`rbcardbans`) are changed only by the CLI (`flask bans add|remove`) until the F10 admin UI; signed-in users read them with `GET /bans`.
- Never trust ids from the client: deck and collection queries are scoped to the logged-in user.

## CSRF, Sessions and Login Protection

- Every `POST`/`PUT`/`PATCH`/`DELETE` needs a valid token in the `X-CSRFToken` header or the `csrf_token` form field. There are no exemptions, API included. `GET /riftbound/api/v1/auth/session` returns a token for API clients.
- `base.html` exposes `<meta name="csrf-token">` and loads `static/js/csrf.js`, which adds the header to same-origin `fetch` calls; existing call sites need no change. Forms in Jinja carry a hidden `csrf_token`.
- Logout is `POST` only (a form with a token).
- Session cookies are HttpOnly, SameSite=Lax and Secure in production.
- Login: 5th consecutive failure locks the account 15 minutes, doubling up to 24 hours; a locked login answers 429 with `Retry-After`. Unlock with `flask users unlock <username>`. Login is limited to 10/minute and 50/hour per IP, register to 5/hour.
- Registration uses an ALTCHA proof of work (`CAPTCHA_PROVIDER`); solved challenges are stored in `rbcaptcha_used` so they cannot be replayed.
- Kill switches (rollback only): `WTF_CSRF_ENABLED`, `RATELIMIT_ENABLED`, `CAPTCHA_PROVIDER=none`, `SPA_CSP=off`.

## JSON vs HTML

`wants_json()` in `app/errors.py` decides: JSON when the path is under `/riftbound/api/`, or the body is JSON, or `Accept` prefers `application/json` over `text/html` (a bare `*/*` counts as JSON). A request with no `Accept` header is HTML. Errors, 401 (Flask-Login) and CSRF failures follow it.

## API v1

Prefix `/riftbound/api/v1`: `GET /health`, `GET /meta/config`, `GET /auth/session`, `GET /auth/captcha`, `POST /auth/login`, `POST /auth/logout`, `POST /auth/register`, `GET /me/prefs`, `PATCH /me/prefs`, `GET /bans`.

- `GET /auth/session` returns `{authenticated, csrf_token}` for anonymous callers and `{authenticated, user, prefs, csrf_token}` when signed in. `prefs` always has the five keys `lang`, `density`, `accent`, `bg_intensity`, `collection_view`; `null` means Auto (a user without a row gets five `null`s and no row is created).
- `POST /auth/login` takes `{username, password, remember?}`. `remember` is a strict boolean (default `false`); `true` also issues a 30-day `remember_token` cookie (`REMEMBER_COOKIE_DURATION`, absolute expiry). Logout expires it, and a blocked user stays anonymous. The Jinja login form never remembers.
- `GET`/`PATCH /me/prefs` (`app/api/v1/me.py`): a key that is absent stays unchanged, `null` resets it to Auto, an invalid value is a 400 and nothing is stored (all-or-nothing), unknown keys are ignored. Domains live in `app/schemas/prefs_domain.py` (shared by the schema and the model CHECKs). Logic is in `app/services/prefs.py`.
- `GET /bans` (`app/api/v1/bans.py`, U) returns `{items: [{name, mode, since, reason, printings: [{set_id, card_id}]}]}` ordered by mode, then name; optional `?mode=1v1|2v2` (any other value is a 400 `validation_error`). A ban covers every printing of a card name (`name_key` in `app/services/bans.py`); modes come from `app/schemas/game_domain.py`. Bans are managed with `flask bans list [--mode M]`, `flask bans add NAME --mode 1v1|2v2|all [--since YYYY-MM-DD] [--reason TEXT] [--force]` and `flask bans remove NAME --mode 1v1|2v2|all`. The legacy `rbcar_banned` column is not a source (F11 drops it).

```json
{"success": true, "data": {}, "meta": {}}
{"success": false, "error": "Validation Error", "message": "Invalid request data", "details": [{"field": "password", "message": "...", "type": "..."}]}
```

Errors may also carry a machine-readable `code` and `params` (`{"code": "locked", "params": {"retry_after": 30}}`); `message` is always the fallback and codeless errors keep the F0 shape. The codes are the `ErrorCode` values of `app/api/error_codes.py`: `invalid_credentials`, `locked`, `rate_limited`, `username_taken`, `email_taken`, `captcha_failed`, `csrf_invalid`, `unauthenticated`, `validation_error`, `bad_request` (unreadable body on a `@validate_json` endpoint), `internal_error` (unexpected failure of a legacy endpoint). Each item of `details` keeps `field`, `message`, `type` and adds `code` (`required`, `too_short`, `too_long`, `invalid_format`, `invalid_value`, `out_of_range`) and, when it applies, `params` (`{"min": 8}`). The codes are additive and also appear on the legacy JSON endpoints that use `@validate_json`, the CSRF and 429 handlers and the 401 handler. A new code needs the enum value, both frontend catalogs and the catalog test (`tests/test_error_catalogs.py`). Unexpected failures of legacy endpoints go through `unexpected_failure()` (`app/errors.py`): a clear `message` and `code`, the traceback in the server log, and the exception text only under `detail` for a signed-in admin.

Use `ok()` / `fail()` from `app/api/responses.py`. Error names: `Validation Error`, `Unauthorized`, `Forbidden`, `Not Found`, `Method Not Allowed`, `Conflict`, `Captcha Error`, `CSRF Error`, `Too Many Requests`, `Service Unavailable`, `Internal Server Error`. 500 responses never include exception text.

## Development Guidelines

### Before Writing Code
1. Read the existing patterns in `app/routes/domains/` and `app/services/`
2. Check the schemas in `app/schemas/validators.py`
3. Check the models in `app/models/` for the data structure
4. Review templates in `app/templates/` for UI patterns
5. Check `openspec/` for the spec of the change you are working on

### Code Style
- PEP 8, type hints where useful
- Keep routes thin: put logic in `app/services/`
- Use `db.session.commit()` after database operations
- Preserve each file's line endings (some files are CRLF)

### Request Validation
Every endpoint that receives JSON uses `@validate_json`:
```python
from app.schemas.validators import SetCreate
from app.schemas.validation import validate_json

@sets_bp.route('/add', methods=['POST'])
@admin_required
@validate_json(SetCreate)
def add_set():
    data = request.validated_data  # Validated Pydantic model
    ...
```

### Database Changes (Alembic)
The database is built only by migrations (`db.create_all()` is used by the tests alone).
```bash
flask db migrate -m "describe the change"   # autogenerate, then READ the file
flask db upgrade                             # apply
flask db check                               # must report no drift
flask db downgrade -1                        # every revision must be reversible
```
Revisions live in `migrations/versions/`. Change the model and the revision together; the unit adds a round-trip and drift test for its revision (see Testing). Back up before upgrading a real database; see `docs/migrations.md`.

### Testing
**Test policy (since 2026-10-22, unit M-a).** The pre-existing suites were removed. Only
`tests/test_authz_matrix.py` (every URL rule classified P/U/A) and the startup smoke tests
(`tests/test_smoke.py`, `frontend/src/app/smoke.test.tsx`) remain. Strict TDD still applies: every
unit writes the tests for the behaviour it adds or changes. When a unit touches an area whose old
guard was removed, it re-creates that guard in its smallest form: a migration → a round-trip and
model/schema drift test for that revision (`tests/migration_helpers.py`); new UI strings → the ES/EN
parity test; a new error code → the backend/frontend catalog test; a new legacy link → the
legacy-routes check against the Flask `url_map`; a new pinned version → the pin check. The last
commit with the old suites is `902047c6579e5ee670e1fb4b103a941159b85c00`; recover any file with `git show 902047c6579e5ee670e1fb4b103a941159b85c00:<path>`.

Strict TDD: write the failing test first, then the code.
```bash
pip install -r requirements.txt
pytest                                    # SQLite, no setup
pytest --cov=app --cov-report=term
TEST_POSTGRES_URL=postgresql+psycopg://user:password@localhost:5432/riftbound_test pytest -m postgres
```
- `tests/conftest.py` sets `RB_ENV=testing`; the default `app` has CSRF, rate limits and captcha **off**.
- Fixtures: `make_user`, `login_as`, `authenticated_client`, `admin_client`, `other_user_client`, `csrf_app`, `limited_app`, `altcha_app`, `frozen_clock`, `migration_app`, `pg_url`.
- Request `admin_client` / `authenticated_client` **before** `csrf_app` (they log in through the form).
- PostgreSQL-marked tests (none today) need a database whose name contains `test`; a unit that adds them re-adds the `pytest -m postgres` CI step (PostgreSQL 18).
- Nothing in the tests may reach the internet.

### Security
- Passwords are hashed with Werkzeug's `generate_password_hash`; minimum 8 characters.
- All routes except login, register, landing and the public API endpoints require login.
- Secrets only through environment variables.
- File uploads and image paths go through `app/services/card_images.py`: `card_image_path(current_app.config['CARD_IMAGES_DIR'], image, set_id)`, never the static folder or the working directory.
- Cardmarket URLs must be on the allow-list (`CARDMARKET_ALLOWED_HOSTS`).

## Database Operations

```python
# Query with filters
cards = RbCard.query.filter(RbCard.rbcar_name.ilike(f'%{search}%')).all()

# Pagination
pagination = query.paginate(page=page, per_page=per_page, error_out=False)

# Join query
query = db.session.query(RbCollection, RbCard).join(
    RbCard,
    (RbCollection.rbcol_rbset_id == RbCard.rbcar_rbset_id) &
    (RbCollection.rbcol_rbcar_id == RbCard.rbcar_id)
)
```

## Running

```bash
python run.py                    # http://127.0.0.1:5000/riftbound (loopback, debug off)
```

Production (systemd unit in `docs/riftbound.service`, Nginx template in `docs/nginx_config`):
```bash
gunicorn --workers 3 --bind 0.0.0.0:8000 run:app
```
Firewall port 8000 so only the Nginx host reaches it. ProxyFix trusts exactly one proxy hop (`PROXY_FIX_X_*=1`); the proxy must send `Host`, `X-Forwarded-For` and `X-Forwarded-Proto`, and must not strip `Referer` (the CSRF check needs it over HTTPS).

Background jobs (table `rbjobs`): `riftbound-jobs.timer` starts `flask jobs run-pending` every minute under `flock -n`; kinds: `heartbeat` (diagnostic) and `daily_prices` (daily Cardmarket load at 06:30 Europe/Madrid, retried at 08:00 with `--unless-succeeded-today` when it did not succeed) (templates in `docs/systemd/`, install and rollback in `docs/knowledge/ops-runbook.md` → "Scheduled jobs").
```bash
flask jobs enqueue <kind> [--param key=value]...   # one queued or running job per kind
flask jobs enqueue <kind> --unless-succeeded-today  # skip (exit 0) when a <kind> job succeeded today (UTC)
flask jobs run-pending                             # expire stale jobs, run the queued ones (exit 0)
flask jobs list [--limit N]                        # newest first, default 20
```

## Error Handling

HTTP errors are handled in `app/errors.py`: 400, 401, 403, 404, 405, 429, 500 and CSRF failures. Browsers get an HTML page, JSON clients get:
```json
{
  "success": false,
  "error": "Error Type",
  "message": "Description"
}
```

## Common Tasks

### Adding a New Model
1. Create a file in `app/models/` with `__tablename__` and `{"schema": "riftbound"}`
2. Import it in `app/models/__init__.py`
3. `flask db migrate`, review, `flask db upgrade`, `flask db check`
4. Add a route or service and its tests

### Adding a New Route
1. Create or update a file in `app/routes/domains/`
2. Add `@blueprint.route()` with `@login_required` (or `@admin_required`) and `@validate_json(schema)`
3. Classify it in `tests/test_authz_matrix.py`
4. Add a template in `app/templates/` and a nav link in `base.html` if it is a page

### Adding Request Validation
1. Define the schema in `app/schemas/validators.py`
2. Use `@validate_json(SchemaClass)`
3. Read `request.validated_data`

### Adding a Job Kind
1. A module in `app/jobs/` with `handler(params: dict) -> dict` that calls `register(JobKind(name, handler, timeout_seconds))`; import it in `app/jobs/__init__.py`; raise `JobFailed(message)` for an expected failure (the message is stored without the class name)
2. A migration that extends the `ck_rbjobs_kind` CHECK, and `JOB_KINDS` in `app/models/job.py`
3. Tests through `app.services.jobs` (`run_pending()`) and the runbook entry in `docs/knowledge/ops-runbook.md` → "Scheduled jobs"

## Troubleshooting

- **App does not start**: the error names the missing or weak variable (`SECRET_KEY`, `DATABASE_URL`); check `.env.example`.
- **`flask db check` reports drift**: the model and the migrations disagree; fix one of them.
- **POST returns 400 "CSRF"**: the request has no token, or Nginx strips `Referer` / does not send `X-Forwarded-Proto`.
- **Locked out**: `flask users unlock <username>`.
- **Template not found**: check it exists in `app/templates/`.

## Frontend

The React app lives in `frontend/` (Node 24, see `.nvmrc`). Work there with `npm`:

| Command | What it does |
|---------|--------------|
| `npm ci` | Install the exact versions of `package-lock.json` |
| `npm run dev` | Vite dev server; proxies `/riftbound/api` and `/riftbound/static` to Flask |
| `npm run lint` / `typecheck` | ESLint (folder boundaries, a11y) plus Prettier check / `tsc -b` |
| `npx vitest run` | Unit and component tests (strict TDD: test first) |
| `npm run build` then `npm run check:dist` | Production build in `frontend/dist` and its checks (manifest, icons, service worker, altcha chunking) |
| `npm run icons` | Regenerate the committed icons in `frontend/public/` from the brand mark |

Conventions: dependencies are pinned without `^` or `~` (`frontend/.npmrc`); CSS is layered (`@layer reset, tokens, base, layout, components, utilities`) and every `*.module.css` wraps its rules in `@layer components`; `@media` widths come only from `src/lib/breakpoints.ts`; the background never brightens the map and body text keeps at least 4.5:1 contrast over it (`src/lib/background.ts`).

App shell and preferences (unit e): signed-in pages render inside `frontend/src/shell/AppShell.tsx`; `shell/navRegistry.ts` is the single list behind the topbar, the bottom navigation, the "Más" sheet and the home hub (each entry is `spa`, `legacy` or `planned`; legacy entries are plain links to the Jinja pages listed in `shell/legacy-routes.json`, whose keys must exist in the Flask `url_map`; a unit that adds a legacy link adds a test for it). Interface preferences live in `frontend/src/prefs/` (`rb_prefs_v1` mirror applied before the first render, Auto resolved below 860 px, optimistic PATCH with revert) and are edited at `/riftbound/app/account/interface`. The Jinja layout (`app/templates/base.html`) links to the new app ("Nueva app"). See `docs/frontend.md`.

PWA (unit f): the app installs as "Rift Manager" (`pwa-options.ts`, vite-plugin-pwa `generateSW`, prompt mode). The worker is `/riftbound/app/sw.js` with scope `/riftbound/app/`; it precaches the app shell only and never touches `/riftbound/api/*`, `/riftbound/static/*` or Jinja pages. `frontend/src/pwa/` holds the "Nueva versión" update toast (`useUpdatePrompt`), the install item (`installPrompt.ts` is started in `app/bootstrap.tsx`; iOS Safari gets `IosInstallDialog`) and the offline behaviour lives in `auth/offline.ts` plus `components/ui/OfflineBanner.tsx` (the shell opens offline when a signed-in hint exists; settings and logout are read-only offline). A plain revert is not a rollback of the PWA: build with `VITE_PWA_SELF_DESTROY=true` first (see `docs/frontend.md`, "Rolling back the PWA"). Icons are committed; `npm run icons` regenerates them and `npm run check:dist` verifies them.

Authentication and API access (unit d): `frontend/src/api/client.ts` is the only code that calls `fetch`. It unwraps `{success, data}`, throws `ApiError` (`kind` http, network, timeout or parse; `code` normalised from `body.code` or derived from the F0 body), keeps the CSRF token in memory only (`api/csrf.ts`, never in web storage), sends `X-CSRFToken` on POST, PATCH, PUT and DELETE, retries once after `csrf_invalid`, and calls the registered unauthorized handler on a 401 from any path except `/auth/login` and `/auth/logout`. The session is the TanStack Query entry `['session']` (`auth/session.ts`); route loaders `requireAuth`, `requireAnon` and `requireAdmin` (`auth/guards.ts`) run before anything renders. `next` is always an absolute `/riftbound/...` path and `auth/safeNext.ts` decides between a router navigation and a full page load. `altcha` is imported only by `auth/AltchaWidget.tsx` (lazy register route) and must keep the version pinned in `requirements.txt`. Text lives in `src/i18n/locales/{es,en}/*.json` (`es` is the typed source; both languages need the same keys, the same `{{placeholders}}` and the plural forms; a unit that adds strings adds the parity test). A backend error code needs `code.<value>` in both `errors.json` files; the unit that adds a code adds a test for it. See `docs/frontend.md`.
