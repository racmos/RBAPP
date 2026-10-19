"""Helpers shared by the SQLite (`test_migrations`) and PostgreSQL
(`test_migrations_pg`) migration tests. Everything runs against the database of
the current app context (`db.engine`)."""
import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask import current_app

from app import db
from sqlalchemy.engine import make_url

from app.db_schema import MIGRATE_OPTIONS


def alembic(action, revision, **kwargs):
    """Run `alembic <action> <revision>` through Flask-Migrate's own config.

    Calls `alembic.command` directly (not `flask_migrate.upgrade`) because
    Flask-Migrate turns a failing revision into `sys.exit(1)`, hiding the
    original exception the tests want to inspect."""
    config = current_app.extensions['migrate'].migrate.get_config()
    getattr(command, action)(config, revision, **kwargs)


def upgrade(revision='head'):
    alembic('upgrade', revision)


def downgrade(revision):
    alembic('downgrade', revision)


def inspector():
    return sa.inspect(db.engine)


def tables():
    return set(inspector().get_table_names(schema='riftbound'))


def run(sql, **params):
    """Execute raw SQL on the shared connection and commit."""
    with db.engine.begin() as conn:
        return conn.execute(sa.text(sql), params)


def rows(sql, **params):
    with db.engine.connect() as conn:
        return [tuple(r) for r in conn.execute(sa.text(sql), params)]


def drift(metadata=None):
    """What Alembic autogenerate would change to make the DB match `metadata`
    (default: the app models), using the SAME options as env.py."""
    with db.engine.connect() as conn:
        context = MigrationContext.configure(conn, opts=dict(MIGRATE_OPTIONS))
        return compare_metadata(context, metadata or db.metadata)


def checked_test_database_url(url):
    """Return `url` if its DATABASE NAME contains "test", else raise ValueError.

    The PostgreSQL tests drop schema `riftbound`; this is the guard that keeps
    them away from real data (D20). Only the database name counts: a host or
    user called "test" proves nothing."""
    database = make_url(url).database or ''
    if 'test' not in database.lower():
        raise ValueError(
            f"TEST_POSTGRES_URL database {database!r} must contain 'test'; "
            'refusing to run destructive tests against it')
    return url
