"""F13-c S9 (AC3): the riot_sync job kind, params, result, migrations."""
import pytest
from sqlalchemy.exc import IntegrityError

from app import db
from app.jobs import registry
from app.jobs.riot_sync import run
from app.jobs.registry import JobFailed
from app.models.card import RbCard
from app.models.card_change import RbCardChange
from app.models.set import RbSet
from app.services import riot_sync
from tests.migration_helpers import downgrade, drift, inspector, rows, run as sql, tables, upgrade


def test_kind_is_registered_with_its_timeout():
    kind = registry.get('riot_sync')
    assert kind.timeout_seconds == 1800
    assert 'riot_sync' in registry.names()


@pytest.mark.parametrize('params', [
    {'trigger': 'bogus'},
    {'slot': 'night'},
    {'unknown': 'x'},
    {'sets': ''},
    {'sets': '  '},
])
def test_bad_params_fail(app, params):
    with pytest.raises(JobFailed, match='riot_sync: invalid params'):
        run(params)


def test_sets_are_split_and_the_slot_is_ignored(app, monkeypatch):
    seen = {}

    def _fake(set_codes, trigger, now, job_id=None):
        seen['args'] = (set_codes, trigger, job_id)
        return {'trigger': trigger}
    monkeypatch.setattr(riot_sync, 'sync', _fake)
    assert run({'sets': 'OGN, OGS', 'slot': 'am'}) == {'trigger': 'manual'}
    assert seen['args'][0] == ['OGN', 'OGS']
    assert seen['args'][1] == 'manual'


def test_run_pending_stores_the_result_and_stamps_the_job(app, make_user, monkeypatch):
    from datetime import date
    import copy
    from tests.test_riot_sync import GALLERY, FakeSession
    from app.services import jobs as jobs_service

    from tests.test_riot_sync import seed_gallery_card
    make_user('admin', is_admin=True)
    db.session.add(RbSet(rbset_id='OGN', rbset_name='O',
                         rbset_outdat=date(2025, 1, 1)))
    seed_gallery_card('OGN', '1', rbcar_energy=9)

    only_one = copy.deepcopy(GALLERY)
    only_one['cards'] = [c for c in only_one['cards'] if c['rbcar_rbset_id'] == 'OGN'
                         and c['rbcar_id'] == '1']
    only_one['set_codes'] = ['OGN']
    monkeypatch.setattr('app.services.riot_sync.fetch_gallery',
                        lambda: copy.deepcopy(only_one))
    monkeypatch.setattr('app.services.riot_sync._get_session', lambda: FakeSession())
    job = jobs_service.enqueue('riot_sync', {'trigger': 'manual'})
    done = jobs_service.run_pending()
    assert [j.rbjob_id for j in done] == [job.rbjob_id]
    stored = db.session.get(type(job), job.rbjob_id)
    assert stored.rbjob_status == 'success'
    assert stored.rbjob_result['trigger'] == 'manual'
    row = RbCardChange.query.one()
    assert (row.rbchg_status, row.rbchg_job_id) == ('pending', job.rbjob_id)


def test_one_active_job_at_a_time(app):
    from app.services import jobs as jobs_service
    from app.services.jobs import JobAlreadyActive
    jobs_service.enqueue('riot_sync', {'trigger': 'manual'})
    with pytest.raises(JobAlreadyActive):
        jobs_service.enqueue('riot_sync', {'trigger': 'manual'})


