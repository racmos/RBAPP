"""F13-h S4, S5: the image upload service (decode, check, fit inside, WebP, names).

Images are made in memory with Pillow (`tests/image_helpers.py`); files only ever land in the
`card_images_dir` / `product_images_dir` fixtures. Nothing here reaches the network.
"""
import io

import pytest
from PIL import Image

from app import db
from app.models.card import RbCard
from app.models.set import RbSet
from app.services import image_upload
from app.services.image_upload import CARD, PRODUCT, ImageRejected
from tests.image_helpers import (BLUE, RED, close, encode, exif_with_gps, halves, jpeg,
                                 noise_png, opened, png, png_with_header_size, solid, webp)


def rejected(blob, profile=CARD):
    with pytest.raises(ImageRejected) as err:
        image_upload.process(blob, profile)
    return err.value.detail


class TestProcess:
    def test_a_big_card_fits_inside_640_by_894_keeping_the_ratio(self, app):
        out = image_upload.process(png((3000, 4200)), CARD)
        image = opened(out.data)
        assert image.format == 'WEBP'
        assert (out.width, out.height) == image.size
        assert out.width <= 640 and out.height <= 894
        assert out.height == 894 and out.width == 639          # 3000 x 4200 scaled by 894/4200
        assert out.bytes_out == len(out.data)

    def test_a_wide_product_fits_inside_640_by_640(self, app):
        out = image_upload.process(png((2000, 1000)), PRODUCT)
        assert (out.width, out.height) == (640, 320)

    @pytest.mark.parametrize('profile, size', [(CARD, (300, 420)), (PRODUCT, (150, 130))])
    def test_a_small_image_is_never_upscaled(self, app, profile, size):
        out = image_upload.process(png(size), profile)
        assert (out.width, out.height) == size

    @pytest.mark.parametrize('blob', [png(), jpeg(), webp()], ids=['png', 'jpeg', 'webp'])
    def test_png_jpeg_and_webp_are_accepted(self, app, blob):
        out = image_upload.process(blob, CARD)
        assert out.bytes_in == len(blob)
        assert opened(out.data).format == 'WEBP'

    def test_no_metadata_survives(self, app):
        blob = encode(solid((400, 560)), 'JPEG', exif=exif_with_gps(1))
        image = opened(image_upload.process(blob, CARD).data)
        assert 'exif' not in image.info
        assert 'icc_profile' not in image.info
        assert 'xmp' not in image.info
        assert not image.getexif()

    def test_the_exif_orientation_is_applied(self, app):
        """Orientation 6 = rotate 90 degrees clockwise to display: 560 x 400 stored -> 400 x 560
        upright, the red left half on top."""
        blob = encode(halves((560, 400), RED, BLUE), 'JPEG', exif=exif_with_gps(6), quality=95)
        image = opened(image_upload.process(blob, CARD).data).convert('RGB')
        assert image.size == (400, 560)
        assert close(image.getpixel((200, 40)), RED)
        assert close(image.getpixel((200, 520)), BLUE)

    def test_transparency_is_kept(self, app):
        blob = png((400, 560), (0, 0, 0, 0), mode='RGBA')
        assert opened(image_upload.process(blob, CARD).data).mode == 'RGBA'

    def test_webp_quality_85_method_6(self, app, monkeypatch):
        seen = []
        original = Image.Image.save

        def spy(self, fp, format=None, **params):
            seen.append((format, params))
            return original(self, fp, format, **params)
        blob = png()
        monkeypatch.setattr(Image.Image, 'save', spy)
        image_upload.process(blob, CARD)
        assert seen == [('WEBP', {'quality': 85, 'method': 6})]


