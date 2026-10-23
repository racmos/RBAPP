# Database migrations (Alembic)

The schema `riftbound` is built and changed ONLY by Alembic, through
Flask-Migrate (`flask db ...`). `run.py` no longer creates tables. The old hand
written SQL is archived, frozen, in `migrations/legacy_sql/`.

| Revision                           | What it does                                                                                                                                                                                                                                                                                                                                                                                              |
| ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `0001_baseline`                    | Exact copy of the dev database on 2026-10-18 (16 tables, including the legacy `old1_rbusers` and `old_rbdecks`). Reference: `tests/fixtures/dev_schema_snapshot.txt`.                                                                                                                                                                                                                                     |
| `0002_drop_legacy_tables`          | Backs up and drops the two legacy tables; repoints `rbdecks.fk_deck_user` to `rbusers(username)`.                                                                                                                                                                                                                                                                                                         |
| `0003_collection_quantity_integer` | `rbcollection.rbcol_quantity` Text -> Integer NOT NULL, plus CHECK `rbcollection_quantity_chk` (`>= 1`).                                                                                                                                                                                                                                                                                                  |
| `0004_user_admin_flags`            | `rbusers.is_admin` and `rbusers.is_blocked`, BOOLEAN NOT NULL DEFAULT false. Nobody becomes admin by migrating: see "Admin accounts" below.                                                                                                                                                                                                                                                               |
| `0004a_schema_comments`            | The table and column COMMENTs the dev database already had (8 tables). PostgreSQL only (a no-op on SQLite). Setting a comment twice is harmless, so it is safe on dev.                                                                                                                                                                                                                                    |
| `0005_login_protection`            | `rbusers.failed_login_count` (INTEGER NOT NULL DEFAULT 0), `locked_until` and `last_login_at` (TIMESTAMP NULL), and the table `rbcaptcha_used` (replay store of the ALTCHA captcha). Nobody is locked after migrating. See "Login protection" below.                                                                                                                                                      |
| `0006_user_prefs`                  | The table `rbuserprefs`: interface preferences of one account (`rbprf_lang`, `rbprf_density`, `rbprf_accent`, `rbprf_bg_intensity`, `rbprf_collection_view`, all nullable, NULL = Auto, plus `rbprf_updated_at`). 1:1 with `rbusers` (primary key and foreign key `rbprf_user_id`, ON DELETE CASCADE), five named CHECK constraints. No rows are created by migrating. See "Interface preferences" below. |

`flask` finds the app through `.flaskenv` (`FLASK_APP=wsgi.py`) and reads
`DATABASE_URL` like the application does (see `.env.example`).

## Fresh database (CI, a new developer, a new server)

```bash
flask db upgrade        # creates schema riftbound, then every table
flask db check          # must print "No new upgrade operations detected."
```

## Existing dev database: adopt it with `stamp`, then upgrade

Do these in order. Stop at the first surprise.

1. **Back up the schema outside the repository, and check the file.**
   ```bash
   mkdir -p ~/backups/rbapp
   STAMP=$(date +%Y%m%d_%H%M)
   pg_dump -h <host> -U <user> -d <database> -n riftbound -Fc \
       -f ~/backups/rbapp/riftbound_pre_alembic_$STAMP.dump
   pg_restore -l ~/backups/rbapp/riftbound_pre_alembic_$STAMP.dump | head
   ```
   (`pg_dump` does not understand the SQLAlchemy `postgresql+psycopg://` URL: pass
   the host, user and database as flags.)
2. **Compare the real database with the baseline.** The command only reads the
   catalog:
   ```bash
   flask schema snapshot > /tmp/dev_now.txt
   diff /tmp/dev_now.txt tests/fixtures/dev_schema_snapshot.txt && echo IDENTICAL
   ```
   Any difference (other than the first `-- PostgreSQL ...` line) means dev
   drifted since the baseline was written: stop and report it.
