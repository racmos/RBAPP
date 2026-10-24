"""F2-a S1/S3: `app/schemas/game_domain.py` and the `RbCardBan` model
(table `riftbound.rbcardbans`), checked on the test schema (`create_all`)."""
from datetime import date

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import RbCardBan
from app.schemas import game_domain
from app.schemas.prefs_domain import sql_in

COLUMNS = {
    # name: (type, nullable, length)
    'rbban_id': (sa.Integer, False, None),
    'rbban_name_key': (sa.String, False, 200),
    'rbban_name': (sa.String, False, 200),
    'rbban_mode': (sa.String, False, 3),
    'rbban_since': (sa.Date, False, None),
    'rbban_reason': (sa.String, True, 500),
    'rbban_created_at': (sa.DateTime, False, None),
}


def _ban(**overrides):
    values = dict(rbban_name_key='jinx, loose cannon', rbban_name='Jinx, Loose Cannon',
                  rbban_mode='1v1', rbban_since=date(2026, 9, 1))
    values.update(overrides)
    return RbCardBan(**values)


def _count():
    return db.session.execute(sa.select(sa.func.count()).select_from(RbCardBan)).scalar_one()


# --- S1 ------------------------------------------------------------------------------

def test_game_modes_are_1v1_and_2v2():
    assert game_domain.GAME_MODES == ('1v1', '2v2')


def test_game_domain_docstring_names_it_the_single_source():
    doc = ' '.join(game_domain.__doc__.split())
    assert 'single source of game enumerations' in doc
    assert 'F2-b' in doc and 'F5' in doc


def test_mode_check_is_built_from_game_modes():
    checks = {c.name: str(c.sqltext) for c in RbCardBan.__table__.constraints
              if isinstance(c, sa.CheckConstraint)}
    assert checks == {'rbcardbans_mode_chk': sql_in('rbban_mode', game_domain.GAME_MODES)}
    assert checks['rbcardbans_mode_chk'] == "rbban_mode IN ('1v1', '2v2')"


# --- S3 ------------------------------------------------------------------------------

def test_table_name_schema_and_comment():
    table = RbCardBan.__table__
    assert (table.name, table.schema) == ('rbcardbans', 'riftbound')
    assert table.comment == 'Bans by card name and game mode (F2).'


def test_columns_types_nullability_and_comments():
    table = RbCardBan.__table__
    assert list(table.columns.keys()) == list(COLUMNS)
    for name, (type_, nullable, length) in COLUMNS.items():
        column = table.columns[name]
        assert isinstance(column.type, type_), name
        assert column.nullable is nullable, name
        assert getattr(column.type, 'length', None) == length, name
        assert column.comment and column.comment.strip(), f'{name} has no comment'
    assert table.columns['rbban_id'].primary_key
    assert table.columns['rbban_id'].autoincrement in (True, 'auto')
    assert table.columns['rbban_created_at'].server_default is not None


def test_named_primary_key_and_unique():
    table = RbCardBan.__table__
    assert table.primary_key.name == 'rbcardbans_pkey'
    uniques = {c.name: [col.name for col in c.columns] for c in table.constraints
               if isinstance(c, sa.UniqueConstraint)}
    assert uniques == {'rbcardbans_name_mode_key': ['rbban_name_key', 'rbban_mode']}


def test_insert_defaults_created_at_from_the_clock(app, frozen_clock):
    db.session.add(_ban(rbban_reason='Too strong'))
    db.session.commit()
    ban = db.session.execute(sa.select(RbCardBan)).scalar_one()
    assert (ban.rbban_id, ban.rbban_mode, ban.rbban_since, ban.rbban_reason,
            ban.rbban_created_at) == (1, '1v1', date(2026, 9, 1), 'Too strong', frozen_clock())


def test_same_name_in_both_modes_is_allowed(app):
    db.session.add_all([_ban(), _ban(rbban_mode='2v2')])
    db.session.commit()
    assert _count() == 2


@pytest.mark.parametrize('second', [dict(), dict(rbban_name='JINX, LOOSE CANNON')])
def test_unique_rejects_a_second_row_for_the_same_key_and_mode(app, second):
    db.session.add(_ban())
    db.session.commit()
    db.session.add(_ban(**second))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
    assert _count() == 1


@pytest.mark.parametrize('mode', ['3v3', 'ffa', '1V1'])
def test_check_rejects_other_modes(app, mode):
    db.session.add(_ban(rbban_mode=mode))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
    assert _count() == 0
