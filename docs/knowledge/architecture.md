# Architecture: how Rift Manager is built today

State described: `main` at commit `492279b` (F1 units a to f merged, 2026-10-21). F1 unit g
(optional CSP hardening) is NOT merged; nothing about `SPA_CSP` exists yet. Everything below was
checked against the code. Where the code and an older document disagree, the code wins and the
difference is called out as "Note".

Companions: `docs/knowledge/product.md` (decisions), `docs/knowledge/conventions.md` (rules),
`docs/knowledge/specs-index.md` (formal specs).

## 1. Overview

One Flask application serves three front doors that share one session cookie:

```
 browser or installed PWA
        |  HTTPS
        v
 Nginx (TLS, limit_req on the auth POSTs, proxies "/" and "/riftbound/" to one upstream)
        |  HTTP, exactly one trusted proxy hop (X-Forwarded-For / -Proto / -Host)
        v
 Gunicorn (3 workers)  ->  Flask app  (create_app, ProxyFix)
        |
        +-- Jinja pages (legacy)      /riftbound/...            HTML, forms, small JSON endpoints
        +-- Landing page + partials   /  and  /api/*  /frames/*  public, HTMX fragments
        +-- JSON API v1               /riftbound/api/v1/...     envelope {success, data, meta}
        +-- React SPA (the new app)   /riftbound/app/...        static build from FRONTEND_DIST
        v
 PostgreSQL, schema "riftbound"   (SQLite in memory in the tests)
```

- Nginx does NOT serve the SPA: Flask does (`spa_bp`). Nginx only terminates TLS and proxies.
- The SPA calls the JSON API with the same-origin session cookie plus the `X-CSRFToken` header.
- Jinja pages and the SPA share the session: signing in or out in one applies to both.
- The PWA takes over one module per phase. A module that is not ported yet stays a Jinja page and
  is linked from the SPA ("legacy" entries of the nav registry). Jinja is retired in F11.
- Environment: there is no production yet. The only server is the dev server.

Top-level layout (only what matters):

| Path | What it is |
|---|---|
| `app/` | Flask package: factory, blueprints, models, services, schemas, CLI, Jinja templates, static files |
| `frontend/` | React 19 + TypeScript + Vite app (Node 24); build output `frontend/dist` is git-ignored |
| `migrations/` | Alembic revisions (`versions/`) and the frozen pre-Alembic SQL (`legacy_sql/`) |
| `tests/` | pytest suite (SQLite in memory by default) |
| `docs/` | `frontend.md`, `migrations.md`, `nginx_config`, `riftbound.service`, `knowledge/`, `requirements/` |
| `openspec/` | F0/F1 specification artifacts (see `specs-index.md`) |
| `.github/workflows/` | `ci.yml`, `security.yml`, `release.yml` |
| `config.py`, `run.py`, `wsgi.py`, `.flaskenv` | settings, local entry point, WSGI entry point, `FLASK_APP=wsgi.py` |

## 2. Backend

### 2.1 App factory and extensions (`app/__init__.py`)

`create_app(**overrides)` runs in this order: load `.env` only if the effective environment is
development, resolve `RB_ENV`, create `Flask` with static files at `/riftbound/static`, read settings
from the environment, apply `overrides` (tests), compute SQLAlchemy engine options from the FINAL
database URI, validate (fail fast), install the SQLite shims (only for `sqlite` URIs: a
`regexp_replace` function and an in-memory database attached as `riftbound`), then initialise the
extensions, CLI, `ProxyFix` and the blueprints.

Extensions are module-level singletons in `app/__init__.py`:
`db` (Flask-SQLAlchemy), `migrate` (Flask-Migrate; directory `migrations/`, options from
`app/db_schema.py`), `login` (Flask-Login, `login_view = 'auth.login'`), `csrf` (`CSRFProtect`),
`limiter` (Flask-Limiter keyed by the client IP that `ProxyFix` rewrote).

Details that matter:
- `ProxyFix` trusts `PROXY_FIX_X_FOR`, `PROXY_FIX_X_PROTO`, `PROXY_FIX_X_HOST` hops (default 1 each),
  `x_prefix=0`.
- The limiter hooks are always wired and the switch (`limiter.enabled`) is read per request, so a test
  can turn limits on for an existing app.
- `db.create_all()` is used by the tests only. Production and dev schemas are built by Alembic.
- Time: new code uses `app.utils.clock.utcnow()` (naive UTC, patched in tests). Older route code still
  calls `datetime.utcnow()` directly (collection and deck routes).

### 2.2 Blueprints and URL prefixes

80 URL rules at this commit (`app.url_map`). Prefix `/riftbound` is in every blueprint URL except the
landing page.

| Blueprint | Prefix | Module | Access |
|---|---|---|---|
| `landing_bp` | none: `/`, `/api/*`, `/frames/*`, `/landing/static/*` | `app/routes/landing.py` | public |
| `main_bp` | `/riftbound` | `app/routes/routes.py` (dashboard at `/riftbound/`) | user |
| `auth_bp` | `/riftbound` | `app/routes/auth.py` (`/login`, `/register`, `/logout`) | public / user |
| `sets_bp` | `/riftbound/set` | `app/routes/domains/sets.py` | user, writes admin |
| `cards_bp` | `/riftbound/card` (singular) | `app/routes/domains/cards.py` | user, writes admin |
| `collection_bp` | `/riftbound/collection` | `app/routes/domains/collection.py` | user |
| `deck_bp` | `/riftbound/deck` | `app/routes/domains/deck.py` | user |
| `price_bp` | `/riftbound/price` | `app/routes/domains/price.py` | admin (all 23 rules) |
| `profile_bp` | `/riftbound/profile` | `app/routes/domains/profile.py` | user |
| `spa_bp` | `/riftbound/app` | `app/routes/spa.py` | public |
| `api_v1` | `/riftbound/api/v1` | `app/api/v1/{auth,me,meta}.py` | mixed, see section 3 |
| `static` (Flask) | `/riftbound/static` | `app/static/` | public |

Every URL rule is classified public (P), authenticated (U) or admin (A) in `tests/test_authz_matrix.py`
(`MATRIX`, `fnmatch` patterns on the endpoint name). An unclassified rule fails the suite and names
the rule.

### 2.3 JSON or HTML (`app/errors.py`)

`wants_json()` is true when the path starts with `/riftbound/api/`, or the body is JSON, or `Accept`
prefers `application/json` over `text/html` (a bare `*/*`, which `fetch` sends, counts as JSON). A
request with no `Accept` header is HTML. Every error path uses it, so one request gets one kind of
answer:

- `HTTPException` handler: JSON envelope for JSON clients (405 keeps the `Allow` header), else the
  Jinja page `errors/{400,401,403,404,500}.html` or `errors/generic.html`.
- Non-HTTP exceptions: logged with the stack, answered as a generic 500. Exception text is never
  returned by these handlers.
- `CSRFError`: 400, `error: "CSRF Error"`, `code: csrf_invalid` (JSON) or `errors/400.html`.
- 429: always carries an integer `Retry-After`; JSON has `code: rate_limited`, `params.retry_after`.
- Flask-Login `unauthorized_handler`: JSON 401 with `code: unauthenticated` for JSON clients, else flash
  plus redirect to `/riftbound/login?next=...`.
- The `api_v1` blueprint has its own catch-all error handler that returns the envelope for anything.
- `spa_bp` errors never use Jinja (`base.html` would write the session cookie): JSON for JSON clients,
  a minimal inline HTML page otherwise, `Cache-Control: no-store`.

