"""Interface preferences: schema, service and API (PREF-2..5, API-4; unit c of f1-app-shell).

Preferences are account-level; `NULL` / `None` means Auto. The five keys are
`lang`, `density`, `accent`, `bg_intensity` and `collection_view`.
"""
from datetime import timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import RbUserPrefs, User
from app.schemas.validators import PrefsUpdate
from app.services import prefs as prefs_service
from tests.conftest import login_as

API = '/riftbound/api/v1'
KEYS = ['lang', 'density', 'accent', 'bg_intensity', 'collection_view']
ALL_AUTO = {key: None for key in KEYS}

# The domains of PREF-2, written out here on purpose (not imported from the app).
ALLOWED = {
    'lang': ['es', 'en'],
    'density': ['compact', 'regular', 'comfy'],
    'accent': ['cyan', 'orange'],
    'bg_intensity': [0, 1, 50, 99, 100],
    'collection_view': ['table', 'grid'],
}
INVALID = {
    'lang': ['fr', 'EN', '', 'es-ES', 1, True, ['es']],
    'density': ['huge', 'Compact', '', 3, False],
    'accent': ['purple', 'Cyan', '', 7],
    'bg_intensity': [101, -1, 50.5, 50.0, '50', True, False, '', [1], 1000],
    'collection_view': ['list', 'Grid', '', 0],
}
# Model columns by preference key.
COLUMN = {key: f'rbprf_{key}' for key in KEYS}


def make_prefs_row(user_id, **values):
    """Insert a prefs row straight through the ORM (bypasses the service)."""
    row = RbUserPrefs(rbprf_user_id=user_id, **{COLUMN[k]: v for k, v in values.items()})
    db.session.add(row)
    db.session.commit()
    return row


def stored(user_id):
    """The five values stored for `user_id`, read fresh from the database, or None (no row)."""
    db.session.expire_all()
    row = db.session.get(RbUserPrefs, user_id)
    if row is None:
        return None
    return {key: getattr(row, COLUMN[key]) for key in KEYS}


def count_rows():
    return db.session.query(RbUserPrefs).count()


# ---------------------------------------------------------------------------
# 3.11 PrefsUpdate (PREF-2, PREF-4)
# ---------------------------------------------------------------------------

class TestPrefsUpdateSchema:
    @pytest.mark.parametrize('field, value', [
        (field, value) for field, values in ALLOWED.items() for value in values])
    def test_every_allowed_value_passes(self, field, value):
        data = PrefsUpdate(**{field: value})
        assert getattr(data, field) == value
        assert data.model_fields_set == {field}

    @pytest.mark.parametrize('field, value', [
        (field, value) for field, values in INVALID.items() for value in values])
    def test_invalid_values_fail_naming_the_field(self, field, value):
        with pytest.raises(ValidationError) as err:
            PrefsUpdate(**{field: value})
        assert [e['loc'] for e in err.value.errors()] == [(field,)]

    @pytest.mark.parametrize('field', KEYS)
    def test_none_is_allowed_for_every_field_and_counts_as_present(self, field):
        data = PrefsUpdate(**{field: None})
        assert getattr(data, field) is None
        assert data.model_fields_set == {field}

    def test_an_empty_object_is_valid_and_sets_nothing(self):
        data = PrefsUpdate()
        assert data.model_fields_set == set()
        assert data.model_dump(include=data.model_fields_set) == {}

    def test_unknown_fields_are_ignored_and_never_present(self):
        data = PrefsUpdate(accent='cyan', is_admin=True, theme='light')
        assert data.model_fields_set == {'accent'}
        assert data.model_dump(include=data.model_fields_set) == {'accent': 'cyan'}
        assert not hasattr(data, 'is_admin')

    def test_only_the_keys_that_were_sent_are_reported_present(self):
        data = PrefsUpdate(lang='en', density=None)
        assert data.model_fields_set == {'lang', 'density'}
        assert data.model_dump(include=data.model_fields_set) == {'lang': 'en', 'density': None}

    def test_one_bad_field_fails_the_whole_object(self):
        with pytest.raises(ValidationError):
            PrefsUpdate(lang='en', density='huge')


