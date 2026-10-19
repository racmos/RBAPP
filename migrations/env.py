import logging
from logging.config import fileConfig

from flask import current_app
from sqlalchemy import text

from alembic import context

from app.db_schema import SCHEMA

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging. Skipped when the process
# already has logging handlers (pytest, an embedding app): fileConfig would
# replace them, and it must never disable the application's loggers.
if config.config_file_name is not None and not logging.getLogger().handlers:
    fileConfig(config.config_file_name, disable_existing_loggers=False)
logger = logging.getLogger('alembic.env')


def get_engine():
    try:
        # this works with Flask-SQLAlchemy<3 and Alchemical
        return current_app.extensions['migrate'].db.get_engine()
    except (TypeError, AttributeError):
        # this works with Flask-SQLAlchemy>=3
        return current_app.extensions['migrate'].db.engine


def get_engine_url():
    try:
        return get_engine().url.render_as_string(hide_password=False).replace(
            '%', '%%')
    except AttributeError:
        return str(get_engine().url).replace('%', '%%')


# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
config.set_main_option('sqlalchemy.url', get_engine_url())
target_db = current_app.extensions['migrate'].db

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_metadata():
    if hasattr(target_db, 'metadatas'):
        return target_db.metadatas[None]
    return target_db.metadata


def get_configure_args():
    """Options shared by every run: `app.db_schema.MIGRATE_OPTIONS` (passed to
    Migrate in create_app) plus batch rendering, which SQLite needs for ALTER."""
    args = dict(current_app.extensions['migrate'].configure_args)
    args.setdefault('render_as_batch', True)
    return args


def ensure_schema(connection):
    """Create schema `riftbound` on PostgreSQL BEFORE Alembic creates
    `riftbound.alembic_version` in it (MIG-1). Existence is checked first so
    a role without CREATE privilege on the database can still run migrations
    once the schema exists. SQLite has no CREATE SCHEMA (tests ATTACH one)."""
    if connection.dialect.name != 'postgresql':
        return
    exists = connection.execute(
        text('SELECT 1 FROM information_schema.schemata WHERE schema_name = :s'),
        {'s': SCHEMA},
    ).scalar()
    if not exists:
        connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS {SCHEMA}'))
    # Always end the transaction SQLAlchemy 2.0 autobegan above. If it stayed
    # open Alembic would treat it as an EXTERNAL transaction, never commit it,
    # and every migration would be rolled back when the connection closes.
    connection.commit()


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=get_metadata(), literal_binds=True,
        **get_configure_args()
    )

    with context.begin_transaction():
        if url.startswith('postgresql'):
            context.execute(f'CREATE SCHEMA IF NOT EXISTS {SCHEMA}')
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    # this callback is used to prevent an auto-migration from being generated
    # when there are no changes to the schema
    # reference: http://alembic.zzzcomputing.com/en/latest/cookbook.html
    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, 'autogenerate', False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info('No changes in schema detected.')

    conf_args = get_configure_args()
    if conf_args.get("process_revision_directives") is None:
        conf_args["process_revision_directives"] = process_revision_directives

    connectable = get_engine()

    with connectable.connect() as connection:
        ensure_schema(connection)
        context.configure(
            connection=connection,
            target_metadata=get_metadata(),
            **conf_args
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