Note: a few legacy admin endpoints (`cards.upload_card_image` and several in `price.py`) still return
`str(exception)` in a 500 body, and `validate_json`'s generic `except` puts it in a 400. That predates the API contract; the
rule "500 never includes exception text" holds for the API v1 and the global handlers. Do not copy
the legacy pattern.

### 2.4 Security model

- **Roles.** `rbusers.is_admin` and `is_blocked` change only through the CLI, never through a request.
  `User.is_active` is `not is_blocked`; a blocked user is rejected exactly like a wrong password and
  loses a live session on the next request. `app/security.py`: `admin_required` (decorator) and
  `require_admin` (a `before_request` hook; the whole `price_bp` uses it). Anonymous callers go to
  login (HTML) or get a JSON 401, never 403; a signed-in non-admin gets 403.
- **CSRF.** `CSRFProtect` on every POST/PUT/PATCH/DELETE with no exemptions, API included. Token in the
  `X-CSRFToken` header or the `csrf_token` form field; no time limit (lives as long as the session).
  Jinja: `<meta name="csrf-token">` in `base.html` plus `app/static/js/csrf.js` (adds the header to
  same-origin `fetch`). SPA/API clients read the token from `GET /riftbound/api/v1/auth/session`.
  Logout is `POST` only.
- **Rate limits** (per IP, in memory per Gunicorn worker): login `10/minute;50/hour`, register `5/hour`.
  The Jinja form and the API share one budget per scope (`scope='login'`, `scope='register'`).
  Opening the pages is free (`exempt_when` for non-POST). Nginx `limit_req` (zone `rb_auth`, 20 requests
  per minute, burst 10, status 429) on POST to login, register and `/riftbound/api/v1/auth/` is the
  global limit.
- **Lockout** (`app/services/auth.py`): the 5th consecutive wrong password locks the account 15 min;
  each further failure doubles the lock up to 24 h (`min(base * 2**(n - max), cap)` minutes). A locked
  login answers 429 + `Retry-After` + `code: locked`. A success resets the count. Unknown users and
  blocked users get the same 401 `invalid_credentials` and the same hashing work (a dummy hash is
  verified). `flask users unlock <username>` clears a lock.
- **Captcha** (`app/services/captcha.py`): provider `altcha` (proof of work, default outside testing) or
  `none`. The server signs a challenge that expires after `ALTCHA_EXPIRE_SECONDS`; the widget posts a
  base64 payload (form field and JSON field `altcha`). A verified challenge is stored by sha256 in
  `rbcaptcha_used` (shared by all workers) inside a SAVEPOINT, so a replay is an IntegrityError.
  Expired rows are purged on every verify. Register order: field validation, then captcha, then
  duplicate check.
- **Cookies.** Session and remember cookies: HttpOnly, SameSite=Lax (never Strict: future OAuth
  callbacks), Secure by default in production only. `remember: true` on `POST /auth/login` issues a
  30-day `remember_token` (absolute expiry, `REMEMBER_COOKIE_DURATION` is a constant, not an env var).
  The Jinja login form never remembers.
- **Passwords.** Werkzeug `generate_password_hash`; length 8 to 128 (`PASSWORD_MIN_LENGTH`,
  `PASSWORD_MAX_LENGTH` in `app/schemas/validators.py`, used by register, profile and the CLI).
- **Outbound URLs.** Cardmarket loader overrides must be https on `CARDMARKET_ALLOWED_HOSTS`, port 443
  or none, no userinfo (`validate_override_url`).
- **Images.** Reads use `RbCard.image_src`; every write goes through `app/services/card_images.card_image_path`
  (folder letters and digits only, path must stay under the `CARD_IMAGES_DIR` root, default `<static>/images/cards/`). Since M-d the files live
  outside git and `card_images.serve` serves them at the same `/riftbound/static/images/cards/...` URLs.
- **Secrets.** Only through environment variables; `SECRET_KEY` weak or default is refused outside
  development; errors name variables, never values.

### 2.5 Configuration (`config.py`, `.env.example`)

`RB_ENV` is `development`, `testing` or `production` (unset or blank = production). A git-ignored `.env`
is read only for development. Real environment variables always win.

| Variable | Meaning | Default |
|---|---|---|
| `RB_ENV` | environment | production |
| `SECRET_KEY` | 32+ random chars; required outside development (random per process in development) | none |
| `DATABASE_URL` | `postgresql+psycopg://...` with the psycopg 3 driver; required everywhere | none |
| `RB_HOST`, `RB_PORT` | bind of `python run.py` | loopback, 5000 |
| `FLASK_DEBUG` | `1` enables the debugger; refused when `RB_ENV=production` | off |
| `RB_VERSION` | reported by `GET /health` | `dev` |
| `PROXY_FIX_X_FOR`, `_X_PROTO`, `_X_HOST` | trusted proxy hops | 1, 1, 1 |
| `CARDMARKET_ALLOWED_HOSTS` | comma list for loader overrides | host of the built-in download URLs |
| `RB_LEGACY_BACKUP_DIR` | where migration 0002 saves the legacy tables (personal data) | `<project>/instance/backups` |
| `SESSION_COOKIE_SECURE`, `REMEMBER_COOKIE_SECURE` | Secure flag | true in production only |
| `WTF_CSRF_ENABLED` | CSRF kill switch | on (off only in testing) |
| `RATELIMIT_ENABLED` | limiter kill switch | on (off only in testing) |
| `CAPTCHA_PROVIDER` | `altcha` or `none` (kill switch) | `altcha` (`none` in testing) |
| `RATELIMIT_STORAGE_URI` | limiter storage | `memory://` |
| `LOGIN_MAX_FAILURES`, `LOGIN_LOCK_BASE_MINUTES`, `LOGIN_LOCK_MAX_MINUTES` | lockout | 5, 15, 1440 |
| `ALTCHA_HMAC_KEY`, `ALTCHA_EXPIRE_SECONDS`, `ALTCHA_MAX_NUMBER` | captcha key (derived from `SECRET_KEY` when empty), lifetime, difficulty | derived, 300, 1000000 |
| `LANDING_CACHE_TTL` | seconds the landing feeds are cached per worker (0 = off) | 300 |
| `FRONTEND_DIST` | directory with the Vite build served at `/riftbound/app/` | `<project>/frontend/dist` |

The three kill switches (`WTF_CSRF_ENABLED`, `RATELIMIT_ENABLED`, `CAPTCHA_PROVIDER=none`) are for
rollback only and log a warning when off outside testing. Two Flask config keys have no environment
variable: `TESTING` (skips validation) and `LEGACY_BACKUP_DIR` (read by migration 0002 before the
`RB_LEGACY_BACKUP_DIR` variable; tests set it). Engine options: PostgreSQL gets
`client_encoding=utf8` and `pool_pre_ping`; SQLite only `pool_pre_ping`.

### 2.6 CLI

- `flask users promote|demote|block|unblock|set-password|list|unlock <username>` (aliases
  `make-admin`, `revoke-admin`). The only way to create an admin. Works while no admin exists.
  `set-password` uses a hidden prompt; `list` never shows hashes. Unknown user: exit 1, nothing changed.
- `flask schema snapshot` prints the live `riftbound` schema from `pg_catalog` (PostgreSQL only). Its
  output has the format of `tests/fixtures/dev_schema_snapshot.txt`.
- `flask db migrate|upgrade|downgrade|check|stamp|current` (Flask-Migrate).
- `python run.py` (loopback, debug off); `gunicorn --workers 3 run:app` in production
  (`wsgi.py` exposes `application` and `app`).

## 3. API v1 (`/riftbound/api/v1`, blueprint `api_v1`)

