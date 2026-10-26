"""F13-e S1-S2 (AC1): queue a sync, list jobs."""
from datetime import date

import pytest

from app import db
from app.models.audit import RbAdminAudit
from app.models.job import RbJob
from app.models.set import RbSet
from app.models.user import User

URL = '/riftbound/api/v1/admin/riot/sync'
JOBS = '/riftbound/api/v1/admin/jobs'


@pytest.fixture
def sets(app):
    db.session.add_all([
        RbSet(rbset_id='OGN', rbset_name='Origen', rbset_ncard=1,
              rbset_outdat=date(2026, 1, 1)),
        RbSet(rbset_id='SFD', rbset_name='Segundo', rbset_ncard=0),
    ])
    db.session.commit()
    return app


class TestQueueSync:
    def test_queues_a_manual_job(self, admin_client, sets):
        from app.models import User
        resp = admin_client.post(URL, json={'sets': ['ogn', 'SFD']})
        assert resp.status_code == 202
        body = resp.get_json()
        job = RbJob.query.get(body['data']['job_id'])
        assert job.rbjob_kind == 'riot_sync'
        assert job.rbjob_params == {'trigger': 'manual', 'sets': 'OGN,SFD'}
        admin = User.query.filter_by(username='admin').one()
        assert job.rbjob_requested_by == admin.id
        row = RbAdminAudit.query.filter_by(rbaud_action='riot.sync_requested').one()
        assert row.rbaud_target_id == str(job.rbjob_id)

    def test_no_sets_means_every_gallery_set(self, admin_client, sets):
        resp = admin_client.post(URL, json={})
        job = RbJob.query.get(resp.get_json()['data']['job_id'])
        assert job.rbjob_params == {'trigger': 'manual'}

    def test_unknown_set_is_400(self, admin_client, sets):
        resp = admin_client.post(URL, json={'sets': ['OGN', 'NOPE']})
        assert resp.status_code == 400
        body = resp.get_json()
        assert body['code'] == 'validation_error'
        assert any(d['field'] == 'sets' and d['code'] == 'invalid_value'
                   and d['params'] == {'values': ['NOPE']} for d in body['details'])
        assert RbJob.query.count() == 0

    def test_active_job_is_409(self, admin_client, sets):
        admin_client.post(URL, json={})
        resp = admin_client.post(URL, json={})
        assert resp.status_code == 409
        assert resp.get_json()['code'] == 'job_running'

    def test_anonymous_is_401_and_plain_user_is_403(self, app, authenticated_client, sets):
        assert app.test_client().post(URL, json={}).status_code == 401
        assert authenticated_client.post(URL, json={}).status_code == 403


def _job(kind='riot_sync', status='success', by=None, message=None, result=None, params=None):
    job = RbJob(rbjob_kind=kind, rbjob_status=status, rbjob_requested_by=by,
                rbjob_message=message, rbjob_result=result,
                rbjob_params=params or {})
    db.session.add(job)
    db.session.commit()
    return job


class TestJobs:
    def test_list_filters_limit_and_order(self, admin_client, app, make_user):
        user = make_user('op')
        first = _job(by=user.id)
        _job(kind='daily_prices')
        _job(status='error', message='boom')
        body = admin_client.get(f'{JOBS}?kind=riot_sync&limit=1').get_json()
        assert [i['id'] for i in body['data']['items']] == [first.rbjob_id + 2]
        item = body['data']['items'][0]
        assert set(item) == {'id', 'kind', 'status', 'requested_by', 'requested_at',
                             'started_at', 'finished_at', 'message'}
        body = admin_client.get(f'{JOBS}?kind=riot_sync').get_json()
        assert [i['requested_by'] for i in body['data']['items']] == [None, 'op']

    def test_limit_is_validated(self, admin_client):
        assert admin_client.get(f'{JOBS}?limit=0').status_code == 400
        assert admin_client.get(f'{JOBS}?limit=101').status_code == 400

    def test_detail_has_params_and_result(self, admin_client, app):
        job = _job(message='m', result={'sets': [{'set_id': 'OGN'}]},
                   params={'trigger': 'manual'})
        body = admin_client.get(f'{JOBS}/{job.rbjob_id}').get_json()
        assert body['data']['params'] == {'trigger': 'manual'}
        assert body['data']['result'] == {'sets': [{'set_id': 'OGN'}]}
        assert body['data']['message'] == 'm'

    def test_unknown_job_is_404(self, admin_client):
        assert admin_client.get(f'{JOBS}/9999').status_code == 404
