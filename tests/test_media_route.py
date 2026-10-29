"""GET /riftbound/media/cards/<folder>/<filename> (M-d, S4) and
GET /riftbound/media/products/<filename> (F14-d S1).

Files come from a temporary CARD_IMAGES_DIR (`card_images_dir`). `secret.txt`
sits NEXT TO the images root, so a traversal that worked would hand it out.
"""
import pytest

from tests.test_authz_matrix import MATRIX, classify

PNG = b'\x89PNG\r\n\x1a\n' + b'card-image-bytes' * 8
WEBP = b'RIFF\x00\x00\x00\x00WEBPVP8 '
SECRET = b'TOP-SECRET-OUTSIDE-THE-IMAGES-ROOT'
MEDIA = '/riftbound/media/cards'
WEEK = 'public, max-age=604800'


@pytest.fixture
def images(card_images_dir, tmp_path):
    """The images root with ogn/ogn_1.png and sfd/sfd_2.webp, and a secret beside it."""
    (card_images_dir / 'ogn').mkdir(parents=True)
    (card_images_dir / 'ogn' / 'ogn_1.png').write_bytes(PNG)
    (card_images_dir / 'sfd').mkdir()
    (card_images_dir / 'sfd' / 'sfd_2.webp').write_bytes(WEBP)
    (tmp_path / 'secret.txt').write_bytes(SECRET)
    return card_images_dir


def _assert_not_found(resp):
    assert resp.status_code == 404
    assert SECRET not in resp.data


class TestServe:
    @pytest.mark.parametrize('path, body, mimetype', [
        ('ogn/ogn_1.png', PNG, 'image/png'),
        ('sfd/sfd_2.webp', WEBP, 'image/webp'),
    ])
    def test_a_file_is_served_with_its_type_and_a_week_of_cache(self, images, client,
                                                               path, body, mimetype):
        resp = client.get(f'{MEDIA}/{path}')
        assert resp.status_code == 200
        assert resp.data == body
        assert resp.mimetype == mimetype
        assert resp.headers['Cache-Control'] == WEEK

    def test_the_endpoint_is_media_card_image(self, app):
        adapter = app.url_map.bind('localhost')
        assert adapter.match(f'{MEDIA}/ogn/ogn_1.png') == (
            'media.card_image', {'folder': 'ogn', 'filename': 'ogn_1.png'})

    def test_anonymous_and_signed_in_users_get_it(self, images, client, authenticated_client):
        assert client.get(f'{MEDIA}/ogn/ogn_1.png').status_code == 200
        assert authenticated_client.get(f'{MEDIA}/ogn/ogn_1.png').status_code == 200

    @pytest.mark.parametrize('path', ['ogn/ogn_1.png', 'ogn/ogn_404.png', 'og.n/ogn_1.png'])
    def test_no_response_sets_a_cookie(self, images, client, path):
        resp = client.get(f'{MEDIA}/{path}')
        assert 'Set-Cookie' not in resp.headers

    def test_conditional_requests_answer_304(self, images, client):
        first = client.get(f'{MEDIA}/ogn/ogn_1.png')
        assert first.headers.get('ETag')
        again = client.get(f'{MEDIA}/ogn/ogn_1.png',
                           headers={'If-None-Match': first.headers['ETag']})
        assert again.status_code == 304
        assert again.data == b''

    def test_the_old_static_url_does_not_serve_the_images_root(self, images, client):
        # A name that exists only in CARD_IMAGES_DIR: the old prefix is plain static now.
        (images / 'ogn' / 'ogn_only_in_data.png').write_bytes(PNG)
        assert client.get(f'{MEDIA}/ogn/ogn_only_in_data.png').status_code == 200
        old = client.get('/riftbound/static/images/cards/ogn/ogn_only_in_data.png')
        assert old.status_code == 404


