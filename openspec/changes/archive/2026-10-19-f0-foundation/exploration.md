# Exploration: f0-foundation (Roadmap F0 "Base")

> Date: 2026-10-18 | Branch: `feat/f0-foundation` (HEAD = `1ae1f6e`, 1 commit ahead of `origin/main`)
> Mode: openspec. Read-only investigation; no application code was modified.
> Method: code reading + throw-away probes with the Flask test client + two Alembic spikes
> (scratch venv outside the repo, see sections 3 and 4). Prod DB was NOT contacted.

## 0. Executive summary and blockers

| # | Finding | Severity |
|---|---------|----------|
| B1 | `config.py:14` falls back to `SECRET_KEY='you-will-never-guess'` and `config.py:17-18,21-22` embeds `postgres:<old-db-password>@192.168.1.33`. **The GitHub repo is PUBLIC** and the values are in history since `b310f07`. `docs/riftbound.service` sets no env vars and nothing calls `load_dotenv` (python-dotenv is unused), so prod very likely runs on the public default key: anyone can forge a Flask-Login session cookie for user id 1. | CRITICAL (act before F0 lands) |
| B2 | **26 tracked files are owned by root with mode 644** and are NOT writable by `racmos` (verified with `test -w`): `app/routes/domains/{collection,deck,price}.py`, `app/schemas/validators.py`, `app/models/{__init__,collection,cardmarket}.py`, `app/services/cardmarket_matcher.py`, `app/templates/{collection,deck,deck_view,price}.html`, `tests/test_{cardmarket_ignored,cardmarket_matcher,collection_foil,collection_merge}.py`, `.gitignore`, `.atl/skill-registry.md`, `migrations/install_db.sql`, `migrations/database/04..08_*.sql`, `docs/diagnostic_*.sql`; `.git/index` is root-owned too. `sdd-apply` will fail with EACCES on most files F0 must edit (writable: `config.py`, `app/__init__.py`, `errors.py`, `auth.py`, `models/user.py`, `sets.py`, `cards.py`, `profile.py`, `base.html`, `cards.html`, `sets.html`, `tests/conftest.py`, `tests/test_routes.py`). Fix: `sudo chown -R racmos:racmos /home/racmos/RBAPP` (user action; directories are already racmos-owned so `cp x x.tmp && mv x.tmp x` is a stop-gap). | BLOCKER for apply |
| B3 | Any logged-in user can today: create/edit sets and cards, run Cardmarket loads with **caller-supplied URLs (SSRF)**, trigger Riot scraping, and **write files outside the repo via `upload_image` path traversal** (`cards.py:152,168`, reproduced with the test client). | HIGH |
| B4 | Prod schema is unknown. Three divergent DDL sources exist (`docs/database_setup.sql`, `migrations/database/01..08`, `migrations/install_db.sql`) and they disagree with each other and with the models (section 3). A baseline must start from `pg_dump -s -n riftbound` of prod. | Needs user input |

Recommendation in one line: one SDD change `f0-foundation` (single proposal/specs/design) delivered as **5 PR-sized work units** (section 11), ordered config/secrets -> Alembic+quantity -> admin/authz -> CSRF+login hardening -> API skeleton+CI+docs.

---

## 1. Secrets and configuration

### Current state
- `config.py`: `Config` evaluates env at import time with insecure fallbacks (SECRET_KEY, full DB URI incl. password). `SQLALCHEMY_ENGINE_OPTIONS` is computed at import from the same fallback.
- `python-dotenv==1.0.1` is in `requirements.txt` but `grep -rn dotenv app config.py run.py wsgi.py` returns nothing: `.env` is never loaded. `.env.example` uses `postgresql://` (psycopg2 dialect, not installed) instead of `postgresql+psycopg://`.
- `docs/riftbound.service`: `Environment="PATH=..."` only, `ExecStart=... gunicorn --workers 3 --bind 0.0.0.0:8000 run:app`. No `EnvironmentFile`. (AGENTS.md says `-w 4 ... wsgi:app`, but `wsgi.py` exposes `application`, not `app`.)
- `docs/riftbound-landing.service` still starts a FastAPI app (`landing:app`) although the landing was migrated into Flask (`app/routes/landing.py`); `docs/nginx_config` still proxies `/` to 8001 (that obsolete service). Docs are stale.
- `run.py:27`: `app.run(host='0.0.0.0', port=5000, debug=True)` (Werkzeug debugger reachable from the LAN) and `db.create_all()` in `__main__` (conflicts with Alembic later).
- CI (`ci.yml`) injects `secrets.DATABASE_URL` / `SECRET_KEY` although `conftest.py` overrides both (`sqlite:///:memory:`, `'test-secret-key'`); `FLASK_ENV` is a no-op since Flask 2.3.
- `conftest.py` already passes `WTF_CSRF_ENABLED=False` (a hint that Flask-WTF was intended).
- Session cookie today (probed): `Set-Cookie: session=...; HttpOnly; Path=/` (no `Secure`, no `SameSite`).

### Options
| Option | Pros | Cons |
|--------|------|------|
| A. Env-only config classes (`Base/Development/Production/Testing`), selected by `RB_ENV` (default `production`), validated **inside `create_app` after test overrides are applied** | Fail-fast in prod; tests unaffected because `conftest` already passes `TESTING=True`, URI and `SECRET_KEY`; no import-time raise | Must move `SQLALCHEMY_ENGINE_OPTIONS` computation into `create_app` (already half done for sqlite) |
| B. Keep `Config`, only raise at import when env missing | Smallest diff | Raises at import -> breaks `from config import Config` in tests and tooling (`flask db`, `diagnose`) |
| C. Secrets manager (Vault/SOPS) | Strongest | Overkill for one VPS |

