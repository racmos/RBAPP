"""
Characterization tests for card image paths (IMG-1).

They pin the behavior introduced by commit 1ae1f6e: the image folder comes
from the filename prefix (text before the last '_'), NOT from the set id.
They must pass on the unchanged code and keep passing after unit c moves the
rule into `card_image_folder` (`_image_folder` stays as an alias).
"""
import pytest

from app.models.card import RbCard, _image_folder

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