class TestDomainParity:
    """PREF-2: the schema and the model CHECKs agree on every value."""

    @pytest.fixture(autouse=True)
    def a_user(self, app, make_user):
        self.uid = make_user('alice').id

    @pytest.mark.parametrize('field, value', [
        (field, value) for field, values in ALLOWED.items() for value in values])
    def test_allowed_values_pass_both_layers(self, field, value):
        PrefsUpdate(**{field: value})
        make_prefs_row(self.uid, **{field: value})
        assert stored(self.uid)[field] == value

    @pytest.mark.parametrize('field, value', [
        ('lang', 'fr'), ('lang', 'EN'), ('lang', ''), ('lang', 'es-ES'),
        ('density', 'huge'), ('density', 'Compact'), ('density', ''),
        ('accent', 'purple'), ('accent', 'Cyan'), ('accent', ''),
        ('bg_intensity', 101), ('bg_intensity', -1), ('bg_intensity', 1000),
        ('collection_view', 'list'), ('collection_view', 'Grid'), ('collection_view', ''),
    ])
    def test_invalid_values_are_refused_by_both_layers(self, field, value):
        with pytest.raises(ValidationError):
            PrefsUpdate(**{field: value})
        with pytest.raises(IntegrityError):
            make_prefs_row(self.uid, **{field: value})
        db.session.rollback()
        assert stored(self.uid) is None


# ---------------------------------------------------------------------------
# 3.13 Service (D7)
# ---------------------------------------------------------------------------

class TestPrefsService:
    @pytest.fixture(autouse=True)
    def a_user(self, app, make_user):
        self.uid = make_user('alice').id        # plain ints: sessions get expunged
        self.oid = make_user('bob').id

    def test_get_prefs_without_a_row_is_five_nones_and_inserts_nothing(self):
        assert prefs_service.get_prefs(self.uid) == ALL_AUTO
        assert list(prefs_service.get_prefs(self.uid)) == KEYS
        assert count_rows() == 0

    def test_get_prefs_returns_the_stored_values(self):
        make_prefs_row(self.uid, lang='en', bg_intensity=40)
        assert prefs_service.get_prefs(self.uid) == {
            **ALL_AUTO, 'lang': 'en', 'bg_intensity': 40}

    def test_get_prefs_is_per_user(self):
        make_prefs_row(self.uid, accent='cyan')
        assert prefs_service.get_prefs(self.oid) == ALL_AUTO

    def test_the_first_update_creates_the_row(self):
        assert count_rows() == 0
        result = prefs_service.update_prefs(self.uid, {'accent': 'cyan'})
        assert result == {**ALL_AUTO, 'accent': 'cyan'}
        assert count_rows() == 1
        assert stored(self.uid) == result

    def test_update_changes_only_the_given_keys(self):
        make_prefs_row(self.uid, lang='en', accent='cyan', density='comfy')
        result = prefs_service.update_prefs(self.uid, {'density': 'compact'})
        assert result == {**ALL_AUTO, 'lang': 'en', 'accent': 'cyan', 'density': 'compact'}
        assert stored(self.uid) == result

    def test_none_resets_a_key_to_auto(self):
        make_prefs_row(self.uid, lang='en', density='comfy')
        result = prefs_service.update_prefs(self.uid, {'density': None})
        assert result == {**ALL_AUTO, 'lang': 'en'}
        assert stored(self.uid)['density'] is None

    def test_an_empty_change_creates_no_row(self):
        assert prefs_service.update_prefs(self.uid, {}) == ALL_AUTO
        assert count_rows() == 0

    def test_an_empty_change_leaves_an_existing_row_untouched(self, frozen_clock):
        make_prefs_row(self.uid, lang='en')
        frozen_clock.advance(hours=1)
        assert prefs_service.update_prefs(self.uid, {}) == {**ALL_AUTO, 'lang': 'en'}
        assert stored(self.uid)['lang'] == 'en'

    def test_unknown_keys_are_not_persisted(self):
        result = prefs_service.update_prefs(self.uid, {'accent': 'cyan', 'is_admin': True})
        assert result == {**ALL_AUTO, 'accent': 'cyan'}
        assert 'is_admin' not in result

    def test_update_refreshes_the_timestamp_on_create_and_on_update(self, frozen_clock):
        prefs_service.update_prefs(self.uid, {'lang': 'es'})
        db.session.expire_all()
        created = db.session.get(RbUserPrefs, self.uid).rbprf_updated_at
        assert created == frozen_clock.now
        frozen_clock.advance(minutes=5)
        prefs_service.update_prefs(self.uid, {'lang': 'en'})
        db.session.expire_all()
        updated = db.session.get(RbUserPrefs, self.uid).rbprf_updated_at
        assert updated == created + timedelta(minutes=5)

    def test_users_do_not_share_rows(self):
        prefs_service.update_prefs(self.uid, {'lang': 'en'})
        prefs_service.update_prefs(self.oid, {'lang': 'es'})
        assert stored(self.uid)['lang'] == 'en'
        assert stored(self.oid)['lang'] == 'es'

    def _lose_the_first_race(self, monkeypatch, always=False):
        """Make the service believe there is no row although another request just
        inserted one: its INSERT then collides with the primary key."""
        db.session.execute(db.text(
            'INSERT INTO riftbound.rbuserprefs (rbprf_user_id, rbprf_lang, rbprf_updated_at)'
            " VALUES (:id, 'en', '2030-01-01 00:00:00')"), {'id': self.uid})
        db.session.commit()
        db.session.expunge_all()
        real_get = db.session.get
        calls = []

        def blind_get(entity, ident, *args, **kwargs):
            calls.append(ident)
            if always or len(calls) == 1:
                return None
            return real_get(entity, ident, *args, **kwargs)

        monkeypatch.setattr(db.session, 'get', blind_get)
        return calls

    def test_a_lost_first_insert_race_is_retried_once_as_an_update(self, monkeypatch):
        calls = self._lose_the_first_race(monkeypatch)
        result = prefs_service.update_prefs(self.uid, {'density': 'compact'})
        assert result == {**ALL_AUTO, 'lang': 'en', 'density': 'compact'}
        assert len(calls) == 2                       # the miss, then the retry
        monkeypatch.undo()
        assert stored(self.uid) == result
        assert count_rows() == 1

    def test_if_the_retry_finds_no_row_either_the_error_surfaces(self, monkeypatch):
        self._lose_the_first_race(monkeypatch, always=True)
        with pytest.raises(IntegrityError):
            prefs_service.update_prefs(self.uid, {'density': 'compact'})
        monkeypatch.undo()
        db.session.rollback()
        assert stored(self.uid)['density'] is None       # nothing half-written