class TestMigrations:
    def test_round_trip_and_no_drift(self, migration_app):
        upgrade()
        assert {'rbcardchanges', 'rbjobs'} <= tables()
        downgrade('0010_admin_audit')
        assert 'rbcardchanges' not in tables()
        assert 'rbjobs' in tables()
        upgrade()
        assert {'rbcardchanges', 'rbjobs'} <= tables()
        assert drift() == []

    def test_named_constraints_and_partial_unique_index(self, migration_app):
        upgrade()
        checks = {c['name'] for c in inspector().get_check_constraints(
            'rbcardchanges', schema='riftbound')}
        assert {'rbcardchanges_field_chk', 'rbcardchanges_status_chk'} <= checks
        indexes = {i['name']: i for i in inspector().get_indexes(
            'rbcardchanges', schema='riftbound')}
        assert indexes['uq_rbcardchanges_pending']['unique']
        assert indexes['uq_rbcardchanges_pending']['column_names'] == [
            'rbchg_rbset_id', 'rbchg_rbcar_id', 'rbchg_field']

    def test_checks_reject_bad_values(self, migration_app):
        upgrade()
        with pytest.raises(IntegrityError):
            sql("INSERT INTO riftbound.rbcardchanges (rbchg_rbset_id, rbchg_rbcar_id, "
                "rbchg_field, rbchg_status, rbchg_detected_at) "
                "VALUES ('OGN', '1', 'nope', 'pending', '2030-01-01 12:00:00')")
        with pytest.raises(IntegrityError):
            sql("INSERT INTO riftbound.rbcardchanges (rbchg_rbset_id, rbchg_rbcar_id, "
                "rbchg_field, rbchg_status, rbchg_detected_at) "
                "VALUES ('OGN', '1', 'rbcar_name', 'maybe', '2030-01-01 12:00:00')")

    def test_two_pendings_conflict_but_a_decided_row_does_not(self, migration_app):
        upgrade()
        sql("INSERT INTO riftbound.rbcardchanges (rbchg_rbset_id, rbchg_rbcar_id, "
            "rbchg_field, rbchg_status, rbchg_detected_at) "
            "VALUES ('OGN', '1', 'rbcar_name', 'approved', '2030-01-01 12:00:00')")
        sql("INSERT INTO riftbound.rbcardchanges (rbchg_rbset_id, rbchg_rbcar_id, "
            "rbchg_field, rbchg_status, rbchg_detected_at) "
            "VALUES ('OGN', '1', 'rbcar_name', 'pending', '2030-01-01 12:00:00')")
        with pytest.raises(IntegrityError):
            sql("INSERT INTO riftbound.rbcardchanges (rbchg_rbset_id, rbchg_rbcar_id, "
                "rbchg_field, rbchg_status, rbchg_detected_at) "
                "VALUES ('OGN', '1', 'rbcar_name', 'pending', '2030-01-01 12:00:00')")

    def test_downgrade_refuses_while_jobs_exist(self, migration_app):
        upgrade()
        sql("INSERT INTO riftbound.rbjobs (rbjob_kind, rbjob_status, rbjob_requested_at) "
            "VALUES ('riot_sync', 'success', '2030-01-01 12:00:00')")
        with pytest.raises(RuntimeError, match='riot_sync'):
            downgrade('0011_card_changes')
        assert 'rbjobs' in tables()


class TestSchedule:
    def test_missing_slot_is_invalid(self, app):
        with pytest.raises(JobFailed, match='riot_sync: invalid params'):
            run({'trigger': 'schedule'})

    def test_nothing_due_runs_no_fetch(self, app, monkeypatch):
        from app.services import riot_sync as rs
        def _no_fetch():
            raise AssertionError('fetch must not run without due sets')
        monkeypatch.setattr(rs, 'fetch_gallery', _no_fetch)
        result = run({'trigger': 'schedule', 'slot': 'am'})
        assert result == {'trigger': 'schedule', 'slot': 'am', 'today': result['today'],
                          'message': 'nothing due', 'sets': []}

    def test_only_due_sets_are_passed_to_sync(self, app, monkeypatch):
        from datetime import date
        from app.models.set import RbSet
        db.session.add(RbSet(rbset_id='PRE', rbset_name='Pre',
                             rbset_outdat=date(2030, 1, 10)))
        db.session.add(RbSet(rbset_id='OLD', rbset_name='Old',
                             rbset_outdat=date(2025, 1, 1)))
        db.session.commit()
        seen = {}

        def _fake(set_codes, trigger, now, job_id=None):
            seen['set_codes'] = set_codes
            return {'trigger': trigger, 'sets': []}
        monkeypatch.setattr('app.services.riot_sync.sync', _fake)
        monkeypatch.setattr('app.jobs.riot_sync.clock.utcnow',
                            lambda: __import__('datetime').datetime(2030, 1, 15, 12, 0))
        result = run({'trigger': 'schedule', 'slot': 'am'})
        assert seen['set_codes'] == ['PRE']
        assert result['trigger'] == 'schedule'
