"""Settings read from the environment (`config.py`).

M-d S1: CARD_IMAGES_DIR. F14-d S1: PRODUCT_IMAGES_DIR.
"""
from pathlib import Path

import pytest

from app import create_app
from config import ConfigError, load_settings

PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_IMAGES_DIR = str(PROJECT_DIR / 'data' / 'card-images')


def _app_from_env(clean_env, value=None):
    clean_env.setenv('RB_ENV', 'testing')
    if value is not None:
        clean_env.setenv('CARD_IMAGES_DIR', value)
    return create_app(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
                      SECRET_KEY='test-secret-key')


class TestCardImagesDir:
    @pytest.mark.parametrize('value', [None, '', '   '])
    def test_unset_or_blank_is_data_card_images_in_the_project(self, clean_env, value):
        app = _app_from_env(clean_env, value)
        assert app.config['CARD_IMAGES_DIR'] == DEFAULT_IMAGES_DIR

    def test_an_absolute_path_is_used_stripped(self, clean_env, tmp_path):
        app = _app_from_env(clean_env, f'  {tmp_path / "images"}  ')
        assert app.config['CARD_IMAGES_DIR'] == str(tmp_path / 'images')

    def test_the_directory_is_not_created_at_startup(self, clean_env, tmp_path):
        _app_from_env(clean_env, str(tmp_path / 'images'))
        assert not (tmp_path / 'images').exists()

    @pytest.mark.parametrize('value', ['card-images', './data/card-images', '~/card-images',
                                       'data/../card-images'])
    def test_a_relative_path_stops_the_app(self, clean_env, value):
        with pytest.raises(ConfigError) as err:
            _app_from_env(clean_env, value)
        assert str(err.value) == 'CARD_IMAGES_DIR must be an absolute path'

    @pytest.mark.parametrize('env', ['development', 'testing', 'production'])
    def test_the_rule_holds_in_every_environment(self, env, tmp_path):
        with pytest.raises(ConfigError, match='^CARD_IMAGES_DIR must be an absolute path$'):
            load_settings(env, {'CARD_IMAGES_DIR': 'relative'})
        assert load_settings(env, {})['CARD_IMAGES_DIR'] == DEFAULT_IMAGES_DIR
        assert load_settings(env, {'CARD_IMAGES_DIR': str(tmp_path)})['CARD_IMAGES_DIR'] == str(tmp_path)


# ---------------------------------------------------------------------------
# F14-d S1: PRODUCT_IMAGES_DIR, same rules as CARD_IMAGES_DIR
# ---------------------------------------------------------------------------

DEFAULT_PRODUCT_IMAGES_DIR = str(PROJECT_DIR / 'data' / 'product-images')


def _app_with_product_dir(clean_env, value=None):
    clean_env.setenv('RB_ENV', 'testing')
    if value is not None:
        clean_env.setenv('PRODUCT_IMAGES_DIR', value)
    return create_app(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
                      SECRET_KEY='test-secret-key')


class TestProductImagesDir:
    @pytest.mark.parametrize('value', [None, '', '   '])
    def test_unset_or_blank_is_data_product_images_in_the_project(self, clean_env, value):
        app = _app_with_product_dir(clean_env, value)
        assert app.config['PRODUCT_IMAGES_DIR'] == DEFAULT_PRODUCT_IMAGES_DIR

    def test_an_absolute_path_is_used_stripped(self, clean_env, tmp_path):
        app = _app_with_product_dir(clean_env, f'  {tmp_path / "products"}  ')
        assert app.config['PRODUCT_IMAGES_DIR'] == str(tmp_path / 'products')

    def test_the_directory_is_not_created_at_startup(self, clean_env, tmp_path):
        _app_with_product_dir(clean_env, str(tmp_path / 'products'))
        assert not (tmp_path / 'products').exists()

    @pytest.mark.parametrize('value', ['product-images', './data/product-images',
                                       '~/product-images', 'data/../product-images'])
    def test_a_relative_path_stops_the_app(self, clean_env, value):
        with pytest.raises(ConfigError) as err:
            _app_with_product_dir(clean_env, value)
        assert str(err.value) == 'PRODUCT_IMAGES_DIR must be an absolute path'

    @pytest.mark.parametrize('env', ['development', 'testing', 'production'])
    def test_the_rule_holds_in_every_environment(self, env, tmp_path):
        with pytest.raises(ConfigError, match='^PRODUCT_IMAGES_DIR must be an absolute path$'):
            load_settings(env, {'PRODUCT_IMAGES_DIR': 'relative'})
        assert load_settings(env, {})['PRODUCT_IMAGES_DIR'] == DEFAULT_PRODUCT_IMAGES_DIR
        assert load_settings(env, {'PRODUCT_IMAGES_DIR': str(tmp_path)})[
            'PRODUCT_IMAGES_DIR'] == str(tmp_path)

    def test_it_is_independent_of_card_images_dir(self, tmp_path):
        settings = load_settings('testing', {'CARD_IMAGES_DIR': str(tmp_path / 'cards')})
        assert settings['CARD_IMAGES_DIR'] == str(tmp_path / 'cards')
        assert settings['PRODUCT_IMAGES_DIR'] == DEFAULT_PRODUCT_IMAGES_DIR
        with pytest.raises(ConfigError, match='^CARD_IMAGES_DIR must be an absolute path$'):
            load_settings('testing', {'CARD_IMAGES_DIR': 'rel',
                                      'PRODUCT_IMAGES_DIR': str(tmp_path)})
