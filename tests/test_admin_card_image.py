"""F13-b S9 (AC3), F13-h S4, S5, S7, S8 (AC2-AC4): admin card image upload.

Every upload is decoded, fitted inside 640 x 894 and stored as `<set>_<id>.webp` (`-<n>` when
the name exists); the previous file stays until the Undo expires or the next upload. Images are
made in memory; files land only in the `card_images_dir` fixture.
"""
import io

import pytest

from app import db
from app.models.audit import RbAdminAudit
from app.models.card import RbCard
from app.models.set import RbSet
from tests.image_helpers import (encode, exif_with_gps, jpeg, noise_png, opened, png, solid,
                                 webp)

URL = '/riftbound/api/v1/admin/cards'
OLD = png((300, 420))


@pytest.fixture
def catalog(app, card_images_dir):
    db.session.add_all([RbSet(rbset_id='OGN', rbset_name='Origen', rbset_ncard=2),
                        RbSet(rbset_id='OGNX', rbset_name='Origen promos', rbset_ncard=1)])
    db.session.add_all([
        RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='With Image',
               image='ogn_1.png'),
        RbCard(rbcar_rbset_id='OGN', rbcar_id='2', rbcar_name='No Image', image=None),
        RbCard(rbcar_rbset_id='OGNX', rbcar_id='257', rbcar_name='Promo', image='ogn_257.png'),
    ])
    db.session.commit()
    (card_images_dir / 'ogn').mkdir(parents=True)
    (card_images_dir / 'ogn' / 'ogn_1.png').write_bytes(OLD)
    return app


def payload(resp):
    return resp.get_json()


def card(set_id, card_id):
    db.session.expire_all()
    return db.session.get(RbCard, (set_id, card_id))


def files(root, folder='ogn'):
    path = root / folder
    return sorted(p.name for p in path.iterdir()) if path.exists() else []


def upload(client, set_id, card_id, data, filename='scan.png'):
    return client.post(f'{URL}/{set_id}/{card_id}/image',
                       data={'file': (io.BytesIO(data), filename)},
                       content_type='multipart/form-data')


class TestUpload:
    @pytest.mark.parametrize('data, filename', [
        (png((1280, 1788)), 'scan.png'), (jpeg((1280, 1788)), 'photo.jpg'),
        (webp((1280, 1788)), 'art.webp'),
        (jpeg((1280, 1788)), 'renamed.txt'),  # the type follows the magic bytes, not the name
    ], ids=['png', 'jpeg', 'webp', 'renamed'])
    def test_every_format_is_stored_as_set_id_webp(self, admin_client, catalog,
                                                   card_images_dir, data, filename):
        resp = upload(admin_client, 'OGN', '2', data, filename)
        assert resp.status_code == 200
        body = payload(resp)['data']
        stored = card_images_dir / 'ogn' / 'ogn_2.webp'
        assert body['image'] == 'ogn_2.webp'
        assert body['image_src'] == '/riftbound/media/cards/ogn/ogn_2.webp'
        assert body['has_image'] is True
        assert (body['width'], body['height']) == (640, 894)
        assert body['bytes'] == stored.stat().st_size
        assert body['previous'] is None
        assert opened(stored.read_bytes()).format == 'WEBP'
        assert card('OGN', '2').image == 'ogn_2.webp'
        row = RbAdminAudit.query.one()
        assert (row.rbaud_action, row.rbaud_target_type, row.rbaud_target_id) == (
            'card.image', 'card', 'OGN-2')
        assert row.rbaud_details == {'image': 'ogn_2.webp', 'bytes_in': len(data),
                                     'bytes_out': stored.stat().st_size,
                                     'width': 640, 'height': 894}

    def test_a_3000_by_4200_png_becomes_at_most_640_by_894_without_metadata(
            self, admin_client, catalog, card_images_dir):
        """AC2."""
        blob = encode(solid((3000, 4200)), 'PNG', exif=exif_with_gps(1))
        body = payload(upload(admin_client, 'OGN', '2', blob))['data']
        image = opened((card_images_dir / 'ogn' / 'ogn_2.webp').read_bytes())
        assert image.size == (body['width'], body['height'])
        assert image.width <= 640 and image.height <= 894
        assert not image.getexif() and 'exif' not in image.info

    def test_the_previous_file_is_kept_at_upload(self, admin_client, catalog, card_images_dir):
        """S7 / AC2: the old file stays until the Undo expires."""
        body = payload(upload(admin_client, 'OGN', '1', png()))['data']
        assert (body['image'], body['previous']) == ('ogn_1.webp', 'ogn_1.png')
        assert files(card_images_dir) == ['ogn_1.png', 'ogn_1.webp']
        assert (card_images_dir / 'ogn' / 'ogn_1.png').read_bytes() == OLD

    def test_a_taken_name_gets_the_next_free_number(self, admin_client, catalog,
                                                    card_images_dir):
        """AC4: a re-upload never overwrites, so the browser never reuses the old URL."""
        (card_images_dir / 'ogn' / 'ogn_2.webp').write_bytes(b'the first upload')
        card('OGN', '2').image = 'ogn_2.webp'
        db.session.commit()
        body = payload(upload(admin_client, 'OGN', '2', png()))['data']
        assert (body['image'], body['previous']) == ('ogn_2-2.webp', 'ogn_2.webp')
        assert card('OGN', '2').image == 'ogn_2-2.webp'
        assert (card_images_dir / 'ogn' / 'ogn_2.webp').read_bytes() == b'the first upload'

    def test_a_name_taken_by_a_file_no_row_uses_is_skipped_too(self, admin_client, catalog,
                                                               card_images_dir):
        """The leftover file is never overwritten; being an older file of the card that no
        row names, it goes with the next-upload clean-up (S7)."""
        (card_images_dir / 'ogn' / 'ogn_2.webp').write_bytes(b'leftover')
        body = payload(upload(admin_client, 'OGN', '2', png()))['data']
        assert body['image'] == 'ogn_2-2.webp'
        assert files(card_images_dir) == ['ogn_1.png', 'ogn_2-2.webp']

    def test_the_next_upload_deletes_the_older_files_of_the_card(self, admin_client, catalog,
                                                                 card_images_dir):
        """S7: upload 1 keeps ogn_1.png for the Undo; upload 2 keeps ogn_1.webp (its previous)
        and deletes ogn_1.png, which no row uses."""
        upload(admin_client, 'OGN', '1', png())
        body = payload(upload(admin_client, 'OGN', '1', png()))['data']
        assert (body['image'], body['previous']) == ('ogn_1-2.webp', 'ogn_1.webp')
        assert files(card_images_dir) == ['ogn_1-2.webp', 'ogn_1.webp']

    def test_a_file_another_card_uses_is_never_deleted(self, admin_client, catalog,
                                                       card_images_dir):
        card('OGN', '2').image = 'ogn_1.png'
        db.session.commit()
        upload(admin_client, 'OGN', '1', png())
        upload(admin_client, 'OGN', '1', png())
        assert 'ogn_1.png' in files(card_images_dir)

    def test_a_promo_card_gets_its_own_folder(self, admin_client, catalog, card_images_dir):
        body = payload(upload(admin_client, 'OGNX', '257', png()))['data']
        assert body['image'] == 'ognx_257.webp'
        assert body['image_src'] == '/riftbound/media/cards/ognx/ognx_257.webp'
        assert files(card_images_dir, 'ognx') == ['ognx_257.webp']


