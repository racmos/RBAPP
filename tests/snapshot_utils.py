"""Parser for the dev schema snapshot (`tests/fixtures/dev_schema_snapshot.txt`).

The snapshot is the text printed by `flask schema snapshot` on the dev
database (see `app/cli/schema.py`). It is the only source of truth for the
`0001_baseline` revision (MIG-2, D5). Tests parse it here so the SQLite
structure checks and the PostgreSQL comparison read the same file.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

FIXTURE = Path(__file__).resolve().parent / 'fixtures' / 'dev_schema_snapshot.txt'


@dataclass
class Column:
    name: str
    type: str
    notnull: bool
    default: str | None


@dataclass
class Table:
    name: str
    columns: list = field(default_factory=list)
    primary_key: tuple = None          # (constraint name, [columns])
    uniques: dict = field(default_factory=dict)   # name -> [columns]
    foreign_keys: dict = field(default_factory=dict)  # name -> dict
    checks: dict = field(default_factory=dict)    # name -> expression text
    indexes: dict = field(default_factory=dict)   # name -> dict(unique, columns, where)


_FK = re.compile(
    r'FOREIGN KEY \((?P<cols>[^)]*)\) REFERENCES (?P<schema>\w+)\.(?P<table>\w+)'
    r'\((?P<refs>[^)]*)\)(?P<rest>.*)$')
_INDEX = re.compile(
    r'CREATE (?P<unique>UNIQUE )?INDEX (?P<name>\w+) ON \w+\.(?P<table>\w+) '
    r'USING btree \((?P<cols>[^)]*)\)(?: WHERE (?P<where>.*))?$')


_ACTION = r'ON %s (CASCADE|RESTRICT|NO ACTION|SET NULL|SET DEFAULT)'


def _cols(text):
    return [c.strip() for c in text.split(',')]


def parse_snapshot(text):
    """-> {table name: Table}. Only `-- TABLE riftbound.<t>` blocks."""
    tables = {}
    current = None
    for raw in text.splitlines():
        if raw.startswith('-- TABLE riftbound.'):
            current = Table(raw.split('.', 1)[1].strip())
            tables[current.name] = current
            continue
        if raw.startswith('--') or not raw.strip():
            if raw.startswith('-- OTHER'):
                current = None
            continue
        if current is None:
            continue
        line = raw.strip()
        if line.startswith('CONSTRAINT '):
            _, name, rest = line.split(' ', 2)
            if rest.startswith('PRIMARY KEY'):
                current.primary_key = (name, _cols(rest[rest.index('(') + 1:rest.rindex(')')]))
            elif rest.startswith('UNIQUE'):
                current.uniques[name] = _cols(rest[rest.index('(') + 1:rest.rindex(')')])
            elif rest.startswith('FOREIGN KEY'):
                m = _FK.match(rest)
                tail = m['rest']
                current.foreign_keys[name] = dict(
                    columns=_cols(m['cols']), table=m['table'], refs=_cols(m['refs']),
                    onupdate=(re.search(_ACTION % 'UPDATE', tail) or [None, None])[1],
                    ondelete=(re.search(_ACTION % 'DELETE', tail) or [None, None])[1])
            elif rest.startswith('CHECK'):
                current.checks[name] = rest
            # 'NOT NULL col' constraint lines are covered by Column.notnull
        elif line.startswith('CREATE '):
            m = _INDEX.match(line)
            current.indexes[m['name']] = dict(
                unique=bool(m['unique']), columns=_cols(m['cols']), where=m['where'])
        else:
            name, rest = line.split(' ', 1)
            default = None
            if ' DEFAULT ' in rest:
                rest, default = rest.split(' DEFAULT ', 1)
            notnull = rest.endswith(' NOT NULL')
            if notnull:
                rest = rest[:-len(' NOT NULL')]
            current.columns.append(Column(name, rest, notnull, default))
    return tables


def load_snapshot():
    return parse_snapshot(FIXTURE.read_text())
