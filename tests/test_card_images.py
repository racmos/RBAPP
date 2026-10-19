"""
Card images (IMG-1, IMG-2, IMG-3).

IMG-1 (characterization) pins the behavior introduced by commit 1ae1f6e: the
image folder comes from the filename prefix (text before the last '_'), NOT
from the set id. It passed on the unchanged code and keeps passing now that the
rule lives in `card_image_folder` (`_image_folder` stays as an alias).

IMG-2 / IMG-3 (unit c): one rule for reading and writing, and writes can never
leave `<static>/images/cards/`. Every filesystem test runs in a tmp tree with
the working directory moved away from the repo.
"""
import io
import os
from types import SimpleNamespace

import pytest

from app import db
from app.models import RbCard, RbSet
from app.models.card import card_image_folder, _image_folder
from app.services import riot_scraper
from app.services.card_images import card_image_path

IMAGE_BASE = '/riftbound/static/images/cards'


def _card(set_id, image):
    """In-memory RbCard (never added to a session): image_src is a pure property."""
    return RbCard(rbcar_rbset_id=set_id, rbcar_id='1', rbcar_name='X', image=image)


class TestImageSrc:
    @pytest.mark.parametrize('set_id, image, expected_folder', [
        ('OGNX', 'ogn_257.png', 'ogn'),    # promo set: folder from filename, not 'ognx'
        ('OGN', 'ogn_1.png', 'ogn'),       # regular set
        ('PROK', 'ogn_265.png', 'ogn'),    # PROK reuses OGN artwork
        ('OGN', 'OGN_9.png', 'ogn'),       # prefix is lowercased
    ])
    def test_folder_comes_from_filename_prefix(self, set_id, image, expected_folder):
        card = _card(set_id, image)
        assert card.image_src == f'{IMAGE_BASE}/{expected_folder}/{image}'

    @pytest.mark.parametrize('image', [None, ''])
    def test_no_image_gives_none(self, image):
        assert _card('OGN', image).image_src is None


class TestImageFolder:
    @pytest.mark.parametrize('image, expected', [
        ('ogn_257.png', 'ogn'),
        ('ogn_1.png', 'ogn'),
        ('OGN_9.png', 'ogn'),
        ('', ''),
        (None, ''),
        ('noprefix.png', ''),
    ])
    def test_image_folder(self, image, expected):
        assert _image_folder(image) == expected


# ---------------------------------------------------------------------------
# D13 the shared folder rule
# ---------------------------------------------------------------------------

class TestCardImageFolder:
    @pytest.mark.parametrize('image, set_id, expected', [
        ('ogn_257.png', 'OGNX', 'ogn'),         # prefix wins over the set id
        ('ogn_265.png', 'PROK', 'ogn'),
        ('OGN_9.png', 'OGN', 'ogn'),
        ('promo.png', 'PROK', 'prok'),          # no '_': the set id, lower-cased
        ('plain.png', 'Ognx', 'ognx'),
        ('noprefix.png', None, ''),             # nothing to fall back to
        ('', 'OGN', 'ogn'),
    ])
    def test_prefix_else_set_id(self, image, set_id, expected):
        assert card_image_folder(image, set_id) == expected

    @pytest.mark.parametrize('image, set_id', [
        ('x.png', '../../evil'), ('x.png', '..'), ('x.png', '/tmp/x'), ('x.png', 'a/b'),
        ('x.png', 'a\\b'), ('x.png', ''), ('x.png', None), ('x.png', 'og n'), ('x.png', 'ogn.'),
        ('../_x.png', 'ogn'), ('a-b_1.png', 'ogn'), ('a/b_1.png', 'ogn'), ('.._1.png', 'ogn'),
    ])
    def test_invalid_folder_gives_empty_string(self, image, set_id):
        assert card_image_folder(image, set_id) == ''

    def test_image_folder_alias_keeps_the_old_signature(self):
        assert _image_folder('ogn_257.png') == 'ogn'
        assert _image_folder('noprefix.png') == ''

    def test_image_src_falls_back_to_the_set_when_the_name_has_no_prefix(self):
        assert _card('PROK', 'promo.png').image_src == f'{IMAGE_BASE}/prok/promo.png'

    def test_image_src_is_none_when_no_safe_folder_exists(self):
        assert _card('OGN', 'a-b_1.png').image_src is None


