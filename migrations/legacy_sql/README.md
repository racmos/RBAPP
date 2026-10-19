# Legacy SQL (frozen)

These scripts built the Riftbound schema by hand before Alembic existed.
They are **frozen**: kept only as history and are replaced by the Alembic
revision `0001_baseline` (see `migrations/versions/`).

Do not run them against a database and do not edit them. Every schema change
now goes through Alembic (`flask db migrate` / `flask db upgrade`); see
`docs/migrations.md`.

Contents:

- `install_db.sql` - the one-file installer that was used on first deployments.
- `database/` - the numbered step-by-step scripts (`01_...` to `08_...`) and
  their README.
- `database_setup.sql` - the older setup script that used to live in `docs/`.
