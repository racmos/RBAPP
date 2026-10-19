# Riftbound - Agent Instructions

## Project Overview

**Riftbound Manager** is a web application to manage the Riftbound trading card game:
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

The exact pins live in `requirements.txt`; if you change one, update this table (`tests/test_docs.py` fails when they differ).

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
│   │       ├── me.py        # GET/PATCH /me/prefs (interface preferences)
│   │       └── meta.py      # health, meta/config
│   ├── cli/                 # Flask CLI groups
│   │   ├── schema.py        # flask schema snapshot
│   │   └── users.py         # flask users promote|demote|block|unblock|set-password|list|unlock
│   ├── models/              # SQLAlchemy models (Rb prefix)
│   │   ├── user.py          # User (rbusers)
│   │   ├── set.py           # RbSet (rbset)
│   │   ├── card.py          # RbCard (rbcards)
│   │   ├── collection.py    # RbCollection (rbcollection)
│   │   ├── deck.py          # RbDeck (rbdecks)
│   │   ├── market.py        # RbCardMarket (rbcardmarket)
│   │   ├── cardmarket.py    # Rbcm* models (rbcm_* tables, Cardmarket loader) and RbProducts (rbproducts)
│   │   ├── captcha.py       # RbCaptchaUsed (rbcaptcha_used)
│   │   └── prefs.py         # RbUserPrefs (rbuserprefs): interface preferences, NULL = Auto
│   ├── routes/
│   │   ├── auth.py          # Login / register / logout (Jinja forms)
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
│   │   ├── captcha.py       # none / altcha providers, replay store
│   │   ├── prefs.py         # get_prefs / update_prefs (interface preferences)
│   │   ├── pricing.py       # resolve_price, latest_price_for_card
│   │   ├── card_images.py   # Safe image paths
│   │   ├── cardmarket_loader.py
│   │   ├── cardmarket_matcher.py
│   │   ├── riot_scraper.py
│   │   └── scraper.py       # Landing feeds with a TTL cache
│   ├── schemas/             # Pydantic
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
├── tests/
│   ├── conftest.py          # Fixtures (see Testing)
│   └── test_*.py
├── docs/
│   ├── migrations.md        # Migration runbook
│   ├── nginx_config         # Nginx template
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

The rest (cookies, kill switches, lockout, captcha, proxy hops) is documented in `.env.example`. Never commit real values and never write a credential, IP address or hostname into code or docs.

## Conventions

### Database Naming
- Tables: `rbusers`, `rbset`, `rbcards`, `rbcollection`, `rbdecks`, `rbcardmarket`, `rbproducts`, `rbcaptcha_used`, `rbuserprefs`, and the Cardmarket loader tables `rbcm_categories`, `rbcm_expansions`, `rbcm_ignored`, `rbcm_load_history`, `rbcm_price`, `rbcm_product_card_map`, `rbcm_products`
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
`landing_bp`, `main_bp` (dashboard), `auth_bp`, `sets_bp`, `cards_bp`, `collection_bp`, `deck_bp`, `price_bp`, `profile_bp` and `api_v1` (JSON API).

### SPA hosting (`spa_bp`)
`app/routes/spa.py` serves the frontend build (`FRONTEND_DIST`, default `frontend/dist`, read per request) at `/riftbound/app/`. Public, never touches the session, so no `Set-Cookie`. `assets/*` are immutable; everything else is `no-cache`. A path without a file extension gets `index.html`; a missing file with an extension is a real 404; no build is a 503 (JSON for JSON clients, a minimal inline page otherwise, never the Jinja error templates). It is registered after the domain blueprints; `tests/test_spa_hosting.py` uses a temporary dist (`spa_dist` / `spa_app` fixtures), no Node needed. See `docs/frontend.md`.

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
- Never trust ids from the client: deck and collection queries are scoped to the logged-in user.

## CSRF, Sessions and Login Protection