# ---------------------------------------------------------------------------
# 3.26 GET /me/prefs (PREF-3)
# ---------------------------------------------------------------------------

def get_prefs_body(client, **kwargs):
    return client.get(f'{API}/me/prefs', **kwargs)


def patch(client, body, **headers):
    return client.patch(f'{API}/me/prefs', json=body, headers=headers)


def prefs_of(resp):
    return resp.get_json()['data']['prefs']


class TestGetPrefs:
    def test_defaults_are_five_nulls_and_no_row_is_created(self, client, make_user):
        make_user('alice')
        login_as(client, 'alice')
        resp = get_prefs_body(client)
        assert resp.status_code == 200
        assert resp.get_json() == {'success': True, 'data': {'prefs': ALL_AUTO}}
        assert set(prefs_of(resp)) == set(KEYS)           # JSON key order is not meaningful
        assert count_rows() == 0

    def test_returns_exactly_the_stored_values(self, client, make_user):
        user = make_user('alice')
        make_prefs_row(user.id, lang='en', accent='cyan', bg_intensity=0, collection_view='grid',
                       density='comfy')
        login_as(client, 'alice')
        assert prefs_of(get_prefs_body(client)) == {
            'lang': 'en', 'density': 'comfy', 'accent': 'cyan', 'bg_intensity': 0,
            'collection_view': 'grid'}

    def test_anonymous_is_a_json_401_with_the_unauthenticated_code(self, client):
        resp = get_prefs_body(client)
        body = resp.get_json()
        assert resp.status_code == 401
        assert 'Location' not in resp.headers
        assert (body['success'], body['error'], body['code']) == (
            False, 'Unauthorized', 'unauthenticated')

    def test_anonymous_with_a_browser_accept_is_still_json(self, client):
        resp = get_prefs_body(client, headers={'Accept': 'text/html'})
        assert resp.status_code == 401 and resp.is_json

    def test_each_user_sees_only_their_own(self, app, make_user):
        alice, bob = make_user('alice'), make_user('bob')
        make_prefs_row(alice.id, lang='en')
        make_prefs_row(bob.id, lang='es', accent='cyan')
        one, two = app.test_client(), app.test_client()
        login_as(one, 'alice')
        login_as(two, 'bob')
        assert prefs_of(get_prefs_body(one)) == {**ALL_AUTO, 'lang': 'en'}
        assert prefs_of(get_prefs_body(two)) == {**ALL_AUTO, 'lang': 'es', 'accent': 'cyan'}

    def test_post_is_not_allowed(self, client, make_user):
        make_user('alice')
        login_as(client, 'alice')
        resp = client.post(f'{API}/me/prefs', json={})
        assert resp.status_code == 405 and resp.is_json


