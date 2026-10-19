# Proposal: F0 Foundation (roadmap phase F0 "Base")

## Intent

RBAPP is about to turn into a multi-user JSON API + PWA (F1–F12). Right now:
- secrets sit in a public repo (`config.py` defaults)
- any logged-in user can change the catalog, run price loads (SSRF) and write files (`upload_image` path traversal)
- there is no CSRF or brute-force protection
- the schema comes from three SQL sources that disagree
- `rbcol_quantity` is stored as text

F0 secures the **dev** host. There is no production, and the user is the only user. It also lays the groundwork that every later phase and the F12 production rollout need. Evidence for all of this is in `exploration.md`.

## Scope

### In Scope: 5 PR-sized units, shipped in order a→e
- **a** Config & secrets. Also carries the pending fix `1ae1f6e`.
- **b** Alembic baseline, legacy tables, integer quantity
- **c** Admin authorization and fixes for data exposure
- **d** CSRF, login hardening, cookies
- **e** API v1 skeleton, CI, docs, cleanup

### Out of Scope
- React frontend (F1). Deck v2 and per-mode bans (F5). Production deploy (F12). OAuth, 2FA and a session table (F9). A user-admin UI (F10; F0 ships a CLI only).
- Redis. CAPTCHA on login. Unrelated older bugs (`bulk_*` 500s, `search_id` regex, dead deck JS).
- Rotating the DB password and SECRET_KEY. This is a manual step for the user. We recommend it, but it is not code.

## Capabilities

### New Capabilities
- `app-config`: config comes only from env, no credentials in code, startup fails fast outside development/testing
- `db-migrations`: Alembic baseline matching the dev snapshot; legacy tables backed up then dropped; `rbdecks` FK repointed; upgrades work on PostgreSQL and SQLite; drift guard
- `collection-quantity`: quantity stored as an integer, numeric sort, atomic merge, validated import quantity
- `access-control`: `is_admin` and an account-block flag; admin guard; non-admins see the catalog read-only; admin CLI; route authorization matrix
- `card-images`: uploads cannot escape their folder; upload and scraper write to the folder that `image_src` reads
- `deck-viewing`: have/missing uses the viewer's collection; name lookups are deterministic; legacy routes removed; `versions` fixed
- `user-profile`: a duplicate email does not cause a 500; the current password is needed to change it
- `price-resolution`: one shared fallback chain, `avg7_foil→avg7→low_foil→low`
- `csrf-protection`: CSRFProtect, a global fetch wrapper, logout via POST
- `login-protection`: Flask-Limiter on `memory://`, DB lockout (5 failures → 15 min, escalating), ALTCHA on register
- `session-security`: cookies get SameSite=Lax, Secure on HTTPS and HttpOnly; debug is off by default
- `api-v1`: `health`, `meta/config`, `auth/*`; the `{success,data,meta}` envelope; JSON 401; correct JSON vs HTML negotiation
- `ci-pipeline`: Python 3.12, a PostgreSQL migrations job, a placeholder frontend job, least-privilege permissions
- `landing-feeds`: landing scraper partials are cached

### Modified Capabilities
None (`openspec/specs/` is empty).

## Approach and Rollback per Unit

| Unit | Approach | DB revision | Rollback |
|---|---|---|---|
| a | `RB_ENV` picks the config class. `create_app` validates it after test overrides. dotenv loads only in dev. Remove secrets from CI. | none | Revert the PR and restore `.env` |
| b | Flask-Migrate with a `riftbound` version table and a schema filter. Write the baseline by hand from `dev-schema-snapshot.txt`, `stamp` it on dev, `upgrade` on empty DBs. Make the models match (BigInteger/JSONB variants, FKs, indexes). Use `batch_alter_table`. | baseline; legacy drop (dump to a gitignored SQL file, warn if a deck is missing from `rbdecks`, repoint the FK before the drop); quantity cast with a pre-flight that aborts on non-numeric values | Take a full `pg_dump -n riftbound` first. Then `flask db downgrade` (quantity goes back to Text; legacy tables are recreated and their data reloaded from the dump), stamp `base`, revert the PR |
| c | Admin decorator plus a `price_bp.before_request` guard. Override `is_active` so blocked users lose their sessions. `flask users` CLI. Hide admin UI from non-admins. Allow-list hosts for Cardmarket URLs. `services/pricing.py`. Fixtures `admin_client` and `other_user_client`. | `is_admin`, block flag | Promote the owner with the CLI before the guard goes live. `downgrade`, then revert the PR |
| d | CSRFProtect without a token expiry. `services/auth.py` shared by Jinja and the API. Nginx `limit_req` doc. | lockout columns (+ captcha replay store, decided in design) | Env kill switches (`WTF_CSRF_ENABLED`, `RATELIMIT_ENABLED`, `CAPTCHA_PROVIDER=none`), `flask users unlock`, `downgrade`, then revert |
| e | `app/api/v1`, a response helper, a fixed error predicate, an unauthorized handler. Rework CI. Update docs. Remove `package.json*` and `diagnose.py`. Move legacy SQL to `migrations/legacy_sql/`. | none | Revert the PR; all changes add new things only |

