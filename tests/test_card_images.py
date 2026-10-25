"""Card images in a data directory (M-d, S1-S5).

Every test points CARD_IMAGES_DIR at a temporary directory: nothing here reads
or writes the repository's images. `secret.txt` sits NEXT TO the images root,
so a traversal that worked would hand it out.
"""
import io
import os
from pathlib import Path

import pytest
import requests

from app import create_app
from app.models import RbCard
from app.services import riot_scraper
from app.services.card_images import card_image_path
from config import ConfigError

PNG = b'\x89PNG\r\n\x1a\n' + b'card-image-bytes' * 8
SECRET = b'TOP-SECRET-OUTSIDE-THE-IMAGES-ROOT'
CARDS_URL = '/riftbound/static/images/cards'
STATIC_DIR = Path(__file__).resolve().parent.parent / 'app' / 'static'


@pytest.fixture
def images_root(app, tmp_path):
    """`app` reading and writing card images in `tmp_path/card-images`."""
    root = tmp_path / 'card-images'
    root.mkdir()
    (tmp_path / 'secret.txt').write_bytes(SECRET)
    app.config['CARD_IMAGES_DIR'] = str(root)
    return root


@pytest.fixture
def no_network(monkeypatch):
    def refuse(self, method, url, *args, **kwargs):
        raise requests.ConnectionError('network disabled in tests')
    monkeypatch.setattr(requests.Session, 'request', refuse)


def _app_from_env(clean_env, value=None):
    clean_env.setenv('RB_ENV', 'testing')
    if value is not None:
        clean_env.setenv('CARD_IMAGES_DIR', value)
    return create_app(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
                      SECRET_KEY='test-secret-key')


# ---------------------------------------------------------------------------
# S1: the setting
# ---------------------------------------------------------------------------

class TestSetting:
    @pytest.mark.parametrize('value', [None, '', '   '])
    def test_unset_or_empty_is_the_static_cards_folder(self, clean_env, value):
        app = _app_from_env(clean_env, value)
        assert app.config['CARD_IMAGES_DIR'] == os.path.join(app.static_folder, 'images', 'cards')

    def test_an_absolute_path_is_used_as_given(self, clean_env, tmp_path):
        app = _app_from_env(clean_env, str(tmp_path / 'data'))
        assert app.config['CARD_IMAGES_DIR'] == str(tmp_path / 'data')

    @pytest.mark.parametrize('value', ['card-images', './data/cards', '~/card-images'])
    def test_a_relative_path_stops_the_app_naming_the_variable(self, clean_env, value):
        with pytest.raises(ConfigError) as err:
            _app_from_env(clean_env, value)
        message = str(err.value)
        assert 'CARD_IMAGES_DIR' in message
        assert 'absolute' in message
        assert value not in message                 # names, never values


# ---------------------------------------------------------------------------
# S2: card_image_path takes the images root directly
# ---------------------------------------------------------------------------

class TestCardImagePath:
    def test_the_path_is_root_folder_file_with_no_suffix_added(self, tmp_path):
        root = tmp_path / 'card-images'
        root.mkdir()
        assert card_image_path(str(root), 'ogn_257.png', 'OGNX') == str(root / 'ogn' / 'ogn_257.png')

    def test_a_name_without_prefix_uses_the_set_id(self, tmp_path):
        assert card_image_path(str(tmp_path), 'promo.png', 'PROK') == str(tmp_path / 'prok' / 'promo.png')

    @pytest.mark.parametrize('image', ['', '.', '..', '../ogn_1.png', 'ogn/ogn_1.png',
                                       'ogn\\ogn_1.png', 'ogn_1.png\x00', '/etc/ogn_1.png'])
    def test_anything_but_a_plain_file_name_is_refused(self, tmp_path, image):
        with pytest.raises(ValueError, match='plain file name'):
            card_image_path(str(tmp_path), image, 'OGN')

    def test_no_safe_folder_is_refused(self, tmp_path):
        with pytest.raises(ValueError, match='safe image folder'):
            card_image_path(str(tmp_path), 'og.n_1.png', 'OGN')

    def test_a_folder_symlinked_outside_the_root_is_refused(self, tmp_path):
        root = tmp_path / 'card-images'
        root.mkdir()
        (tmp_path / 'elsewhere').mkdir()
        (root / 'ogn').symlink_to(tmp_path / 'elsewhere', target_is_directory=True)
        with pytest.raises(ValueError, match='escapes'):
            card_image_path(str(root), 'ogn_1.png', 'OGN')


# ---------------------------------------------------------------------------
# S2 + S3: the admin upload writes into the root, the route serves it back
# ---------------------------------------------------------------------------

def _upload(client, name='ogn_7.png', set_id='ogn', data=PNG):
    return client.post('/riftbound/card/upload_image',
                       data={'set_id': set_id, 'image': (io.BytesIO(data), name)},
                       content_type='multipart/form-data')


