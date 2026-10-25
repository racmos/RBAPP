"""F13-b S9 (AC3): admin card image upload."""
import io

import pytest

from app import db
from app.models.audit import RbAdminAudit
from app.models.card import RbCard
from app.models.set import RbSet

URL = '/riftbound/api/v1/admin/cards'
PNG = (b'\x89PNG\r\n\x1a\n' + b'card-image-bytes' * 100)[:5000]
JPG = b'\xff\xd8\xff' + b'card-image-bytes' * 100
WEBP = b'RIFF\x00\x00\x00\x00WEBPVP8 ' + b'card-image-bytes' * 100


@pytest.fixture
def catalog(app, card_images_dir):
    db.session.add(RbSet(rbset_id='OGN', rbset_name='Origen', rbset_ncard=2))
    db.session.add_all([
        RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='With Image',
               image='ogn_1.png'),
        RbCard(rbcar_rbset_id='OGN', rbcar_id='2', rbcar_name='No Image', image=None),
    ])
    db.session.commit()
    return app


def payload(resp):
    return resp.get_json()


def upload(client, set_id, card_id, data, filename):
    return client.post(f'{URL}/{set_id}/{card_id}/image',
                       data={'file': (io.BytesIO(data), filename)},
                       content_type='multipart/form-data')


class TestUpload:
    @pytest.mark.parametrize('data, filename, ext', [
        (PNG, 'scan.png', 'png'), (JPG, 'photo.jpg', 'jpg'), (WEBP, 'art.webp', 'webp'),
        (JPG, 'renamed.txt', 'jpg'),  # the extension follows the magic bytes, not the name
    ])
    def test_type_comes_from_the_magic_bytes(self, admin_client, catalog,
                                             card_images_dir, data, filename, ext):
        resp = upload(admin_client, 'OGN', '1', data, filename)
        assert resp.status_code == 200
        body = payload(resp)
        assert body['data']['image'] == f'ogn_1.{ext}'
        stored = card_images_dir / 'ogn' / f'ogn_1.{ext}'
        assert stored.is_file() and stored.read_bytes()[:8] == data[:8]
        row = RbAdminAudit.query.one()
        assert row.rbaud_action == 'card.image'
        assert row.rbaud_details == {'image': f'ogn_1.{ext}', 'bytes': len(data)}

    def test_stem_rule_without_a_current_image(self, admin_client, catalog, card_images_dir):
        resp = upload(admin_client, 'OGN', '2', PNG, 'whatever.png')
        assert payload(resp)['data']['image'] == 'ogn_2.png'
        assert (card_images_dir / 'ogn' / 'ogn_2.png').is_file()

    def test_wrong_type_is_400(self, admin_client, catalog):
        resp = upload(admin_client, 'OGN', '1', b'GIF89a' + b'x' * 100, 'anim.gif')
        assert resp.status_code == 400
        assert any(d['field'] == 'file' and d['code'] == 'invalid_format'
                   for d in payload(resp)['details'])

    def test_over_2mb_is_400(self, admin_client, catalog, card_images_dir):
        big = b'\x89PNG\r\n\x1a\n' + b'x' * 2_097_152
        resp = upload(admin_client, 'OGN', '1', big, 'big.png')
        assert resp.status_code == 400
        body = payload(resp)
        assert any(d['field'] == 'file' and d['code'] == 'out_of_range'
                   and d['params'] == {'max': 2097152} for d in body['details'])
        assert not (card_images_dir / 'ogn').exists()

    def test_unknown_card_is_404(self, admin_client, catalog):
        assert upload(admin_client, 'OGN', '999', PNG, 'x.png').status_code == 404

    def test_a_plain_user_gets_403(self, authenticated_client, catalog):
        assert upload(authenticated_client, 'OGN', '1', PNG, 'x.png').status_code == 403
