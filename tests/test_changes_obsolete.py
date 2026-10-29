"""Owner feedback 2026-10-29 S17 (status `obsolete`) and S11 (page size 50/100/200):
the changes API and the sync around obsolete proposals."""
from datetime import date, datetime

import pytest

from app import db
from app.models.card import RbCard
from app.models.card_change import RbCardChange
from app.models.set import RbSet

URL = '/riftbound/api/v1/admin/riot/changes'


@pytest.fixture
def data(app, card_images_dir):
    db.session.add(RbSet(rbset_id='OGN', rbset_name='Origen', rbset_ncard=2,
                         rbset_outdat=date(2025, 1, 1)))
    db.session.add(RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='Alpha Unit',
                          rbcar_energy=9, image='ogn_1.png'))
    db.session.add_all([
        RbCardChange(rbchg_id=1, rbchg_rbset_id='OGN', rbchg_rbcar_id='1',
                     rbchg_field='rbcar_energy', rbchg_old_value='9', rbchg_new_value='2',
                     rbchg_status='pending', rbchg_detected_at=datetime(2026, 5, 1, 12, 0)),
        RbCardChange(rbchg_id=2, rbchg_rbset_id='OGN', rbchg_rbcar_id='1',
                     rbchg_field='rbcar_name', rbchg_old_value='Alpha Unit',
                     rbchg_new_value='Alpha', rbchg_status='obsolete',
                     rbchg_detected_at=datetime(2026, 5, 2, 12, 0),
                     rbchg_decided_at=datetime(2026, 5, 3, 12, 0)),
    ])
    db.session.commit()
    return app


def body(resp):
    return resp.get_json()


class TestList:
    def test_obsolete_is_not_pending(self, admin_client, data):
        meta = body(admin_client.get(URL))['data']['meta']
        assert meta['total'] == 1
        assert meta['counts'] == {'pending': 1, 'approved': 0, 'rejected': 0, 'obsolete': 1}

    def test_status_obsolete_lists_them(self, admin_client, data):
        items = body(admin_client.get(f'{URL}?status=obsolete'))['data']['items']
        assert [(i['id'], i['status'], i['decided_by']) for i in items] == [
            (2, 'obsolete', None)]
        assert body(admin_client.get(f'{URL}?status=all'))['data']['meta']['total'] == 2

    def test_page_sizes(self, admin_client, data):
        for size in (50, 100, 200):
            resp = admin_client.get(f'{URL}?per_page={size}')
            assert resp.status_code == 200
            assert body(resp)['data']['meta']['per_page'] == size
        for size in (150, 0, 25):
            resp = admin_client.get(f'{URL}?per_page={size}')
            assert resp.status_code == 400
            assert body(resp)['code'] == 'validation_error'
        assert body(admin_client.get(URL))['data']['meta']['per_page'] == 50


class TestDecisions:
    def test_obsolete_cannot_be_approved_or_rejected(self, admin_client, data):
        assert admin_client.post(f'{URL}/2/approve').status_code == 409
        assert admin_client.post(f'{URL}/2/reject').status_code == 409
        assert RbCardChange.query.get(2).rbchg_status == 'obsolete'
        assert RbCard.query.one().rbcar_name == 'Alpha Unit'

    def test_bulk_skips_obsolete(self, admin_client, data):
        result = body(admin_client.post(f'{URL}/bulk', json={'ids': [1, 2], 'action': 'reject'}))
        assert result['data']['results'] == [{'id': 1, 'outcome': 'rejected'},
                                             {'id': 2, 'outcome': 'decided'}]
        assert RbCardChange.query.get(2).rbchg_status == 'obsolete'


class TestSync:
    def test_an_obsolete_value_does_not_block_a_new_proposal(self, app, card_images_dir,
                                                             monkeypatch):
        from app.services import riot_sync
        from tests.test_riot_sync import FakeSession
        db.session.add(RbSet(rbset_id='OGN', rbset_name='Origen', rbset_outdat=date(2025, 1, 1)))
        db.session.add(RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='Alpha Unit',
                              rbcar_energy=9))
        db.session.add(RbCardChange(rbchg_rbset_id='OGN', rbchg_rbcar_id='1',
                                    rbchg_field='rbcar_energy', rbchg_old_value='9',
                                    rbchg_new_value='2', rbchg_status='obsolete',
                                    rbchg_detected_at=datetime(2026, 1, 1)))
        db.session.commit()
        parsed = {'rbcar_rbset_id': 'OGN', 'rbcar_id': '1', 'rbcar_name': 'Alpha Unit',
                  'rbcar_domain': None, 'rbcar_type': None, 'rbcar_tags': None,
                  'rbcar_energy': 2, 'rbcar_power': None, 'rbcar_might': None,
                  'rbcar_ability': None, 'rbcar_rarity': None, 'rbcar_artist': None,
                  'image_url': None, 'image': None}
        monkeypatch.setattr(riot_sync, 'fetch_gallery',
                            lambda: {'cards': [parsed], 'set_codes': ['OGN'], 'unparsed': 0})
        monkeypatch.setattr(riot_sync, '_get_session', lambda: FakeSession())
        riot_sync.sync(set_codes=['OGN'], now=datetime(2026, 10, 10))
        pending = RbCardChange.query.filter_by(rbchg_status='pending').all()
        assert [(r.rbchg_field, r.rbchg_new_value) for r in pending] == [('rbcar_energy', '2')]