class TestUpload:
    def test_the_upload_lands_in_the_root_and_is_served_at_image_src(self, images_root,
                                                                    admin_client, client):
        resp = _upload(admin_client)
        assert resp.status_code == 200
        assert resp.get_json() == {'success': True, 'filename': 'ogn_7.png'}
        assert (images_root / 'ogn' / 'ogn_7.png').read_bytes() == PNG

        src = RbCard(rbcar_rbset_id='OGN', rbcar_id='7', image='ogn_7.png').image_src
        served = client.get(src)
        assert served.status_code == 200
        assert served.data == PNG
        assert served.mimetype == 'image/png'

    @pytest.mark.parametrize('kwargs, message', [
        ({'set_id': '../x'}, 'Invalid set id: use letters and digits only'),
        ({'name': 'ogn_7.gif'}, 'Invalid file type. Allowed: jpg, jpeg, png, webp'),
        ({'data': b'x' * (2 * 1024 * 1024 + 1)}, 'File size exceeds 2MB limit'),
        ({'name': ''}, 'No file selected'),
    ])
    def test_the_upload_rules_still_hold_and_write_nothing(self, images_root, admin_client,
                                                          kwargs, message):
        resp = _upload(admin_client, **kwargs)
        assert resp.status_code == 400
        assert resp.get_json() == {'success': False, 'message': message}
        assert list(images_root.iterdir()) == []

    def test_a_plain_user_cannot_upload(self, images_root, authenticated_client):
        assert _upload(authenticated_client).status_code == 403
        assert list(images_root.iterdir()) == []


# ---------------------------------------------------------------------------
# S3: the route
# ---------------------------------------------------------------------------

class TestServe:
    def test_a_file_of_the_root_is_served(self, images_root, client):
        (images_root / 'sfd').mkdir()
        (images_root / 'sfd' / 'sfd_1.png').write_bytes(PNG)
        resp = client.get(f'{CARDS_URL}/sfd/sfd_1.png')
        assert resp.status_code == 200
        assert resp.data == PNG

    def test_the_endpoint_is_card_images_serve(self, app):
        adapter = app.url_map.bind('localhost')
        assert adapter.match(f'{CARDS_URL}/ogn/ogn_1.png')[0] == 'card_images.serve'
        assert adapter.match('/riftbound/static/js/csrf.js')[0] == 'static'

    @pytest.mark.parametrize('url', [
        f'{CARDS_URL}/ogn/ogn_404.png',
        f'{CARDS_URL}/nope.png',
        f'{CARDS_URL}/ogn',                         # a folder is not a file
    ])
    def test_a_missing_file_is_404(self, images_root, client, url):
        (images_root / 'ogn').mkdir()
        assert client.get(url).status_code == 404

    @pytest.mark.parametrize('suffix', ['ogn_1.png%00', 'ogn_1.png%00.png', '%00'])
    def test_a_null_byte_is_a_404_like_static(self, images_root, client, suffix):
        (images_root / 'ogn').mkdir()
        (images_root / 'ogn' / 'ogn_1.png').write_bytes(PNG)
        assert client.get(f'{CARDS_URL}/ogn/{suffix}').status_code == 404
        assert client.get('/riftbound/static/js/csrf.js%00').status_code == 404

    @pytest.mark.parametrize('suffix', [
        '../secret.txt',
        'ogn/../../secret.txt',
        '%2e%2e/secret.txt',
        '%2E%2E%2Fsecret.txt',
        'ogn/%2e%2e/%2e%2e/secret.txt',
    ])
    def test_traversal_is_404(self, images_root, client, suffix):
        (images_root / 'ogn').mkdir()
        resp = client.get(f'{CARDS_URL}/{suffix}', follow_redirects=True)
        assert resp.status_code == 404
        assert SECRET not in resp.data

    def test_an_absolute_path_is_404(self, images_root, client):
        secret = images_root.parent / 'secret.txt'
        for url in (f'{CARDS_URL}/{secret}', f'{CARDS_URL}/%2F{str(secret).lstrip("/")}'):
            resp = client.get(url, follow_redirects=True)
            assert resp.status_code == 404, url
            assert SECRET not in resp.data

    def test_a_symlink_pointing_outside_is_404(self, images_root, client):
        (images_root / 'ogn').mkdir()
        (images_root / 'ogn' / 'leak.png').symlink_to(images_root.parent / 'secret.txt')
        (images_root / 'out').symlink_to(images_root.parent, target_is_directory=True)
        for url in (f'{CARDS_URL}/ogn/leak.png', f'{CARDS_URL}/out/secret.txt'):
            resp = client.get(url)
            assert resp.status_code == 404, url
            assert SECRET not in resp.data

    def test_a_symlink_inside_the_root_is_followed(self, images_root, client):
        (images_root / 'ogn').mkdir()
        (images_root / 'ogn' / 'ogn_1.png').write_bytes(PNG)
        (images_root / 'ogs').symlink_to(images_root / 'ogn', target_is_directory=True)
        resp = client.get(f'{CARDS_URL}/ogs/ogn_1.png')
        assert resp.status_code == 200
        assert resp.data == PNG

    def test_conditional_requests_like_the_static_files(self, images_root, client):
        (images_root / 'ogn').mkdir()
        (images_root / 'ogn' / 'ogn_1.png').write_bytes(PNG)
        first = client.get(f'{CARDS_URL}/ogn/ogn_1.png')
        assert first.headers.get('ETag')
        assert first.headers.get('Last-Modified')
        again = client.get(f'{CARDS_URL}/ogn/ogn_1.png',
                           headers={'If-None-Match': first.headers['ETag']})
        assert again.status_code == 304
        assert again.data == b''

    @pytest.mark.parametrize('max_age', [None, 3600])
    def test_cache_control_follows_send_file_max_age_like_static(self, app, images_root,
                                                                client, max_age):
        app.config['SEND_FILE_MAX_AGE_DEFAULT'] = max_age
        (images_root / 'ogn').mkdir()
        (images_root / 'ogn' / 'ogn_1.png').write_bytes(PNG)
        image = client.get(f'{CARDS_URL}/ogn/ogn_1.png')
        static = client.get('/riftbound/static/js/csrf.js')
        assert image.headers.get('Cache-Control') == static.headers.get('Cache-Control')
        if max_age:
            assert image.cache_control.max_age == max_age

    def test_other_static_urls_are_unchanged(self, images_root, client):
        resp = client.get('/riftbound/static/js/csrf.js')
        assert resp.status_code == 200
        assert resp.data == (STATIC_DIR / 'js' / 'csrf.js').read_bytes()
        assert client.get('/riftbound/static/js/no-such-file.js').status_code == 404