class TestCardImagePath:
    def test_path_is_under_images_cards_and_the_folder(self, tmp_path):
        path = card_image_path(str(tmp_path), 'ogn_257.png', 'OGNX')
        assert path == os.path.join(os.path.realpath(tmp_path), 'images', 'cards', 'ogn',
                                    'ogn_257.png')

    def test_fallback_folder_for_unprefixed_names(self, tmp_path):
        assert card_image_path(str(tmp_path), 'promo.png', 'PROK').endswith(
            os.path.join('images', 'cards', 'prok', 'promo.png'))

    def test_does_not_create_anything(self, tmp_path):
        card_image_path(str(tmp_path), 'ogn_1.png', 'OGN')
        assert list(tmp_path.iterdir()) == []

    @pytest.mark.parametrize('image', [
        '../../evil.png', '../ogs/ogn_1.png', '/etc/passwd', 'sub/ogn_1.png', 'a\\b_1.png',
        '..', '.', '', 'ogn_1.png\x00.png'])
    def test_names_that_are_not_plain_files_raise(self, tmp_path, image):
        with pytest.raises(ValueError):
            card_image_path(str(tmp_path), image, 'OGN')

    @pytest.mark.parametrize('set_id', ['../../evil', '..', '/tmp/x', 'a/b', '', None])
    def test_a_bad_set_id_without_prefix_raises(self, tmp_path, set_id):
        with pytest.raises(ValueError):
            card_image_path(str(tmp_path), 'x.png', set_id)

    def test_a_symlinked_folder_pointing_outside_raises(self, tmp_path):
        outside = tmp_path / 'outside'
        outside.mkdir()
        cards = tmp_path / 'static' / 'images' / 'cards'
        cards.mkdir(parents=True)
        (cards / 'ogn').symlink_to(outside, target_is_directory=True)
        with pytest.raises(ValueError):
            card_image_path(str(tmp_path / 'static'), 'ogn_1.png', 'OGN')

    def test_a_symlinked_cards_root_is_fine_when_everything_stays_inside(self, tmp_path):
        real = tmp_path / 'real_static'
        (real / 'images' / 'cards').mkdir(parents=True)
        link = tmp_path / 'static'
        link.symlink_to(real, target_is_directory=True)
        assert card_image_path(str(link), 'ogn_1.png', 'OGN').startswith(
            os.path.realpath(real))


# ---------------------------------------------------------------------------
# IMG-2 upload
# ---------------------------------------------------------------------------

@pytest.fixture
def sandbox(app, tmp_path, monkeypatch):
    """A tmp static folder for the app, and a working directory deep inside the
    tmp tree, so a CWD-relative write (the old behavior) or a `../..` escape
    lands somewhere the test can see."""
    static = tmp_path / 'static'
    static.mkdir()
    cwd = tmp_path / 'a' / 'b' / 'cwd'
    cwd.mkdir(parents=True)
    monkeypatch.chdir(cwd)
    monkeypatch.setattr(app, 'static_folder', str(static))
    return SimpleNamespace(root=tmp_path, static=static, cards=static / 'images' / 'cards')


def tree(root):
    return sorted(str(p.relative_to(root)) for p in root.rglob('*'))


def upload(client, set_id, filename, data=b'png-bytes'):
    return client.post('/riftbound/card/upload_image', content_type='multipart/form-data',
                       data={'set_id': set_id, 'image': (io.BytesIO(data), filename)})


