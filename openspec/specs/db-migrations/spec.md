# db-migrations Specification

Source: change f0-foundation (archived 2026-10-19)

> Tags: `[a]`..`[e]` = delivery unit of change f0-foundation. `[PG-CI]` = verify in the PostgreSQL CI job; `[MANUAL]` = manual/ops check; `[GH-CI]` = only observable in GitHub Actions. Untagged scenarios are pytest-testable on SQLite with a `riftbound` schema attached (as `tests/conftest.py` does). "Baseline" = revision reproducing `dev-schema-snapshot.txt` (16 tables, incl. legacy `old1_rbusers`, `old_rbdecks`). Revisions of change f0-foundation, in order: baseline, legacy drop + FK repoint [b], quantity [b], admin columns [c], lockout columns [d].

## Requirements

### Requirement: MIG-1 Alembic via Flask-Migrate, schema-scoped [b]

`flask db` commands MUST work. The version table MUST live in schema `riftbound`. Autogenerate/compare MUST consider only schema `riftbound` (never `public`).

#### Scenario: Upgrade on empty SQLite
- GIVEN an empty SQLite DB with `riftbound` attached
- WHEN `flask_migrate.upgrade()` runs to head
- THEN every model table exists as `riftbound.<table>` and `riftbound.alembic_version` holds the head id

#### Scenario: Upgrade on empty PostgreSQL [PG-CI]
- GIVEN an empty PostgreSQL database
- WHEN `flask db upgrade head` runs
- THEN schema `riftbound` is created, and no table is created in `public`

### Requirement: MIG-2 Baseline equals the dev snapshot [b]

The baseline MUST create exactly the tables, columns, types, nullability, defaults, PKs, UNIQUEs, FKs (including `rbdecks.fk_deck_user -> old1_rbusers(rbus_username)`), CHECKs (`rbcollection_selling_chk`, `rbcollection_playset_chk`, `rbcm_pcm_foil_chk`) and indexes (including `idx_rbcollection_selling`, `idx_rbcollection_user_card_foil`, partial `idx_rbcm_expansions_unmapped`) in the snapshot. It MUST NOT add FKs the snapshot lacks (`rbcm_product_card_map`, `rbproducts`).

#### Scenario: Structure after baseline
- GIVEN an empty SQLite DB upgraded to the baseline revision only
- WHEN inspected
- THEN 16 tables exist, the three named indexes exist, and `rbcm_product_card_map` and `rbproducts` have no FK

#### Scenario: CHECKs enforced
- GIVEN the baseline schema
- WHEN a row with `rbcol_selling='X'` (or `rbcol_playset=4`) is inserted into `rbcollection`
- THEN the insert fails with an integrity error

#### Scenario: Matches real PostgreSQL [PG-CI]
- GIVEN an empty PostgreSQL DB upgraded to the baseline
- WHEN structurally compared with the snapshot (columns, types, constraints, indexes)
- THEN there are no differences

### Requirement: MIG-3 Stamp the existing dev database [b]

The existing dev DB MUST be adoptable with `flask db stamp <baseline>` without executing DDL; a later `flask db upgrade` MUST apply only the revisions after the baseline.

#### Scenario: Stamp keeps data [MANUAL]
- GIVEN the dev DB with its tables and rows
- WHEN `flask db stamp <baseline>` runs
- THEN `flask db current` shows the baseline and row counts are unchanged

### Requirement: MIG-4 Legacy tables are backed up, then dropped [b]

A revision MUST drop `old1_rbusers` and `old_rbdecks` only after writing their full contents to an SQL file at a gitignored path. That file contains emails and password hashes and MUST NEVER be committed. The revision MUST emit a warning listing each `old_rbdecks` deck (user + name) that has no match in `rbdecks`, and MUST continue. If the backup cannot be written the revision MUST abort before any DROP. Downgrade MUST recreate both tables and reload their rows from the backup.

#### Scenario: Backup then drop
- GIVEN legacy tables with 2 users and 3 deck rows, upgraded to just before this revision
- WHEN the revision runs
- THEN a backup file exists containing all 5 rows, both tables are gone

#### Scenario: Backup path is ignored
- GIVEN the backup path used by the revision
- WHEN `git check-ignore -q <path>` runs
- THEN it exits 0

