"""
Access control (unit c, specs ACL-1..ACL-4).

Part 1: admin flag and blocked accounts (ACL-1, ACL-2).
Part 2: admin guard on the catalog and price routes, hidden admin UI (ACL-3, ACL-4).
"""
import pytest

from app import db
from app.models import RbSet, RbCard, User
from tests.conftest import DEFAULT_PASSWORD, login_as


def flashes(client):
    """The flash messages waiting in the client's session."""
    with client.session_transaction() as sess:
        return [message for _category, message in sess.get('_flashes', [])]


def is_logged_in(client):
    """True if the session still opens the dashboard."""
    resp = client.get('/riftbound/')
    return resp.status_code == 200


# ---------------------------------------------------------------------------
# ACL-1 no self-promotion
# ---------------------------------------------------------------------------

class TestNoSelfPromotion:
    def test_register_form_with_is_admin_creates_a_plain_user(self, app, client):
        resp = client.post('/riftbound/register', data={
            'username': 'mallory', 'email': 'mallory@test.com',
            'password': 'longenough1', 'is_admin': 'true', 'is_blocked': 'false',
        })
        assert resp.status_code == 302
        user = User.query.filter_by(username='mallory').one()
        assert user.is_admin is False
        assert user.is_blocked is False

    def test_register_json_with_is_admin_never_creates_an_admin(self, app, client):
        client.post('/riftbound/register', json={
            'username': 'mallory2', 'email': 'mallory2@test.com',
            'password': 'longenough1', 'is_admin': True,
        })
        assert User.query.filter_by(is_admin=True).count() == 0

    def test_new_users_default_to_not_admin_and_not_blocked(self, app, make_user):
        user = make_user('plain')
        db.session.refresh(user)
        assert (user.is_admin, user.is_blocked, user.is_active) == (False, False, True)


# ---------------------------------------------------------------------------
# ACL-2 blocked accounts lose access
# ---------------------------------------------------------------------------

class TestBlockedAccounts:
    def test_existing_session_is_cut_on_the_next_request(self, app, make_user):
        make_user('victim')
        client = login_as(app.test_client(), 'victim')
        assert is_logged_in(client)                      # proves the session worked

        user = User.query.filter_by(username='victim').one()
        user.is_blocked = True
        db.session.commit()

        resp = client.get('/riftbound/')
        assert resp.status_code == 302
        assert resp.headers['Location'].startswith('/riftbound/login')

    def test_unblocking_restores_access_without_a_new_login(self, app, make_user):
        make_user('victim')
        client = login_as(app.test_client(), 'victim')
        user = User.query.filter_by(username='victim').one()
        user.is_blocked = True
        db.session.commit()
        assert client.get('/riftbound/').status_code == 302
        user.is_blocked = False
        db.session.commit()
        assert client.get('/riftbound/').status_code == 200

    def test_blocked_user_with_the_correct_password_gets_no_session(self, app, make_user):
        make_user('victim', is_blocked=True)
        client = app.test_client()
        resp = client.post('/riftbound/login', data={
            'username': 'victim', 'password': DEFAULT_PASSWORD})
        assert resp.status_code == 302
        assert not is_logged_in(client)

    def test_blocked_response_equals_the_wrong_password_response(self, app, make_user):
        make_user('victim', is_blocked=True)
        make_user('normal')

        blocked = app.test_client()
        blocked_resp = blocked.post('/riftbound/login', data={
            'username': 'victim', 'password': DEFAULT_PASSWORD})
        wrong = app.test_client()
        wrong_resp = wrong.post('/riftbound/login', data={
            'username': 'normal', 'password': 'not-the-password'})

        assert blocked_resp.status_code == wrong_resp.status_code == 302
        assert blocked_resp.headers['Location'] == wrong_resp.headers['Location']
        assert flashes(blocked) == flashes(wrong) == ['Invalid username or password']

    def test_active_user_still_logs_in(self, app, make_user):
        make_user('normal')
        client = app.test_client()
        resp = client.post('/riftbound/login', data={
            'username': 'normal', 'password': DEFAULT_PASSWORD})
        assert resp.status_code == 302
        assert is_logged_in(client)


# ---------------------------------------------------------------------------
# ACL-3 admin guard on the catalog and price routes
# ---------------------------------------------------------------------------

NEW_SET = {'rbset_id': 'NEW1', 'rbset_name': 'Brand New Set', 'rbset_ncard': 10}
NEW_CARD = {'rbcar_rbset_id': 'TEST1', 'rbcar_id': '777', 'rbcar_name': 'Fresh Card'}


