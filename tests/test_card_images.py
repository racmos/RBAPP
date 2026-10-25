"""Card images in CARD_IMAGES_DIR (M-d, S3, S5, S6).

Every test points CARD_IMAGES_DIR at a temporary folder (`card_images_dir`):
nothing here reads or writes the real images. `secret.txt` sits NEXT TO the
images root, so a path that escaped it would land there.
"""
import io
from pathlib import Path

import pytest
import requests

from app.models import RbCard
from app.services import riot_scraper
from app.services.card_images import card_image_path, card_image_url, images_root

PNG = b'\x89PNG\r\n\x1a\n' + b'card-image-bytes' * 8
APP_DIR = Path(__file__).resolve().parent.parent / 'app'
OLD_PREFIX = '/riftbound/static/images/cards'


@pytest.fixture
def no_network(monkeypatch):
    def refuse(self, method, url, *args, **kwargs):
        raise requests.ConnectionError('network disabled in tests')
    monkeypatch.setattr(requests.Session, 'request', refuse)


# ---------------------------------------------------------------------------
# S3: images_root and card_image_path
# ---------------------------------------------------------------------------

class TestImagesRoot:
    def test_it_is_the_setting(self, card_images_dir):
        assert images_root() == str(card_images_dir)


class TestCardImagePath:
    def test_the_path_is_root_folder_file(self, card_images_dir):
        assert card_image_path('ogn_257.png', 'OGNX') == str(card_images_dir / 'ogn' / 'ogn_257.png')

    def test_the_set_id_is_optional(self, card_images_dir):
        assert card_image_path('sfd_3.png') == str(card_images_dir / 'sfd' / 'sfd_3.png')

    def test_a_name_without_prefix_uses_the_set_id(self, card_images_dir):
        assert card_image_path('promo.png', 'PROK') == str(card_images_dir / 'prok' / 'promo.png')

    def test_nothing_is_created(self, card_images_dir):
        card_image_path('ogn_1.png')
        assert not card_images_dir.exists()

    @pytest.mark.parametrize('image', [
        '', '.', '..',
        '../ogn_1.png', '..\\ogn_1.png',
        'ogn/ogn_1.png', '/etc/ogn_1.png',
        'ogn\\ogn_1.png',
        'ogn_1.png\x00', 'ogn_1\x00.png',
        'ogn_1.png\n', 'ogn_1.png\r', 'ogn_1.png\r\nSet-Cookie: evil=1',
        None,
    ])
    def test_anything_but_a_plain_file_name_is_refused(self, card_images_dir, image):
        with pytest.raises(ValueError, match='^the image name must be a plain file name$'):
            card_image_path(image, 'OGN')

    @pytest.mark.parametrize('image, set_id', [
        ('og.n_1.png', 'OGN'),
        ('promo.png', '../x'),
        ('promo.png', None),
        ('OG-N_1.png', 'OGN'),
    ])
    def test_no_safe_folder_is_refused(self, card_images_dir, image, set_id):
        with pytest.raises(ValueError, match='^cannot derive a safe image folder '
                                             r'\(expected letters and digits only\)$'):
            card_image_path(image, set_id)

    def test_a_folder_symlinked_outside_the_root_is_refused(self, card_images_dir, tmp_path):
        card_images_dir.mkdir()
        (tmp_path / 'elsewhere').mkdir()
        (card_images_dir / 'ogn').symlink_to(tmp_path / 'elsewhere', target_is_directory=True)
        with pytest.raises(ValueError, match='^the image path escapes the card images folder$'):
            card_image_path('ogn_1.png', 'OGN')

    def test_a_file_symlinked_outside_the_root_is_refused(self, card_images_dir, tmp_path):
        (card_images_dir / 'ogn').mkdir(parents=True)
        (tmp_path / 'secret.txt').write_bytes(b'secret')
        (card_images_dir / 'ogn' / 'ogn_1.png').symlink_to(tmp_path / 'secret.txt')
        with pytest.raises(ValueError, match='escapes'):
            card_image_path('ogn_1.png', 'OGN')


# ---------------------------------------------------------------------------
# S3: card_image_url and RbCard.image_src
# ---------------------------------------------------------------------------

URL_CASES = [
    ('ogn_257.png', 'OGNX', '/riftbound/media/cards/ogn/ogn_257.png'),
    ('ogn_265.png', 'PROK', '/riftbound/media/cards/ogn/ogn_265.png'),
    ('sfd_12.png', 'SFD', '/riftbound/media/cards/sfd/sfd_12.png'),
    ('promo.png', 'PROK', '/riftbound/media/cards/prok/promo.png'),
    ('', 'OGN', None),
    (None, 'OGN', None),
    ('og.n_1.png', 'OGN', None),
    ('promo.png', None, None),
]


class TestCardImageUrl:
    @pytest.mark.parametrize('image, set_id, expected', URL_CASES)
    def test_the_media_url_or_none(self, image, set_id, expected):
        assert card_image_url(image, set_id) == expected

    def test_the_set_id_is_optional(self):
        assert card_image_url('ogs_4.png') == '/riftbound/media/cards/ogs/ogs_4.png'