class TestUpload:
    def test_a_valid_upload_lands_where_image_src_reads(self, admin_client, sandbox):
        resp = upload(admin_client, 'ognx', 'ogn_257.png')
        assert resp.status_code == 200
        assert resp.json == {'success': True, 'filename': 'ogn_257.png'}
        assert (sandbox.cards / 'ogn' / 'ogn_257.png').read_bytes() == b'png-bytes'
        assert not (sandbox.cards / 'ognx').exists()
        # ... and that is exactly the file the page links to
        assert _card('OGNX', 'ogn_257.png').image_src.endswith('/cards/ogn/ogn_257.png')

    def test_a_name_without_prefix_falls_back_to_the_set_folder(self, admin_client, sandbox):
        resp = upload(admin_client, 'PROK', 'promo.png')
        assert resp.status_code == 200
        assert (sandbox.cards / 'prok' / 'promo.png').exists()

    def test_traversal_in_the_filename_is_flattened_not_followed(self, admin_client, sandbox):
        resp = upload(admin_client, 'ogn', '../../evil.png')
        assert resp.status_code == 200
        assert resp.json == {'success': True, 'filename': 'evil.png'}
        assert (sandbox.cards / 'ogn' / 'evil.png').exists()
        assert tree(sandbox.root) == [
            'a', 'a/b', 'a/b/cwd', 'static', 'static/images', 'static/images/cards',
            'static/images/cards/ogn', 'static/images/cards/ogn/evil.png']

    @pytest.mark.parametrize('set_id', ['../../evil', '..', 'a/b', 'a\\b', '', '.', 'og n'])
    def test_a_bad_set_id_is_a_400_and_writes_nothing(self, admin_client, sandbox, set_id):
        before = tree(sandbox.root)
        resp = upload(admin_client, set_id, 'x.png')
        assert resp.status_code == 400
        assert resp.json['success'] is False and resp.json['message']
        assert tree(sandbox.root) == before

    def test_an_absolute_set_id_is_a_400_and_writes_nothing(self, admin_client, sandbox):
        absolute = str(sandbox.root / 'absolute')
        before = tree(sandbox.root)
        resp = upload(admin_client, absolute, 'x.png')
        assert resp.status_code == 400
        assert tree(sandbox.root) == before

    def test_a_bad_set_id_is_refused_even_when_the_filename_has_a_good_prefix(
            self, admin_client, sandbox):
        before = tree(sandbox.root)
        assert upload(admin_client, '../../evil', 'ogn_1.png').status_code == 400
        assert tree(sandbox.root) == before

    def test_files_over_2_mb_are_refused(self, admin_client, sandbox):
        before = tree(sandbox.root)
        resp = upload(admin_client, 'ogn', 'ogn_9.png', data=b'x' * (3 * 1024 * 1024))
        assert resp.status_code == 400
        assert tree(sandbox.root) == before

    def test_exactly_2_mb_is_accepted(self, admin_client, sandbox):
        resp = upload(admin_client, 'ogn', 'ogn_9.png', data=b'x' * (2 * 1024 * 1024))
        assert resp.status_code == 200

    @pytest.mark.parametrize('filename', ['payload.exe', 'ogn_1.png.exe', 'noextension'])
    def test_other_extensions_are_refused(self, admin_client, sandbox, filename):
        before = tree(sandbox.root)
        resp = upload(admin_client, 'ogn', filename)
        assert resp.status_code == 400
        assert tree(sandbox.root) == before

    @pytest.mark.parametrize('filename', ['a.jpg', 'a.JPEG', 'a.webp', 'a.png'])
    def test_the_allowed_extensions_pass(self, admin_client, sandbox, filename):
        assert upload(admin_client, 'ogn', filename).status_code == 200

    def test_the_working_directory_does_not_matter(self, admin_client, sandbox, monkeypatch):
        other = sandbox.root / 'elsewhere'
        other.mkdir()
        monkeypatch.chdir(other)
        assert upload(admin_client, 'ogn', 'ogn_3.png').status_code == 200
        assert (sandbox.cards / 'ogn' / 'ogn_3.png').exists()
        assert list(other.iterdir()) == []                # nothing relative to the CWD

    def test_a_symlinked_set_folder_pointing_outside_is_refused(self, admin_client, sandbox):
        outside = sandbox.root / 'outside'
        outside.mkdir()
        sandbox.cards.mkdir(parents=True)
        (sandbox.cards / 'ogn').symlink_to(outside, target_is_directory=True)
        resp = upload(admin_client, 'ogn', 'ogn_1.png')
        assert resp.status_code == 400
        assert list(outside.iterdir()) == []


# ---------------------------------------------------------------------------
# IMG-3 scraper
# ---------------------------------------------------------------------------

