"""Product images in PRODUCT_IMAGES_DIR (F14-d S1, S4).

Every test points PRODUCT_IMAGES_DIR at a temporary folder (`product_images_dir`):
nothing here reads or writes real images.
"""
import pytest

from app import db
from app.services.product_images import images_root, product_image_path, product_image_url
from app.services.product_list import product_summary
from tests.product_helpers import add_product


class TestImagesRoot:
    def test_it_is_the_setting(self, product_images_dir):
        assert images_root() == str(product_images_dir)

    def test_it_is_not_the_card_images_root(self, product_images_dir, card_images_dir):
        assert images_root() != str(card_images_dir)


class TestProductImagePath:
    def test_the_path_is_root_file(self, product_images_dir):
        assert product_image_path('42.png') == str(product_images_dir / '42.png')

    def test_nothing_is_created(self, product_images_dir):
        product_image_path('42.png')
        assert not product_images_dir.exists()

    @pytest.mark.parametrize('name', [
        '', '.', '..',
        '../42.png', '..\\42.png',
        'sub/42.png', '/etc/42.png', 'sub\\42.png',
        '42.png\x00', '42\x00.png',
        '42.png\n', '42.png\r', '42.png\r\nSet-Cookie: evil=1',
        None,
    ])
    def test_anything_but_a_plain_file_name_is_refused(self, product_images_dir, name):
        with pytest.raises(ValueError, match='^the image name must be a plain file name$'):
            product_image_path(name)

    def test_a_file_symlinked_outside_the_root_is_refused(self, product_images_dir, tmp_path):
        product_images_dir.mkdir()
        (tmp_path / 'secret.txt').write_bytes(b'secret')
        (product_images_dir / '42.png').symlink_to(tmp_path / 'secret.txt')
        with pytest.raises(ValueError,
                           match='^the image path escapes the product images folder$'):
            product_image_path('42.png')

    def test_a_root_that_is_a_symlink_is_followed(self, product_images_dir, tmp_path):
        (tmp_path / 'real').mkdir()
        product_images_dir.symlink_to(tmp_path / 'real', target_is_directory=True)
        assert product_image_path('42.png') == str(tmp_path / 'real' / '42.png')


class TestProductImageUrl:
    @pytest.mark.parametrize('name, expected', [
        ('42.png', '/riftbound/media/products/42.png'),
        ('7.webp', '/riftbound/media/products/7.webp'),
        ('', None),
        (None, None),
        ('../42.png', None),
        ('sub/42.png', None),
    ])
    def test_the_media_url_or_none(self, name, expected):
        assert product_image_url(name) == expected


class TestSummaryImageSrc:
    def _product(self, image):
        add_product(42, 'Origins Booster')
        db.session.commit()
        from app.models import RbProducts
        product = db.session.get(RbProducts, 42)
        product.rbpdt_image = image
        return product

    def test_image_src_is_the_media_url_when_set(self, app):
        summary = product_summary(self._product('42.png'), price=None, owned_qty=0)
        assert summary['image_src'] == '/riftbound/media/products/42.png'

    @pytest.mark.parametrize('image', [None, ''])
    def test_image_src_is_null_without_an_image(self, app, image):
        summary = product_summary(self._product(image), price=None, owned_qty=0)
        assert summary['image_src'] is None

    def test_the_key_order_is_unchanged(self, app):
        summary = product_summary(self._product('42.png'), price=None, owned_qty=0)
        assert list(summary) == ['id', 'name', 'kind', 'category', 'set_id', 'image_src',
                                 'listed', 'price', 'owned_qty']
