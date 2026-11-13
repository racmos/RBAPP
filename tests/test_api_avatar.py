"""Avatar API (F9-c S3, S6-S9): POST/DELETE /me/avatar and GET /users/<id>/avatar.

Every test that can write uses the `avatar_dir` fixture (a temporary AVATAR_DIR), never a
real path. Images are made in memory; nothing reaches the network.
"""
import io
import os

import pytest
from PIL import Image

from app import db
from app.models import RbUserProfile
from tests.conftest import api_csrf_token, login_as

API = '/riftbound/api/v1'
AVATAR = f'{API}/me/avatar'
SESSION = f'{API}/auth/session'
ME = f'{API}/me'
MAX_FILE = 5 * 1024 * 1024                      # 5,242,880 bytes (S3)
MAX_BODY = MAX_FILE + 64 * 1024
TOO_LARGE = {'success': False, 'error': 'Payload Too Large', 'message': 'The file is too large',
             'code': 'file_too_large', 'params': {'max_mb': 5}}
IMAGE_INVALID = {'success': False, 'error': 'Validation Error',
                 'message': 'The file is not a supported image', 'code': 'image_invalid'}


def image_bytes(fmt='PNG', size=(120, 90), color=(20, 200, 20)):
    buffer = io.BytesIO()
    Image.new('RGB', size, color).save(buffer, fmt)
    return buffer.getvalue()


def padded_png(total):
    """A valid PNG of exactly `total` bytes: bytes after IEND are never read by a decoder."""
    blob = image_bytes()
    return blob + b'\0' * (total - len(blob))


def upload(client, blob, filename='photo.png', content_type='image/png', field='file',
           **kwargs):
    return client.post(AVATAR, data={field: (io.BytesIO(blob), filename, content_type)},
                       content_type='multipart/form-data', **kwargs)


def files_in(root):
    return sorted(os.listdir(root)) if os.path.isdir(root) else []


def profile_row(user_id):
    db.session.expire_all()
    return db.session.get(RbUserProfile, user_id)


@pytest.fixture
def ana(app, make_user):
    return make_user('ana')


@pytest.fixture
def ana_client(app, ana):
    return login_as(app.test_client(), 'ana')


# --- S3/S6/S8: upload ----------------------------------------------------------------