class TestImageSrc:
    @pytest.mark.parametrize('image, set_id, expected', [
        ('ogn_257.png', 'OGNX', '/riftbound/static/images/cards/ogn/ogn_257.png'),
        ('promo.png', 'PROK', '/riftbound/static/images/cards/prok/promo.png'),
        ('', 'OGN', None),
        (None, 'OGN', None),
        ('og.n_1.png', 'OGN', None),
    ])
    def test_image_src_is_unchanged(self, app, image, set_id, expected):
        assert RbCard(rbcar_rbset_id=set_id, rbcar_id='1', image=image).image_src == expected


# ---------------------------------------------------------------------------
# S2 + S5: the Riot scraper, step 4
# ---------------------------------------------------------------------------

RIOT_CARD = {
    'id': 'ogn-7-298',
    'name': 'Scraped Card',
    'cardImage': {'url': 'https://cdn.example.invalid/ogn-7.png'},
}


class _FakeResponse:
    content = PNG

    def raise_for_status(self):
        return None


class _FakeSession:
    def __init__(self):
        self.urls = []

    def get(self, url, timeout=None):
        self.urls.append(url)
        return _FakeResponse()


class TestScraperStep4:
    def test_the_download_lands_in_the_root_and_is_served(self, images_root, client,
                                                         monkeypatch, no_network):
        session = _FakeSession()
        monkeypatch.setattr(riot_scraper, '_get_session', lambda: session)
        monkeypatch.setattr(riot_scraper, '_fetch_gallery_json', lambda s: [RIOT_CARD])

        result = riot_scraper.extract_riot_cards()

        step4 = next(s for s in result['steps'] if s['step'] == '4. Download images')
        assert step4['status'] == 'SUCCESS'
        assert result['stats']['images_downloaded'] == 1
        assert session.urls == [RIOT_CARD['cardImage']['url']]
        assert (images_root / 'ogn' / 'ogn_7.png').read_bytes() == PNG
        card = RbCard.query.filter_by(rbcar_rbset_id='OGN', rbcar_id='7').one()
        assert client.get(card.image_src).data == PNG

    def test_an_existing_file_in_the_root_is_not_downloaded_again(self, images_root,
                                                                 monkeypatch, no_network):
        (images_root / 'ogn').mkdir()
        (images_root / 'ogn' / 'ogn_7.png').write_bytes(b'already here')
        session = _FakeSession()
        monkeypatch.setattr(riot_scraper, '_get_session', lambda: session)
        monkeypatch.setattr(riot_scraper, '_fetch_gallery_json', lambda s: [RIOT_CARD])

        result = riot_scraper.extract_riot_cards()

        assert result['stats']['images_existed'] == 1
        assert result['stats']['images_downloaded'] == 0
        assert session.urls == []
        assert (images_root / 'ogn' / 'ogn_7.png').read_bytes() == b'already here'
