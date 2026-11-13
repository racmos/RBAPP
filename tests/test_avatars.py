"""Avatar service (F9-c S2, S4-S6): untrusted image parsing, processing and storage.

Images are made in memory with Pillow; the avatars live in the `avatar_dir` fixture (a
temporary folder), never in a real path. Nothing here reaches the network.
"""
import io
import logging
import os
import struct
import zlib

import pytest
from PIL import Image, ImageCms, ImageFile

from app import db
from app.models import RbUserProfile
from app.services import avatars
from app.services.avatars import ImageInvalid

RED = (220, 20, 20)
GREEN = (20, 200, 20)
BLUE = (20, 20, 220)


# --- helpers ------------------------------------------------------------------------

def encode(image, fmt, **params):
    buffer = io.BytesIO()
    image.save(buffer, fmt, **params)
    return buffer.getvalue()


def solid(size=(120, 120), color=GREEN, mode='RGB'):
    return Image.new(mode, size, color)


def stripes(size, colors, vertical=True):
    """Equal bands of `colors`: left to right when `vertical`, else top to bottom."""
    image = Image.new('RGB', size)
    width, height = size
    count = len(colors)
    for index, color in enumerate(colors):
        if vertical:
            box = (index * width // count, 0, (index + 1) * width // count, height)
        else:
            box = (0, index * height // count, width, (index + 1) * height // count)
        image.paste(color, box)
    return image


def png_with_header_size(width, height):
    """A real small PNG whose IHDR claims `width` x `height` (the pixel data stays small)."""
    data = bytearray(encode(solid((64, 64)), 'PNG'))
    ihdr = data.index(b'IHDR')
    data[ihdr + 4:ihdr + 12] = struct.pack('>II', width, height)
    crc = zlib.crc32(bytes(data[ihdr:ihdr + 17])) & 0xffffffff
    data[ihdr + 17:ihdr + 21] = struct.pack('>I', crc)
    return bytes(data)


def exif_with_gps(orientation):
    exif = Image.Exif()
    exif[0x0112] = orientation
    gps = exif.get_ifd(0x8825)
    gps[1], gps[2], gps[3], gps[4] = 'N', (40.0, 26.0, 0.0), 'W', (3.0, 42.0, 0.0)
    return exif


def close(pixel, color, tolerance=40):
    return all(abs(a - b) <= tolerance for a, b in zip(pixel[:3], color))


def decoded(blob):
    image = Image.open(io.BytesIO(blob))
    image.load()
    return image


def files_in(root):
    return sorted(os.listdir(root)) if os.path.isdir(root) else []


# --- S4: what is accepted -----------------------------------------------------------

class TestAcceptedFormats:
    @pytest.mark.parametrize('fmt', ['JPEG', 'PNG', 'WEBP', 'GIF'])
    def test_each_accepted_format_gives_two_webp_sizes(self, app, fmt):
        out = avatars.process_image(encode(solid((150, 100)), fmt))
        assert sorted(out) == [64, 256]
        for size, blob in out.items():
            image = decoded(blob)
            assert image.format == 'WEBP'
            assert image.size == (size, size)

    def test_the_format_comes_from_the_content_not_a_name(self, app):
        """There is no name or content type in the call: a PNG is a PNG whatever it is called."""
        assert sorted(avatars.process_image(encode(solid(), 'PNG'))) == [64, 256]

    def test_an_animated_gif_uses_its_first_frame(self, app):
        frames = [solid(color=RED), solid(color=BLUE)]
        blob = encode(frames[0], 'GIF', save_all=True, append_images=frames[1:], duration=100,
                      loop=0)
        assert Image.open(io.BytesIO(blob)).n_frames == 2
        image = decoded(avatars.process_image(blob)[256])
        assert close(image.getpixel((128, 128)), RED)
        assert getattr(image, 'n_frames', 1) == 1

    def test_exactly_64_px_is_accepted(self, app):
        assert sorted(avatars.process_image(encode(solid((64, 64)), 'PNG'))) == [64, 256]

    def test_an_image_with_alpha_stays_transparent(self, app):
        image = decoded(avatars.process_image(encode(solid(color=(0, 0, 0, 0), mode='RGBA'),
                                                     'PNG'))[256])
        assert image.mode == 'RGBA'
        assert image.getpixel((128, 128))[3] == 0

    def test_an_opaque_image_is_rgb(self, app):
        assert decoded(avatars.process_image(encode(solid(), 'JPEG'))[64]).mode == 'RGB'


# --- S4: what is refused ------------------------------------------------------------

class TestRefusedFiles:
    @pytest.mark.parametrize('blob', [
        pytest.param(encode(solid(), 'BMP'), id='bmp'),
        pytest.param(encode(solid(), 'TIFF'), id='tiff'),
        pytest.param(b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" '
                     b'width="200" height="200"><rect width="200" height="200"/></svg>', id='svg'),
        pytest.param(b'just some plain text, not an image at all\n' * 10, id='text'),
        pytest.param(b'', id='empty'),
        pytest.param(b'GIF89a' + b'\x00' * 50, id='garbage-after-a-gif-signature'),
        pytest.param(encode(solid(), 'PNG')[:16] + b'<?php echo 1; ?>' * 20,
                     id='polyglot-png-header-then-script'),
    ])
    def test_other_formats_and_garbage_are_refused(self, app, blob):
        with pytest.raises(ImageInvalid):
            avatars.process_image(blob)

    def test_a_truncated_jpeg_is_refused(self, app):
        blob = encode(stripes((300, 300), [RED, GREEN, BLUE]), 'JPEG', quality=95)
        with pytest.raises(ImageInvalid):
            avatars.process_image(blob[:len(blob) // 2])

    @pytest.mark.parametrize('size', [(63, 200), (200, 63), (63, 63)])
    def test_a_side_under_64_px_is_refused(self, app, size):
        with pytest.raises(ImageInvalid) as err:
            avatars.process_image(encode(solid(size), 'PNG'))
        assert err.value.reason == 'too_small'

    def test_a_header_over_25_megapixels_is_refused_before_decoding(self, app, monkeypatch):
        blob = png_with_header_size(5001, 5000)
        assert Image.open(io.BytesIO(blob)).size == (5001, 5000)

        def no_decode(self):
            raise AssertionError('the pixels must not be decoded')
        monkeypatch.setattr(ImageFile.ImageFile, 'load', no_decode)
        with pytest.raises(ImageInvalid) as err:
            avatars.process_image(blob)
        assert err.value.reason == 'too_many_pixels'

    def test_exactly_25_megapixels_passes_the_pixel_check(self, app):
        """5000 x 5000 is not over the limit; this header's pixel data is damaged instead."""
        with pytest.raises(ImageInvalid) as err:
            avatars.process_image(png_with_header_size(5000, 5000))
        assert err.value.reason == 'damaged'

    def test_the_decompression_bomb_warning_is_an_error(self, app, monkeypatch):
        """Pillow warns above MAX_IMAGE_PIXELS; the guard turns the warning into a refusal."""
        monkeypatch.setattr(Image, 'MAX_IMAGE_PIXELS', 10_000)       # 120 x 120 = 14,400
        with pytest.raises(ImageInvalid):
            avatars.process_image(encode(solid(), 'PNG'))


# --- S5: processing -----------------------------------------------------------------

class TestProcessing:
    def test_a_landscape_is_cropped_to_its_centre(self, app):
        image = decoded(avatars.process_image(
            encode(stripes((300, 100), [RED, GREEN, BLUE]), 'PNG'))[256])
        for x in (4, 128, 251):
            assert close(image.getpixel((x, 128)), GREEN), x

    def test_a_portrait_is_cropped_to_its_centre(self, app):
        image = decoded(avatars.process_image(
            encode(stripes((100, 300), [RED, GREEN, BLUE], vertical=False), 'PNG'))[256])
        for y in (4, 128, 251):
            assert close(image.getpixel((128, y)), GREEN), y

    def test_the_exif_orientation_is_applied(self, app):
        """Orientation 6 = rotate 90 degrees clockwise to display: the red left half of the
        stored 200 x 100 picture becomes the top half."""
        blob = encode(stripes((200, 100), [RED, BLUE]), 'JPEG', quality=95,
                      exif=exif_with_gps(6))
        image = decoded(avatars.process_image(blob)[256])
        assert close(image.getpixel((128, 30)), RED)
        assert close(image.getpixel((128, 226)), BLUE)

    def test_the_output_carries_no_metadata(self, app):
        """S5: a JPEG with GPS and orientation, a PNG with an ICC profile and text."""
        icc = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
        sources = [
            encode(stripes((200, 100), [RED, BLUE]), 'JPEG', exif=exif_with_gps(6),
                   icc_profile=icc),
            encode(solid(), 'PNG', icc_profile=icc, exif=exif_with_gps(1)),
            encode(solid(), 'WEBP', icc_profile=icc, exif=exif_with_gps(1),
                   xmp=b'<x:xmpmeta xmlns:x="adobe:ns:meta/"/>'),
        ]
        source = Image.open(io.BytesIO(sources[0]))
        assert source.getexif().get_ifd(0x8825)          # the upload really has GPS data
        for blob in sources:
            for out in avatars.process_image(blob).values():
                image = decoded(out)
                assert not image.getexif()
                for key in ('exif', 'icc_profile', 'xmp'):
                    assert key not in image.info, key
                for chunk in (b'EXIF', b'ICCP', b'XMP '):
                    assert chunk not in out, chunk


# --- S2: paths and URLs -------------------------------------------------------------

class TestPaths:
    def test_the_root_is_the_setting(self, app, avatar_dir):
        assert avatars.avatars_root() == str(avatar_dir)

    def test_a_path_is_stem_and_size_under_the_root(self, app, avatar_dir):
        assert avatars.avatar_path('7-3', 256) == os.path.join(
            os.path.realpath(avatar_dir), '7-3-256.webp')
        assert avatars.avatar_path('7-3', 64).endswith('7-3-64.webp')

    @pytest.mark.parametrize('stem', ['../7-3', '7-3/..', '7', 'a-1', '7-3\x00', '', '/7-3',
                                      '7--3', ' 7-3', None, 7])
    def test_a_stem_that_is_not_two_numbers_is_refused(self, app, avatar_dir, stem):
        with pytest.raises(ValueError):
            avatars.avatar_path(stem, 256)

    @pytest.mark.parametrize('size', [128, 0, '256', None])
    def test_only_the_two_sizes_exist(self, app, avatar_dir, size):
        with pytest.raises(ValueError):
            avatars.avatar_path('7-3', size)

    def test_a_symlink_out_of_the_root_is_refused(self, app, avatar_dir, tmp_path):
        avatar_dir.mkdir()
        (tmp_path / 'elsewhere').mkdir()
        os.symlink(tmp_path / 'elsewhere' / 'x.webp', avatar_dir / '7-3-256.webp')
        with pytest.raises(ValueError):
            avatars.avatar_path('7-3', 256)

    def test_the_url_is_the_versioned_api_path(self, app):
        assert avatars.avatar_url(7, 3) == '/riftbound/api/v1/users/7/avatar?v=3'


# --- S6/S7: storage -----------------------------------------------------------------

def _profile(user_id):
    db.session.expire_all()
    return db.session.get(RbUserProfile, user_id)


class TestStorage:
    def test_the_first_upload_creates_the_row_and_both_files(self, app, avatar_dir,
                                                             make_user):
        user = make_user('ana')
        url = avatars.save_avatar(user.id, encode(solid(), 'PNG'))
        assert url == f'/riftbound/api/v1/users/{user.id}/avatar?v=1'
        row = _profile(user.id)
        assert (row.rbupf_avatar_file, row.rbupf_avatar_version) == (f'{user.id}-1', 1)
        assert files_in(avatar_dir) == [f'{user.id}-1-256.webp', f'{user.id}-1-64.webp']

    def test_a_new_upload_replaces_the_files_of_the_previous_version(self, app, avatar_dir,
                                                                     make_user):
        user = make_user('ana')
        avatars.save_avatar(user.id, encode(solid(), 'PNG'))
        url = avatars.save_avatar(user.id, encode(solid(color=RED), 'JPEG'))
        assert url.endswith('?v=2')
        assert files_in(avatar_dir) == [f'{user.id}-2-256.webp', f'{user.id}-2-64.webp']
        assert _profile(user.id).rbupf_avatar_file == f'{user.id}-2'

    def test_the_version_continues_after_a_removal(self, app, avatar_dir, make_user):
        user = make_user('ana')
        avatars.save_avatar(user.id, encode(solid(), 'PNG'))
        avatars.remove_avatar(user.id)
        assert avatars.save_avatar(user.id, encode(solid(), 'PNG')).endswith('?v=3')

    def test_a_profile_without_avatar_keeps_its_fields(self, app, avatar_dir, make_user):
        from app.services import profile
        user = make_user('ana')
        profile.update_profile(user.id, {'display_name': 'Ana', 'city': 'Madrid'})
        avatars.save_avatar(user.id, encode(solid(), 'PNG'))
        row = _profile(user.id)
        assert (row.rbupf_display_name, row.rbupf_city) == ('Ana', 'Madrid')

    def test_a_refused_file_writes_nothing(self, app, avatar_dir, make_user):
        user = make_user('ana')
        with pytest.raises(ImageInvalid):
            avatars.save_avatar(user.id, b'not an image')
        assert _profile(user.id) is None
        assert files_in(avatar_dir) == []

    def test_a_refusal_keeps_the_current_avatar(self, app, avatar_dir, make_user):
        user = make_user('ana')
        avatars.save_avatar(user.id, encode(solid(), 'PNG'))
        with pytest.raises(ImageInvalid):
            avatars.save_avatar(user.id, encode(solid((63, 63)), 'PNG'))
        assert _profile(user.id).rbupf_avatar_version == 1
        assert files_in(avatar_dir) == [f'{user.id}-1-256.webp', f'{user.id}-1-64.webp']

    def test_temporary_files_are_never_left_behind(self, app, avatar_dir, make_user,
                                                   monkeypatch):
        user = make_user('ana')
        avatars.save_avatar(user.id, encode(solid(), 'PNG'))
        real_replace = os.replace
        calls = []

        def failing_replace(src, dst):
            calls.append(dst)
            if len(calls) == 2:
                raise OSError('disk full')
            return real_replace(src, dst)
        monkeypatch.setattr(avatars.os, 'replace', failing_replace)
        with pytest.raises(OSError):
            avatars.save_avatar(user.id, encode(solid(color=RED), 'PNG'))
        assert files_in(avatar_dir) == [f'{user.id}-1-256.webp', f'{user.id}-1-64.webp']
        assert _profile(user.id).rbupf_avatar_version == 1

    def test_a_failed_commit_removes_the_new_files(self, app, avatar_dir, make_user,
                                                   monkeypatch):
        user = make_user('ana')

        def failing_commit():
            raise RuntimeError('database gone')
        monkeypatch.setattr(db.session, 'commit', failing_commit)
        with pytest.raises(RuntimeError):
            avatars.save_avatar(user.id, encode(solid(), 'PNG'))
        assert files_in(avatar_dir) == []

    def test_a_failure_to_delete_old_files_is_logged_not_raised(self, app, avatar_dir,
                                                                make_user, monkeypatch,
                                                                caplog):
        user = make_user('ana')
        avatars.save_avatar(user.id, encode(solid(), 'PNG'))

        def failing_remove(path):
            raise PermissionError('read-only')
        monkeypatch.setattr(avatars.os, 'remove', failing_remove)
        with caplog.at_level(logging.WARNING):
            url = avatars.save_avatar(user.id, encode(solid(color=RED), 'PNG'))
        assert url.endswith('?v=2')
        assert 'could not delete' in caplog.text
        assert _profile(user.id).rbupf_avatar_version == 2

    def test_remove_clears_the_file_bumps_the_version_and_deletes(self, app, avatar_dir,
                                                                  make_user):
        user = make_user('ana')
        avatars.save_avatar(user.id, encode(solid(), 'PNG'))
        avatars.remove_avatar(user.id)
        row = _profile(user.id)
        assert (row.rbupf_avatar_file, row.rbupf_avatar_version) == (None, 2)
        assert files_in(avatar_dir) == []

    def test_remove_without_an_avatar_changes_nothing(self, app, avatar_dir, make_user):
        from app.services import profile
        user = make_user('ana')
        avatars.remove_avatar(user.id)
        assert _profile(user.id) is None
        profile.update_profile(user.id, {'city': 'Madrid'})
        stamp = _profile(user.id).rbupf_updated_at
        avatars.remove_avatar(user.id)
        row = _profile(user.id)
        assert (row.rbupf_avatar_version, row.rbupf_updated_at) == (0, stamp)
        assert not avatar_dir.exists()

    def test_stored_avatar_gives_the_file_and_version(self, app, avatar_dir, make_user):
        user = make_user('ana')
        assert avatars.stored_avatar(user.id, 256) is None
        avatars.save_avatar(user.id, encode(solid(), 'PNG'))
        path, version = avatars.stored_avatar(user.id, 64)
        assert (os.path.basename(path), version) == (f'{user.id}-1-64.webp', 1)
        os.remove(path)
        assert avatars.stored_avatar(user.id, 64) is None
