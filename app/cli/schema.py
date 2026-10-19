"""`flask schema snapshot`: print the live `riftbound` schema as plain text.

The output has the format of `tests/fixtures/dev_schema_snapshot.txt`, the
reference copy of the dev database that `0001_baseline` reproduces (D5). It is
used in two places: on dev, before `flask db stamp 0001_baseline`, to prove the
baseline equals the real database (diff the output against the fixture), and
in the PostgreSQL test lane. PostgreSQL only: it reads `pg_catalog`.

Read-only, and `alembic_version` is left out (migration tooling, not schema).
"""
import click
from flask.cli import AppGroup
from sqlalchemy import text

from app import db
from app.db_schema import SCHEMA

schema_cli = AppGroup('schema', help='Inspect the database schema.')

# Tables that belong to the migration tooling, not to the application schema.
_TOOLING_TABLES = ('alembic_version',)


def _column_line(name, type_, not_null, default):
    line = f'  {name} {type_}'
    if not_null:
        line += ' NOT NULL'
    if default is not None:
        line += f' DEFAULT {default}'
    return line


def render_snapshot(conn) -> str:
    """The snapshot text for schema `riftbound`, read through `conn` (PostgreSQL).

    `search_path` is pinned to pg_catalog for the duration of the reads so that
    PostgreSQL always schema-qualifies riftbound objects (types, sequences,
    foreign-key targets), whatever the role's own search_path is."""
    params = {'schema': SCHEMA}
    conn.execute(text('SET LOCAL search_path TO pg_catalog'))

    version = conn.execute(text('SELECT version()')).scalar()
    lines = [f'-- {version}', '']

    tables = conn.execute(text(
        'SELECT c.oid, c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace'
        " WHERE n.nspname = :schema AND c.relkind IN ('r', 'p')"), params).all()
    for oid, name in sorted(tables, key=lambda t: t.relname):
        if name in _TOOLING_TABLES:
            continue
        lines.append(f'-- TABLE {SCHEMA}.{name}')
        for col in conn.execute(text(
                'SELECT a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull,'
                ' pg_get_expr(d.adbin, d.adrelid)'
                ' FROM pg_attribute a LEFT JOIN pg_attrdef d'
                '  ON d.adrelid = a.attrelid AND d.adnum = a.attnum'
                ' WHERE a.attrelid = :oid AND a.attnum > 0 AND NOT a.attisdropped'
                ' ORDER BY a.attnum'), {'oid': oid}):
            lines.append(_column_line(*col))
        constraints = conn.execute(text(
            'SELECT contype::text, conname, pg_get_constraintdef(oid)'
            ' FROM pg_constraint WHERE conrelid = :oid'), {'oid': oid}).all()
        for _type, conname, definition in sorted(constraints, key=lambda c: (c[0], c[1])):
            lines.append(f'  CONSTRAINT {conname} {definition}')
        indexes = conn.execute(text(
            'SELECT indexname, indexdef FROM pg_indexes'
            ' WHERE schemaname = :schema AND tablename = :table'),
            {'schema': SCHEMA, 'table': name}).all()
        for _indexname, definition in sorted(indexes):
            lines.append(f'  {definition}')
        lines.append('')

    others = conn.execute(text(
        'SELECT c.relkind::text, c.relname FROM pg_class c'
        ' JOIN pg_namespace n ON n.oid = c.relnamespace'
        " WHERE n.nspname = :schema AND c.relkind IN ('v', 'm', 'S')"), params).all()
    lines.append('-- OTHER OBJECTS (v=view, m=matview, S=sequence)')
    lines += [f'  {kind} {name}' for kind, name in sorted(others)]

    functions = conn.execute(text(
        'SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace'
        ' WHERE n.nspname = :schema'), params).scalars().all()
    triggers = conn.execute(text(
        'SELECT t.tgname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid'
        ' JOIN pg_namespace n ON n.oid = c.relnamespace'
        ' WHERE n.nspname = :schema AND NOT t.tgisinternal'), params).scalars().all()
    lines.append('-- FUNCTIONS: ' + ', '.join(sorted(functions)))
    lines.append('-- TRIGGERS: ' + ', '.join(sorted(triggers)))
    return '\n'.join(lines) + '\n'


@schema_cli.command('snapshot')
def snapshot():
    """Print the riftbound schema in the dev-snapshot format (PostgreSQL only)."""
    with db.engine.connect() as conn:
        if conn.dialect.name != 'postgresql':
            raise click.ClickException(
                'flask schema snapshot reads pg_catalog and needs a PostgreSQL '
                f'database (this one is {conn.dialect.name}).')
        try:
            output = render_snapshot(conn)
        finally:
            conn.rollback()       # only reads; also discards the SET LOCAL
    click.echo(output, nl=False)
