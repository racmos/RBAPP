"""Owner feedback 2026-10-29 S17: migration `0023_card_changes_obsolete` adds the
`obsolete` status to `rbcardchanges_status_chk`: round trip, drift, refusal."""
import pytest
from sqlalchemy.exc import IntegrityError

from tests.migration_helpers import downgrade, drift, rows, run, upgrade

BEFORE = '0022_snapshot_products_value'
REVISION = '0023_card_changes_obsolete'
CHANGE = ("INSERT INTO riftbound.rbcardchanges (rbchg_rbset_id, rbchg_rbcar_id, rbchg_field, "
          "rbchg_status, rbchg_detected_at) "
          "VALUES ('OGN', '1', 'rbcar_name', :status, '2030-01-01 12:00:00')")


def test_the_check_accepts_obsolete_only_after_the_revision(migration_app):
    upgrade(BEFORE)
    with pytest.raises(IntegrityError):
        run(CHANGE, status='obsolete')
    upgrade(REVISION)
    run(CHANGE, status='obsolete')
    with pytest.raises(IntegrityError):
        run(CHANGE, status='maybe')
    assert rows('SELECT rbchg_status FROM riftbound.rbcardchanges') == [('obsolete',)]


def test_round_trip_and_drift(migration_app):
    upgrade()
    assert drift() == []
    downgrade(BEFORE)
    with pytest.raises(IntegrityError):
        run(CHANGE, status='obsolete')
    run(CHANGE, status='rejected')
    upgrade()
    assert drift() == []
    assert rows('SELECT rbchg_status FROM riftbound.rbcardchanges') == [('rejected',)]


def test_downgrade_refuses_while_obsolete_rows_exist(migration_app):
    upgrade(REVISION)
    run(CHANGE, status='obsolete')
    with pytest.raises(RuntimeError, match="1 'obsolete' change"):
        downgrade(BEFORE)
    assert rows('SELECT rbchg_status FROM riftbound.rbcardchanges') == [('obsolete',)]
    run("UPDATE riftbound.rbcardchanges SET rbchg_status = 'rejected'")
    downgrade(BEFORE)
    with pytest.raises(IntegrityError):
        run(CHANGE, status='obsolete')