#### Scenario: Missing deck warning
- GIVEN `old_rbdecks` has a deck (user `u`, name `Foo`) absent from `rbdecks`
- WHEN the revision runs
- THEN the output warns about `u/Foo` and the revision still completes

#### Scenario: Unwritable backup aborts
- GIVEN the backup directory is not writable
- WHEN the revision runs
- THEN it fails and both legacy tables still exist with their rows

#### Scenario: Downgrade restores
- GIVEN head after the previous scenarios
- WHEN the revision is downgraded
- THEN both tables exist again with the original rows

### Requirement: MIG-5 rbdecks user FK repointed [b]

The revision MUST repoint `rbdecks.rbdck_user` to `rbusers(username)` BEFORE dropping the legacy tables. If any `rbdecks.rbdck_user` has no matching `rbusers.username`, the revision MUST abort listing them, changing nothing.

#### Scenario: FK target after head
- GIVEN an empty DB upgraded to head
- WHEN `rbdecks` FKs are inspected
- THEN `rbdck_user` references `rbusers.username` and no FK references `old1_rbusers`

#### Scenario: Orphan deck owner
- GIVEN a deck whose `rbdck_user` is not in `rbusers`
- WHEN the revision runs
- THEN it aborts, the message names the user, and `rbdecks` is unchanged

### Requirement: MIG-6 Models match the migrated schema (drift guard) [b]

After `upgrade head`, comparing the SQLAlchemy metadata with the DB MUST report no table, column, type, nullability, index, FK or CHECK differences. Models MUST use `BigInteger` for `rbcol_id` and JSONB for `rbdck_cards` on PostgreSQL (Integer/JSON on SQLite).

The dev database carries table and column COMMENTs, so the models carry the same text. Revision `0004a_schema_comments` (down_revision `0004`, before `0005`) sets those COMMENTs on PostgreSQL only (no-op on SQLite; downgrade removes them). Drift is clean on dev and on a fresh PostgreSQL upgrade, pinned by the PG lane. The revision chain at head is `0001`, `0002`, `0003`, `0004`, `0004a`, `0005`.

#### Scenario: Clean drift on SQLite
- GIVEN an empty SQLite DB upgraded to head
- WHEN `compare_metadata` runs against the models
- THEN the diff list is empty

#### Scenario: Guard catches drift
- GIVEN a model column added without a revision
- WHEN the drift-guard test runs
- THEN it fails naming the column

#### Scenario: Clean drift on PostgreSQL [PG-CI]
- GIVEN PostgreSQL upgraded to head
- WHEN `flask db check` runs
- THEN it exits 0

### Requirement: MIG-7 Both dialects, both directions [b]

Every revision MUST upgrade and downgrade on SQLite and PostgreSQL (SQLite via batch operations; PG-only DDL behind dialect guards).

#### Scenario: Full round trip
- GIVEN an empty SQLite DB
- WHEN upgrade head, downgrade base, upgrade head run in sequence
- THEN all succeed and the final schema equals the first head schema

### Requirement: MIG-8 Alembic is the only schema builder; legacy SQL archived [b]

`run.py` MUST NOT call `db.create_all()`. `migrations/database/*` and `migrations/install_db.sql` MUST be moved to `migrations/legacy_sql/` with a README stating they are frozen; `migrations/` MUST then hold only the Alembic layout plus `legacy_sql/`. Tests MAY keep `create_all()`.

#### Scenario: Layout
- GIVEN the repo after unit b
- WHEN paths are listed
- THEN `migrations/legacy_sql/install_db.sql` and `migrations/legacy_sql/README.md` exist, and `migrations/database/` and `migrations/install_db.sql` do not

#### Scenario: No implicit create
- GIVEN `run.py`
- WHEN scanned
- THEN it contains no `create_all`

### Requirement: MIG-9 Pre-migration backup is documented [b]

The docs MUST instruct taking `pg_dump -n riftbound` before the destructive revisions and describe the downgrade/restore path.

#### Scenario: Runbook [MANUAL]
- GIVEN the migrations doc
- WHEN reviewed
- THEN it contains the `pg_dump -n riftbound` step, the stamp step and the rollback steps
