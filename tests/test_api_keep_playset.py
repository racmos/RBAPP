"""F3-c S7, S8 (AC5): POST /collection/keep-playset and the playset size preference."""
import pytest

from app import db
from app.models import RbKeepPlayset, RbUserPrefs, User
from tests.collection_write_helpers import BASE, line, seed_catalog

URL = f'{BASE}/keep-playset'
PREFS = '/riftbound/api/v1/me/prefs'


@pytest.fixture
def api(app, authenticated_client, make_user):
    make_user('otheruser')
    with app.app_context():
        seed_catalog()
        db.session.add_all([line('79', 1), line('257', 1, set_id='SFD', condition='EX'),
                            line('79', 3, user='otheruser')])
        db.session.commit()
    return authenticated_client


def keep(api, keep=True, card_id='79', set_id='OGN'):
    return api.post(URL, json={'set_id': set_id, 'card_id': card_id, 'keep': keep})


def marks():
    db.session.expire_all()
    return [(m.rbkps_user_id, m.rbkps_name_key) for m in RbKeepPlayset.query.all()]


class TestKeepPlayset:
    def test_marks_the_name_and_reports_the_shortfall(self, api):
        response = keep(api)
        assert response.status_code == 200
        assert response.get_json()['data'] == {
            'name': 'Jinx, Loose Cannon', 'keep_playset': True, 'kept': 2, 'playset_size': 3,
            'playset_short': True}
        assert [name for _, name in marks()] == ['jinx, loose cannon']

    def test_any_printing_marks_the_same_name(self, api):
        keep(api, card_id='257', set_id='SFD')
        keep(api)
        assert len(marks()) == 1

    def test_is_idempotent(self, api):
        first = keep(api).get_json()['data']
        second = keep(api).get_json()['data']
        assert first == second and len(marks()) == 1

    def test_unmarking_deletes_the_row_and_is_idempotent(self, api):
        keep(api)
        data = keep(api, keep=False).get_json()['data']
        assert (data['keep_playset'], data['playset_short']) == (False, False)
        assert marks() == []
        assert keep(api, keep=False).status_code == 200

    def test_a_complete_playset_is_not_short(self, app, api):
        with app.app_context():
            db.session.add(line('79', 1, condition='MT'))
            db.session.commit()
        assert keep(api).get_json()['data']['playset_short'] is False

    def test_copies_for_sale_do_not_count_as_kept(self, app, api):
        with app.app_context():
            db.session.add(line('79', 4, condition='MT', selling='Y', sell_qty=3))
            db.session.commit()
        data = keep(api).get_json()['data']
        assert (data['kept'], data['playset_short']) == (3, False)    # 1 + 1 + (4 - 3)

    def test_uses_the_users_playset_size(self, app, api):
        user = User.query.filter_by(username='testuser').one()
        db.session.add(RbUserPrefs(rbprf_user_id=user.id, rbprf_playset_size=2))
        db.session.commit()
        data = keep(api).get_json()['data']
        assert (data['playset_size'], data['playset_short']) == (2, False)

    def test_does_not_touch_another_users_marks(self, app, api):
        other = User.query.filter_by(username='otheruser').one()
        db.session.add(RbKeepPlayset(rbkps_user_id=other.id, rbkps_name_key='jinx, loose cannon'))
        db.session.commit()
        keep(api, keep=False)
        assert marks() == [(other.id, 'jinx, loose cannon')]

    def test_unknown_card_and_bad_body(self, api):
        unknown = keep(api, card_id='999')
        assert unknown.status_code == 400
        assert unknown.get_json()['details'][0]['field'] == 'card_id'
        for body in ({}, {'set_id': 'OGN', 'card_id': '79'}, {'set_id': 'OGN', 'card_id': '79',
                                                              'keep': 'yes'}):
            assert api.post(URL, json=body).status_code == 400

    def test_requires_a_session(self, app):
        assert app.test_client().post(URL, json={}).status_code == 401


class TestPlaysetSizePreference:
    def test_default_is_null(self, api):
        assert api.get(PREFS).get_json()['data']['prefs']['playset_size'] is None

    def test_can_be_set_changed_and_reset(self, api):
        patch = lambda value: api.patch(PREFS, json={'playset_size': value})
        assert patch(4).get_json()['data']['prefs']['playset_size'] == 4
        assert api.get(PREFS).get_json()['data']['prefs']['playset_size'] == 4
        assert patch(None).get_json()['data']['prefs']['playset_size'] is None

    def test_other_prefs_keep_their_values(self, api):
        api.patch(PREFS, json={'lang': 'en', 'playset_size': 5})
        prefs = api.patch(PREFS, json={'density': 'comfy'}).get_json()['data']['prefs']
        assert (prefs['lang'], prefs['playset_size'], prefs['density']) == ('en', 5, 'comfy')

    @pytest.mark.parametrize('value, params', [(0, {'min': 1}), (10, {'max': 9}), (-3, {'min': 1})])
    def test_out_of_range_is_refused(self, api, value, params):
        response = api.patch(PREFS, json={'playset_size': value})
        body = response.get_json()
        assert response.status_code == 400
        detail = body['details'][0]
        assert (detail['field'], detail['code']) == ('playset_size', 'out_of_range')
        assert detail['params'] == params

    @pytest.mark.parametrize('value', ['3', 3.5, True, [3]])
    def test_wrong_types_are_refused(self, api, value):
        assert api.patch(PREFS, json={'playset_size': value}).status_code == 400

    def test_the_session_payload_carries_it(self, api):
        api.patch(PREFS, json={'playset_size': 6})
        session = api.get('/riftbound/api/v1/auth/session').get_json()['data']
        assert session['prefs']['playset_size'] == 6