@pytest.fixture
def catalog(app):
    """One set and one card (TEST1 / 001) so update routes have a target."""
    db.session.add(RbSet(rbset_id='TEST1', rbset_name='Test Set 1', rbset_ncard=100))
    db.session.add(RbCard(rbcar_rbset_id='TEST1', rbcar_id='001', rbcar_name='Test Card'))
    db.session.commit()


def catalog_state():
    return (sorted((s.rbset_id, s.rbset_name, s.rbset_ncard) for s in RbSet.query.all()),
            sorted((c.rbcar_rbset_id, c.rbcar_id, c.rbcar_name) for c in RbCard.query.all()))


CATALOG_WRITES = [
    ('set/add', NEW_SET),
    ('set/update/TEST1', {'rbset_name': 'Hijacked'}),
    ('card/add', NEW_CARD),
    ('card/update/TEST1/001', {'rbcar_name': 'Hijacked'}),
]


class TestNonAdminCannotChangeTheCatalog:
    @pytest.mark.parametrize('path, body', CATALOG_WRITES)
    def test_valid_json_is_refused_with_403_and_nothing_changes(
            self, catalog, authenticated_client, path, body):
        before = catalog_state()
        resp = authenticated_client.post(f'/riftbound/{path}', json=body)
        assert resp.status_code == 403
        assert resp.json == {
            'success': False, 'error': 'Forbidden',
            'message': 'You do not have permission to access this resource'}
        assert catalog_state() == before

    def test_image_upload_is_refused_and_writes_nothing(
            self, catalog, authenticated_client, tmp_path, monkeypatch):
        import io
        monkeypatch.chdir(tmp_path)
        resp = authenticated_client.post(
            '/riftbound/card/upload_image', content_type='multipart/form-data',
            data={'set_id': 'ogn', 'image': (io.BytesIO(b'png-bytes'), 'x.png')})
        assert resp.status_code == 403
        assert list(tmp_path.rglob('x.png')) == []

    def test_html_clients_get_the_403_page(self, catalog, authenticated_client):
        resp = authenticated_client.post('/riftbound/set/add', data={'rbset_id': 'A'})
        assert resp.status_code == 403
        assert b'<html' in resp.data.lower()

    @pytest.mark.parametrize('path, body', CATALOG_WRITES)
    def test_anonymous_callers_are_sent_to_login_not_403(self, catalog, client, path, body):
        resp = client.post(f'/riftbound/{path}', json=body)
        assert resp.status_code == 302
        assert resp.headers['Location'].startswith('/riftbound/login')


class TestAdminCanChangeTheCatalog:
    def test_admin_adds_a_set(self, catalog, admin_client):
        resp = admin_client.post('/riftbound/set/add', json=NEW_SET)
        assert resp.status_code == 200
        assert resp.json == {'success': True}
        assert RbSet.query.get('NEW1').rbset_name == 'Brand New Set'

    def test_admin_updates_a_set(self, catalog, admin_client):
        resp = admin_client.post('/riftbound/set/update/TEST1', json={'rbset_name': 'Renamed'})
        assert resp.status_code == 200
        assert RbSet.query.get('TEST1').rbset_name == 'Renamed'

    def test_admin_adds_and_updates_a_card(self, catalog, admin_client):
        assert admin_client.post('/riftbound/card/add', json=NEW_CARD).status_code == 200
        assert RbCard.query.get(('TEST1', '777')).rbcar_name == 'Fresh Card'
        resp = admin_client.post('/riftbound/card/update/TEST1/001', json={'rbcar_name': 'Renamed'})
        assert resp.status_code == 200
        assert RbCard.query.get(('TEST1', '001')).rbcar_name == 'Renamed'

    def test_admin_reaches_the_upload_handler(self, catalog, admin_client):
        resp = admin_client.post('/riftbound/card/upload_image', data={'set_id': 'ogn'})
        assert resp.status_code == 400            # past the guard: "No file uploaded"
        assert resp.json['message'] == 'No file uploaded'