class TestNotFound:
    @pytest.mark.parametrize('path', [
        'ogn/ogn_404.png',          # missing file
        'xyz/ogn_1.png',            # missing folder
        'ogn/.',                    # not a file name
    ])
    def test_a_missing_file_is_404(self, images, client, path):
        _assert_not_found(client.get(f'{MEDIA}/{path}'))

    def test_without_the_images_folder_everything_is_404(self, card_images_dir, client):
        assert not card_images_dir.exists()
        _assert_not_found(client.get(f'{MEDIA}/ogn/ogn_1.png'))

    @pytest.mark.parametrize('folder', ['OGN', 'og.n', 'og-n', 'og_n', '%2e%2e', '..', '%00ogn'])
    def test_a_folder_that_is_not_letters_and_digits_is_404(self, images, client, folder):
        (images / 'OGN').mkdir()
        (images / 'OGN' / 'ogn_1.png').write_bytes(PNG)
        _assert_not_found(client.get(f'{MEDIA}/{folder}/ogn_1.png'))

    @pytest.mark.parametrize('suffix', [
        'ogn/..',
        'ogn/%2e%2e',
        'ogn/ogn_1.png%00',
        'ogn/ogn_1.png%00.png',
        'ogn/%00',
        'ogn/..%5Csecret.txt',
        'ogn/%5C..%5C..%5Csecret.txt',
    ])
    def test_a_file_name_that_is_not_plain_is_404(self, images, client, suffix):
        _assert_not_found(client.get(f'{MEDIA}/{suffix}'))

    @pytest.mark.parametrize('suffix', [
        'ogn_1.png%0A',
        'ogn_1.png%0D',
        'ogn_1.png%0D%0ASet-Cookie:%20evil=1',
    ])
    def test_control_characters_in_a_file_name_are_404(self, images, client, suffix):
        resp = client.get(f'{MEDIA}/ogn/{suffix}')
        _assert_not_found(resp)
        assert 'Set-Cookie' not in resp.headers

    @pytest.mark.parametrize('suffix', [
        '../secret.txt',
        'ogn/../../secret.txt',
        '%2e%2e/secret.txt',
        '%2e%2e/%2e%2e/secret.txt',
        'ogn/%2e%2e%2F%2e%2e%2Fsecret.txt',
        '%2E%2E%2Fsecret.txt',
    ])
    def test_traversal_is_404(self, images, client, suffix):
        _assert_not_found(client.get(f'{MEDIA}/{suffix}', follow_redirects=True))

    def test_a_symlink_pointing_outside_is_404(self, images, client, tmp_path):
        (images / 'ogn' / 'leak.png').symlink_to(tmp_path / 'secret.txt')
        (images / 'out').symlink_to(tmp_path, target_is_directory=True)
        for url in (f'{MEDIA}/ogn/leak.png', f'{MEDIA}/out/secret.txt'):
            _assert_not_found(client.get(url))

    def test_a_folder_is_not_a_file(self, images, client):
        (images / 'ogn' / 'sub').mkdir()
        _assert_not_found(client.get(f'{MEDIA}/ogn/sub'))


class TestAuthz:
    def test_the_rule_is_classified_public(self, app):
        rules = [r for r in app.url_map.iter_rules() if r.endpoint == 'media.card_image']
        assert [r.rule for r in rules] == ['/riftbound/media/cards/<folder>/<filename>']
        assert classify(rules[0]) == 'P'
        assert MATRIX['media.card_image'] == 'P'


# ---------------------------------------------------------------------------
# F14-d S1: GET /riftbound/media/products/<filename>
# ---------------------------------------------------------------------------

PRODUCTS = '/riftbound/media/products'
JPG = b'\xff\xd8\xff' + b'product-image-bytes' * 8


@pytest.fixture
def product_images(product_images_dir, tmp_path):
    """The product images root with 42.png, 7.webp, 8.jpg, 9.jpeg and a notes.txt,
    and a secret beside it."""
    product_images_dir.mkdir(parents=True)
    (product_images_dir / '42.png').write_bytes(PNG)
    (product_images_dir / '7.webp').write_bytes(WEBP)
    (product_images_dir / '8.jpg').write_bytes(JPG)
    (product_images_dir / '9.jpeg').write_bytes(JPG)
    (product_images_dir / 'notes.txt').write_bytes(b'not an image')
    (tmp_path / 'secret.txt').write_bytes(SECRET)
    return product_images_dir