class TestRejected:
    def test_a_text_file_renamed_png_is_invalid_format(self, app):
        assert rejected(b'just some text, not an image' * 10) == {
            'field': 'file', 'message': 'unsupported image type', 'type': 'value_error',
            'code': 'invalid_format'}

    @pytest.mark.parametrize('blob', [
        encode(solid(), 'GIF'), b'', b'<svg xmlns="http://www.w3.org/2000/svg"></svg>',
        png()[:200],                                   # PNG magic, damaged body
        b'\x89PNG\r\n\x1a\n' + b'x' * 300,             # PNG magic, no PNG at all
    ], ids=['gif', 'empty', 'svg', 'truncated-png', 'fake-png'])
    def test_other_or_damaged_files_are_invalid_format(self, app, blob):
        assert rejected(blob)['code'] == 'invalid_format'

    def test_over_25_megapixels_is_out_of_range(self, app):
        blob = encode(Image.new('L', (6000, 5000)), 'PNG')     # 30 Mpx, a small file
        assert rejected(blob) == {
            'field': 'file', 'message': 'image has too many pixels', 'type': 'value_error',
            'code': 'out_of_range', 'params': {'max_pixels': 25_000_000}}

    def test_a_header_over_25_megapixels_is_refused_before_decoding(self, app):
        assert rejected(png_with_header_size(5001, 5000))['params'] == {
            'max_pixels': 25_000_000}

    @pytest.mark.parametrize('side', [10_000, 20_000], ids=['bomb-warning', 'bomb-error'])
    def test_a_decompression_bomb_header_is_out_of_range_too(self, app, side):
        """Pillow warns over 89 Mpx and refuses over 179 Mpx while opening: same answer."""
        assert rejected(png_with_header_size(side, side))['params'] == {
            'max_pixels': 25_000_000}

    def test_over_10_mb_is_out_of_range(self, app):
        assert rejected(noise_png(12 * 1024 * 1024)) == {
            'field': 'file', 'message': 'file is too large', 'type': 'value_error',
            'code': 'out_of_range', 'params': {'max': 10 * 1024 * 1024}}

    @pytest.mark.parametrize('profile, size, minimum', [
        (CARD, (100, 100), 200), (CARD, (199, 900), 200), (PRODUCT, (119, 400), 120)])
    def test_a_short_side_under_the_minimum_is_too_small(self, app, profile, size, minimum):
        assert rejected(png(size), profile) == {
            'field': 'file', 'message': 'image is too small', 'type': 'value_error',
            'code': 'too_small', 'params': {'min': minimum}}

    @pytest.mark.parametrize('profile, size', [(CARD, (200, 200)), (PRODUCT, (120, 120))])
    def test_exactly_the_minimum_is_accepted(self, app, profile, size):
        assert image_upload.process(png(size), profile).width == size[0]


class TestNames:
    @pytest.mark.parametrize('set_id, card_id, stem', [
        ('OGN', '66', 'ogn_66'), ('OGNX', '66', 'ognx_66'), ('PLAT', 'sfd189', 'plat_sfd189'),
        ('SFD', '12A', 'sfd_12a')])
    def test_the_card_stem_is_set_and_id_lower_case(self, set_id, card_id, stem):
        assert image_upload.card_stem(set_id, card_id) == stem

    def test_a_free_name_skips_taken_names(self):
        taken = {'ogn_66.webp', 'ogn_66-2.webp'}
        assert image_upload.free_name('ogn_66', taken.__contains__) == 'ogn_66-3.webp'
        assert image_upload.free_name('ogn_7', taken.__contains__) == 'ogn_7.webp'


@pytest.fixture
def card(app, card_images_dir):
    db.session.add(RbSet(rbset_id='OGN', rbset_name='Origen', rbset_ncard=1))
    row = RbCard(rbcar_rbset_id='OGN', rbcar_id='66', rbcar_name='Card', image=None)
    db.session.add(row)
    db.session.commit()
    return row


class TestStore:
    def test_the_file_is_written_atomically_and_nothing_else_is_left(self, card,
                                                                     card_images_dir):
        stored = image_upload.store_card_image(card, png((900, 1260)))
        assert stored.image == 'ogn_66.webp' and stored.previous is None
        assert sorted(p.name for p in (card_images_dir / 'ogn').iterdir()) == ['ogn_66.webp']
        assert card.image == 'ogn_66.webp'

    def test_a_failed_write_leaves_no_temporary_file(self, card, card_images_dir,
                                                     monkeypatch):
        def broken(src, dst):
            raise OSError('disk full')
        monkeypatch.setattr(image_upload.os, 'replace', broken)
        with pytest.raises(OSError):
            image_upload.store_card_image(card, png())
        assert list((card_images_dir / 'ogn').iterdir()) == []
        assert card.image is None

    def test_a_rejected_image_writes_nothing(self, card, card_images_dir):
        with pytest.raises(ImageRejected):
            image_upload.store_card_image(card, io.BytesIO(b'x').getvalue())
        assert not card_images_dir.exists()
        assert card.image is None