class TestPriceRoutesAreAdminOnly:
    @staticmethod
    def price_rules(app):
        rules = [r for r in app.url_map.iter_rules() if r.endpoint.startswith('price.')]
        assert len(rules) == 23
        return rules

    @staticmethod
    def request(client, rule, **kwargs):
        import re
        url = re.sub(r'<[^>]+>', 'x', rule.rule)
        method = 'GET' if 'GET' in rule.methods else 'POST'
        return client.open(url, method=method, **kwargs)

    def test_every_price_rule_gives_403_and_makes_no_outbound_request(
            self, app, authenticated_client, monkeypatch):
        import requests
        calls = []
        monkeypatch.setattr(requests.Session, 'request',
                            lambda self, *a, **k: calls.append(a) or (_ for _ in ()).throw(
                                requests.ConnectionError('blocked')))
        for rule in self.price_rules(app):
            resp = self.request(authenticated_client, rule, json={})
            assert resp.status_code == 403, rule.rule
            assert resp.json['error'] == 'Forbidden', rule.rule
        assert calls == []

    def test_cardmarket_load_is_refused_before_any_download(
            self, app, authenticated_client, monkeypatch):
        from app.services import cardmarket_loader
        downloads = []
        monkeypatch.setattr(cardmarket_loader.requests, 'get',
                            lambda *a, **k: downloads.append(a))
        resp = authenticated_client.post('/riftbound/price/cardmarket-load', json={})
        assert resp.status_code == 403
        assert downloads == []

    def test_an_admin_is_let_in(self, app, admin_client):
        assert admin_client.get('/riftbound/price').status_code == 200


# ---------------------------------------------------------------------------
# ACL-4 the catalog stays readable; the admin UI is hidden
# ---------------------------------------------------------------------------

ADMIN_MARKERS = {
    '/riftbound/set': ['Add New Set', 'onclick="openEditModal(', 'id="addModal"',
                       'id="editForm"'],
    '/riftbound/card': ['Add New Card', 'onclick="openEditModal(', 'id="addModal"',
                        'id="editModal"', 'Upload Image', 'Upload New Image'],
    '/riftbound/': ['/riftbound/price', 'Generate Prices'],
}


class TestCatalogReadableAdminUiHidden:
    @pytest.mark.parametrize('path', ['/riftbound/set', '/riftbound/card', '/riftbound/'])
    def test_non_admin_pages_render(self, catalog, authenticated_client, path):
        assert authenticated_client.get(path).status_code == 200

    @pytest.mark.parametrize('path', list(ADMIN_MARKERS))
    def test_non_admin_html_has_no_admin_controls_and_no_price_link(
            self, catalog, authenticated_client, path):
        html = authenticated_client.get(path).get_data(as_text=True)
        assert 'Test Set 1' in html or 'Test Card' in html or 'Dashboard' in html  # real page
        for marker in ADMIN_MARKERS[path]:
            assert marker not in html, marker
        assert '/riftbound/price' not in html

    @pytest.mark.parametrize('path', list(ADMIN_MARKERS))
    def test_admin_html_has_the_controls_and_the_price_link(
            self, catalog, admin_client, path):
        html = admin_client.get(path).get_data(as_text=True)
        for marker in ADMIN_MARKERS[path]:
            assert marker in html, marker
        assert '/riftbound/price' in html          # nav link on every page

    def test_the_price_link_is_in_the_navigation_for_admins_only(
            self, catalog, authenticated_client, admin_client):
        assert 'href="/riftbound/price"' not in authenticated_client.get('/riftbound/profile').get_data(as_text=True)
        assert 'href="/riftbound/price"' in admin_client.get('/riftbound/profile').get_data(as_text=True)


class TestAdminScriptsOnlyForAdmins:
    """The page script must not reach for elements that only admins get, or it
    would throw for everybody else and stop the rest of the page's script."""

    LISTENERS = {
        '/riftbound/set': ["getElementById('addForm').addEventListener",
                           "getElementById('editForm').addEventListener"],
        '/riftbound/card': ["getElementById('addForm').addEventListener",
                            "getElementById('editForm').addEventListener",
                            "getElementById('add_rbcar_domain_selector').addEventListener",
                            "getElementById('edit_rbcar_domain_selector').addEventListener"],
    }

    @pytest.mark.parametrize('path', list(LISTENERS))
    def test_non_admin_pages_have_no_listeners_on_admin_only_forms(
            self, catalog, authenticated_client, path):
        html = authenticated_client.get(path).get_data(as_text=True)
        for listener in self.LISTENERS[path]:
            assert listener not in html, listener
        # the rest of the page script is still there
        assert '<script>' in html

    @pytest.mark.parametrize('path', list(LISTENERS))
    def test_admin_pages_keep_them(self, catalog, admin_client, path):
        html = admin_client.get(path).get_data(as_text=True)
        for listener in self.LISTENERS[path]:
            assert listener in html, listener