**Jinja coexistence:** every page stays. Non-admins lose the Add/Edit and Price controls. Logout becomes a POST button. Login and register get a CSRF token, and register also gets ALTCHA. Browser error pages show HTML again. The 35 `fetch` calls stay as they are, because the wrapper adds the token.

## Affected Areas

| Area | Impact | Units |
|---|---|---|
| `config.py`, `app/__init__.py`, `run.py`, `.env.example`, `requirements.txt` | Modified | a,b,d |
| `migrations/` (Alembic), `migrations/legacy_sql/` | New/Moved | b,e |
| `app/models/*` | Modified | b,c,d |
| `app/routes/auth.py`, `app/routes/domains/{sets,cards,price,deck,profile,collection}.py` | Modified | b,c,d |
| `app/services/{pricing,auth,captcha}.py`, `riot_scraper.py`, admin decorator, CLI | New/Modified | c,d |
| `app/api/`, `app/errors.py` | New/Modified | d,e |
| `app/templates/{base,login,register,sets,cards,dashboard}.html` | Modified | c,d |
| `tests/` (about 14 tests move to `admin_client`) | Modified/New | all |
| `.github/workflows/*`, `AGENTS.md`, `README.md`, `docs/*` | Modified | a,e |
| `package.json`, `package-lock.json`, `diagnose.py` | Removed | e |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| The baseline drifts from the dev DB, and autogenerate drops indexes or FKs | Med | Build it from the snapshot, stamp only on dev, schema filter, drift-guard test, PostgreSQL CI job |
| The legacy dump (password hashes) gets committed to the public repo | Med | Write it to a gitignored path and never commit it |
| The owner gets locked out | Med | Promote with the CLI first; `unlock` CLI; kill switches |
| CSRF breaks a fetch call or a form | Med | Global wrapper, a test that checks every template for the meta tag, tests with CSRF enabled |
| The in-memory limiter runs per worker | High | The DB lockout is the real control; document Nginx `limit_req` |
| Root-owned files block apply | High | The user runs `chown` before apply |

## Dependencies

- Before apply, the user runs: `sudo chown -R racmos:racmos /home/racmos/RBAPP`.
- After a: the user rotates the DB password and SECRET_KEY into `.env` (recommended).
- New packages: Flask-Migrate 4.1.0 + a pinned alembic (b); Flask-WTF, Flask-Limiter, altcha (d).
- The order is strict, a→b→c→d→e, and each unit branches from the updated `main`. The CI part of e can go earlier.

## Success Criteria

- [ ] No credentials in code. Starting outside dev/test without env fails with a clear error.
- [ ] `flask db upgrade head` builds the schema on empty SQLite and on PostgreSQL. Dev is stamped and upgraded. The drift guard is clean. Legacy tables are dropped and the backup exists. The `rbdecks` FK points to `rbusers(username)`.
- [ ] `rbcol_quantity` is an integer and sorts numerically.
- [ ] The authorization matrix classifies every URL rule. Non-admins get 403 on set/card changes and on all `price/*`. Path traversal is rejected.
- [ ] A shared deck shows have/missing from the viewer's collection. The removed deck routes return 404. A duplicate email returns a 4xx.
- [ ] A missing CSRF token returns 400. The 6th failed login locks the account (`Retry-After`). Register without ALTCHA is rejected.
- [ ] `/riftbound/api/v1/health` returns 200 `{success,data}`. A protected API call without a session returns JSON 401. A browser 404 returns HTML.
- [ ] CI is green on Python 3.12, including the PostgreSQL job. The 93 baseline tests and the new tests pass, with every unit built strict TDD.

## Approval (user, 2026-10-18)
Approved, including the three proposer additions (Cardmarket URL host allow-list in c; quantity validation
in current `import_csv` in b; lockout columns as their own revision in d) and two orchestrator adjustments:
1. Legacy-table backup files (contain emails + password hashes) MUST be written to a gitignored path and
   never committed.
2. Move legacy SQL (`migrations/database/*`, `migrations/install_db.sql`) to `migrations/legacy_sql/` in
   unit **b** (not e), so Alembic starts from a clean `migrations/` layout.