# ---------------------------------------------------------------------------
# 3.27 PATCH /me/prefs (PREF-4)
# ---------------------------------------------------------------------------

@pytest.fixture
def alice(app, make_user, client):
    """A logged-in user: (client, user id)."""
    user = make_user('alice')
    login_as(client, 'alice')
    return client, user.id


class TestPatchPrefs:
    def test_a_partial_update_keeps_the_other_fields(self, alice):
        client, uid = alice
        make_prefs_row(uid, lang='en', accent='cyan')
        resp = patch(client, {'density': 'compact'})
        assert resp.status_code == 200
        assert prefs_of(resp) == {**ALL_AUTO, 'lang': 'en', 'accent': 'cyan',
                                  'density': 'compact'}
        assert prefs_of(get_prefs_body(client)) == prefs_of(resp)

    def test_null_resets_to_auto_and_leaves_the_rest(self, alice):
        client, uid = alice
        make_prefs_row(uid, density='comfy', lang='en')
        resp = patch(client, {'density': None})
        assert prefs_of(resp) == {**ALL_AUTO, 'lang': 'en'}
        assert prefs_of(get_prefs_body(client)) == {**ALL_AUTO, 'lang': 'en'}

    def test_the_first_write_creates_the_row(self, alice):
        client, uid = alice
        assert count_rows() == 0
        assert prefs_of(patch(client, {'bg_intensity': 0})) == {**ALL_AUTO, 'bg_intensity': 0}
        assert count_rows() == 1
        assert stored(uid)['bg_intensity'] == 0

    def test_every_field_can_be_set_in_one_request(self, alice):
        client, uid = alice
        body = {'lang': 'en', 'density': 'regular', 'accent': 'cyan', 'bg_intensity': 100,
                'collection_view': 'grid'}
        assert prefs_of(patch(client, body)) == body
        assert stored(uid) == body

    @pytest.mark.parametrize('body, field', [
        ({'bg_intensity': 101}, 'bg_intensity'),
        ({'bg_intensity': -1}, 'bg_intensity'),
        ({'accent': 'purple'}, 'accent'),
        ({'bg_intensity': 50.5}, 'bg_intensity'),
        ({'bg_intensity': True}, 'bg_intensity'),
        ({'bg_intensity': '50'}, 'bg_intensity'),
        ({'lang': 'fr'}, 'lang'),
        ({'density': 'huge'}, 'density'),
        ({'collection_view': 'list'}, 'collection_view'),
    ])
    def test_invalid_values_are_a_400_naming_the_field_and_change_nothing(
            self, alice, body, field):
        client, uid = alice
        make_prefs_row(uid, lang='en', accent='cyan', bg_intensity=40)
        before = stored(uid)
        resp = patch(client, body)
        payload = resp.get_json()
        assert resp.status_code == 400
        assert (payload['error'], payload['code']) == ('Validation Error', 'validation_error')
        assert [d['field'] for d in payload['details']] == [field]
        assert stored(uid) == before

    def test_an_invalid_value_on_a_user_without_a_row_creates_none(self, alice):
        client, _uid = alice
        assert patch(client, {'bg_intensity': 101}).status_code == 400
        assert count_rows() == 0

    def test_out_of_range_reports_code_and_bound(self, alice):
        client, _uid = alice
        [detail] = patch(client, {'bg_intensity': 101}).get_json()['details']
        assert (detail['code'], detail['params']) == ('out_of_range', {'max': 100})

    def test_a_request_is_all_or_nothing(self, alice):
        client, uid = alice
        make_prefs_row(uid, lang='es')
        resp = patch(client, {'lang': 'en', 'density': 'huge'})
        assert resp.status_code == 400
        assert [d['field'] for d in resp.get_json()['details']] == ['density']
        assert stored(uid)['lang'] == 'es'

    def test_an_empty_object_is_a_200_and_creates_no_row(self, alice):
        client, _uid = alice
        resp = patch(client, {})
        assert resp.status_code == 200
        assert prefs_of(resp) == ALL_AUTO
        assert count_rows() == 0

    def test_an_empty_object_changes_nothing_when_a_row_exists(self, alice):
        client, uid = alice
        make_prefs_row(uid, lang='en')
        assert prefs_of(patch(client, {})) == {**ALL_AUTO, 'lang': 'en'}

    def test_unknown_fields_are_ignored_never_stored_and_never_a_500(self, alice):
        client, uid = alice
        resp = patch(client, {'accent': 'cyan', 'theme': 'light', 'is_admin': True,
                              'rbprf_user_id': 999})
        assert resp.status_code == 200
        assert prefs_of(resp) == {**ALL_AUTO, 'accent': 'cyan'}
        assert stored(uid) == {**ALL_AUTO, 'accent': 'cyan'}
        assert db.session.get(RbUserPrefs, 999) is None
        assert User.query.get(uid).is_admin is False

    def test_only_unknown_fields_is_a_200_that_changes_nothing(self, alice):
        client, _uid = alice
        resp = patch(client, {'theme': 'light'})
        assert resp.status_code == 200 and prefs_of(resp) == ALL_AUTO
        assert count_rows() == 0

    @pytest.mark.parametrize('kwargs', [
        {'data': 'accent=cyan', 'content_type': 'application/x-www-form-urlencoded'},
        {'data': 'not json', 'content_type': 'text/plain'},
    ])
    def test_a_non_json_body_is_a_400(self, alice, kwargs):
        client, uid = alice
        resp = client.patch(f'{API}/me/prefs', **kwargs)
        assert resp.status_code == 400 and resp.is_json
        assert resp.get_json()['success'] is False
        assert stored(uid) is None

    def test_a_json_array_body_is_a_400(self, alice):
        client, _uid = alice
        resp = patch(client, ['accent'])
        assert resp.status_code == 400 and resp.is_json

    def test_success_refreshes_updated_at(self, alice, frozen_clock):
        client, uid = alice
        patch(client, {'lang': 'es'})
        db.session.expire_all()
        first = db.session.get(RbUserPrefs, uid).rbprf_updated_at
        assert first == frozen_clock.now
        frozen_clock.advance(minutes=3)
        patch(client, {'lang': 'en'})
        db.session.expire_all()
        assert db.session.get(RbUserPrefs, uid).rbprf_updated_at == first + timedelta(minutes=3)

    def test_anonymous_is_a_json_401_and_writes_nothing(self, client):
        resp = patch(client, {'accent': 'cyan'})
        assert resp.status_code == 401
        assert resp.get_json()['code'] == 'unauthenticated'
        assert count_rows() == 0

    def test_a_user_cannot_touch_another_users_row(self, app, make_user):
        alice_, bob = make_user('alice'), make_user('bob')
        make_prefs_row(bob.id, lang='es')
        client = app.test_client()
        login_as(client, 'alice')
        patch(client, {'lang': 'en', 'rbprf_user_id': bob.id})
        assert stored(bob.id)['lang'] == 'es'
        assert stored(alice_.id)['lang'] == 'en'

    def test_get_is_not_changed_by_a_failed_patch(self, alice):
        client, _uid = alice
        patch(client, {'lang': 'en'})
        patch(client, {'lang': 'xx'})
        assert prefs_of(get_prefs_body(client))['lang'] == 'en'


