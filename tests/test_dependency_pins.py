"""Dependency pins (conventions section 4; re-created by F9-c S1/S12).

Every requirement is pinned with `==`, and every package the `AGENTS.md` technology table
names shows the pinned version. Only committed files are read: no pip, no network.
"""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
REQUIREMENT = re.compile(r'^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[A-Za-z0-9,._-]+\])?'
                         r'==(?P<version>[0-9][A-Za-z0-9.+!-]*)$')
VERSION = r'[0-9]+(?:\.[0-9A-Za-z]+)+'


def _normal(name):
    """PEP 503 normal form: lower case, runs of `-`, `_`, `.` become one `-`."""
    return re.sub(r'[-_.]+', '-', name).lower()


def _requirement_lines():
    lines = []
    for raw in (ROOT / 'requirements.txt').read_text(encoding='utf-8').splitlines():
        line = raw.split('#', 1)[0].strip()
        if line:
            lines.append(line)
    return lines


def _pins():
    pins = {}
    for line in _requirement_lines():
        match = REQUIREMENT.match(line)
        assert match, f'requirements.txt: {line!r} is not pinned as name==version'
        pins[_normal(match['name'])] = match['version']
    return pins


def _technology_table():
    text = (ROOT / 'AGENTS.md').read_text(encoding='utf-8')
    section = text.split('## Technology Stack', 1)[1].split('\n## ', 1)[0]
    return '\n'.join(line for line in section.splitlines() if line.startswith('|'))


def _table_mentions(table):
    """`{normal name: [versions]}` for every `<Name> <version>` the table shows."""
    found = {}
    for match in re.finditer(rf'(?P<name>[A-Za-z][A-Za-z0-9._-]*) (?P<version>{VERSION})', table):
        found.setdefault(_normal(match['name']), []).append(match['version'])
    return found


@pytest.mark.parametrize('line', _requirement_lines())
def test_every_requirement_is_pinned_exactly(line):
    assert REQUIREMENT.match(line), f'{line!r} is not pinned as name==version'


def test_the_table_shows_the_pinned_version_of_every_package_it_names():
    pins = _pins()
    mentions = _table_mentions(_technology_table())
    wrong = {name: (versions, pins[name]) for name, versions in mentions.items()
             if name in pins and any(version != pins[name] for version in versions)}
    assert not wrong, f'AGENTS.md table versions differ from requirements.txt: {wrong}'


@pytest.mark.parametrize('package', ['flask', 'sqlalchemy', 'flask-sqlalchemy', 'psycopg',
                                     'alembic', 'flask-migrate', 'flask-login', 'flask-wtf',
                                     'flask-limiter', 'altcha', 'pydantic', 'pytest',
                                     'pytest-cov', 'gunicorn', 'pillow'])
def test_the_table_names_each_main_package(package):
    assert package in _table_mentions(_technology_table()), \
        f'the AGENTS.md technology table does not show {package} with its version'


def test_pillow_is_pinned_and_shown_with_the_same_version():
    """F9-c S1: the only new package of the unit."""
    pin = _pins()['pillow']
    assert _table_mentions(_technology_table())['pillow'] == [pin]


def test_the_frontend_altcha_equals_the_python_pin():
    """The widget and the server library must speak the same protocol (conventions 5)."""
    package = json.loads((ROOT / 'frontend' / 'package.json').read_text(encoding='utf-8'))
    versions = {**package.get('dependencies', {}), **package.get('devDependencies', {})}
    assert versions['altcha'] == _pins()['altcha']