- Every `POST`/`PUT`/`PATCH`/`DELETE` needs a valid token in the `X-CSRFToken` header or the `csrf_token` form field. There are no exemptions, API included. `GET /riftbound/api/v1/auth/session` returns a token for API clients.
- `base.html` exposes `<meta name="csrf-token">` and loads `static/js/csrf.js`, which adds the header to same-origin `fetch` calls; existing call sites need no change. Forms in Jinja carry a hidden `csrf_token`.
- Logout is `POST` only (a form with a token).
- Session cookies are HttpOnly, SameSite=Lax and Secure in production.
- Login: 5th consecutive failure locks the account 15 minutes, doubling up to 24 hours; a locked login answers 429 with `Retry-After`. Unlock with `flask users unlock <username>`. Login is limited to 10/minute and 50/hour per IP, register to 5/hour.
- Registration uses an ALTCHA proof of work (`CAPTCHA_PROVIDER`); solved challenges are stored in `rbcaptcha_used` so they cannot be replayed.
- Kill switches (rollback only): `WTF_CSRF_ENABLED`, `RATELIMIT_ENABLED`, `CAPTCHA_PROVIDER=none`.

## JSON vs HTML

`wants_json()` in `app/errors.py` decides: JSON when the path is under `/riftbound/api/`, or the body is JSON, or `Accept` prefers `application/json` over `text/html` (a bare `*/*` counts as JSON). A request with no `Accept` header is HTML. Errors, 401 (Flask-Login) and CSRF failures follow it.

## API v1

Prefix `/riftbound/api/v1`: `GET /health`, `GET /meta/config`, `GET /auth/session`, `GET /auth/captcha`, `POST /auth/login`, `POST /auth/logout`, `POST /auth/register`, `GET /me/prefs`, `PATCH /me/prefs`.

- `GET /auth/session` returns `{authenticated, csrf_token}` for anonymous callers and `{authenticated, user, prefs, csrf_token}` when signed in. `prefs` always has the five keys `lang`, `density`, `accent`, `bg_intensity`, `collection_view`; `null` means Auto (a user without a row gets five `null`s and no row is created).
- `POST /auth/login` takes `{username, password, remember?}`. `remember` is a strict boolean (default `false`); `true` also issues a 30-day `remember_token` cookie (`REMEMBER_COOKIE_DURATION`, absolute expiry). Logout expires it, and a blocked user stays anonymous. The Jinja login form never remembers.
- `GET`/`PATCH /me/prefs` (`app/api/v1/me.py`): a key that is absent stays unchanged, `null` resets it to Auto, an invalid value is a 400 and nothing is stored (all-or-nothing), unknown keys are ignored. Domains live in `app/schemas/prefs_domain.py` (shared by the schema and the model CHECKs). Logic is in `app/services/prefs.py`.

```json
{"success": true, "data": {}, "meta": {}}
{"success": false, "error": "Validation Error", "message": "Invalid request data", "details": [{"field": "password", "message": "...", "type": "..."}]}
```

Errors may also carry a machine-readable `code` and `params` (`{"code": "locked", "params": {"retry_after": 30}}`); `message` is always the fallback and codeless errors keep the F0 shape. The codes are the `ErrorCode` values of `app/api/error_codes.py`: `invalid_credentials`, `locked`, `rate_limited`, `username_taken`, `email_taken`, `captcha_failed`, `csrf_invalid`, `unauthenticated`, `validation_error`. Each item of `details` keeps `field`, `message`, `type` and adds `code` (`required`, `too_short`, `too_long`, `invalid_format`, `invalid_value`, `out_of_range`) and, when it applies, `params` (`{"min": 8}`). The codes are additive and also appear on the legacy JSON endpoints that use `@validate_json`, the CSRF and 429 handlers and the 401 handler. A new code needs the enum value, both frontend catalogs and the contract test.

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
Revisions live in `migrations/versions/`. Change the model and the revision together; `tests/test_migrations.py` fails when they disagree. Back up before upgrading a real database; see `docs/migrations.md`.

### Testing
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
- The PostgreSQL tests need a database whose name contains `test`; CI runs them against PostgreSQL 18.
- Nothing in the tests may reach the internet.

### Security
- Passwords are hashed with Werkzeug's `generate_password_hash`; minimum 8 characters.
- All routes except login, register, landing and the public API endpoints require login.
- Secrets only through environment variables.
- File uploads and image paths go through `app/services/card_images.py`.
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

## Troubleshooting

- **App does not start**: the error names the missing or weak variable (`SECRET_KEY`, `DATABASE_URL`); check `.env.example`.
- **`flask db check` reports drift**: the model and the migrations disagree; fix one of them.
- **POST returns 400 "CSRF"**: the request has no token, or Nginx strips `Referer` / does not send `X-Forwarded-Proto`.
- **Locked out**: `flask users unlock <username>`.
- **Template not found**: check it exists in `app/templates/`.