3. **Stamp**: records the baseline revision, executes no DDL.
   ```bash
   flask db stamp 0001_baseline
   flask db current          # 0001_baseline (head is a later revision)
   ```
   Row counts must not change.
4. **Upgrade** (runs 0002, 0003 and the later revisions; see "Admin accounts" below for 0004):
   ```bash
   flask db upgrade
   ```
   `0002` writes `instance/backups/legacy_tables_<UTC>.sql` (see below) only if
   the legacy tables hold rows, and prints a warning for every `old_rbdecks`
   deck (`user/name`) that has no match in `rbdecks`. `0003` aborts, changing
   nothing, if a `rbcol_quantity` is not a whole number in 1..9999 and lists the
   offending `rbcol_id`s.
5. **Verify**:
   ```bash
   flask db check            # "No new upgrade operations detected."
   ls -l instance/backups/   # -rw------- legacy_tables_....sql
   git status                # the backup must NOT appear
   ```

## Admin accounts: upgrade to 0004, promote the owner, then restart

From revision `0004` the catalog write routes (set/card add and edit, image
upload) and every `/riftbound/price/...` route are admin-only. Nobody is admin
after the migration, so promote the owner BEFORE restarting the service, or the
owner loses those screens until you do.

```bash
flask db upgrade                 # 0004 and 0004a (additive: the old code keeps working)
flask users promote <owner>      # first admin; works while no admin exists
flask users list                 # confirm: the owner shows "admin"
sudo systemctl restart rbapp     # only now start the new code
```

Then log in as the owner (the Price link and the Add/Edit buttons appear) and as
a second ordinary account (none of them appear and the routes answer 403).

`flask users` commands (all exit 1 and change nothing for an unknown user;
`promote`, `demote`, `block`, `unblock` are idempotent):

| Command                                | Effect                                                                   |
| -------------------------------------- | ------------------------------------------------------------------------ |
| `promote <user>` (alias `make-admin`)  | grants the admin role                                                    |
| `demote <user>` (alias `revoke-admin`) | removes it                                                               |
| `block <user>` / `unblock <user>`      | a blocked user cannot log in and a live session ends on its next request |
| `set-password <user>`                  | hidden prompt, asked twice, 8-128 characters                             |
| `list`                                 | accounts with role and state (never hashes)                              |

Rollback of this step: `flask db downgrade 0003_collection_quantity_integer`
(drops `is_admin`, `is_blocked` and, on PostgreSQL, removes the COMMENTs that
`0004a` set; `flask db upgrade` puts them back), then revert the code.

## Login protection: upgrade to 0005, then restart (CSRF, lockout, captcha)

Revision `0005` adds the lockout columns and the captcha replay table. It is
additive, but the NEW code reads the new `rbusers` columns on every login, so the
order matters: **install, upgrade the database, only then restart**.

```bash
pip install -r requirements.txt      # Flask-WTF, Flask-Limiter, altcha and their dependencies
pg_dump -h <host> -U <user> -d <database> -n riftbound -Fc -f ~/backups/rbapp/riftbound_pre_0005_$(date +%Y%m%d_%H%M).dump
flask db upgrade                     # 0005 (additive: the old code keeps working until the restart)
flask db check                       # "No new upgrade operations detected."
sudo systemctl restart rbapp         # only now start the new code
```

Then, in a browser over HTTPS: log in as the owner (the nav Logout is now a button),
use a page that saves something (Profile, Sets), and open `/riftbound/register`
(the ALTCHA widget needs HTTPS or localhost).

What the new code does, and what to touch when it misbehaves:

