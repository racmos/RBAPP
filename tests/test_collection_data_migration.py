"""F3-a S2 (AC1): migration `0014_collection_selling` back-fills `rbcol_sell_qty`, turns 'S' into
'Y', adds the purchase price and the new CHECKs; `0015_playset` adds the playset size. Round trips
and drift for both (SQLite; the `migrations-pg` CI job runs the same revisions on PostgreSQL 18)."""
import importlib.util
import logging
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from tests.migration_helpers import downgrade, drift, inspector, rows, run, tables, upgrade

VERSIONS = Path(__file__).resolve().parents[1] / 'migrations' / 'versions'
BEFORE = '0013_price_product_date_idx'
SELLING = '0014_collection_selling'
PLAYSET = '0015_playset'

USER = ("INSERT INTO riftbound.rbusers (id, username, email, password_hash, is_admin, is_blocked, "
        "failed_login_count) VALUES (:id, :name, :name || '@test.com', 'x', 0, 0, 0)")
LINE = ("INSERT INTO riftbound.rbcollection (rbcol_rbset_id, rbcol_rbcar_id, rbcol_foil, rbcol_user, "
        "rbcol_quantity, rbcol_selling, rbcol_playset, rbcol_chadat) "
        "VALUES ('OGN', :card, :foil, :user, :qty, :selling, :playset, '2026-10-01 10:00:00')")