class TestImageSrc:
    @pytest.mark.parametrize('image, set_id, expected', URL_CASES)
    def test_image_src_is_the_media_url(self, app, image, set_id, expected):
        assert RbCard(rbcar_rbset_id=set_id, rbcar_id='1', image=image).image_src == expected


# ---------------------------------------------------------------------------
# S5: the admin upload writes into the root, the media route serves it back
# ---------------------------------------------------------------------------

def _upload(client, name='ogn_7.png', set_id='ogn', data=PNG):
    return client.post('/riftbound/card/upload_image',
                       data={'set_id': set_id, 'image': (io.BytesIO(data), name)},
                       content_type='multipart/form-data')


class TestUpload:
    def test_the_upload_creates_the_folder_and_is_served_at_image_src(self, card_images_dir,
                                                                     admin_client, client):
        assert not card_images_dir.exists()
        resp = _upload(admin_client)
        assert resp.status_code == 200
        assert resp.get_json() == {'success': True, 'filename': 'ogn_7.png'}
        assert (card_images_dir / 'ogn' / 'ogn_7.png').read_bytes() == PNG

        src = RbCard(rbcar_rbset_id='OGN', rbcar_id='7', image='ogn_7.png').image_src
        served = client.get(src)
        assert served.status_code == 200
        assert served.data == PNG
        assert served.mimetype == 'image/png'

    def test_a_promo_upload_lands_in_the_prefix_folder(self, card_images_dir, admin_client):
        assert _upload(admin_client, name='ogn_257.png', set_id='ognx').status_code == 200
        assert (card_images_dir / 'ogn' / 'ogn_257.png').read_bytes() == PNG

    @pytest.mark.parametrize('kwargs, message', [
        ({'set_id': '../x'}, 'Invalid set id: use letters and digits only'),
        ({'name': 'ogn_7.gif'}, 'Invalid file type. Allowed: jpg, jpeg, png, webp'),
        ({'data': b'x' * (2 * 1024 * 1024 + 1)}, 'File size exceeds 2MB limit'),
        ({'name': ''}, 'No file selected'),
    ])
    def test_the_upload_rules_still_hold_and_write_nothing(self, card_images_dir, admin_client,
                                                          kwargs, message):
        resp = _upload(admin_client, **kwargs)
        assert resp.status_code == 400
        assert resp.get_json() == {'success': False, 'message': message}
        assert not card_images_dir.exists()

    def test_a_plain_user_cannot_upload(self, card_images_dir, authenticated_client):
        assert _upload(authenticated_client).status_code == 403
        assert not card_images_dir.exists()


# ---------------------------------------------------------------------------
# S5: the Riot scraper, step 4
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
    def test_the_download_lands_in_the_root_and_is_served(self, card_images_dir, client,
                                                         monkeypatch, no_network):
        session = _FakeSession()
        monkeypatch.setattr(riot_scraper, '_get_session', lambda: session)
        monkeypatch.setattr(riot_scraper, '_fetch_gallery_json', lambda s: [RIOT_CARD])

        result = riot_scraper.extract_riot_cards()

        step4 = next(s for s in result['steps'] if s['step'] == '4. Download images')
        assert step4['status'] == 'SUCCESS'
        assert result['stats']['images_downloaded'] == 1
        assert session.urls == [RIOT_CARD['cardImage']['url']]
        assert (card_images_dir / 'ogn' / 'ogn_7.png').read_bytes() == PNG
        card = RbCard.query.filter_by(rbcar_rbset_id='OGN', rbcar_id='7').one()
        assert card.image_src == '/riftbound/media/cards/ogn/ogn_7.png'
        assert client.get(card.image_src).data == PNG

    def test_an_existing_file_in_the_root_is_not_downloaded_again(self, card_images_dir,
                                                                 monkeypatch, no_network):
        (card_images_dir / 'ogn').mkdir(parents=True)
        (card_images_dir / 'ogn' / 'ogn_7.png').write_bytes(b'already here')
        session = _FakeSession()
        monkeypatch.setattr(riot_scraper, '_get_session', lambda: session)
        monkeypatch.setattr(riot_scraper, '_fetch_gallery_json', lambda s: [RIOT_CARD])

        result = riot_scraper.extract_riot_cards()

        assert result['stats']['images_existed'] == 1
        assert result['stats']['images_downloaded'] == 0
        assert session.urls == []
        assert (card_images_dir / 'ogn' / 'ogn_7.png').read_bytes() == b'already here'


# ---------------------------------------------------------------------------
# S6 + G7: nothing in the app builds the old static URLs any more
# ---------------------------------------------------------------------------

class TestNoOldImageUrls:
    def test_no_source_or_template_uses_the_old_prefix(self):
        offenders = [
            str(path.relative_to(APP_DIR))
            for pattern in ('**/*.py', '**/*.html', '**/*.js')
            for path in APP_DIR.glob(pattern)
            if 'vendor' not in path.parts and OLD_PREFIX in path.read_text(encoding='utf-8')
        ]
        assert offenders == []

    def test_the_deck_legend_placeholder_is_an_inline_svg(self):
        deck = (APP_DIR / 'templates' / 'deck.html').read_text(encoding='utf-8')
        assert "img.src = legend.image || 'data:image/svg+xml," in deck