| Protection                                                         | Switch (env, see `.env.example`)                                          | Notes                                                                                                                                                                                         |
| ------------------------------------------------------------------ | ------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CSRF on every POST/PUT/PATCH/DELETE                                | `WTF_CSRF_ENABLED=false`                                                  | the page script `static/js/csrf.js` adds the token to same-origin `fetch` calls; on HTTPS the `Referer` of a POST must match the public host (Nginx must pass `Host` and `X-Forwarded-Proto`) |
| Per-IP rate limit (login 10/min + 50/h, register 5/h)              | `RATELIMIT_ENABLED=false`                                                 | in-memory, per Gunicorn worker; the Nginx `limit_req` zone in `docs/nginx_config` is the global one                                                                                           |
| Account lockout (5th wrong password: 15 min, then 30, 60 ... 24 h) | `LOGIN_MAX_FAILURES`, `LOGIN_LOCK_BASE_MINUTES`, `LOGIN_LOCK_MAX_MINUTES` | `flask users unlock <user>` clears it at once; `flask users list` marks locked accounts                                                                                                       |
| ALTCHA captcha on register                                         | `CAPTCHA_PROVIDER=none`                                                   | replays are stored in `rbcaptcha_used`; `ALTCHA_HMAC_KEY` defaults to a key derived from `SECRET_KEY`                                                                                         |
| Landing feed cache                                                 | `LANDING_CACHE_TTL` (seconds, 0 = off)                                    | per worker                                                                                                                                                                                    |

Put a switch in `.env` (development) or `/etc/riftbound/riftbound.env` (the service)
and restart. Every switch that is off outside testing logs a warning at start-up.
They are for rollback, not for normal use.

Cookies: `session` and `remember` are HttpOnly + `SameSite=Lax`; `Secure` is on in
production and off in development unless `SESSION_COOKIE_SECURE` /
`REMEMBER_COOKIE_SECURE` say otherwise.

Rollback of this step: `flask db downgrade 0004a_schema_comments` (drops the three
columns and `rbcaptcha_used`; users are kept), then revert the code. A user locked
by mistake needs only `flask users unlock <user>`.

## Interface preferences: upgrade to 0006, then restart (F1 app shell)

Revision `0006` adds one table, `riftbound.rbuserprefs`. It is additive: the old
code does not know the table and keeps working. The NEW code reads it on every
`GET /api/v1/auth/session` of a signed-in user, so the order matters:
**upgrade the database, only then restart**.

```bash
pg_dump -h <host> -U <user> -d <database> -n riftbound -Fc -f ~/backups/rbapp/riftbound_pre_0006_$(date +%Y%m%d_%H%M).dump
pg_restore -l ~/backups/rbapp/riftbound_pre_0006_*.dump | head   # the dump is readable
flask db upgrade                     # 0006 (additive)
flask db check                       # "No new upgrade operations detected."
sudo systemctl restart rbapp         # only now start the new code
```

What the table holds, and how it behaves:

| Column                  | Type                                                                | Allowed values (CHECK)        |
| ----------------------- | ------------------------------------------------------------------- | ----------------------------- |
| `rbprf_user_id`         | INTEGER, primary key, foreign key to `rbusers.id` ON DELETE CASCADE | an existing user              |
| `rbprf_lang`            | VARCHAR(2) NULL                                                     | `es`, `en`                    |
| `rbprf_density`         | VARCHAR(10) NULL                                                    | `compact`, `regular`, `comfy` |
| `rbprf_accent`          | VARCHAR(10) NULL                                                    | `cyan`, `orange`              |
| `rbprf_bg_intensity`    | SMALLINT NULL                                                       | 0 to 100                      |
| `rbprf_collection_view` | VARCHAR(10) NULL                                                    | `table`, `grid`               |
| `rbprf_updated_at`      | TIMESTAMP NOT NULL, default `now()`                                 | set again on every write      |

- NULL means Auto: the client decides. A user with no row has every preference on Auto;
  the row is created by the first `PATCH /api/v1/me/prefs`.