def parsed(set_id, card_id, image):
    """One parsed scraper card (the dict `_parse_card` returns)."""
    return {
        'rbcar_rbset_id': set_id, 'rbcar_id': card_id, 'rbcar_name': f'Card {card_id}',
        'rbcar_domain': '', 'rbcar_type': '', 'rbcar_tags': '', 'rbcar_energy': None,
        'rbcar_power': None, 'rbcar_might': None, 'rbcar_ability': '', 'rbcar_rarity': 'Common',
        'rbcar_artist': '', 'rbcar_banned': 'N',
        'image_url': f'https://img.example/{image}', 'image': image,
    }


class FakeSession:
    """Answers every GET with the same PNG-ish bytes and records the URLs."""

    def __init__(self):
        self.urls = []

    def get(self, url, timeout=None):
        self.urls.append(url)
        return SimpleNamespace(content=b'scraped-bytes', raise_for_status=lambda: None)


@pytest.fixture
def scraper(app, sandbox, monkeypatch):
    """Run `extract_riot_cards` over the given parsed cards with HTTP mocked."""
    session = FakeSession()

    def run(*cards):
        by_id = {c['rbcar_id']: c for c in cards}
        monkeypatch.setattr(riot_scraper, '_get_session', lambda: session)
        monkeypatch.setattr(riot_scraper, '_fetch_gallery_json',
                            lambda s: [{'id': c['rbcar_id']} for c in cards])
        monkeypatch.setattr(riot_scraper, '_parse_card', lambda raw: by_id[raw['id']])
        return riot_scraper.extract_riot_cards()

    run.session = session
    return run


class TestScraper:
    def test_a_promo_card_is_stored_in_the_prefix_folder_and_image_src_finds_it(
            self, scraper, sandbox):
        result = scraper(parsed('OGNX', '257', 'ogn_257.png'))
        assert result['success'] is True
        stored = sandbox.cards / 'ogn' / 'ogn_257.png'
        assert stored.read_bytes() == b'scraped-bytes'
        assert not (sandbox.cards / 'ognx').exists()
        assert result['stats']['images_downloaded'] == 1

        card = RbCard.query.filter_by(rbcar_rbset_id='OGNX', rbcar_id='257').one()
        assert card.image_src == '/riftbound/static/images/cards/ogn/ogn_257.png'
        assert (sandbox.cards / card.image_src.rsplit('/cards/', 1)[1]).exists()

    def test_a_name_without_prefix_goes_to_the_set_folder(self, scraper, sandbox):
        scraper(parsed('PROK', '1', 'plain.png'))
        assert (sandbox.cards / 'prok' / 'plain.png').read_bytes() == b'scraped-bytes'

    def test_several_sets_each_get_their_own_folder(self, scraper, sandbox):
        result = scraper(parsed('OGN', '1', 'ogn_1.png'), parsed('SFD', '2', 'sfd_2.png'),
                         parsed('OGNX', '3', 'ogn_3.png'))
        assert result['stats']['images_downloaded'] == 3
        assert sorted(str(p.relative_to(sandbox.cards)) for p in sandbox.cards.rglob('*.png')) == [
            'ogn/ogn_1.png', 'ogn/ogn_3.png', 'sfd/sfd_2.png']

    def test_an_existing_image_is_not_downloaded_again(self, scraper, sandbox):
        (sandbox.cards / 'ogn').mkdir(parents=True)
        (sandbox.cards / 'ogn' / 'ogn_1.png').write_bytes(b'already here')
        result = scraper(parsed('OGN', '1', 'ogn_1.png'))
        assert result['stats']['images_existed'] == 1
        assert result['stats']['images_downloaded'] == 0
        assert (sandbox.cards / 'ogn' / 'ogn_1.png').read_bytes() == b'already here'
        assert scraper.session.urls == []

    def test_an_image_name_that_would_escape_is_counted_as_failed_and_not_written(
            self, scraper, sandbox):
        before = tree(sandbox.root)
        result = scraper(parsed('OGN', '1', '../../evil.png'))
        assert result['stats']['images_failed'] == 1
        assert result['stats']['images_downloaded'] == 0
        assert tree(sandbox.root) == before
        assert scraper.session.urls == []

    def test_the_module_docstring_describes_the_real_folder_rule(self):
        assert 'app/static/images/cards/<set_id>/' not in riot_scraper.__doc__
