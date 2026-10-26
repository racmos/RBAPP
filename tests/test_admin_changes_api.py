"""F13-e S3-S6 (AC2): change list, approve, reject, bulk."""
from datetime import date, datetime

import pytest

from app import db
from app.models.audit import RbAdminAudit
from app.models.card import RbCard
from app.models.card_change import RbCardChange
from app.models.set import RbSet

URL = '/riftbound/api/v1/admin/riot/changes'


@pytest.fixture
def data(app, card_images_dir):
    db.session.add(RbSet(rbset_id='OGN', rbset_name='Origen', rbset_ncard=2,
                         rbset_outdat=date(2025, 1, 1)))
    db.session.add_all([
        RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='Alpha Unit',
               rbcar_energy=9, rbcar_domain='fury', rbcar_type='Unit',
               rbcar_rarity='Common', image='ogn_1.png',
               image_url='https://img.test/ogn_1.png'),
        RbCard(rbcar_rbset_id='OGN', rbcar_id='2', rbcar_name='Beta Spell',
               rbcar_energy=1, image='ogn_2.png',
               image_url='https://img.test/ogn_2.png'),
    ])
    db.session.add_all([
        RbCardChange(rbchg_rbset_id='OGN', rbchg_rbcar_id='1', rbchg_field='rbcar_energy',
                     rbchg_old_value='9', rbchg_new_value='2', rbchg_status='pending',
                     rbchg_detected_at=datetime(2026, 5, 1, 12, 0), rbchg_job_id=4),
        RbCardChange(rbchg_rbset_id='OGN', rbchg_rbcar_id='2', rbchg_field='rbcar_name',
                     rbchg_old_value='Beta Spell', rbchg_new_value='Beta Spell!',
                     rbchg_status='pending', rbchg_detected_at=datetime(2026, 5, 2, 12, 0)),
        RbCardChange(rbchg_rbset_id='OGN', rbchg_rbcar_id='1', rbchg_field='rbcar_rarity',
                     rbchg_old_value=None, rbchg_new_value='Rare',
                     rbchg_status='approved', rbchg_detected_at=datetime(2026, 4, 1, 12, 0)),
    ])
    db.session.commit()
    return app


def payload(resp):
    return resp.get_json()


class TestList:
    def test_default_is_pending_newest_first(self, admin_client, data):
        body = payload(admin_client.get(URL))
        assert [i['id'] for i in body['data']['items']] == [2, 1]
        assert body['data']['meta']['counts'] == {'pending': 2, 'approved': 1, 'rejected': 0}
        assert body['data']['meta']['total'] == 2

    def test_item_shape(self, admin_client, data):
        item = payload(admin_client.get(URL))['data']['items'][0]
        assert item == {'id': 2, 'set_id': 'OGN', 'card_id': '2', 'card_name': 'Beta Spell',
                        'image_src': '/riftbound/media/cards/ogn/ogn_2.png',
                        'field': 'rbcar_name', 'old_value': 'Beta Spell',
                        'new_value': 'Beta Spell!', 'status': 'pending',
                        'detected_at': '2026-05-02T12:00:00', 'job_id': None,
                        'decided_at': None, 'decided_by': None}

    def test_filters(self, admin_client, data):
        assert payload(admin_client.get(f'{URL}?status=all'))['data']['meta']['total'] == 3
        assert payload(admin_client.get(f'{URL}?status=rejected'))['data']['meta']['total'] == 0
        assert [i['id'] for i in
                payload(admin_client.get(f'{URL}?status=all&set=OGN&field=rbcar_energy'))['data']['items']] == [1]
        assert [i['id'] for i in
                payload(admin_client.get(f'{URL}?status=all&q=beta'))['data']['items']] == [2]

    def test_bounded_statements(self, admin_client, data):
        from sqlalchemy import event
        counted = []

        def before(conn, cursor, statement, params, context, executemany):
            if statement.lstrip().upper().startswith('SELECT') and 'rbusers' not in statement:
                counted.append(statement)

        event.listen(db.engine, 'before_cursor_execute', before)
        try:
            assert admin_client.get(URL).status_code == 200
        finally:
            event.remove(db.engine, 'before_cursor_execute', before)
        assert len(counted) <= 3, counted

    def test_bad_status_is_400(self, admin_client):
        assert payload(admin_client.get(f'{URL}?status=maybe'))['code'] == 'validation_error'