# ---------------------------------------------------------------------------
# 3.28 CSRF (PREF-4)
# ---------------------------------------------------------------------------

class TestPatchCsrf:
    def test_without_a_token_it_is_a_400_csrf_invalid_and_nothing_is_stored(
            self, app, client, make_user):
        uid = make_user('alice').id
        login_as(client, 'alice')
        app.config['WTF_CSRF_ENABLED'] = True
        try:
            resp = patch(client, {'accent': 'cyan'})
            body = resp.get_json()
            assert resp.status_code == 400
            assert (body['error'], body['code']) == ('CSRF Error', 'csrf_invalid')
            assert stored(uid) is None
            token = client.get(f'{API}/auth/session').get_json()['data']['csrf_token']
            ok = patch(client, {'accent': 'cyan'}, **{'X-CSRFToken': token})
            assert ok.status_code == 200
            assert prefs_of(ok)['accent'] == 'cyan'
        finally:
            app.config['WTF_CSRF_ENABLED'] = False

    def test_anonymous_with_a_token_is_a_json_401(self, csrf_app, client):
        token = client.get(f'{API}/auth/session').get_json()['data']['csrf_token']
        resp = patch(client, {'accent': 'cyan'}, **{'X-CSRFToken': token})
        assert resp.status_code == 401
        assert resp.get_json()['code'] == 'unauthenticated'

    def test_get_needs_no_token(self, app, client, make_user):
        make_user('alice')
        login_as(client, 'alice')
        app.config['WTF_CSRF_ENABLED'] = True
        try:
            assert get_prefs_body(client).status_code == 200
        finally:
            app.config['WTF_CSRF_ENABLED'] = False


