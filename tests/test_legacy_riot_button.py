"""F13-c S10 (AC4): the legacy Jinja button queues a manual riot_sync job."""
from unittest.mock import patch

from app.services.jobs import JobAlreadyActive

URL = '/riftbound/price/extract-riot-cards'


def test_queues_a_manual_job(admin_client):
    with patch('app.services.jobs.enqueue', return_value=type('J', (), {'rbjob_id': 7})()) as queue:
        resp = admin_client.post(URL, json={'sets': ['OGN']})
    assert resp.status_code == 200
    queue.assert_called_once_with('riot_sync', {'trigger': 'manual', 'sets': 'OGN'})
    assert resp.get_json() == {
        'success': True, 'job_id': 7,
        'message': 'Sincronización encolada (trabajo 7). '
                   'Revisa el resultado en la nueva administración.'}


def test_empty_sets_means_every_set(admin_client):
    with patch('app.services.jobs.enqueue', return_value=type('J', (), {'rbjob_id': 1})()) as queue:
        admin_client.post(URL, json={'sets': []})
    queue.assert_called_once_with('riot_sync', {'trigger': 'manual'})


def test_active_job_is_409(admin_client):
    with patch('app.services.jobs.enqueue', side_effect=JobAlreadyActive(7)):
        resp = admin_client.post(URL, json={'sets': []})
    assert resp.status_code == 409
    assert resp.get_json() == {'success': False,
                               'message': 'Ya hay una sincronización en curso.'}


def test_a_plain_user_gets_403(authenticated_client):
    with patch('app.services.jobs.enqueue') as queue:
        resp = authenticated_client.post(URL, json={'sets': []})
    assert resp.status_code == 403
    assert not queue.called