class TestApprove:
    def test_approve_applies_and_records(self, admin_client, data):
        body = payload(admin_client.post(f'{URL}/1/approve'))
        assert body['data']['status'] == 'approved'
        card = RbCard.query.filter_by(rbcar_rbset_id='OGN', rbcar_id='1').one()
        assert card.rbcar_energy == 2
        row = RbCardChange.query.get(1)
        assert row.rbchg_status == 'approved' and row.rbchg_decided_by is not None
        audit = RbAdminAudit.query.filter_by(rbaud_action='riot.change_approve').one()
        assert audit.rbaud_details == {'card': 'OGN-1', 'field': 'rbcar_energy',
                                       'old': '9', 'new': '2'}

    def test_stale_change_is_409_and_writes_nothing(self, admin_client, data):
        card = RbCard.query.filter_by(rbcar_rbset_id='OGN', rbcar_id='1').one()
        card.rbcar_energy = 5
        db.session.commit()
        resp = admin_client.post(f'{URL}/1/approve')
        assert resp.status_code == 409
        assert payload(resp)['code'] == 'change_stale'
        assert RbCard.query.filter_by(rbcar_rbset_id='OGN', rbcar_id='1').one().rbcar_energy == 5
        assert RbCardChange.query.get(1).rbchg_status == 'pending'
        assert RbAdminAudit.query.count() == 0

    def test_decided_change_is_409(self, admin_client, data):
        resp = admin_client.post(f'{URL}/1/approve')
        assert resp.status_code == 200
        resp2 = admin_client.post(f'{URL}/1/approve')
        assert resp2.status_code == 409
        assert payload(resp2)['code'] == 'change_decided'

    def _image_change(self, new_url):
        from datetime import datetime
        db.session.add(RbCard(rbcar_rbset_id='OGN', rbcar_id='9', rbcar_name='Image Unit',
                              image='ogn_9.png',
                              image_url='https://img.test/ogn_9_old.png'))
        db.session.add(RbCardChange(rbchg_rbset_id='OGN', rbchg_rbcar_id='9',
                                    rbchg_field='image_url',
                                    rbchg_old_value='https://img.test/ogn_9_old.png',
                                    rbchg_new_value=new_url, rbchg_status='pending',
                                    rbchg_detected_at=datetime(2026, 5, 3, 12, 0)))
        db.session.commit()
        return RbCardChange.query.filter_by(rbchg_rbcar_id='9').one().rbchg_id

    def test_image_download_failure_keeps_approved_with_warning(self, admin_client, data,
                                                                monkeypatch):
        import app.services.change_review as review
        monkeypatch.setattr(review, '_download_image', lambda *a: False)
        change_id = self._image_change('https://img.test/ogn_9_new.png')
        body = payload(admin_client.post(f'{URL}/{change_id}/approve'))
        assert body['data']['status'] == 'approved'
        assert body.get('warnings') == ['image_download_failed']

    def test_image_download_success_writes_the_file(self, admin_client, data, monkeypatch,
                                                    card_images_dir):
        import app.services.change_review as review
        seen = {}

        def _fake(session, url, dest):
            seen['url'] = url
            with open(dest, 'wb') as handle:
                handle.write(b'IMG')
            return True
        monkeypatch.setattr(review, '_download_image', _fake)
        change_id = self._image_change('https://img.test/ogn_9_new.png')
        body = payload(admin_client.post(f'{URL}/{change_id}/approve'))
        assert 'warnings' not in body
        assert seen['url'] == 'https://img.test/ogn_9_new.png'
        assert (card_images_dir / 'ogn' / 'ogn_9.png').read_bytes() == b'IMG'

    def test_unknown_change_is_404(self, admin_client):
        assert admin_client.post(f'{URL}/999/approve').status_code == 404


class TestReject:
    def test_reject(self, admin_client, data):
        body = payload(admin_client.post(f'{URL}/1/reject'))
        assert body['data']['status'] == 'rejected'
        assert RbCard.query.filter_by(rbcar_rbset_id='OGN', rbcar_id='1').one().rbcar_energy == 9
        row = RbCardChange.query.get(1)
        assert row.rbchg_decided_by is not None
        audit = RbAdminAudit.query.filter_by(rbaud_action='riot.change_reject').one()
        assert audit.rbaud_details == {'card': 'OGN-1', 'field': 'rbcar_energy'}


class TestBulk:
    def test_mixed_outcomes(self, admin_client, data):
        resp = admin_client.post(f'{URL}/bulk', json={'ids': [1, 2, 999], 'action': 'approve'})
        body = payload(resp)
        assert [r['outcome'] for r in body['data']['results']] == ['approved', 'approved', 'not_found']
        assert body['data']['counts'] == {'approved': 2, 'rejected': 0, 'stale': 0,
                                          'decided': 0, 'not_found': 1}

    def test_reject_and_stale(self, admin_client, data):
        card = RbCard.query.filter_by(rbcar_rbset_id='OGN', rbcar_id='1').one()
        card.rbcar_energy = 5
        db.session.commit()
        body = payload(admin_client.post(f'{URL}/bulk', json={'ids': [1, 2], 'action': 'reject'}))
        assert [r['outcome'] for r in body['data']['results']] == ['rejected', 'rejected']
        body = payload(admin_client.post(f'{URL}/bulk', json={'ids': [1], 'action': 'approve'}))
        assert body['data']['results'] == [{'id': 1, 'outcome': 'decided'}]

    def test_bad_action_is_400(self, admin_client):
        assert admin_client.post(f'{URL}/bulk', json={'ids': [1], 'action': 'merge'}).status_code == 400