Success: `{"success": true, "data": {...}, "meta": {...}?}` built by `ok(data, status, meta)`.
Error: `{"success": false, "error": "<Name>", "message": "...", "details": [...]?, "code": "<snake>"?, "params": {...}?}`
built by `fail(...)` / `json_error(...)` (`app/api/responses.py`, `app/errors.py`). `message` is always
the English fallback; `code` and `params` are additive. Error names in use: `Validation Error`,
`Bad Request`, `Unauthorized`, `Forbidden`, `Not Found`, `Method Not Allowed`, `Conflict`,
`Captcha Error`, `CSRF Error`, `Too Many Requests`, `Service Unavailable`, `Internal Server Error`.

| Method and path | Auth | Purpose |
|---|---|---|
| `GET /health` | P | 200 `{status:"ok", db:"ok", version}` after `SELECT 1`; 503 `Service Unavailable` if the DB fails (failure logged, never returned) |
| `GET /meta/config` | P | `{env, registration_open: true, captcha:{provider, required_for:["register"] or []}, csrf:{header:"X-CSRFToken"}}` |
| `GET /auth/session` | P | anonymous: `{authenticated:false, csrf_token}`; signed in: adds `user:{id, username, email, is_admin}` and `prefs` (five keys, `null` = Auto). A blocked user is anonymous |
| `GET /auth/captcha` | P | `{provider, challenge}`; `challenge` is `null` for provider `none` |
| `POST /auth/login` | P | body `{username, password, remember?}` (`remember` strict boolean, default false). 200 `{user}`; 401 `invalid_credentials`; 429 `locked` + `Retry-After`; 400 `validation_error` |
| `POST /auth/logout` | U | 200 `{}`; anonymous gets JSON 401 |
| `POST /auth/register` | P | body `{username, email, password, altcha?}`. 201 `{user:{id, username}}`, no session; 400 `captcha_failed` (`Captcha Error`); 409 `username_taken` / `email_taken` (`Conflict`); 429 |
| `GET /me/prefs` | U | `{prefs:{lang, density, accent, bg_intensity, collection_view}}`; never creates a row |
| `PATCH /me/prefs` | U | absent key = unchanged, `null` = Auto, invalid value = 400 and nothing stored (all-or-nothing), unknown keys ignored; returns all five |

Register validation (`RegisterRequest`): username `[A-Za-z0-9_.-]{3,32}`, email at most 120 chars with a
simple `x@y.z` pattern, password 8 to 128. Login only requires non-empty username and password, so
legacy usernames keep working. Duplicate e-mail is compared case-insensitively. `is_admin` in a request
body is ignored. Preference domains (`app/schemas/prefs_domain.py`): `lang` es|en; `density`
compact|regular|comfy; `accent` cyan|orange; `bg_intensity` integer 0..100 (strict: `true`, `50.0`
and `"50"` are refused); `collection_view` table|grid.