class TestUpload:
    def test_the_url_appears_in_the_session_and_me(self, avatar_dir, ana, ana_client):
        response = upload(ana_client, image_bytes())
        assert response.status_code == 200
        url = f'{API}/users/{ana.id}/avatar?v=1'
        assert response.get_json() == {'success': True, 'data': {'avatar_url': url}}
        assert ana_client.get(SESSION).get_json()['data']['user']['avatar_url'] == url
        me = ana_client.get(ME).get_json()['data']
        assert me['user']['avatar_url'] == url
        assert me['profile']['avatar_url'] == url
        assert files_in(avatar_dir) == [f'{ana.id}-1-256.webp', f'{ana.id}-1-64.webp']

    def test_a_new_upload_bumps_the_version_and_deletes_the_old_files(self, avatar_dir, ana,
                                                                      ana_client):
        upload(ana_client, image_bytes())
        response = upload(ana_client, image_bytes('JPEG', color=(200, 20, 20)), 'b.jpg',
                          'image/jpeg')
        url = f'{API}/users/{ana.id}/avatar?v=2'
        assert response.get_json()['data'] == {'avatar_url': url}
        assert ana_client.get(SESSION).get_json()['data']['user']['avatar_url'] == url
        assert files_in(avatar_dir) == [f'{ana.id}-2-256.webp', f'{ana.id}-2-64.webp']

    def test_the_name_and_content_type_of_the_part_are_ignored(self, avatar_dir, ana_client):
        assert upload(ana_client, image_bytes(), 'notes.txt', 'text/plain').status_code == 200
        response = upload(ana_client, b'plain text, not an image\n' * 20, 'photo.jpg',
                          'image/jpeg')
        assert response.status_code == 400
        assert response.get_json() == IMAGE_INVALID

    def test_a_refused_image_writes_nothing(self, avatar_dir, ana, ana_client):
        response = upload(ana_client, image_bytes(size=(63, 300)))
        assert response.status_code == 400
        assert response.get_json() == IMAGE_INVALID
        assert profile_row(ana.id) is None
        assert files_in(avatar_dir) == []
        assert ana_client.get(SESSION).get_json()['data']['user']['avatar_url'] is None

    def test_exactly_5_mb_is_accepted(self, avatar_dir, ana_client):
        blob = padded_png(MAX_FILE)
        assert len(blob) == 5_242_880
        assert upload(ana_client, blob).status_code == 200

    def test_one_byte_more_is_refused(self, avatar_dir, ana, ana_client):
        response = upload(ana_client, padded_png(MAX_FILE + 1))
        assert response.status_code == 413
        assert response.get_json() == TOO_LARGE
        assert profile_row(ana.id) is None
        assert files_in(avatar_dir) == []

    @pytest.mark.parametrize('with_csrf', [False, True])
    def test_an_oversized_body_is_refused_before_it_is_read(self, app, avatar_dir, ana,
                                                            with_csrf):
        """S3: Content-Length over 5 MB + 64 KB is a 413 without reading one byte, also when
        the CSRF check (which reads the form) runs first."""
        if with_csrf:
            app.config['WTF_CSRF_ENABLED'] = True
        try:
            client = login_as(app.test_client(), 'ana')
            reads = []

            class Body(io.RawIOBase):
                """A body that claims MAX_BODY + 1 bytes and records every read."""
                position, size = 0, MAX_BODY + 1

                def readable(self):
                    return True

                def seekable(self):
                    return True

                def tell(self):
                    return self.position

                def seek(self, offset, whence=0):
                    self.position = self.size if whence == 2 else offset
                    return self.position

                def readinto(self, buffer):
                    reads.append(len(buffer))
                    return 0
            headers = {'X-CSRFToken': api_csrf_token(client)} if with_csrf else {}
            response = client.post(AVATAR, input_stream=Body(),
                                   content_type='multipart/form-data; boundary=x',
                                   headers=headers)
        finally:
            app.config['WTF_CSRF_ENABLED'] = False
        assert response.status_code == 413
        assert response.get_json() == TOO_LARGE
        assert reads == []
        assert profile_row(ana.id) is None

    @pytest.mark.parametrize('kwargs', [
        {'data': {}},
        {'data': {'avatar': (io.BytesIO(b'x'), 'a.png', 'image/png')}},
        {'data': {'file': 'not a file part'}},
    ])
    def test_without_a_file_part_it_is_a_validation_error(self, avatar_dir, ana_client, kwargs):
        response = ana_client.post(AVATAR, content_type='multipart/form-data', **kwargs)
        assert response.status_code == 400
        assert response.get_json() == {
            'success': False, 'error': 'Validation Error', 'message': 'Invalid request data',
            'code': 'validation_error',
            'details': [{'field': 'file', 'message': 'Field required', 'type': 'missing',
                         'code': 'required'}]}

    def test_the_limit_is_20_per_hour(self, limited_app, avatar_dir, ana_client):
        for _ in range(20):
            assert ana_client.post(AVATAR, data={}).status_code == 400
        response = ana_client.post(AVATAR, data={})
        assert response.status_code == 429
        assert response.get_json()['code'] == 'rate_limited'
        assert 'Retry-After' in response.headers

    def test_anonymous_is_refused(self, avatar_dir, client):
        response = upload(client, image_bytes())
        assert response.status_code == 401
        assert response.get_json()['code'] == 'unauthenticated'
        assert files_in(avatar_dir) == []


# --- S7: delete ----------------------------------------------------------------------