class TestProductServe:
    @pytest.mark.parametrize('name, body, mimetype', [
        ('42.png', PNG, 'image/png'),
        ('7.webp', WEBP, 'image/webp'),
        ('8.jpg', JPG, 'image/jpeg'),
        ('9.jpeg', JPG, 'image/jpeg'),
    ])
    def test_a_file_is_served_with_its_type_and_a_week_of_cache(self, product_images, client,
                                                               name, body, mimetype):
        resp = client.get(f'{PRODUCTS}/{name}')
        assert resp.status_code == 200
        assert resp.data == body
        assert resp.mimetype == mimetype
        assert resp.headers['Cache-Control'] == WEEK

    def test_the_endpoint_is_media_product_image(self, app):
        adapter = app.url_map.bind('localhost')
        assert adapter.match(f'{PRODUCTS}/42.png') == (
            'media.product_image', {'filename': '42.png'})

    def test_anonymous_and_signed_in_users_get_it(self, product_images, client,
                                                  authenticated_client):
        assert client.get(f'{PRODUCTS}/42.png').status_code == 200
        assert authenticated_client.get(f'{PRODUCTS}/42.png').status_code == 200

    @pytest.mark.parametrize('name', ['42.png', '404.png', 'notes.txt', '..'])
    def test_no_response_sets_a_cookie(self, product_images, client, name):
        assert 'Set-Cookie' not in client.get(f'{PRODUCTS}/{name}').headers

    def test_conditional_requests_answer_304(self, product_images, client):
        first = client.get(f'{PRODUCTS}/42.png')
        again = client.get(f'{PRODUCTS}/42.png',
                           headers={'If-None-Match': first.headers['ETag']})
        assert again.status_code == 304

    def test_card_images_are_not_served_from_the_product_root(self, product_images, client,
                                                             card_images_dir):
        (card_images_dir / 'ogn').mkdir(parents=True)
        (card_images_dir / 'ogn' / 'ogn_1.png').write_bytes(PNG)
        _assert_not_found(client.get(f'{PRODUCTS}/ogn_1.png'))
        _assert_not_found(client.get(f'{PRODUCTS}/ogn/ogn_1.png'))


class TestProductNotFound:
    def test_a_missing_file_is_404(self, product_images, client):
        _assert_not_found(client.get(f'{PRODUCTS}/404.png'))

    def test_without_the_folder_everything_is_404(self, product_images_dir, client):
        assert not product_images_dir.exists()
        _assert_not_found(client.get(f'{PRODUCTS}/42.png'))

    @pytest.mark.parametrize('name', ['notes.txt', 'secret.txt', '42', '42.png.txt',
                                      '42.svg', '42.html', '42.gif'])
    def test_an_extension_off_the_allow_list_is_404(self, product_images, client, name):
        (product_images / '42.svg').write_bytes(b'<svg/>')
        (product_images / '42.html').write_bytes(b'<script>1</script>')
        (product_images / '42.gif').write_bytes(b'GIF89a')
        (product_images / '42').write_bytes(PNG)
        (product_images / '42.png.txt').write_bytes(PNG)
        _assert_not_found(client.get(f'{PRODUCTS}/{name}'))

    @pytest.mark.parametrize('suffix', [
        '..', '%2e%2e', '.',
        '42.png%00', '42.png%00.png', '%00',
        '..%5Csecret.txt', '%5C..%5C..%5Csecret.txt',
        '42.png%0A', '42.png%0D', '42.png%0D%0ASet-Cookie:%20evil=1',
    ])
    def test_a_file_name_that_is_not_plain_is_404(self, product_images, client, suffix):
        resp = client.get(f'{PRODUCTS}/{suffix}')
        _assert_not_found(resp)
        assert 'Set-Cookie' not in resp.headers

    @pytest.mark.parametrize('suffix', [
        '../secret.txt',
        '%2e%2e/secret.txt',
        '%2e%2e%2Fsecret.txt',
        '%2E%2E%2F%2E%2E%2Fsecret.txt',
    ])
    def test_traversal_is_404(self, product_images, client, suffix):
        _assert_not_found(client.get(f'{PRODUCTS}/{suffix}', follow_redirects=True))

    def test_a_symlink_pointing_outside_is_404(self, product_images, client, tmp_path):
        (tmp_path / 'outside.png').write_bytes(SECRET)
        (product_images / 'leak.png').symlink_to(tmp_path / 'outside.png')
        _assert_not_found(client.get(f'{PRODUCTS}/leak.png'))

    def test_a_folder_is_not_a_file(self, product_images, client):
        (product_images / 'sub.png').mkdir()
        _assert_not_found(client.get(f'{PRODUCTS}/sub.png'))


class TestProductAuthz:
    def test_the_rule_is_classified_public(self, app):
        rules = [r for r in app.url_map.iter_rules() if r.endpoint == 'media.product_image']
        assert [r.rule for r in rules] == ['/riftbound/media/products/<filename>']
        assert classify(rules[0]) == 'P'
        assert MATRIX['media.product_image'] == 'P'