# ---------------------------------------------------------------------------
# 3.29 Session carries prefs (API-4, PREF-5)
# ---------------------------------------------------------------------------

def session_data(client):
    return client.get(f'{API}/auth/session').get_json()['data']


class TestSessionPrefs:
    def test_anonymous_has_no_prefs_key(self, client):
        data = session_data(client)
        assert data['authenticated'] is False
        assert 'prefs' not in data
        assert set(data) == {'authenticated', 'csrf_token'}

    def test_logged_in_user_keeps_exactly_its_four_fields(self, alice):
        client, uid = alice
        data = session_data(client)
        assert set(data['user']) == {'id', 'username', 'email', 'is_admin'}
        assert data['user']['id'] == uid
        assert set(data) == {'authenticated', 'user', 'prefs', 'csrf_token'}

    def test_prefs_without_a_row_are_five_nulls_and_no_row_exists_afterwards(self, alice):
        client, _uid = alice
        assert session_data(client)['prefs'] == ALL_AUTO
        assert set(session_data(client)['prefs']) == set(KEYS)
        assert count_rows() == 0

    def test_stored_values_come_back(self, alice):
        client, uid = alice
        make_prefs_row(uid, lang='en', bg_intensity=40)
        assert session_data(client)['prefs'] == {**ALL_AUTO, 'lang': 'en', 'bg_intensity': 40}

    def test_after_a_patch_the_session_shows_the_new_value(self, alice):
        client, _uid = alice
        assert session_data(client)['prefs']['accent'] is None
        patch(client, {'accent': 'cyan'})
        assert session_data(client)['prefs']['accent'] == 'cyan'
        patch(client, {'accent': None})
        assert session_data(client)['prefs']['accent'] is None

    def test_a_blocked_user_is_anonymous_without_prefs(self, alice):
        client, uid = alice
        make_prefs_row(uid, lang='en')
        user = db.session.get(User, uid)
        user.is_blocked = True
        db.session.commit()
        data = session_data(client)
        assert data['authenticated'] is False and 'prefs' not in data

    def test_the_login_response_does_not_carry_prefs(self, client, make_user):
        make_user('alice', password='Passw0rd!x')
        body = client.post(f'{API}/auth/login', json={
            'username': 'alice', 'password': 'Passw0rd!x'}).get_json()
        assert set(body['data']) == {'user'}