`@validate_json(Schema)` (`app/schemas/validation.py`): not JSON gives 400 `Bad Request` ("Content-Type
must be application/json", no code); a Pydantic failure gives 400 `Validation Error` with
`code: validation_error` and `details[]` items `{field, message, type, code, params?}`.

### Error codes (`app/api/error_codes.py`)

`ErrorCode`: `invalid_credentials` (login 401, also blocked), `locked` (login 429, `params.retry_after`),
`rate_limited` (limiter 429, `params.retry_after`), `username_taken` and `email_taken` (register 409),
`captcha_failed` (register 400), `csrf_invalid` (any unsafe request without a valid token, 400),
`unauthenticated` (JSON access without a session, 401), `validation_error` (body failed validation, 400).

`DetailCode` (items of `details[]`): `required`, `too_short` (`params.min`), `too_long` (`params.max`),
`invalid_format`, `invalid_value`, `out_of_range` (`params.min` and/or `params.max`).

To add a code: (1) add the value to `ErrorCode` (or `DetailCode`) and return it with
`fail(..., code=ErrorCode.X)`; (2) add `code.<value>` (or `validation.<value>`) to BOTH
`frontend/src/i18n/locales/es/errors.json` and `.../en/errors.json`; (3) add a test that both
catalogs have the code (the old contract test, which also failed on a catalog code the backend does not
define, was removed by M-a). Codes never carry secrets or internals.

## 4. Data model

Schema `riftbound`. Tables use the `rb` prefix; columns use the table prefix (`rbcar_name`), except
`rbusers`. 16 application tables plus `alembic_version` (in the same schema). Models are in
`app/models/`, imported in `app/models/__init__.py`.

| Table | Model (file) | Primary key | Key columns and relations |
|---|---|---|---|
| `rbusers` | `User` (`user.py`) | `id` | `username` (unique, 64), `email` (unique, 120), `password_hash`, `created_at`, `is_admin`, `is_blocked`, `failed_login_count`, `locked_until`, `last_login_at`. Other tables reference `username` (collection, decks) or `id` (prefs) |
| `rbset` | `RbSet` (`set.py`) | `rbset_id` (text) | `rbset_name`, `rbset_ncard` (smallint), `rbset_outdat` (date). Parent of `rbcards` |
| `rbcards` | `RbCard` (`card.py`) | (`rbcar_rbset_id`, `rbcar_id`), both text | `rbcar_name`, `_domain`, `_type`, `_tags`, `_energy`, `_power`, `_might` (smallint), `_ability`, `_rarity`, `_artist`, `_banned`, `image_url`, `image`. FK to `rbset` (cascade). `image_src` property builds `/riftbound/static/images/cards/<folder>/<image>` |
| `rbcollection` | `RbCollection` (`collection.py`) | `rbcol_id` (synthetic bigint) | `rbcol_rbset_id`, `rbcol_rbcar_id` (FK to `rbcards`), `rbcol_user` (FK to `rbusers.username`), `rbcol_foil`, `rbcol_quantity` (integer), `rbcol_selling`, `rbcol_playset`, `rbcol_sell_price` (numeric), `rbcol_condition`, `rbcol_language`, `rbcol_chadat` |
| `rbdecks` | `RbDeck` (`deck.py`) | `id` | `rbdck_user` (FK to `rbusers.username`), `rbdck_name`, `rbdck_seq`, `rbdck_snapshot`, `rbdck_description`, `rbdck_mode`, `rbdck_format`, `rbdck_max_set`, `rbdck_ncards`, `rbdck_orden`, `rbdck_cards` (JSONB). Unique (`rbdck_user`, `rbdck_name`, `rbdck_seq`) |
| `rbcardmarket` | `RbCardMarket` (`market.py`) | (`rbcmk_snapshot`, `rbcmk_rbset_id`, `rbcmk_rbcar_id`, `rbcmk_foil`) | `rbcmk_name`, `rbcmk_price`. FK to `rbcards`. No route or service reads it (legacy) |
| `rbproducts` | `RbProducts` (`cardmarket.py`) | (`rbpdt_id_set`, `rbpdt_id_product`) | curated product master: `rbpdt_name`, `_description`, `_type`, `_image_url`, `_image`. Read and written only by admin price routes |
| `rbcaptcha_used` | `RbCaptchaUsed` (`captcha.py`) | `rbcap_hash` (sha256, 64) | `rbcap_expires_at`; index on expiry. Replay store of ALTCHA |
| `rbuserprefs` | `RbUserPrefs` (`prefs.py`) | `rbprf_user_id` | FK to `rbusers.id` ON DELETE CASCADE; `rbprf_lang`, `_density`, `_accent`, `_bg_intensity` (smallint), `_collection_view`, `rbprf_updated_at`. All preference columns nullable (NULL = Auto), five named CHECKs. Row created on the first PATCH |
| `rbcm_categories` | `RbcmCategory` | `rbcat_id` | `rbcat_name` |
| `rbcm_expansions` | `RbcmExpansion` | `rbexp_id` | `rbexp_name`, `rbexp_rbset_id` (soft link to `rbset`, NULL = unmapped; partial index on NULL) |
| `rbcm_ignored` | `RbcmIgnored` | (`rbig_id_product`, `rbig_name`) | `rbig_ignored_at`. Products an admin hid in the mappings browser |
| `rbcm_load_history` | `RbcmLoadHistory` | `rblh_id` | `rblh_date` (YYYYMMDD), `rblh_file_type`, `rblh_hash` (sha256), `rblh_rows`, `rblh_status`, `rblh_message`, `rblh_loaded_at` |
| `rbcm_price` | `RbcmPrice` | (`rbprc_date`, `rbprc_id_product`) | `rbprc_avg`, `_low`, `_trend`, `_avg1`, `_avg7`, `_avg30` plus the `_foil` variants, `rbprc_low_ex`, `rbprc_id_category`. One row per product per day |
| `rbcm_product_card_map` | `RbcmProductCardMap` | `rbpcm_id_product` | `rbpcm_rbset_id`, `rbpcm_rbcar_id`, `rbpcm_foil` (N, S or NULL), `rbpcm_match_type` (auto or manual), `rbpcm_confidence` |
| `rbcm_products` | `RbcmProduct` | (`rbprd_date`, `rbprd_id_product`) | `rbprd_name`, category and expansion ids, `rbprd_id_metacard`, `rbprd_type` (single or nonsingle). Every `Rbcm*` model and `RbProducts` live in `app/models/cardmarket.py` |

Quirks to know before touching data:
- **Ownership is by username, not id.** `rbcollection.rbcol_user` and `rbdecks.rbdck_user` hold the
  username (FK `ON UPDATE CASCADE ON DELETE RESTRICT`). Always scope by `current_user.username`.
- **`rbcol_id` is a synthetic key.** Several rows may share (set, card, foil, user) when they differ in
  selling flag, price, condition or language; adding an exact duplicate merges by an atomic SQL
  increment. PostgreSQL bigint, SQLite integer (models use a variant).
- **`rbcol_quantity` is an integer 1..9999** (CHECK `>= 1`); never text.
- **`rbcol_foil`** is `'N'` or `'S'` (S = foil; Spanish "si"). Foil is refused for Rare, Epic and Showcase.
- **`rbcol_selling`** is `'Y'` or `'N'` in the application (the DB CHECK also allows `'S'`, which the app
  never writes). **`rbcol_playset`** is NULL or 1..3 and means "copies kept back for a playset"; the
  sellable surplus is `quantity - coalesce(playset, 0)`; setting it auto-flips `selling` (Y when quantity
  exceeds it, else N). CSV export of "for sale" lines uses that surplus.
- **`rbcol_condition`** is one of MT, NM, EX, GD, LP, PL, PO or NULL; **`rbcol_language`** is free text.
- **`rbcar_banned`** is a single text column, `'N'` (default) or `'S'` (banned), one value for the whole
  card. Per-mode bans (1v1 vs 2v2) do not exist yet; they need a new table (see product decisions).
- **`rbdck_cards`** JSON shape: `{"main": [{"set": "<set id>", "id": "<card id>", "qty": 1..99}],
  "sideboard": [ ...same... ]}`. **`rbdck_snapshot`** is the full timestamp at which that version was
  saved (UTC, naive). A deck "version" is a row: same user and name, higher `rbdck_seq` (next = max + 1).
  `rbdck_ncards` is the sum of quantities (stored as 1 when the sum is 0). `rbdck_mode` is `1v1` (default)
  or any string up to 50 chars, `rbdck_format` defaults to `Standard`; the deck list offers `Standard` and
  `Limited`, `1v1` and `2v2`. Deck visibility today: the list page shows every user's decks to every
  signed-in user; `/deck/view/<id>` opens any deck by id (have/missing use the VIEWER's collection).
- **Card ids are text** such as `1`, `7a`, `79*`; natural sort extracts the leading digits. Promo sets end
  in `X` (for example `OGNX`); their image folder comes from the file-name prefix (`ogn_257.png` lives in
  `ogn/`), not from the set id.
- **Prices** live in `rbcm_price` keyed by Cardmarket product; cards reach them through
  `rbcm_product_card_map` (many products can map to one card; the canonical product is `MIN(id_product)`).
  Dates are `YYYYMMDD` text.
- `old1_rbusers` and `old_rbdecks` (legacy) no longer exist after migration 0002.

### Migrations (`migrations/versions/`, chain in this order)

| Revision | What it does |
|---|---|
| `0001_baseline` | exact copy of the dev database of 2026-10-18 (16 tables including the legacy ones); dev is adopted with `flask db stamp`, not executed |
| `0002_drop_legacy_tables` | backs up (mode 0600, git-ignored) and drops `old1_rbusers`, `old_rbdecks`; repoints `rbdecks.fk_deck_user` to `rbusers(username)`; refuses `--sql` mode |
| `0003_collection_quantity_integer` | `rbcol_quantity` Text to Integer NOT NULL, CHECK `>= 1`; aborts listing ids if any value is not 1..9999 |
| `0004_user_admin_flags` | `is_admin`, `is_blocked` (boolean NOT NULL default false) |
| `0004a_schema_comments` | table/column COMMENTs the dev DB already had (PostgreSQL only, no-op on SQLite) |
| `0005_login_protection` | `failed_login_count`, `locked_until`, `last_login_at` on `rbusers`; table `rbcaptcha_used` |
| `0006_user_prefs` | table `rbuserprefs` (1:1 with `rbusers`, five CHECKs) |

Rules: readable revision ids; every ALTER through `op.batch_alter_table(..., schema='riftbound')`;
PostgreSQL-only DDL behind a dialect guard; every revision reversible; the unit that adds a revision adds
an upgrade/downgrade test on SQLite and a drift guard (`compare_metadata` must be empty, `tests/migration_helpers.py`); `migrations-pg` in CI
repeats it on PostgreSQL 18. Runbook: `docs/migrations.md`.

## 5. Services (`app/services/`, no Flask request objects)

- `auth.py`: `authenticate` (lockout state machine), `register_user`, `unlock_user`, rate-limit strings.
- `captcha.py`: `none` and `altcha` providers, replay store in `rbcaptcha_used`.
- `prefs.py`: `get_prefs` (never writes), `update_prefs` (creates the row; retries once on a lost race).
- `pricing.py`: `resolve_price(row, rarity, foil)`, `canonical_product_id`, `latest_price_for_card`.
  Chain for premium (rarity rare, epic or showcase, case-insensitive) OR foil `S`:
  `avg7_foil -> avg7 -> low_foil -> low`. Everything else (common, uncommon, unknown rarity, non-foil):
  `avg7 -> avg7_foil -> low -> low_foil`. NULL and 0 count as missing; no price gives `None`, never 0.
  Collection and deck views both use it; deck cards are priced as non-foil. Note: the shorthand
  "avg7_foil, avg7, low_foil, low" describes only the premium/foil order.
- `card_images.py`: safe image paths (see 2.4).
- `cardmarket_loader.py`: `CardmarketLoader.run()` downloads price guide, singles and non-singles JSON from
  the allow-listed host, hashes them, loads `rbcm_*` (price guide always reloads; products only when the
  hash changed), records `rbcm_load_history`. `CARDMARKET_URLS`, `validate_override_url`.
- `cardmarket_matcher.py`: `auto_match(dry_run, max_groups)` pairs unmapped products to cards by metacard,
  normalised name and price/rarity ranking (Basic Rune: one slot without foil; common/uncommon: normal and
  foil slots; rare/epic: separate card entries), writing `rbcm_product_card_map`.
- `riot_scraper.py`: `refresh_riot_sets()` and `extract_riot_cards(filter_sets)` read the official card
  gallery (`__NEXT_DATA__` JSON), upsert `rbset`/`rbcards` and download images into `images/cards/<folder>/`.
- `scraper.py`: landing feeds (`fetch_noticias`, `fetch_discord`, `fetch_torneos_online`,
  `fetch_torneos_fisicos`, `fetch_videos`, `fetch_decks`) with placeholder fallbacks and a per-feed,
  per-worker TTL cache (`LANDING_CACHE_TTL`, default 300 s; failures are not cached; `clear_cache()`).
- Not a service: `app/utils/clock.py` (`utcnow()`), `app/schemas/*` (Pydantic request models).

## 6. Legacy Jinja pages (what the PWA will absorb)

All under `/riftbound` unless noted. JSON helpers below them keep the flat `{"success": true, ...}`
shape, not the API v1 envelope. The nav registry (section 7) lists the same modules.

| Page | URL | Blueprint | Auth | What it does | Related endpoints (all CSRF-protected POST unless GET) |
|---|---|---|---|---|---|
| Landing | `/` | `landing_bp` | P | public marketing page; HTMX partials for news, tournaments, videos, decks | GET `/api/{noticias,discord,torneos-online,torneos-fisicos,videos,decks}`, `/frames/*` |
| Login / Register | `/login`, `/register` | `auth_bp` | P | forms with CSRF; register shows the ALTCHA widget (vendored in `app/static/vendor/altcha`) | POST `/logout` (U) |
| Dashboard | `/riftbound/` | `main_bp` | U | tile launcher; admin tile for price tools | none |
| Sets | `/set` | `sets_bp` | U | list/search sets; admins add/edit in modals | A: POST `/set/add`, `/set/update/<set_id>` |
| Cards | `/card` | `cards_bp` | U | catalog with many filters, table/grid, pagination 50; admins add/edit/upload image | A: POST `/card/add`, `/card/update/<set_id>/<card_id>`, `/card/upload_image` (2 MB, jpg/jpeg/png/webp) |
| Collection | `/collection` | `collection_bp` | U | the user's lines with latest Cardmarket price, filters, sorting (set, card id, name, quantity, price), list/grid, bulk edit, add modal, CSV export of lines for sale, CSV import | POST `add`, `update_quantity` (0 deletes), `delete`, `update_selling`, `update_playset`, `update_sell_price`, `update_condition`, `update_language`, `bulk_apply`, `bulk_delete`, `import_csv` (`set;card;foil;quantity` lines), `export_csv`; GET `api/sets`, `api/cards` |
| Decks | `/deck` | `deck_bp` | U | "My decks" and "All public decks" lists (20 per page, filters by name, user, format, mode, set, legend); create modal with a text-list parser | GET `api/legends`, `versions/<name>`, `view/<id>`, `view/<name>`, `view/<name>/<seq>`; POST `save` (always creates a new version row) |
| Deck view | `/deck/view/...` | `deck_bp` | U | enriched deck: images, have/missing vs the viewer's collection, price, text/TTS export, shopping list | |
| Profile | `/profile` | `profile_bp` | U | shows account; change e-mail or password (current password required for a new one) | POST `/profile/update` |
| Price tools | `/price` | `price_bp` | A | price CSV generator, Cardmarket load, mappings browser, auto-match, ignored list, Riot gallery extraction | 22 more routes (all admin): `generate`, `refresh-riot-sets`, `extract-riot-cards`, `cardmarket-load`, `cardmarket-unmatched`, `cardmarket-search-cards`, `cardmarket-map`, `cardmarket-unmap`, `cardmarket-mappings`, `cardmarket-unmapped-expansions`, `cardmarket-map-expansion`, `cardmarket-card-detail`, `cardmarket-card-search-full`, `cardmarket-upsert-card`, `cardmarket-product-detail`, `cardmarket-product-search`, `cardmarket-upsert-product`, `cardmarket-auto-match`, `auto-match/apply`, `ignored`, `ignored/add`, `ignored/restore` |

`base.html` links to the SPA ("Nueva app" to `/riftbound/app/`) and renders Add/Edit/Price controls
only for admins (server checks stay authoritative). Jinja page titles say "Rift Manager"; the landing
keeps its own title until F11.

## 7. Frontend (`frontend/`)

Stack (exact pins in `frontend/package.json`): React 19.3.0, TypeScript 6.0.3, Vite 8.3.2,
`@vitejs/plugin-react` 6.1.1, React Router 8.4.0 (data mode, basename `/riftbound/app`), TanStack Query
5.104.1, i18next 26.4.2 + react-i18next 17.0.15, `altcha` 2.3.0 (same version as the Python pin),
`vite-plugin-pwa` 1.3.0 (Workbox 7.4.1), Vitest 5.0.3 + Testing Library + MSW 3.0.2 + `vitest-axe`,
ESLint 9 (flat) + `jsx-a11y` + Prettier (`singleQuote`, `trailingComma: all`, `printWidth: 100`).
Node 24 (`.nvmrc`), `engines.node >= 22.22`, `.npmrc`: `save-exact=true`, `engine-strict=true`.

Scripts: `dev`, `build` (`tsc -b && vite build`), `preview`, `lint` (`eslint . && prettier --check .`),
`typecheck` (`tsc -b --noEmit`), `test` (`vitest run`), `icons`, `brand:trace`, `check:dist`.
The dev server proxies `/riftbound/api` and `/riftbound/static` to Flask (`VITE_DEV_PROXY`, default the
local Flask dev server on port 5000); `VITE_BASE` defaults to `/riftbound/app/`.

### 7.1 Folder map (`frontend/src/`)

| Folder | Responsibility |
|---|---|
| `app/` | wiring only: `bootstrap.tsx` (`startApp`), `App.tsx`, `AppProviders.tsx`, `routes.tsx` (route table), `queryClient.ts`, `unauthorized.ts`, `chunkReload.ts`, `RouteError.tsx` |
| `api/` | `client.ts` (the only code that calls `fetch`), `csrf.ts`, `errors.ts` (`ApiError`), `endpoints.ts` (typed calls), `types.ts` |
| `auth/` | `session.ts` (`sessionQuery`), `guards.ts`, `safeNext.ts`, `signOut.ts`, `hint.ts`, `offline.ts`, `useAuth.ts`, Login/Register pages, `AltchaWidget.tsx`; public API via `auth/index.ts` |
| `prefs/` | interface preferences: `bootstrap.ts`, `resolve.ts`, `apply.ts`, `storage.ts` (mirror), `sync.ts`, `PrefsProvider.tsx`, `usePrefs.ts`, `AccountLanguageToggle.tsx` |
| `i18n/` | catalogs (`locales/{es,en}/*.json`), `resolveLang.ts`, `translateError.ts`, `LanguageToggle.tsx`, `parity.ts` |
| `shell/` | `AppShell`, `Topbar`, `BottomNav`, `MoreSheet`, `HomeHub`, `NotFound`, `ShellError`, `NavItem`, `navRegistry.ts`, `legacyRoutes.ts`, `legacy-routes.json` |
| `account/` | `InterfacePage.tsx` (route `/account/interface`) and `BackgroundPreview.tsx` |
| `pwa/` | `useUpdatePrompt.ts`, `UpdateToast.tsx`, `installPrompt.ts`, `useInstall.ts`, `InstallItem.tsx`, `IosInstallDialog.tsx` |
| `components/ui/` | design-system primitives (section 7.8) |
| `lib/` | `breakpoints.ts`, `useMediaQuery.ts`, `useOnline.ts`, `format.ts`, `background.ts`, `contrast.ts`, `storage.ts`, `chunkError.ts`, `navigateDocument.ts` |
| `styles/` | `index.css` (layer order), `reset.css`, `fonts.css`, `tokens.css`, `base.css`, `background.css`, `utilities.css` |
| `assets/` | `brand/{mark,mark-simple,wordmark}.svg`, `bg/new_rift-{1280,1920,portrait}.webp` |
| `dev/` | `KitchenSink.tsx`, route `/_kitchen`, present only in `npm run dev` |
| `test/` | Vitest setup, MSW, `renderApp`, viewport mock, CSS helpers |

Outside `src/`: `index.html`, `vite.config.ts`, `pwa-options.ts` (+ test), `pwa-assets.config.ts`,
`eslint.config.js`, `public/` (committed PWA icons and favicon), `assets-src/` (brand and map originals,
never shipped), `scripts/` (`check-dist.mjs`, `icons.mjs`, `brand-trace.mjs`, `make-bg.mjs`).

Import boundaries are enforced by ESLint (`no-restricted-imports`): `lib` imports nothing app-specific;
`components/ui` may import `lib` and the `i18n` hook only; `api` imports `lib` only; the features `auth`,
`prefs`, `i18n`, `pwa` import `api`, `lib`, `components/ui` and other features only through their
`index.ts`, never `shell`, `account` or `app`; `shell` and `account` import everything below but not
`app`. Cross-folder imports use the `@/` alias, never `../`.

### 7.2 Boot sequence

`src/main.tsx` imports `styles/index.css` first (it fixes the `@layer` order), then calls `startApp`:
1. `bootstrapPrefs()` reads the `rb_prefs_v1` mirror, resolves Auto for the viewport and writes
   `data-accent`, `data-density` (absent for regular), `lang` and the background variables on `<html>`
   BEFORE React renders (no theme flash).
2. `listenForInstallPrompt()` (the browser may fire `beforeinstallprompt` before React mounts).
3. `installChunkReload()`: on `vite:preloadError` reload once (`sessionStorage` guard `rb_chunk_reload`).
4. `createI18n(lang)`, `createQueryClient()`, `createBrowserRouter(createAppRoutes(queryClient), {basename: '/riftbound/app'})`.
5. Render `<StrictMode><App/></StrictMode>`; `AppProviders` nests QueryClient, I18next, `PrefsProvider`,
   `LiveAnnouncer`, `ToastStack`, `UpdateToast` and registers the 401 handler.

Routes (`app/routes.tsx`): `requireAnon` group with lazy `/login` and `/register`; `requireAuth` group
with `AppShell` containing `/` (HomeHub), `/account` (redirect), `/account/interface`, dev-only
`/_kitchen`, and `*` (NotFound). A pathless route carries `ShellError` so a page that throws keeps the
topbar. Loaders run `queryClient.ensureQueryData(sessionQuery)` before anything renders, so the login form
never flashes to a signed-in user. `requireAdmin(queryClient)` exists (non-admin sees the 404 view; UX only,
the server is the authority) but no route uses it yet.

### 7.3 API client and session

- `api/client.ts` is the only code that calls `fetch`. Base path `VITE_API_BASE` or `/riftbound/api/v1`;
  `credentials: 'same-origin'`; `Accept: application/json`; 15 s timeout.
- `request<T>(path, {method, body, signal})` unwraps `{success, data}` and throws `ApiError`
  (`kind`: `http`, `network`, `timeout`, `parse`; `status`, `code`, `params`, `details`, `retryAfter`).
  `code` is normalised: `body.code`, else derived from the F0 body shape (`deriveCode`).
- CSRF: token kept in a module variable (`api/csrf.ts`), never in web storage or cookies written by the
  SPA; sent as `X-CSRFToken` on POST, PATCH, PUT, DELETE; fetched via `GET /auth/session` first if none is
  held. A 400 with `code: csrf_invalid` clears the token, refetches the session and repeats the request
  exactly once.
- A 401 from any path except `/auth/login` and `/auth/logout` calls the registered unauthorized handler:
  clear query cache, signed-in hint and CSRF token, go to `/login?next=<absolute path>`.
- Session = TanStack Query key `['session']` (`auth/session.ts`): `{authenticated, user, prefs}`, stale
  time 5 min, refetch on window focus (so a logout elsewhere is noticed). One retry only for network or
  timeout errors, none while `navigator.onLine` is false.
- `next` is always an absolute `/riftbound/...` path; `safeNext` accepts only same-origin paths under
  `/riftbound/` (checked raw and decoded up to twice); `/riftbound/app/...` stays in the router, other
  `/riftbound/` paths (legacy pages) are a full page load.
- Logout (`useLogout`): `POST /auth/logout`; 200 and 401 both clear everything, keep the language in
  `rb_lang` and go to `/login`; other failures keep the user in with an error toast.
- Signed-in hint `rb_was_signed_in` (localStorage, non-sensitive) enables the offline boot.

### 7.4 i18n

react-i18next with bundled catalogs (no runtime fetch; they are precached). Namespaces: `common`, `nav`,
`auth`, `errors`, `prefs` (`i18n/resources.ts`: add a namespace there, in `NAMESPACES` and in both
`resources` objects). `es` is the typed source (`i18next.d.ts`): a missing key fails `tsc`. Both
languages need the same keys, the same `{{placeholders}}` and every plural form (the unit that adds strings
adds the parity test). Language order: account preference, then `rb_lang`, then the first `es`/`en`
entry of `navigator.languages`, then `es`. `fallbackLng` is `es`; a missing key renders nothing in
production and warns in dev. `useDocumentTitle(page)` sets `"<page> · Rift Manager"`. Numbers, money and
dates use `lib/format.ts` (`es-ES` / `en-GB`, money EUR, dates in UTC), never the browser locale.
`translateError(error, i18n)`: `errors:code.<code>` (with `params` and `retry_after`), then the API
`message`, then `errors:status.<http status>`, then `errors:unknown`; network and timeout use
`errors:network`. `translateDetail` uses `errors:validation.<field>.<code>`, then `validation.<code>`,
then the detail `message`. Card names and abilities are data and are not translated.

### 7.5 Preferences

Five account values: `lang`, `density`, `accent`, `bg_intensity`, `collection_view`; `null` = Auto.
- `rb_prefs_v1` (localStorage) mirrors the server copy; corrupt or out-of-domain values are dropped.
- Auto resolves per device (`prefs/resolve.ts`): viewport below 860 px (`down('md')`) is "phone":
  density `compact`, collection view `grid`; otherwise `regular` and `table`; accent `orange`; background 100.
  Re-resolved when the viewport crosses 860 px.
- `sync.ts` is optimistic: the change is written to the session cache at once; one PATCH in flight; each
  request carries only changed fields (`null` for Auto); sliders debounce 400 ms and flush on pointerup,
  blur and `pagehide`; on failure the previous value is restored with an error toast and a "Reintentar" action.
- `rb_lang` is the device language choice (written by the toggle and on logout); when signed in the toggle
  also saves `lang` to the account. While offline, saving is off and the controls are disabled.

### 7.6 App shell and navigation

- `AppShell`: skip link (first tab stop), sticky `Topbar` (64 px, 56 px below `sm`), one `main`
  (content capped at `--maxw`, `--maxw-wide` from `2xl`), and below 860 px the `BottomNav`. Top or bottom
  navigation is MOUNTED by `useMediaQuery(up('md'))`, not hidden. `OfflineBanner` shows while offline.
- `BottomNav`: the entries with placement `bottom` (Inicio, Cartas, Colección, Mazos) plus "Más", which
  opens `MoreSheet` (a native `<dialog>`: Interface, classic modules, language, install, Admin, logout).
- `shell/navRegistry.ts` is the single list behind topbar, bottom nav, sheet and home hub. Entry:
  `{id, icon, placements: ('top'|'bottom'|'hub'|'more')[], adminOnly?, status}` with `status` one of
  `spa` (`to` = router path without basename), `legacy` (`legacy` = key of `legacy-routes.json`, rendered as
  a plain `<a href>`, a full navigation) or `planned` (never rendered). Current entries: `home` and
  `interface` are `spa`; `dashboard`, `sets`, `cards`, `collection`, `decks`, `profile`, `price`
  (admin only) and `admin` (admin only, points at the `price` page) are `legacy`; `events`, `sales`, `stats`
  are `planned`.
- `legacy-routes.json` maps `dashboard`, `sets`, `cards`, `collection`, `decks`, `profile`, `price` to their
  Jinja URLs; each URL must match a GET rule of the Flask `url_map` (a unit that adds a legacy link adds
  that check).
- To port a module: flip its registry entry from `{status: 'legacy', legacy: 'cards'}` to
  `{status: 'spa', to: '/cards'}`, add the lazy route inside the `ShellError` group of `routes.tsx`, add the
  labels in `nav.json` (`items.<id>.label` and `.description`, both languages). Keep the Jinja page and its
  `legacy-routes.json` key until the page is retired (removing a key means updating the contract test).
- `HomeHub` is the launcher: tiles follow the registry status; legacy tiles show an "external" icon.

### 7.7 Styling, breakpoints, background

- `styles/index.css` declares `@layer reset, tokens, base, layout, components, utilities`. Unlayered CSS
  beats every layer, so every `*.module.css` wraps its rules in `@layer components { ... }` (a Vitest scan
  enforces it). Tokens are plain CSS custom properties on `:root` in `tokens.css`: colours (`--bg-0`
  `#06222c`, `--panel*`, `--line*`, `--cyan`, `--orange`, `--red`, `--green`, `--gold`, `--text`, `--muted`,
  `--muted-2`), `--accent*` (switched by `[data-accent]`), shape and density (`--radius`, `--radius-sm`,
  `--gap`, `--pad`, `--row-h`; `[data-density='compact'|'comfy']`, regular = no attribute), `--maxw`
  1280 px, `--maxw-wide` 1760 px, fonts (`--font-ui` Manrope Variable, `--font-display` Space Grotesk
  Variable, self-hosted, latin and latin-ext only), shadows, and the z scale (`--z-bg` -2, `--z-popover` 30,
  `--z-topbar` 40, `--z-botnav` 50, `--z-modal` 80, `--z-toast` 90). Dark mode only.
- Breakpoints (`lib/breakpoints.ts`, the only source; a Vitest scan fails any other `@media` width):
  `sm` 680, `md` 860, `lg` 960, `xl` 1240, `2xl` 1600 px. `up(bp)` is `(min-width: Npx)`, `down(bp)` is
  `(max-width: N-0.02px)`; mobile-first. The phone range is below 860 px. The Interface page shows a live
  preview beside the controls from 1240 px.
- Background: the Summoner's Rift map on a fixed layer, blurred 3 px and darkened, never brightened;
  slider 0..100 only changes how much shows (`bgVars`, overlay gradients as data in `lib/background.ts`);
  at 0 the layer is off and the image is not downloaded; portrait screens get the map rotated 90 degrees
  (`new_rift-portrait.webp`), phones below 860 px use the 1280 px variant. Body text keeps at least 4.5:1
  contrast over the worst case of the background (tests sample a grid at 390 and 1440 px for 0..100%).
- Global `:focus-visible` ring uses the accent; `prefers-reduced-motion` is honoured; safe-area insets are
  tokens (`--safe-top` and so on); font sizes below 11 px are rejected by a test.

### 7.8 UI primitives (`components/ui/`) - reuse these, do not rebuild them

`Avatar`, `Badge` (tones neutral, accent, success, warning, danger), `Brand` (mark, wordmark), `Button`
(variants primary, ghost, danger; sizes md, sm; `block`, `pending`), `Checkbox`, `ConfirmDialog`, `EmptyState`,
`ErrorState` (message + retry), `Field` (label, hint, error, render-prop control with `useId`), `Icon`
(typed names, decorative by default, `title` makes it an image), `Input`, `LiveAnnouncer` (`announce()`),
`Modal` (native `<dialog>`, `variant` modal or sheet, returns focus), `OfflineBanner`, `PageHeader`
(title, subtitle, actions), `Panel` (optional `h2` title), `PasswordInput`, `SegmentedControl`, `Select`,
`SettingsCard` / `SettingsRow`, `Sheet`, `Skeleton` (`aria-busy` region), `Slider` (with `onCommit`),
`Switch` (`role="switch"`), `Toast` / `ToastStack` with `pushToast({kind, message, action?, duration?})`
(default 6000 ms, 0 = persistent; popover in the top layer; announced through `LiveAnnouncer`).
Icons available: `dashboard cards collection decks sales stats calendar search filter image export trash
plus minus edit check close menu arrow refresh copy link logout tag star grid list coin gift card mail lock
key camera device globe pin clock ticket bookmark trophy account users shield sliders eye eye-off more
install warning offline settings info external-link check-circle`. There is no table, tab, chart,
card-image or form-grid primitive yet: those arrive with the phases that need them.

### 7.9 PWA

- Manifest (from `pwa-options.ts`): name and short name "Rift Manager", `id` and `scope` `/riftbound/`,
  `start_url` `/riftbound/app/`, `display: standalone`, `theme_color` and `background_color` `#06222c`,
  `lang: es`, `categories: ['games']`; icons `pwa-192x192.png` and `pwa-512x512.png` (any),
  `maskable-icon-512x512.png` (maskable). `apple-touch-icon-180x180.png`, `favicon.ico`, `favicon.svg`
  are in `public/` (committed; `npm run icons` regenerates them with `@vite-pwa/assets-generator`).
- Service worker: `generateSW`, `registerType: 'prompt'`, served at `/riftbound/app/sw.js`, so its scope is
  `/riftbound/app/` (the manifest scope is wider on purpose: an installed window may open a legacy page,
  which the worker never controls). Disabled in `npm run dev`.
- Precache: hashed JS and CSS, `index.html`, latin fonts, the three background images, brand SVGs, icons and
  the manifest (`globPatterns`; `globIgnores` drops unused font subsets and `.map`; 3 MB per-file cap).
  Navigation fallback `/riftbound/app/index.html`, allowed only under `/riftbound/app/`, denied for
  `/riftbound/api/`, `/riftbound/static/` and anything that looks like a file. There is NO runtime caching of
  the API, static files or Jinja pages: offline in F1 is the app shell only. Read-only offline use of the
  catalog, collection and decks is planned from F2 on and will need runtime caching decisions.
- Update: a new worker waits (`skipWaiting` and `clientsClaim` off). `UpdateToast` shows "Nueva versión
  disponible" with "Actualizar"; accepting activates the worker and reloads. Checks every hour and when the
  window becomes visible (online only). Dismissing keeps the current version and in-progress form data.
- Install: `InstallItem` in the topbar and the "Más" sheet, shown when not standalone and either the browser
  saved a `beforeinstallprompt` or the device is iOS Safari (then `IosInstallDialog` explains Share, then
  Add to Home Screen).
- Offline: `OfflineBanner` (`role="status"`); logout, preference controls and saving are disabled while
  offline. If the boot session request fails with a network error and the signed-in hint exists, the shell
  renders from the precache with the banner and recovers when the connection returns; without the hint the
  error screen offers a retry. Edits must be disabled while offline (new modules follow the same rule via
  `useOffline()` from `@/auth`).
- Rollback: build with `VITE_PWA_SELF_DESTROY=true` to ship a worker that unregisters itself, clears its
  caches and reloads open windows (a plain revert does NOT remove an installed worker). CI builds and checks
  that variant on every run. `npm run check:dist` verifies the manifest, icon sizes, `index.html` head tags,
  precache contents (no API URL, background images present) and that `altcha` is not in the entry chunk.
- Known harmless oddity: the generated `sw.js` lists seven entries twice in the precache (the manifest and
  six icon/favicon files, once from the glob and once from `includeAssets`). `dist/.vite/manifest.json`
  (`build.manifest`) is public and harmless.

## 8. Hosting and CI

### 8.1 SPA hosting (`app/routes/spa.py`)

Public, never touches `session` or `current_user`, so no response carries `Set-Cookie`. The directory
`FRONTEND_DIST` is read per request (a rebuild needs no restart).
- `/riftbound/app` is a 308 to `/riftbound/app/`; `/riftbound/app/` serves `index.html`.
- `/riftbound/app/<path>`: an existing file in dist is served; a missing path whose last segment has a file
  extension (`\.[A-Za-z0-9]{1,8}$`) is a real 404 (never `index.html`); any other path is a client route and
  gets `index.html`. Traversal outside dist never returns a file.
- Cache: `assets/*` is `public, max-age=31536000, immutable`; everything else (`index.html`, `sw.js`,
  `workbox-*.js`, `manifest.webmanifest`, icons) is `no-cache` with ETag (304 on revalidation).
- Every response: `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin` (the
  CSRF Referer check needs it). Explicit mimetypes for `.webmanifest`, `.woff2`, `.webp`, `.js`, `.svg`.
- No dist or no `index.html`: 503 with the build command (JSON or a minimal inline page); the rest of the
  application is unaffected. Details and deploy options: `docs/frontend.md`.

### 8.2 Server

Production-shaped runtime: systemd unit `docs/riftbound.service` (`EnvironmentFile` outside the repo with at
least `RB_ENV`, `SECRET_KEY`, `DATABASE_URL`), Gunicorn `--workers 3 run:app` binding all interfaces on
port 8000 (firewall it so only the Nginx host reaches it), Nginx template `docs/nginx_config` (one upstream,
two `proxy_pass` lines for `/` and `/riftbound/`, `Host`, `X-Forwarded-For`, `X-Forwarded-Proto` headers,
must not strip `Referer`, `limit_req` zone for the auth POSTs). Order for an upgrade: back up the database, install requirements, `flask db upgrade`,
`flask db check`, build the frontend, restart. The dev server runs this stack; there is no production.

### 8.3 GitHub Actions (`.github/workflows/`)

- `ci.yml` (push to `main`, PRs to `main`, `permissions: contents: read`):
  - `test`: Python 3.12, `pip install -r requirements.txt`, `pytest -vv --tb=long --cov=app` (SQLite), uploads
    `coverage-report`.
  - `migrations-pg`: PostgreSQL 18 service (database name contains `test`), `flask db upgrade`,
    `flask db check`, `flask db downgrade base`, `flask db upgrade`, then `pytest -m postgres`.
  - `frontend` (working directory `frontend`, Node from `.nvmrc`): `npm ci`, `npm run lint`,
    `npm run typecheck`, `npx vitest run`, `npm run build`, `npm run check:dist`, a second build with
    `VITE_PWA_SELF_DESTROY=true` into a temp dir plus `node scripts/check-dist.mjs --self-destroy`, then uploads
    `frontend/dist` as `frontend-dist` (7 days).
- `security.yml` (push to `main` and daily cron): `bandit==1.9.4`, `bandit -r app/ -ll`.
- `release.yml` (manual `workflow_dispatch`): input `vX.Y.Z` validated by regex, pushes the tag, creates a
  GitHub release; the only job with `contents: write`.
- No application secret ever enters CI (`DATABASE_URL`, `SECRET_KEY` are not defined in workflows; the
  PostgreSQL job uses `RB_ENV=development` for a per-process key).

## 9. Testing

- Backend: pytest 8.3.4, `pytest.ini` (`testpaths = tests`, marker `postgres`). As of 2026-10-21:
  1681 tests collected = 1640 pass + 41 skipped (the skipped ones are the PostgreSQL lane, which needs
  `TEST_POSTGRES_URL`). The suite sets `RB_ENV=testing` before importing the app, so `.env` is never read.
- Fixtures (`tests/conftest.py`):

| Fixture or helper | What it gives |
|---|---|
| `app` | app on in-memory SQLite, `create_all()` per test, CSRF off, limiter off, captcha `none`; drops the cached login between requests |
| `client` | plain test client |
| `authenticated_client` | client logged in as `testuser` through the real form |
| `make_user(username, email=None, password, is_admin=False, is_blocked=False)` | factory with a cheap password hash |
| `login_as(client, username, password)` | plain function (import from `tests.conftest`), logs in through the form |
| `admin_client`, `other_user_client` | own clients logged in as `admin` / `otheruser` |
| `sample_set`, `sample_card` | `TEST1` set and card `001` |
| `csrf_app`, `limited_app`, `altcha_app` | `app` with one protection switched on (request `admin_client` / `authenticated_client` BEFORE `csrf_app`) |
| `frozen_clock` | freezes `app.utils.clock.utcnow` at 2030-01-01 12:00 UTC; `.advance(minutes=...)` |
| `clean_env` | unsets every config variable and points `.env` at a missing file (config tests) |
| `migration_app` | empty SQLite with no `create_all()`; Alembic builds the schema |
| `pg_url` | throw-away PostgreSQL URL from `TEST_POSTGRES_URL`; refuses a name without `test`; drops schema `riftbound` before and after |
| `spa_dist`, `spa_app` | fake frontend build in a temp dir; `app` pointed at it (no Node needed) |

  Helpers: `tests/auth_helpers.py` (CSRF token extraction, an HTTPS `Browser`), `tests/migration_helpers.py`,
  `tests/snapshot_utils.py`. Nothing in the tests may reach the internet.
- Notable guard tests: `test_authz_matrix.py` (every URL rule classified), `test_docs.py` (AGENTS.md and
  README match the repo), `test_frontend_contracts.py` (altcha pin, error-code catalogs, legacy routes, doc
  sections), `test_ci_workflows.py`, `test_migrations.py` (+ `_pg`), `test_nginx_config_doc.py`,
  `test_spa_hosting.py`, `test_shell_coexistence.py`.
- Frontend: Vitest 5.0.3 in jsdom, about 1181 tests as of 2026-10-21 (unit f). `src/test/setup.ts` polyfills
  `<dialog>`, popover and relative `fetch`, installs the `matchMedia` mock, extends `expect` with axe
  matchers, starts the MSW server with `onUnhandledFrame: 'error'` (an unhandled request fails the test) and
  clears storage and `<html>` attributes after each test. Helpers: `test/renderApp.tsx` (`renderApp({path,
  lang, width, ...})` mounts the whole app on a memory router fed by MSW), `test/viewport.ts`
  (`setViewport(width)`, `setDisplayMode`), `test/msw/handlers.ts` (default handlers = anonymous visitor on
  a server without captcha; `signedInSession()`, `adminSession()`, `failure()`; tests override with
  `server.use`), `test/prefs.tsx` (`renderWithPrefs`), `test/i18n.tsx` (`renderWithI18n`), `test/css.ts`
  (CSS source assertions via postcss; jsdom does not resolve the cascade), `test/dialog.ts`, `test/popover.ts`.
  File-system tests opt out of jsdom with `// @vitest-environment node`.
- No end-to-end browser tests yet (Playwright and Lighthouse are planned for F11); the PWA device checklist in
  `docs/frontend.md` is manual.