class TestDelete:
    def test_delete_clears_the_url_and_the_files(self, avatar_dir, ana, ana_client):
        upload(ana_client, image_bytes())
        response = ana_client.delete(AVATAR)
        assert response.status_code == 200
        assert response.get_json() == {'success': True, 'data': {'avatar_url': None}}
        assert files_in(avatar_dir) == []
        assert ana_client.get(SESSION).get_json()['data']['user']['avatar_url'] is None
        assert ana_client.get(ME).get_json()['data']['profile']['avatar_url'] is None
        assert profile_row(ana.id).rbupf_avatar_version == 2

    def test_delete_twice_answers_the_same_and_changes_nothing(self, avatar_dir, ana,
                                                               ana_client):
        upload(ana_client, image_bytes())
        ana_client.delete(AVATAR)
        stamp = profile_row(ana.id).rbupf_updated_at
        response = ana_client.delete(AVATAR)
        assert response.status_code == 200
        assert response.get_json() == {'success': True, 'data': {'avatar_url': None}}
        row = profile_row(ana.id)
        assert (row.rbupf_avatar_version, row.rbupf_updated_at) == (2, stamp)

    def test_delete_without_any_profile_creates_nothing(self, avatar_dir, ana, ana_client):
        response = ana_client.delete(AVATAR)
        assert response.get_json() == {'success': True, 'data': {'avatar_url': None}}
        assert profile_row(ana.id) is None
        assert not avatar_dir.exists()

    def test_a_cached_url_changes_after_delete_and_upload(self, avatar_dir, ana, ana_client):
        first = upload(ana_client, image_bytes()).get_json()['data']['avatar_url']
        ana_client.delete(AVATAR)
        again = upload(ana_client, image_bytes()).get_json()['data']['avatar_url']
        assert (first, again) == (f'{API}/users/{ana.id}/avatar?v=1',
                                  f'{API}/users/{ana.id}/avatar?v=3')


# --- S9: serving ---------------------------------------------------------------------

class TestServe:
    @pytest.fixture
    def with_avatar(self, avatar_dir, ana, ana_client):
        upload(ana_client, image_bytes())
        return ana

    @pytest.fixture
    def bob_client(self, app, make_user):
        make_user('bob')
        return login_as(app.test_client(), 'bob')

    def url(self, user, query=''):
        return f'{API}/users/{user.id}/avatar{query}'

    @pytest.mark.parametrize('query, size', [('', 256), ('?size=256', 256), ('?size=64', 64)])
    def test_another_signed_in_user_reads_it(self, with_avatar, bob_client, query, size):
        response = bob_client.get(self.url(with_avatar, query))
        assert response.status_code == 200
        assert response.mimetype == 'image/webp'
        assert response.headers['X-Content-Type-Options'] == 'nosniff'
        image = Image.open(io.BytesIO(response.get_data()))
        assert (image.format, image.size) == ('WEBP', (size, size))

    def test_anonymous_gets_a_401_never_the_image(self, with_avatar, client):
        response = client.get(self.url(with_avatar, '?v=1'))
        assert response.status_code == 401
        assert response.mimetype == 'application/json'
        assert response.get_json()['code'] == 'unauthenticated'

    @pytest.mark.parametrize('size', ['128', '', 'abc', '64x64', '256.0'])
    def test_any_other_size_is_a_validation_error(self, with_avatar, bob_client, size):
        response = bob_client.get(self.url(with_avatar, f'?size={size}'))
        assert response.status_code == 400
        body = response.get_json()
        assert body['code'] == 'validation_error'
        assert [item['field'] for item in body['details']] == ['size']

    def test_an_unknown_user_is_a_404(self, with_avatar, bob_client):
        response = bob_client.get(f'{API}/users/9999/avatar')
        assert response.status_code == 404
        assert response.get_json()['success'] is False
        assert response.get_json()['error'] == 'Not Found'

    def test_a_user_without_avatar_is_a_404(self, avatar_dir, ana, bob_client):
        assert bob_client.get(self.url(ana)).status_code == 404

    def test_a_removed_avatar_is_a_404(self, with_avatar, ana_client, bob_client):
        ana_client.delete(AVATAR)
        assert bob_client.get(self.url(with_avatar, '?v=1')).status_code == 404

    def test_the_current_version_is_cached_for_a_year(self, with_avatar, bob_client):
        response = bob_client.get(self.url(with_avatar, '?v=1&size=64'))
        assert response.headers['Cache-Control'] == 'private, max-age=31536000, immutable'

    @pytest.mark.parametrize('query', ['', '?v=0', '?v=2', '?v=abc', '?v='])
    def test_a_stale_or_missing_version_is_not_cached(self, with_avatar, bob_client, query):
        response = bob_client.get(self.url(with_avatar, query))
        assert response.status_code == 200
        assert response.headers['Cache-Control'] == 'private, no-cache'

    def test_never_public(self, with_avatar, ana_client, bob_client):
        for client in (ana_client, bob_client):
            for query in ('?v=1', '?v=7', ''):
                response = client.get(self.url(with_avatar, query))
                assert 'public' not in response.headers['Cache-Control']
                assert 'Expires' not in response.headers
