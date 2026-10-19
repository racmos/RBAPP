# Database migrations (Alembic)

The schema `riftbound` is built and changed ONLY by Alembic, through
Flask-Migrate (`flask db ...`). `run.py` no longer creates tables. The old hand
written SQL is archived, frozen, in `migrations/legacy_sql/`.

| Revision | What it does |
|---|---|
| `0001_baseline` | Exact copy of the dev database on 2026-10-18 (16 tables, including the legacy `old1_rbusers` and `old_rbdecks`). Reference: `tests/fixtures/dev_schema_snapshot.txt`. |
| `0002_drop_legacy_tables` | Backs up and drops the two legacy tables; repoints `rbdecks.fk_deck_user` to `rbusers(username)`. |
| `0003_collection_quantity_integer` | `rbcollection.rbcol_quantity` Text -> Integer NOT NULL, plus CHECK `rbcollection_quantity_chk` (`>= 1`). |

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
   flask db current          # 0001_baseline (head is 0003...)
   ```
   Row counts must not change.
4. **Upgrade** (runs 0002 and 0003):
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
5. `pytest tests/test_migrations.py` runs the upgrade/downgrade round trip and the
   drift guard (`compare_metadata` of the models against the migrated schema must
   be empty). `flask db check` does the same against a real database.

## Tests and CI

- `pytest tests/test_migrations.py`: SQLite, always runs.
- `pytest -m postgres`: needs a PostgreSQL database whose name contains `test`:
  ```bash
  createdb riftbound_test
  TEST_POSTGRES_URL=postgresql+psycopg://user:password@localhost:5432/riftbound_test \
      pytest -m postgres
  ```
  The tests DROP schema `riftbound` of that database before and after each test and
  refuse any database whose name lacks `test`. Never point them at dev data.
- GitHub Actions job `migrations-pg` (`.github/workflows/ci.yml`) starts a
  `postgres:18` service and runs: `flask db upgrade`, `flask db check`,
  `flask db downgrade base`, `flask db upgrade`, then `pytest -m postgres`.