def _migration(name):
    spec = importlib.util.spec_from_file_location(f'migration_{name}', VERSIONS / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _legacy_catalog():
    """A user and three cards on the schema as it was before F3-a."""
    run(USER, id=1, name='ana')
    run("INSERT INTO riftbound.rbset (rbset_id, rbset_name) VALUES ('OGN', 'Origins')")
    for card, name in (('1', 'Ember Wisp'), ('2', 'Fury Rune'), ('3', 'Ayla')):
        run("INSERT INTO riftbound.rbcards (rbcar_rbset_id, rbcar_id, rbcar_name) "
            "VALUES ('OGN', :card, :name)", card=card, name=name)


def _line(card, qty, selling, playset=None, foil='N', user='ana'):
    run(LINE, card=card, foil=foil, user=user, qty=qty, selling=selling, playset=playset)


def test_revisions_chain():
    selling, playset = _migration(SELLING), _migration(PLAYSET)
    assert (selling.revision, selling.down_revision) == (SELLING, BEFORE)
    assert (playset.revision, playset.down_revision) == (PLAYSET, SELLING)


def test_docstrings_state_the_data_loss_on_downgrade():
    assert 'every purchase price and copies-to-sell count is lost' in ' '.join(
        _migration(SELLING).__doc__.split())
    assert 'every playset size and every "keep a playset" mark is lost' in ' '.join(
        _migration(PLAYSET).__doc__.split())


def test_backfill_of_every_kind_of_row(migration_app, caplog):
    upgrade(BEFORE)
    _legacy_catalog()
    _line('1', qty=5, selling='S')                 # legacy 'S' -> 'Y', all for sale
    _line('1', qty=4, selling='Y', foil='S')
    _line('2', qty=3, selling='N')
    _line('2', qty=5, selling='Y', playset=3, foil='S')   # surplus over the playset
    _line('3', qty=2, selling='N', playset=3)             # playset larger than the stock
    _line('3', qty=4, selling='Y', playset=1, foil='S')
    with caplog.at_level(logging.INFO, logger='alembic.runtime.migration'):
        upgrade(SELLING)
    assert 'rbcollection rows S->Y: 1' in caplog.text
    assert rows('SELECT rbcol_rbcar_id, rbcol_foil, rbcol_quantity, rbcol_selling, rbcol_playset, '
                'rbcol_sell_qty, rbcol_purchase_price FROM riftbound.rbcollection '
                'ORDER BY rbcol_id') == [
        ('1', 'N', 5, 'Y', None, 5, None),
        ('1', 'S', 4, 'Y', None, 4, None),
        ('2', 'N', 3, 'N', None, 0, None),
        ('2', 'S', 5, 'Y', 3, 2, None),
        ('3', 'N', 2, 'N', 3, 0, None),
        ('3', 'S', 4, 'Y', 1, 3, None),
    ]


def test_the_new_checks_reject_bad_rows(migration_app):
    upgrade(BEFORE)
    _legacy_catalog()
    _line('1', qty=3, selling='N')
    upgrade(SELLING)
    bad = {
        'negative price': "UPDATE riftbound.rbcollection SET rbcol_purchase_price = -0.01",
        'more to sell than owned': "UPDATE riftbound.rbcollection SET rbcol_sell_qty = 4",
        'negative copies to sell': "UPDATE riftbound.rbcollection SET rbcol_sell_qty = -1",
        'legacy S': "UPDATE riftbound.rbcollection SET rbcol_selling = 'S'",
    }
    for label, sql in bad.items():
        with pytest.raises(IntegrityError):
            run(sql)
        assert rows('SELECT rbcol_purchase_price, rbcol_sell_qty, rbcol_selling '
                    'FROM riftbound.rbcollection') == [(None, 0, 'N')], label
    run("UPDATE riftbound.rbcollection SET rbcol_purchase_price = 0, rbcol_sell_qty = 3")
    run("UPDATE riftbound.rbcollection SET rbcol_purchase_price = 12.34")
    assert rows('SELECT rbcol_purchase_price, rbcol_sell_qty FROM riftbound.rbcollection') == [
        (12.34, 3)]


def test_named_constraints(migration_app):
    upgrade(SELLING)
    names = {check['name'] for check in inspector().get_check_constraints(
        'rbcollection', schema='riftbound')}
    assert {'rbcollection_selling_chk', 'rbcollection_purchase_price_chk',
            'rbcollection_sell_qty_chk', 'rbcollection_playset_chk',
            'rbcollection_quantity_chk'} <= names


def test_selling_round_trip_keeps_the_rows_and_loses_the_new_columns(migration_app):
    upgrade(BEFORE)
    _legacy_catalog()
    _line('1', qty=5, selling='S')
    upgrade(SELLING)
    run("UPDATE riftbound.rbcollection SET rbcol_purchase_price = 3.5")
    downgrade(BEFORE)
    columns = {c['name'] for c in inspector().get_columns('rbcollection', schema='riftbound')}
    assert not {'rbcol_purchase_price', 'rbcol_sell_qty'} & columns
    assert rows('SELECT rbcol_quantity, rbcol_selling FROM riftbound.rbcollection') == [(5, 'Y')]
    run("UPDATE riftbound.rbcollection SET rbcol_selling = 'S'")   # the old CHECK allows it again
    upgrade(SELLING)
    assert rows('SELECT rbcol_selling, rbcol_sell_qty, rbcol_purchase_price '
                'FROM riftbound.rbcollection') == [('Y', 5, None)]


def test_playset_adds_the_size_and_the_marks_table(migration_app):
    upgrade(SELLING)
    assert 'rbkeepplayset' not in tables()
    upgrade(PLAYSET)
    assert 'rbkeepplayset' in tables()
    assert 'rbprf_playset_size' in {c['name'] for c in inspector().get_columns(
        'rbuserprefs', schema='riftbound')}
    assert inspector().get_pk_constraint('rbkeepplayset', schema='riftbound') == {
        'name': 'rbkeepplayset_pkey', 'constrained_columns': ['rbkps_user_id', 'rbkps_name_key']}
    assert 'rbuserprefs_playset_size_chk' in {c['name'] for c in inspector().get_check_constraints(
        'rbuserprefs', schema='riftbound')}


@pytest.mark.parametrize('size, ok', [(1, True), (3, True), (9, True), (None, True),
                                       (0, False), (10, False)])
def test_playset_size_check(migration_app, size, ok):
    upgrade()
    run(USER, id=1, name='ana')
    sql = 'INSERT INTO riftbound.rbuserprefs (rbprf_user_id, rbprf_playset_size) VALUES (1, :size)'
    if ok:
        run(sql, size=size)
        assert rows('SELECT rbprf_playset_size FROM riftbound.rbuserprefs') == [(size,)]
    else:
        with pytest.raises(IntegrityError):
            run(sql, size=size)


def test_playset_round_trip_and_drift_of_both_revisions(migration_app):
    upgrade()
    assert drift() == []
    downgrade(SELLING)
    assert 'rbkeepplayset' not in tables()
    assert 'rbprf_playset_size' not in {c['name'] for c in inspector().get_columns(
        'rbuserprefs', schema='riftbound')}
    assert drift() != []   # the models are ahead of this revision
    downgrade(BEFORE)
    upgrade()
    assert drift() == []