class TestRefused:
    """AC3: refused with the right code, nothing written, the old image stays."""

    @pytest.mark.parametrize('data, code, params', [
        (b'plain text renamed to png' * 20, 'invalid_format', None),
        (encode(solid((10, 10)), 'GIF'), 'invalid_format', None),
        (None, 'out_of_range', {'max_pixels': 25_000_000}),            # 30 Mpx
        (None, 'out_of_range', {'max': 10 * 1024 * 1024}),             # 12 MB
        (png((100, 100)), 'too_small', {'min': 200}),
    ], ids=['text', 'gif', '30mpx', '12mb', 'tiny'])
    def test_refused_uploads(self, admin_client, catalog, card_images_dir, data, code, params):
        if data is None:
            data = (encode(solid((6000, 5000), color=0, mode='L'), 'PNG') if 'max_pixels' in params
                    else noise_png(12 * 1024 * 1024))
        resp = upload(admin_client, 'OGN', '1', data, 'fake.png')
        assert resp.status_code == 400
        body = payload(resp)
        assert body['code'] == 'validation_error'
        (detail,) = body['details']
        assert (detail['field'], detail['code'], detail.get('params')) == ('file', code, params)
        assert files(card_images_dir) == ['ogn_1.png']
        assert card('OGN', '1').image == 'ogn_1.png'
        assert RbAdminAudit.query.count() == 0

    def test_a_missing_part_is_required(self, admin_client, catalog):
        resp = admin_client.post(f'{URL}/OGN/1/image', data={},
                                 content_type='multipart/form-data')
        assert resp.status_code == 400
        assert payload(resp)['details'][0]['code'] == 'required'

    def test_unknown_card_is_404(self, admin_client, catalog):
        assert upload(admin_client, 'OGN', '999', png()).status_code == 404

    def test_a_plain_user_gets_403(self, authenticated_client, catalog, card_images_dir):
        assert upload(authenticated_client, 'OGN', '1', png()).status_code == 403
        assert files(card_images_dir) == ['ogn_1.png']

    def test_csrf_is_required(self, csrf_app, catalog, card_images_dir, admin_client):
        resp = upload(admin_client, 'OGN', '1', png())
        assert resp.status_code == 400
        assert payload(resp)['code'] == 'csrf_invalid'
        assert files(card_images_dir) == ['ogn_1.png']
