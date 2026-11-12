"""F11-f (D-F11-9): the preferences payload has five keys; `lang` is gone (the app is
English-only, column `rbprf_lang` dropped by 0028). An old client that still sends `lang` is
not refused: the key is ignored like any unknown key and nothing is stored."""
from app.models import RbUserPrefs

API = '/riftbound/api/v1'
PREFS = f'{API}/me/prefs'
KEYS = {'density', 'accent', 'bg_intensity', 'collection_view', 'playset_size'}


def _prefs(response):
    assert response.status_code == 200, response.get_json()
    return response.get_json()['data']['prefs']


def test_get_me_prefs_has_the_five_keys(authenticated_client):
    assert _prefs(authenticated_client.get(PREFS)) == dict.fromkeys(KEYS)


def test_the_session_prefs_have_the_five_keys(authenticated_client):
    assert set(_prefs(authenticated_client.get(f'{API}/auth/session'))) == KEYS


def test_patch_returns_the_five_keys(authenticated_client):
    prefs = _prefs(authenticated_client.patch(PREFS, json={'density': 'comfy'}))
    assert prefs == {**dict.fromkeys(KEYS), 'density': 'comfy'}


def test_lang_from_an_old_client_is_ignored_not_refused(app, authenticated_client):
    prefs = _prefs(authenticated_client.patch(PREFS, json={'lang': 'es'}))
    assert prefs == dict.fromkeys(KEYS)
    with app.app_context():
        assert RbUserPrefs.query.count() == 0           # nothing to store, no row
    prefs = _prefs(authenticated_client.patch(PREFS, json={'lang': 'xx', 'accent': 'cyan'}))
    assert prefs == {**dict.fromkeys(KEYS), 'accent': 'cyan'}
    assert _prefs(authenticated_client.get(PREFS)) == prefs