- Deleting a user deletes the row (PostgreSQL; SQLite does not enforce foreign keys here).
- The CHECK names are `rbuserprefs_lang_chk`, `rbuserprefs_density_chk`,
  `rbuserprefs_accent_chk`, `rbuserprefs_bg_intensity_chk` and
  `rbuserprefs_collection_view_chk`. The models and the `PrefsUpdate` schema build their
  domains from `app/schemas/prefs_domain.py`, so all three layers agree.

Rollback of this step: `flask db downgrade 0005_login_protection` (drops
`rbuserprefs`; the stored preferences are lost, the users are kept), then revert the
code. Run the downgrade while the NEW code is stopped, or the session endpoint will
fail until the revert.

## The legacy-table backup contains personal data

`legacy_tables_<UTC>.sql` holds **e-mail addresses and password hashes** of the
old users table. It is written with mode `0600` under a git-ignored directory
and must **never be committed, pasted or shared**.

- Directory: `LEGACY_BACKUP_DIR` (Flask config), else the `RB_LEGACY_BACKUP_DIR`
  environment variable, else `<project>/instance/backups` (`instance/` is in
  `.gitignore`).
- The file is only created when at least one legacy row exists. If it cannot be
  written (permissions, full disk) the revision aborts before dropping anything.
- Keep it as long as you may need to roll back; delete it securely afterwards.
- `0002` also refuses `--sql` (offline) mode: it has to read data and write the
  file.

## Rollback

- **Schema and data back to the baseline**: `flask db downgrade 0001_baseline`.
  It recreates `old1_rbusers` and `old_rbdecks`, replays the NEWEST backup file
  into them and points `fk_deck_user` back at `old1_rbusers`. `0003` downgrades
  the quantity back to text (`'12'`, `'3'`).
  If there is no backup file the legacy tables come back empty; on PostgreSQL
  that makes the FK fail when `rbdecks` has rows, so keep the file.
- **Stop using Alembic on that database**: after the downgrade,
  `flask db stamp base` removes the recorded revision (the tables stay).
- **Anything else goes wrong**: restore the dump from step 1 of the rollout:
  ```bash
  pg_restore --clean --if-exists -d <database> ~/backups/rbapp/riftbound_pre_alembic_<stamp>.dump
  ```
  then revert the code.

## Writing a new migration

1. Change the model in `app/models/`.
2. `flask db migrate -m "short description"`, then **read and edit** the file in
   `migrations/versions/`. Use readable ids (`0004_user_admin_flags`), not the
   generated hash, and keep `down_revision` linked.
3. Every ALTER goes through `op.batch_alter_table(..., schema='riftbound')`:
   SQLite (tests) rebuilds the table, PostgreSQL gets a plain ALTER. Put
   PostgreSQL-only DDL behind `op.get_bind().dialect.name == 'postgresql'`.
4. Write the downgrade. A revision that deletes or converts data must validate it
   first and abort with a message listing the offending rows (see `0003`).
5. The unit adds a test for its revision: the upgrade/downgrade round trip and the
   drift guard (`compare_metadata` of the models against the migrated schema must
   be empty; helpers in `tests/migration_helpers.py`). `flask db check` does the same against a real database.

## Tests and CI

- Migration tests on SQLite always run (the old ones were removed by M-a; each unit
  that adds a revision adds its own).
- `pytest -m postgres` (no marked test today): needs a PostgreSQL database whose name contains `test`:
  ```bash
  createdb riftbound_test
  TEST_POSTGRES_URL=postgresql+psycopg://user:password@localhost:5432/riftbound_test \
      pytest -m postgres
  ```
  The tests DROP schema `riftbound` of that database before and after each test and
  refuse any database whose name lacks `test`. Never point them at dev data.
- GitHub Actions job `migrations-pg` (`.github/workflows/ci.yml`) starts a
  `postgres:18` service and runs: `flask db upgrade`, `flask db check`,
  `flask db downgrade base`, `flask db upgrade`. The `pytest -m postgres` step was
  removed by M-a and comes back with the first new `postgres`-marked test.