### Recommendation: A
- `create_app(config_class=None, **test_config)`: choose class from `RB_ENV`; after `config.update(test_config)` run `_validate_config(app)`: if not (`TESTING` or `DEBUG`) require `SECRET_KEY` (>= 32 chars, not the legacy default or `change-me` patterns) and `DATABASE_URL`; raise `RuntimeError` with an explicit message (visible in `journalctl`).
- Dev: `load_dotenv()` only when `RB_ENV` is unset/`development` (python-dotenv already installed). Prod: systemd `EnvironmentFile=/etc/riftbound/riftbound.env` (`chmod 640 root:www-data`) documented in `docs/`; no dotenv in prod.
- Cookie flags (config, env-overridable): `SESSION_COOKIE_SAMESITE='Lax'` (must be Lax, not Strict: F9 OAuth callbacks are cross-site top-level GETs), `SESSION_COOKIE_SECURE=True` in production (nginx_config already terminates TLS with Let's Encrypt for racmosdev.es), `SESSION_COOKIE_HTTPONLY=True`, optional `SESSION_COOKIE_PATH='/riftbound'`; same for `REMEMBER_COOKIE_*`. Changing the key invalidates all sessions (acceptable, desirable).
- `ProxyFix` count configurable (`PROXY_FIX_X_FOR`, default 1). Gunicorn binds `0.0.0.0:8000` and ProxyFix trusts `X-Forwarded-For`: anyone who can reach :8000 directly can spoof the client IP (defeats IP rate limits). Ops note: firewall :8000 to the Nginx host only.
- `run.py`: `debug` from env, host `127.0.0.1`, drop `db.create_all()` once Alembic lands.
- CI: remove `DATABASE_URL`/`SECRET_KEY`/`FLASK_ENV` env from `ci.yml`.
- **Runbook (out-of-code, user action)**: rotate the Postgres password for `postgres@192.168.1.33` (it is public), generate a new `SECRET_KEY` (`python -c "import secrets; print(secrets.token_urlsafe(48))"`), set both via EnvironmentFile. History rewrite not recommended once rotated.

Risks: prod start-up fails if env missing (intended; document in the PR); forgetting to set `RB_ENV`/vars on deploy. Testability: unit tests for `_validate_config` (RED: no key + not testing -> `RuntimeError`; legacy default -> `RuntimeError`; `TESTING=True` -> ok).

Affected: `config.py`, `app/__init__.py`, `run.py`, `wsgi.py`, `.env.example`, `docs/riftbound.service` (+ new env file doc), `docs/nginx_config`, `.github/workflows/ci.yml`, `tests/conftest.py` (unchanged contract), new `tests/test_config.py`.

---

## 2. Admin role, account block, route inventory and ownership audit

### Current state
`User` (`app/models/user.py`): `id, username(64), email, password_hash, created_at`; no role/active flags. Every route is `@login_required` only. 71 URL rules registered (`main` 1, `auth` 3, `sets` 3, `cards` 4, `collection` 15, `deck` 9, `price` 23, `profile` 2, `landing` 10, static 1).

Flask-Login 0.6.3 facts (verified in `venv/.../mixins.py`, `utils.py:180`): `UserMixin.is_authenticated` returns `self.is_active`, and `login_user` refuses inactive users. So a column `is_active` on `User` blocks **both new logins and existing sessions** on the next request, with no extra code. Unauthenticated JSON requests currently get `302 -> /riftbound/login` (probed), not 401.

### Route inventory (class: P=public, U=any authenticated user, A=admin-only after F0)
| Route (method) | file:line | Class | Notes |
|---|---|---|---|
| `/`, `/api/{noticias,discord,torneos-online,torneos-fisicos,videos,decks}`, `/frames/*`, `/landing/static/*` | `landing.py:50,58-97,104-113` | P | The 6 `/api/*` partials trigger an **uncached outbound scrape per hit** (`scraper.py:217,256,289`, timeout 10 s): unauthenticated worker-exhaustion vector with 3 workers. Rate-limit or cache (F0 limiter covers it). Not colliding with `/riftbound/api/v1`. |
| `/riftbound/login`, `/register` (GET/POST) | `auth.py:8,27` | P | form posts, no Pydantic validation, no length/format checks |
| `/riftbound/logout` (GET) | `auth.py:55-59` | U | state change via GET (logout CSRF) -> make it POST |
| `/riftbound/` dashboard | `routes.py:10` | U | |
| `/riftbound/set` (list) | `sets.py:14` | U | read-only catalog |
| `/riftbound/set/add`, `/set/update/<id>` | `sets.py:31-34, 57-60` | **A** | |
| `/riftbound/card` (list) | `cards.py:17` | U | `search_id` is interpolated into a Postgres regex (`cards.py:45`) -> 500 on `(`; not testable on SQLite (`~` operator) |
| `/riftbound/card/upload_image` | `cards.py:143-145` | **A** | path traversal: `set_id` from form -> `os.path.join('app','static','images','cards', set_id.lower())` (`:168`), CWD-relative, no sanitisation (probe wrote outside `static/`). Also folder = `set_id.lower()` while `image_src` derives it from the filename prefix (mismatch for promo sets). |
| `/riftbound/card/add`, `/card/update/<set>/<card>` | `cards.py:179-181, 213-216` | **A** | |
| `price/*` all 23 routes (`''`, `generate`, `refresh-riot-sets`, `extract-riot-cards`, `cardmarket-{load,unmatched,search-cards,map,unmapped-expansions,map-expansion,card-detail,card-search-full,upsert-card,product-detail,product-search,unmap,mappings,auto-match,upsert-product}`, `ignored{,/add,/restore}`, `auto-match/apply`) | `price.py:23,30,53,65,85,113,168,190,268,310,376,390,403,468,486,499,533,675,697,750,769,783,823` | **A** | `cardmarket-load` accepts `singles_url/nonsingles_url/price_guide_url` from the body (`price.py:93-101`) -> SSRF for any user today. If kept after F0, restrict to an allow-list of hosts. `generate` (CSV of catalog) could arguably stay U; roadmap says all of price/* -> A (confirm). |
| `/riftbound/collection` + 12 mutating routes (`add, update_quantity, delete, update_selling, update_playset, update_sell_price, update_condition, update_language, bulk_apply, bulk_delete, import_csv, export_csv`) | `collection.py:167,298,359,377,388,400,422,434,446,458,585,671,704` | U (owner-scoped) | ownership OK: `_get_owned_row` (`:290-295`), `bulk_*` filter `rbcol_user` (`:542-545, 595-598`), `import_csv` (`:681-686`), `export_csv` (`:722`) |
| `/riftbound/collection/api/{sets,cards}` | `collection.py:603,614` | U | catalog reads |
| `/riftbound/deck` (list: "My decks" owner-scoped + "All public decks") | `deck.py:228` | U | all decks are intentionally visible to every logged-in user; loads all rows in memory (`:287-288`) |
| `/riftbound/deck/api/legends` | `deck.py:336` | U | |
| `/riftbound/deck/view/<int:id>`, `/view/<name>`, `/view/<name>/<seq>` | `deck.py:384,395,411` | U (public among users) | no ownership check by design ("público por defecto"). Problems: `have/missing` is computed from the **owner's** collection (`:184`, `_enrich_cards_for_view`) -> leaks another user's holdings; `/view/<name>[/<seq>]` picks an arbitrary user's deck because names are not unique across users (`:400-404, 415-417`). |
| `/riftbound/deck/versions/<name>` | `deck.py:424-442` | U (owner-scoped) | **broken**: reads `d.rbdck_rbset_id/rbdck_rbcar_id` (`:433-434`) which do not exist -> `AttributeError` 500 as soon as the user has a deck by that name |
| `/riftbound/deck/save` | `deck.py:445-448` | U | ok (`current_user`); `get_next_seq` race vs UNIQUE(user,name,seq) (`:479`) |
| `/riftbound/deck/update/<set>/<card>` (POST), `/deck/delete/<set>/<card>` (DELETE) | `deck.py:505-585, 588-603` | U (owner-scoped filter) | **dead and broken**: filter/ctor use non-existent `rbdck_rbset_id/rbdck_rbcar_id` (`:510-511, 531-532, 572-573, 593-594`) -> 500 (reproduced); `delete` has no `return` (`:603`). No template calls them. Remove in F0 (or return 410) |
| `/riftbound/profile`, `/profile/update` | `profile.py:13,20` | U (self only) | duplicate email -> `IntegrityError` 500 (`:27-28`, reproduced); password change does not require current password (`:30-31`); confirm-password only checked client-side |

Other pre-existing defects seen (not F0 scope unless noted): `bulk_apply` list/garbage body and `bulk_delete` non-numeric ids -> 500 (`collection.py:474,479,591`, reproduced); `import_csv` has no validation (`:671-701`, see section 4); `deck.html:307,675,702` call `/riftbound/deck/api/copy|summary/<ts>` which do not exist (dead JS, F5 rewrites).

### Options for admin enforcement
| Option | Pros | Cons |
|--------|------|------|
| A. `@admin_required` decorator on each mutating route + `price_bp.before_request` guard for the whole blueprint | Blueprint guard cannot be forgotten for new price routes; decorator explicit for 5 set/card routes | two mechanisms |
| B. Decorator on all 28 routes | uniform | easy to miss when adding routes |
| C. Role table / RBAC | extensible | roadmap says single owner-admin; YAGNI |

### Recommendation: A + authorization-matrix test
- Columns on `rbusers` (match existing unprefixed style of that table): `is_admin BOOLEAN NOT NULL DEFAULT false`, `is_active BOOLEAN NOT NULL DEFAULT true` (account block; overrides `UserMixin.is_active`), `failed_login_count INTEGER NOT NULL DEFAULT 0`, `locked_until TIMESTAMP NULL`, `last_login_at TIMESTAMP NULL`. Migration must be an Alembic revision (needs unit F0b first) with `server_default` so existing rows are valid; works on PG and SQLite.
- `app/security.py` (or `app/auth/decorators.py`): `admin_required` = login + `current_user.is_admin` else `abort(403)`; JSON-aware via the shared predicate (section 6).
- Bootstrap admin through Flask CLI (`flask users make-admin <username>`, plus `unlock`, `set-password` since there is no email reset) — no secret in env, no auto-promotion in a migration.
- UI: hide Price link/dashboard card and Add/Edit controls in `base.html`, `dashboard.html`, `sets.html`, `cards.html` when `not current_user.is_admin` (defense in depth; server check is authoritative). GET list pages stay open to users.
- Fix in the same unit because they are authz/ownership related: sanitize `upload_image` (`set_id` allow-list `^[a-z0-9]+$`, resolve under `current_app.static_folder`, derive folder from filename prefix via `_image_folder`), allow-list hosts for `cardmarket-load` overrides, profile email uniqueness + current-password for password change, remove or 410 the two dead deck routes and fix `versions`, decide `have/missing` viewer-vs-owner (recommend viewer's collection).
- Strict-TDD guard: a parametrised test that iterates `app.url_map` and asserts each rule is classified P/U/A in an explicit table and enforces 401/403/200 accordingly; adding an unclassified route fails CI.

Test impact: **~14 existing tests must move from `authenticated_client` to a new `admin_client` fixture**: `tests/test_routes.py` (`set/add` x3 at `:121,138,149`; `card/add` x2 at `:173,188`) and `tests/test_cardmarket_ignored.py` (`price/ignored/*`, `cardmarket-unmatched`, `auto-match/apply` at `:59-148,184,280,316`). Add fixtures `admin_client`, `other_user_client`.

Risks: locking the owner out (mitigate: CLI promote before deploying the guard; migration order); blocked-user semantics with F9 session table later.

---

## 3. Alembic / Flask-Migrate baseline

### Current state
- No Alembic. Schema = raw SQL: `migrations/database/01..08_*.sql`, consolidated snapshot `migrations/install_db.sql` (530 lines, `DROP TABLE IF EXISTS`!), and the oldest `docs/database_setup.sql` (TEXT columns, `rbusers.username VARCHAR(64)`, composite PK on rbcollection). `migrations/database/README.md` documents only 01-03.
- Tests: `db.create_all()` on in-memory SQLite with an `ATTACH DATABASE ':memory:' AS riftbound` hook registered on `Engine` connect (`app/__init__.py:26-58`) plus `regexp_replace` shim.
- **Spike 1 (scratch venv, Flask-Migrate 4.1.0 / Alembic 1.20.0, current PyPI)**: `Migrate(app, db, version_table_schema='riftbound', include_schemas=True)` + autogenerate + `upgrade` on the in-memory SQLite with attached `riftbound` works: all 14 tables created as `riftbound.*` and `riftbound.alembic_version` lives in the attached schema. Hence migrations can be tested in pytest with the same fixture style.

### Model vs SQL drift (expected differences; verify against prod dump)
| Area | Models | SQL 01-08 / install_db | Impact on Alembic |
|---|---|---|---|
| `rbusers.username` | `String(64)` | `VARCHAR(80)` (`database_setup.sql`: 64) | type diff; unique index names differ (`ix_riftbound_rbusers_username` vs UNIQUE + `idx_rbusers_username`) |
| `rbset.*`, `rbcards.*` | `Text` everywhere | `VARCHAR(20/50/100/200)`, `rbcar_banned VARCHAR(1)` | pydantic allows longer values than DB (`SetCreate.rbset_id` max 50 vs VARCHAR(20); `CardCreate.rbcar_tags` 500 vs VARCHAR(200)) -> 500 on insert |
| FKs | none declared in models | `fk_rbcards_set`, `fk_collection_card`, `fk_collection_user -> rbusers(username)`, `fk_deck_user`, `fk_market_card`, `fk_product_card_map_card`, `fk_rbproducts_set` | autogenerate would try to DROP them unless models declare them or `include_object` ignores |
| `rbcollection` | `rbcol_id Integer`; `rbcol_foil/user/chadat` NOT NULL; `rbcol_user String(64)`; `rbcol_quantity Text`; `rbcol_selling Text` | `rbcol_id BIGSERIAL`; `foil/user/chadat` nullable; `VARCHAR(80)`; `rbcol_quantity VARCHAR(20)` (`database_setup.sql`: TEXT); `selling VARCHAR(1)` | PK Integer would shrink BIGINT -> use `BigInteger().with_variant(Integer,'sqlite')`; NOT NULL on `rbcol_user` fails if prod has NULLs |
| `rbcollection` constraints/indexes | none | `rbcollection_selling_chk IN ('Y','N','S')`, `rbcollection_playset_chk IN (1,2,3)`, 4 `idx_rbcollection_*` | absent from models -> autogenerate proposes dropping the indexes (perf regression on the main query) |
| `rbdecks` | `rbdck_user Text`, `rbdck_seq SmallInteger`, `rbdck_cards JSON`, `index=True` x3, UniqueConstraint `uq_deck_user_name_seq` | `VARCHAR(80)` + FK, `INTEGER`, **`JSONB`**, `idx_rbdecks_*` x4, unnamed UNIQUE | JSON vs JSONB (use `JSON().with_variant(JSONB(),'postgresql')`); name drift |
| `rbcm_product_card_map` | no CHECK, no FK, `rbpcm_foil String(1)` | `rbcm_pcm_foil_chk`, FK to rbcards, 4 indexes | same pattern |
| `rbcm_expansions` | `rbexp_rbset_id` col | + partial index `idx_rbcm_expansions_unmapped` | partial index not in model |
| `rbcm_price/products/...` | PKs only | extra `idx_rbcm_*` (e.g. `idx_rbcm_price_id_product`, used by `max(date) GROUP BY id_product`) | must be preserved |
| `rbcardmarket` | model only | table + FK | no route uses it (legacy) but exists in prod |
| Comments | none | many `COMMENT ON` | ignored |

### Options
| Option | Pros | Cons | Effort |
|---|---|---|---|
| A. **Empty baseline + `flask db stamp`** on prod; fresh installs keep `install_db.sql` | trivial, zero prod risk | two ways to build a DB; tests/CI can't validate the real history; autogenerate diffs noisy | Low |
| B. **Full baseline revision** reproducing the prod schema as of 08 (hand-reconciled with a `pg_dump -s`), `stamp` on prod, `upgrade` on fresh DBs; reconcile/aligned-model revision afterwards | single build path; CI can run `upgrade head` on empty PG and SQLite; legacy SQL becomes history | needs prod dump first; baseline must be written carefully | Medium |
| C. Autogenerate baseline from models | fast (spike 1 proves it works) | encodes the models' idea of the schema, not prod's: drops indexes/FKs/CHECKs, wrong types | Low but unsafe |

### Recommendation: B, executed in this order
1. User provides `pg_dump --schema-only -n riftbound` of prod (gate; compare with section table).
2. `Migrate(app, db, directory='migrations', version_table_schema='riftbound', include_schemas=True, compare_type=True)` with `include_name` (schemas `{None,'riftbound'}` only — the DB is the shared `postgres` DB, never touch `public`) and `include_object` (ignore reflected objects not in metadata until models are reconciled).
3. `0001_baseline` = prod state as of migration 08 (`op.create_table`, guarded by `has_table` so it is safe to run on an existing DB; `CREATE SCHEMA IF NOT EXISTS riftbound` only on PG). Prod: `flask db stamp 0001`.
4. `0002` quantity -> Integer (section 4). `0003` is_admin/is_active/lock columns (section 2). Reconcile models with prod (declare real indexes/FKs/CHECKs/BigInteger/JSONB variants) so `alembic check`/`compare_metadata` is clean.
5. Move legacy SQL out of the way: `git mv migrations/database migrations/legacy_sql`, `migrations/install_db.sql` and `docs/database_setup.sql` -> `migrations/legacy_sql/` with a README stating "frozen, superseded by Alembic". Rewrite `migrations/database/README.md`.
6. Tests: keep `create_all()` for the bulk (fast). Add (a) a test that runs `flask_migrate.upgrade()` on the in-memory SQLite fixture and (b) a drift-guard asserting `alembic.autogenerate.compare_metadata` returns no table/column diffs after `upgrade head`. CI adds a Postgres 16 service job: `upgrade head` from empty, then from a restored legacy dump + `stamp`, then `alembic check`.
7. PG+SQLite portability: use `op.batch_alter_table(...)` for ALTERs (SQLite recreates the table; PG emits a plain ALTER), `postgresql_using=` for casts, dialect guards for PG-only DDL.

Risks: baseline wrong vs prod (mitigated by dump comparison + stamp-only on prod); Flask-Migrate default directory `migrations/` collides with the legacy folder (handled by moving it); first `alembic revision --autogenerate` noise.

Affected: `requirements.txt` (+ `Flask-Migrate==4.1.0` and an explicit `alembic` pin; spike used 1.20.0), `app/__init__.py` (`migrate = Migrate()`), new `migrations/{env.py,script.py.mako,alembic.ini,versions/}`, models (index/FK/type reconciliation), `run.py`, `docs/*`, CI.

---

## 4. `rbcol_quantity` Text -> Integer

### Usage inventory (all must change)
| Location | Today | Change |
|---|---|---|
| `models/collection.py:18` | `db.Text, nullable=False` | `db.Integer, nullable=False` (+ `CheckConstraint('rbcol_quantity >= 1')` recommended) |
| `collection.py:34-39` `_qty_int` | tolerant `int()` | delete (or keep as identity during transition); callers `:337,409,574,735` |
| `collection.py:337` | `str(_qty_int(existing)+n)` read-modify-write | `existing.rbcol_quantity = RbCollection.rbcol_quantity + n` (atomic, fixes a lost-update race) |
| `collection.py:346,371,552` | `str(...)` writes | drop `str()` |
| `collection.py:215` | `quantity` sort on a **text** column ("10" < "2") | becomes numeric automatically (bug fixed); add test |
| `collection.py:671-701` `import_csv` | no validation, assigns arbitrary text, overwrites quantity, `.first()` among several rows, 500 on non-JSON | validate with Pydantic (`;` CSV lines -> set, card, foil in {N,S}, qty int 1..9999, card must exist), report skipped lines; semantics (overwrite vs add) to be confirmed |
| `collection.py:704-767` `export_csv` | `_qty_int(...) - playset` | plain int arithmetic |
| `deck.py:132-138` | `int(r.rbcol_quantity)` with try/except | `func.sum` or plain int |
| Templates `collection.html:249,331` | print value; JS reads text | no change (ints render the same) |
| Tests | `test_collection_merge.py:80,105,144` use `int(...)`; `test_collection_foil.py:21`, `test_routes.py:215,229` send ints | still pass; add numeric-sort, import validation, migration tests |
| SQL/docs | `01_create_tables.sql:109`/`install_db.sql:111` `VARCHAR(20)`, `database_setup.sql:98` `TEXT` | superseded by the Alembic revision (prod may be either type) |

### Migration `0002_quantity_integer`
1. Pre-flight (PG): `SELECT rbcol_id, rbcol_quantity FROM riftbound.rbcollection WHERE btrim(rbcol_quantity) !~ '^[0-9]+$' OR btrim(rbcol_quantity)::numeric > 9999` (guard the cast with the regex first). Non-empty result -> `RuntimeError` listing ids (never silently coerce; `_qty_int` treated junk as 0, so such rows may exist because `import_csv` accepts anything). Optional opt-in env to coerce.
2. Alter: `with op.batch_alter_table('rbcollection', schema='riftbound') as b: b.alter_column('rbcol_quantity', existing_type=sa.Text(), type_=sa.Integer(), existing_nullable=False, postgresql_using='btrim(rbcol_quantity)::integer')`. **Spike 2 proved the same code path works on SQLite** (batch recreate keeps data: `'12'`,`'3'` -> integers 12, 3) and on PG it is a plain `ALTER COLUMN ... TYPE ... USING` (table rewrite + ACCESS EXCLUSIVE lock; fine for this table size).
3. Downgrade: back to `Text` with `USING rbcol_quantity::text`.
4. Runbook: `pg_dump -n riftbound` before; run in a maintenance window.

Risks: junk values in prod (pre-flight covers); other readers of the column outside this repo (none found).

---

## 5. CSRF

### Current state / exposure today (probed + read)
Cookie-session auth, no CSRF protection. State-changing endpoints reachable with a cross-site **form-encodable** request (no JSON needed): login and register (forms), `logout` (GET), `card/upload_image` (multipart), `price/refresh-riot-sets`, `price/cardmarket-load` (`get_json(silent=True)`), `price/cardmarket-auto-match` (silent). JSON endpoints behind `@validate_json` are protected incidentally by the content-type check (no CORS configured), others only by `get_json()` 415. The frontend is ~35 `fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}})` calls spread over 7 templates plus 2 HTML forms (`login.html`, `register.html`); all templates extend `base.html`.

### Options
| Option | Pros | Cons |
|---|---|---|
| A. **Flask-WTF `CSRFProtect`** (1.3.0): session token, `X-CSRFToken` header or `csrf_token` field, optional Referer check on HTTPS | maintained, standard, SPA-friendly via `generate_csrf()`; `WTF_CSRF_ENABLED=False` already in conftest | new dep (WTForms); strict Referer check on HTTPS needs correct ProxyFix/Host (verify behind Nginx) |
| B. Custom double-submit / header token (~50 lines, itsdangerous) + `Sec-Fetch-Site`/`Origin` check | zero deps | we own security-critical code, edge cases (rotation, expiry) |
| C. Rely on SameSite=Lax + JSON content-type | no work | does not cover the form-encodable endpoints above; Firefox/Safari don't default to Lax |

### Recommendation: A
- `csrf = CSRFProtect(app)`; `WTF_CSRF_TIME_LIMIT=None` (token lives as long as the session, otherwise a PWA left open >1 h starts failing); `CSRFError` -> JSON `{success:false,error:'CSRF Error',message}` 400 when JSON expected (else HTML 400 page).
- Jinja: `<meta name="csrf-token" content="{{ csrf_token() }}">` in `base.html` + **one global `fetch` wrapper** (adds `X-CSRFToken` to same-origin non-GET) so none of the 35 call sites change; hidden `csrf_token` input in `login.html`/`register.html`; logout becomes a POST form/button. Add a test that renders every template extending `base.html` and asserts the meta tag.
- SPA (F1): `GET /riftbound/api/v1/auth/session` (or `/auth/csrf`) returns the token; client sends it as `X-CSRFToken`; on a CSRF 400 refetch once.
- Cookies: see section 1 (`SameSite=Lax`, `Secure` in prod, `HttpOnly`). Do not exempt the API blueprint.
- Tests: `conftest` keeps `WTF_CSRF_ENABLED=False` (existing 93 tests untouched); new `csrf_app` fixture with it enabled covering: POST without token -> 400; with header token -> 200; login form without token -> 400; multipart upload with header token.

Risks: a missed `fetch` path (mitigated by the wrapper); prod-only failure from the HTTPS Referer check (smoke-test through Nginx with `X-Forwarded-Proto`; ProxyFix `x_proto=1` is already set); PWA/offline later must refetch token.

---

## 6. API v1 skeleton

### Current state
Only HTML + ad-hoc JSON endpoints under domain prefixes (`/riftbound/collection/api/*`, `/riftbound/deck/api/legends`). `app/errors.py`: handlers for 400/401/403/404/500/Exception choose JSON vs HTML with `request_wants_json()` (`errors.py:94-100`) whose `accept_mimetypes.accept_json` is **True for `*/*`**, i.e. also for a normal browser navigation (`Accept: text/html,...,*/*;q=0.8`). Probed: a browser 404 returns `application/json`; HTML error pages are effectively never shown. Flask-Login's unauthorized handler redirects JSON clients to the login page (302) instead of returning 401. `validate_json` already returns the standard `{success:false,error,message,details}`.

Verified predicate that fixes the browser case without breaking `fetch` GETs (which send `*/*`): `request.path.startswith('/riftbound/api/') or request.is_json or request.accept_mimetypes.best_match(['application/json','text/html']) == 'application/json'` (browser nav -> `text/html`; `*/*` -> JSON; no Accept header, as in the test client -> None -> HTML/redirect, so existing tests keep their behavior).

### Proposed layout
```
app/api/__init__.py          # register_api(app)
app/api/v1/__init__.py       # api_v1_bp = Blueprint('api_v1', __name__, url_prefix='/riftbound/api/v1')
app/api/v1/meta.py           # GET /health, GET /meta/config
app/api/v1/auth.py           # GET /auth/session, POST /auth/login|logout|register
app/api/schemas.py           # LoginRequest, RegisterRequest (Pydantic), reused by the Jinja auth views
app/api/responses.py         # ok(data, **meta) / fail(error, message, status, details)
app/services/auth.py         # authenticate()/register_user(): lockout, limiter hooks, captcha check (shared by Jinja + API)
```
Coexistence: existing blueprints untouched; new prefix does not collide with the landing's root-level `/api/*` partials; Nginx `location /riftbound/` already covers it (SPA static + proxy split is F1).

### F0 endpoints (minimal but useful for F1)
| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /health` | P | `{status:'ok', db:'ok', version}` (DB `SELECT 1`), for monitoring/CI smoke |
| `GET /meta/config` | P | `{captcha:{provider, required_for:[...]}, registration_open, env}` so the login screen knows what to render |
| `GET /auth/session` | P | `{authenticated:false, csrf_token}` or `{authenticated:true, user:{id,username,email,is_admin}, csrf_token}` |
| `POST /auth/login` | P | JSON login with limiter/lockout/captcha; 200 / 401 / 423-or-429 with `Retry-After` |
| `POST /auth/logout` | U | |
| `POST /auth/register` | P | Pydantic validation (username `^[A-Za-z0-9_.-]{3,32}$`, email format, password >= 8), captcha required |
Game-rules endpoint: defer to F5 (rules module lives there); F0 only reserves the namespace. Everything else (catalog, collection) migrates per phase.

### Envelope decision (needs user confirmation)
Errors are already `{success:false,error,message,details?}` (also mandated by `openspec/config.yaml`). For success: (1) flat `{success:true, ...fields}` like today, or (2) `{success:true, data:{...}, meta?:{...}}`. Recommend (2) for the typed TS client (no key clashes with `success/error/message`, room for pagination meta) while documenting that legacy Jinja endpoints stay flat.

### Error handling work
- Replace `request_wants_json()` with the predicate above (`app/errors.py`); add handlers for `CSRFError`, `RateLimitExceeded`/429 (+`Retry-After`), 405, 415, 422-style validation; unify `HTTPException` JSON output; log 500s with request id.
- `login.unauthorized_handler`: JSON 401 for API/JSON requests, redirect otherwise.
- Tests: `/api/v1/health` 200; unknown `/api/v1/x` -> JSON 404 even with browser Accept; unauthenticated `/auth/session` -> `authenticated:false`; 401 JSON for protected API stubs; browser Accept on non-API 404 -> HTML.

Risks: changing `request_wants_json` can alter how existing Jinja JS sees errors (kept compatible for `*/*`); two response styles during coexistence.

---

## 7. Rate limiting, CAPTCHA, account lockout

### Host facts
This dev host: no `redis-server`/`redis-cli` (`which` empty; `systemctl is-active redis` = inactive). Prod host (192.168.1.31) unknown. Prod runs Gunicorn with **3 workers** (`riftbound.service`; AGENTS says 4), so in-process counters are per worker.

### Rate-limit storage
| Option | Pros | Cons |
|---|---|---|
| Flask-Limiter 4.1.1 `memory://` | zero infra, per-route decorators, JSON 429 | counters per worker -> effective limit up to 3x; lost on restart |
| Flask-Limiter + Redis | exact, shared | new service to run/secure; not present |
| Nginx `limit_req` on `/riftbound/{login,register}` and `/api/v1/auth/*` | shared across workers, no app code, protects before Python | config outside repo (`docs/nginx_config`), IP-only |
| DB-backed counters (custom table) | exact, no infra | custom code, write load, more to test |

**Recommendation (layered)**: (1) Nginx `limit_req` for IP-level throttling (documented snippet); (2) Flask-Limiter with `RATELIMIT_STORAGE_URI` env (default `memory://`, switch to Redis if it appears) as defense in depth and for JSON 429s, decorated on login (`10/min;50/h`), register (`5/h`), and the public landing `/api/*` partials; (3) **authoritative per-account lockout in the DB** (shared by all workers). Disabled in tests via `RATELIMIT_ENABLED=False`; dedicated tests enable it.

### CAPTCHA (no third-party account)
| Option | Account needed | Pros | Cons |
|---|---|---|---|
| **ALTCHA** (open-source proof-of-work; PyPI `altcha` 2.3.0 = official `altcha-org/altcha-lib-py`, MIT, zero deps; self-hosted web component) | none | privacy-friendly, no external requests, works in Jinja and the future SPA | PoW not a human test (raises bot cost); must add replay protection (store used signatures/salts) and expiry |
| Cloudflare Turnstile / hCaptcha | yes + external JS | strong bot detection | third party, privacy, domain config; outage = no login |
| Home-grown math/image captcha | none | simple | weak vs OCR, accessibility cost, we own the code |
Recommendation: provider interface (`none` for dev/tests, `altcha` default, `turnstile` pluggable via env). Required on **register always**, on **login after >= 3 recent failures** (account or IP). Decision for the user.

### Lockout policy (proposal)
- `failed_login_count` incremented on bad password for an existing user; reset on success. At 5 failures -> `locked_until = now + 15 min` (escalating 15 -> 30 -> 60 min, cap 24 h), response is a generic "invalid credentials or temporarily locked" plus `Retry-After`; correct password during lock is rejected. Unknown usernames: only IP limits apply (username enumeration already possible through `register`'s "Username already exists"; accept).
- Constant-time behavior: verify against a dummy hash when the user does not exist.
- Admin block = `is_active=false` (permanent until admin flips it; F10 UI), distinct from temporary lock. `flask users unlock <username>` CLI for the owner.
- Flask-Login integration: override `is_active`; check `locked_until` in `services.auth.authenticate`, not in `is_active` (a lock should not kill an already-valid session).
- Testability: inject a clock helper (`app/utils/clock.py: utcnow()`) so tests can advance time without freezegun.

Risks: legitimate users behind shared IP; in-memory limiter weaker than it looks (hence DB lock); PoW captcha UX on slow phones (tune difficulty).

Affected: `requirements.txt` (+ Flask-Limiter, + altcha), `app/__init__.py`, `app/services/{auth,captcha}.py`, `app/models/user.py`, `login.html`, `register.html`, `base.html`, Nginx doc.

---

## 8. CI

| Item | Today | Issue / proposal |
|---|---|---|
| `ci.yml` | py **3.13**, `pip install -r requirements.txt`, `pytest -vv --tb=long --cov=app`, injects `secrets.DATABASE_URL/SECRET_KEY`, `FLASK_ENV: testing`; triggers push main/develop (no `develop` branch exists), PR to main | drop env block (tests self-configure; avoid handing a prod DB URL to CI), pip cache, single pinned Python, coverage artifact |
| `security.yml` | bandit on py **3.14**, unpinned, `bandit -r app/ -ll`, daily cron | pin bandit, align Python; fails daily if medium findings exist (expected to fire on `upload_image`, `requests` use) |
| `release.yml` | manual tag + `softprops/action-gh-release@v2` | no `permissions: contents: write`; doesn't require green CI |
| Python drift | local venv/dev **3.12.3**, CI 3.13, bandit 3.14, prod unknown | pick one (recommend 3.12 to match dev/prod, optional matrix 3.12+3.13); add `.python-version`. Remove unused `pandas==2.2.3` (never imported; no 3.14 wheels) and unused `python-dotenv` only if config does not adopt it (it will) |
| Missing jobs | no PG job, no lint | add `migrations-pg` job (service `postgres:16`: `upgrade head` from empty, stamp+upgrade from legacy dump, `alembic check`); optional ruff |
| Frontend placeholder | none | job gated by `hashFiles('frontend/package.json') != ''` and `paths: frontend/**`: setup-node (LTS pinned via `.nvmrc`), `npm ci`, lint, typecheck, `vitest run`, `build`; no-ops until F1 |
| Branch protection | unknown | recommend required checks on `main` |

---

## 9. Housekeeping

| Item | Finding | Action |
|---|---|---|
| `AGENTS.md` (outdated) | stack versions (Flask 3.0.0/SQLA 2.0.23/Pydantic 2.5.3/pytest 7.4.3 vs 3.1.0/2.0.36/2.10.5/8.3.4); structure lacks `landing.py`, `services/`, `models/cardmarket.py`, `migrations/`, `.github`, `.atl`, `openspec`, `static/landing`; "11 templates", "docs 39 files" (actual 6), "~40 tests" (actual 93 in 7 files); table list omits `rbcm_*`/`rbproducts`/`rbcm_ignored`; "all routes except login/register require login" (landing is public); "all JSON endpoints use `@validate_json`" (bulk_*, import_csv, most price/*, deck legacy don't); prod command `gunicorn ... wsgi:app` (actual `run:app`, 3 workers, `wsgi.py` exposes `application`); lists skills `python-pro`, `fastapi-pro` that don't exist (`.agents/skills` has 31 others); no mention of roles/CSRF/API/Alembic/openspec/roadmap | rewrite after F0 content is known |
| `README.md` | 9 bytes (`# RBAPP`) | real README: setup, env vars, running, tests, migrations, deploy |
| `package.json`/`package-lock.json` | only dependency `@anthropic-ai/sdk ^0.78.0`; `grep -rn anthropic` over py/js/html/json finds no use; no `node_modules`; `.gitignore` has no Node entries | delete both; add `node_modules/`, `frontend/dist/`, `.vite/` to `.gitignore` |
| `diagnose.py` | obsolete (expects `app/models.py`, `app/routes.py`, imports `RbCardMarket`, prints `.env` keys, opens DB) | delete (replace by `/api/v1/health`) |
| `docs/*.sql` | `diagnostic_ahri.sql`, `diagnostic_mappings.sql` ad-hoc; `database_setup.sql` oldest DDL | move to `migrations/legacy_sql/` or `docs/legacy/`; mark frozen |
| `docs/riftbound-landing.service`, `docs/nginx_config` | FastAPI landing service obsolete; Nginx still routes `/` to :8001 | update to current topology |
| Root-owned files | see B2 | `chown -R` (user) |
| `.coverage` | **not** tracked (`.gitignore` has it; `git status --ignored` shows `!!`); just root-owned | nothing to commit-clean; fix ownership |
| Untracked tooling | `.agents/`, `.claude/`, `skills-lock.json` (root-owned, ~31 skills) appear in `git status` | decide: ignore via `.gitignore`/`.git/info/exclude` or commit |
| Card images | 377 image files tracked under `app/static/images/cards/ogn` while `.gitignore` ignores `cards/**/`; `.git` = 685 MB, images dir 598 MB | out of F0 scope; flag for F1 (serve from volume/Nginx) |
| `.env.example` | wrong driver URL, lacks new vars | update |
| Deprecations | `User.query.get`, `datetime.utcnow()` widely used (warnings silenced in `pytest.ini`) | leave; use a clock helper in new code |

---

## 10. Pending fix `1ae1f6e`

`git log`: HEAD of `feat/f0-foundation` is `1ae1f6e`, same as local `main`; `origin/main` is one commit behind, so the fix is **present on the branch** and will travel in the first F0 PR. Verified logic:

| Part | Where | Present | Test coverage |
|---|---|---|---|
| Image folder from filename prefix | `models/card.py:4-15,38-48` (`_image_folder`, `image_src`); used in `cards.py`, `deck.py`, `collection.py`, `cards.html` | yes | **none** (`grep image_src tests/` = 0) -> add characterization tests (`ogn_257.png` with set `OGNX` -> `/riftbound/static/images/cards/ogn/ogn_257.png`, empty/no-underscore cases) |
| Basic Rune no foil slot | `cardmarket_matcher.py` `_expand_slots` | yes | yes: `test_cardmarket_matcher.py:847-909` (Common, Showcase, lowercase "basic rune") |
| Price fallback `avg7_foil -> avg7 -> low_foil -> low` | `collection.py:131-164` `_resolve_price` | yes | **none** for `_resolve_price` directly (matcher tests only seed prices) -> add table-driven tests (premium/foil/non-foil, NULL cascades) |

Gaps found while verifying (should be fixed in F0 so the API can reuse them "as the roadmap requires"):
1. **Write side still uses the old folder rule**: `riot_scraper.py:379` saves to `<rbcar_rbset_id.lower()>/` and `cards.py:168` (upload) likewise, while reads use the filename prefix. A scraper run for OGNX/PROK writes to `ognx/`/`prok/` and the UI looks in `ogn/` -> broken images again. Use `_image_folder(card.image)` (fallback `set_id.lower()`).
2. `deck.py:64-103` `_latest_price_for_card` has its own divergent rule (only avg7/avg7_foil, no `showcase`, no `low` fallback) -> extract `_resolve_price` into `app/services/pricing.py` and use it in collection, deck and the future API.
3. `RbCard.image_src` hard-codes `/riftbound/static/...`; the API should expose the relative filename/folder and let the client compose (or use `url_for`).

---

## 11. Split proposal

Single SDD change `f0-foundation` (one proposal/specs/design so cross-cutting decisions — envelope, config, auth service — stay coherent), `tasks.md` grouped into **5 PR-sized work units**, each independently shippable/revertible and reviewed interactively:

| Unit | Content | Why this order | DB change |
|---|---|---|---|
| **F0a config-secrets** | env-only config + fail-fast, cookie flags, `run.py`, `.env.example`, service/nginx docs, CI env cleanup, rotation runbook | Smallest, most urgent (B1); no schema; unblocks safe prod config | none |
| **F0b migrations-quantity** | Flask-Migrate wiring, baseline from prod dump, legacy SQL archived, drift-guard + migration tests, quantity -> Integer, atomic merge, `import_csv` validation, BigInteger/JSONB variants | Alembic must exist before any column is added (config.yaml rule) | `0001` baseline (stamp), `0002` quantity |
| **F0c admin-authz** | `is_admin`/`is_active`/lock columns, `admin_required`, price blueprint guard, set/card guards, CLI, UI hiding, ownership/SSRF/traversal/profile/deck fixes, authorization-matrix test, `admin_client` fixture | needs F0b; highest functional impact | `0003` |
| **F0d csrf-login-hardening** | Flask-WTF CSRF + global fetch wrapper, logout POST, Flask-Limiter, ALTCHA, lockout, `services/auth.py`, Pydantic register/login schemas, Nginx `limit_req` doc | touches every template -> isolate; needs F0c columns | none |
| **F0e api-ci-docs** | `/api/v1` skeleton + JSON error handling + unauthorized handler, `pricing.py` extraction + tests for `1ae1f6e`, scraper/upload folder fix, CI (py version, PG migrations job, frontend placeholder), `AGENTS.md`, `README.md`, `package.json` removal, `diagnose.py` removal | uses auth service from F0d; CI can start earlier if desired | none |

Dependency: a -> b -> c -> d -> e (CI portion of e is independent and can be pulled forward). If the user prefers fewer PRs: merge a into b (config + Alembic) and d into c (security) = 3 units, but d's CSRF change is the riskiest regression surface and is better reviewed alone. Branching: first PR carries `1ae1f6e` (mention in the description); each unit then branches from updated `main`.

---

## 12. Decisions / inputs needed from the user before proposal

1. Confirm prod runs without `SECRET_KEY`/`DATABASE_URL` env (i.e. on the public defaults) and agree to rotate both immediately (could be done today, independent of code).
2. Provide `pg_dump --schema-only -n riftbound` from prod (or authorize read-only introspection) to write `0001_baseline`.
3. `sudo chown -R racmos:racmos /home/racmos/RBAPP` (B2).
4. Prod Python version; does the prod host have Redis (or is installing one acceptable)? Default plan: no Redis (memory limiter + Nginx `limit_req` + DB lock).
5. CAPTCHA: ALTCHA self-hosted (recommended) vs Cloudflare Turnstile.
6. API success envelope: `{success,data,meta}` (recommended) vs flat.
7. Is `price/generate` admin-only (roadmap) or user-level? Should non-admins keep read-only Sets/Cards pages (assumed yes)?
8. Deck `have/missing` on shared decks: use the viewer's collection (recommended) vs owner's (current).
9. Confirm HTTPS is live for racmosdev.es today (nginx_config says so) so `Secure` cookies are safe to enforce.
10. Delivery: 5 units (recommended) vs 3; one SDD change with batches vs separate changes.
11. CI Python: 3.12 only vs matrix 3.12/3.13.

## 13. Risks (consolidated)
- Public-repo credentials and default session key (rotate; sessions will all be invalidated once).
- Root-owned files block apply until ownership is fixed.
- Baseline vs prod mismatch (needs dump); autogenerate noise could drop indexes/FKs if filters are skipped.
- CSRF rollout can break every `fetch` POST if the wrapper/meta tag is missed; Referer check only visible behind Nginx.
- Changing JSON-vs-HTML negotiation may affect existing Jinja JS; kept compatible for `*/*`.
- Per-worker memory limiter is weaker than configured; account lock in DB is the real brute-force defense.
- ~14 existing tests change fixture (admin); all 93 must stay green (`WTF_CSRF_ENABLED=False`, `RATELIMIT_ENABLED=False`, captcha `none` in test config).
- Strict TDD: most F0 behavior is testable (config validation, authz matrix, CSRF on/off app fixture, limiter, lockout with injected clock, SQLite migration upgrade + drift guard); not testable in pytest: Nginx limit_req, Postgres-specific `USING` casts (covered by the PG CI job).

## 14. Ready for proposal
Yes, with the caveat that items 1-3 of section 12 are prerequisites for apply (not for proposal/spec/design). The orchestrator should tell the user: B1 (rotate secrets now), B2 (chown), and ask the section 12 questions, then run `sdd-propose` with the 5-unit delivery plan.

## 15. Addendum (orchestrator, 2026-10-18) — user answers + dev DB snapshot

**There is no production environment.** This host + DB (192.168.1.33) is DEV only; the user is the sole user.
Production rollout becomes a later roadmap phase (F12). Consequences: no emergency hotfix; secrets rotation
is advisable (public repo) but not urgent; "prod schema" below means the dev DB.

Decisions: CAPTCHA = ALTCHA self-hosted. Envelope `{success,data,meta}`. Non-admins keep read-only
Sets/Cards; all `price/*` admin-only. Shared deck have/missing uses the viewer's collection. No Redis
(memory limiter + Nginx limit_req + DB lockout). Delivery: one SDD change, 5 PR-sized units (a–e).

Read-only structural snapshot of schema `riftbound` taken from the dev DB → `dev-schema-snapshot.txt`
(PostgreSQL **18.4**). Key findings for the baseline:
- Legacy tables still present: `old1_rbusers` (rbus_* columns) and `old_rbdecks` (per-card rows).
- **Bug:** `rbdecks.fk_deck_user` references `old1_rbusers(rbus_username)`, not `rbusers(username)`.
- `rbcollection`: `rbcol_id bigint` (sequence), `rbcol_quantity text NOT NULL`, CHECKs on playset/selling,
  FKs to `rbcards` and `rbusers(username)` (ON UPDATE CASCADE / ON DELETE RESTRICT), 2 extra indexes.
- `rbdecks.rbdck_cards` is `jsonb`; varchar lengths differ from models (Text).
- `rbcm_product_card_map.rbpcm_id_product` has a sequence default (unneeded) and **no FK** to `rbcards`;
  `rbproducts` has no FK to `rbset`; no FKs on other `rbcm_*` tables.
- `rbcards.rbcar_banned text DEFAULT 'N'` (to be superseded by a per-mode ban table in F5/F10).
- No views, functions or triggers in the schema.
- Legacy tables decision (user): **backup + drop** `old1_rbusers` and `old_rbdecks` via an Alembic migration
  (dump contents to a SQL file first; warn if any `old_rbdecks` deck is missing from `rbdecks`), and repoint
  `rbdecks` user FK to `rbusers(username)`.
