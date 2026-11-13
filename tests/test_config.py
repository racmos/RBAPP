"""Settings read from the environment (`config.py`).

M-d S1: CARD_IMAGES_DIR. F14-d S1: PRODUCT_IMAGES_DIR. F9-c S2: AVATAR_DIR.
F9-d S2: TOTP_ENCRYPTION_KEY.
"""
from pathlib import Path

import pytest

from app import create_app
from config import ConfigError, load_settings, validate_settings

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


# ---------------------------------------------------------------------------
# F9-c S2: AVATAR_DIR, same rules as CARD_IMAGES_DIR
# ---------------------------------------------------------------------------

DEFAULT_AVATAR_DIR = str(PROJECT_DIR / 'data' / 'avatars')


def _app_with_avatar_dir(clean_env, value=None):
    clean_env.setenv('RB_ENV', 'testing')
    if value is not None:
        clean_env.setenv('AVATAR_DIR', value)
    return create_app(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
                      SECRET_KEY='test-secret-key')


class TestAvatarDir:
    @pytest.mark.parametrize('value', [None, '', '   '])
    def test_unset_or_blank_is_data_avatars_in_the_project(self, clean_env, value):
        app = _app_with_avatar_dir(clean_env, value)
        assert app.config['AVATAR_DIR'] == DEFAULT_AVATAR_DIR

    def test_an_absolute_path_is_used_stripped(self, clean_env, tmp_path):
        app = _app_with_avatar_dir(clean_env, f'  {tmp_path / "avatars"}  ')
        assert app.config['AVATAR_DIR'] == str(tmp_path / 'avatars')

    def test_the_directory_is_not_created_at_startup(self, clean_env, tmp_path):
        _app_with_avatar_dir(clean_env, str(tmp_path / 'avatars'))
        assert not (tmp_path / 'avatars').exists()

    @pytest.mark.parametrize('value', ['avatars', './data/avatars', '~/avatars',
                                       'data/../avatars'])
    def test_a_relative_path_stops_the_app_naming_only_the_variable(self, clean_env, value):
        with pytest.raises(ConfigError) as err:
            _app_with_avatar_dir(clean_env, value)
        assert str(err.value) == 'AVATAR_DIR must be an absolute path'
        assert value not in str(err.value)

    @pytest.mark.parametrize('env', ['development', 'testing', 'production'])
    def test_the_rule_holds_in_every_environment(self, env, tmp_path):
        with pytest.raises(ConfigError, match='^AVATAR_DIR must be an absolute path$'):
            load_settings(env, {'AVATAR_DIR': 'relative'})
        assert load_settings(env, {})['AVATAR_DIR'] == DEFAULT_AVATAR_DIR
        assert load_settings(env, {'AVATAR_DIR': str(tmp_path)})['AVATAR_DIR'] == str(tmp_path)

    def test_it_is_independent_of_the_image_dirs(self, tmp_path):
        settings = load_settings('testing', {'CARD_IMAGES_DIR': str(tmp_path / 'cards'),
                                             'PRODUCT_IMAGES_DIR': str(tmp_path / 'products')})
        assert settings['AVATAR_DIR'] == DEFAULT_AVATAR_DIR
        with pytest.raises(ConfigError, match='^AVATAR_DIR must be an absolute path$'):
            load_settings('testing', {'CARD_IMAGES_DIR': str(tmp_path), 'AVATAR_DIR': 'rel'})


# F9-d S2: TOTP_ENCRYPTION_KEY, a Fernet key (URL-safe base64 of 32 bytes)

STRONG_SECRET = 'a-strong-secret-key-of-more-than-thirty-two-characters'
BAD_KEY = 'not-a-fernet-key-but-SECRET-VALUE-0123456789'


def _cfg(**extra):
    return {'SECRET_KEY': STRONG_SECRET, 'SQLALCHEMY_DATABASE_URI': 'sqlite://', **extra}


def _valid_key():
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()


class TestTotpEncryptionKey:
    @pytest.mark.parametrize('value', [None, '', '   '])
    def test_unset_or_blank_is_none(self, value):
        environ = {} if value is None else {'TOTP_ENCRYPTION_KEY': value}
        assert load_settings('production', environ)['TOTP_ENCRYPTION_KEY'] is None

    def test_the_key_is_read_stripped(self):
        key = _valid_key()
        assert load_settings('production', {'TOTP_ENCRYPTION_KEY': f' {key}\n'})[
            'TOTP_ENCRYPTION_KEY'] == key

    def test_production_without_a_key_stops_the_app(self):
        with pytest.raises(ConfigError) as err:
            validate_settings(_cfg(TOTP_ENCRYPTION_KEY=None), 'production')
        assert 'TOTP_ENCRYPTION_KEY is missing' in str(err.value)

    @pytest.mark.parametrize('env', ['production', 'development'])
    @pytest.mark.parametrize('value', [BAD_KEY, 'x' * 44, 'c2hvcnQ='])
    def test_an_invalid_key_stops_the_app_naming_only_the_variable(self, env, value):
        with pytest.raises(ConfigError) as err:
            validate_settings(_cfg(TOTP_ENCRYPTION_KEY=value), env)
        assert 'TOTP_ENCRYPTION_KEY is not a valid key' in str(err.value)
        assert value not in str(err.value)

    @pytest.mark.parametrize('env', ['production', 'development'])
    def test_a_valid_key_passes(self, env):
        validate_settings(_cfg(TOTP_ENCRYPTION_KEY=_valid_key()), env)

    def test_development_without_a_key_starts_and_2fa_is_unavailable(self, clean_env):
        clean_env.setenv('RB_ENV', 'development')
        clean_env.setenv('DATABASE_URL', 'sqlite:///:memory:')
        app = create_app()
        assert app.config['TOTP_ENCRYPTION_KEY'] is None
        from app.services import mfa
        with app.app_context():
            assert mfa.available() is False

    def test_production_from_the_environment_needs_the_key(self, clean_env):
        clean_env.setenv('RB_ENV', 'production')
        clean_env.setenv('SECRET_KEY', STRONG_SECRET)
        clean_env.setenv('DATABASE_URL', 'sqlite:///:memory:')
        with pytest.raises(ConfigError, match='TOTP_ENCRYPTION_KEY is missing'):
            create_app()
        clean_env.setenv('TOTP_ENCRYPTION_KEY', BAD_KEY)
        with pytest.raises(ConfigError) as err:
            create_app()
        assert 'TOTP_ENCRYPTION_KEY is not a valid key' in str(err.value)
        assert BAD_KEY not in str(err.value)
        clean_env.setenv('TOTP_ENCRYPTION_KEY', _valid_key())
        assert create_app().config['RB_ENV'] == 'production'

    def test_testing_skips_the_check(self):
        app = create_app(TESTING=True, SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
                         SECRET_KEY='test-secret-key', TOTP_ENCRYPTION_KEY=BAD_KEY)
        from app.services import mfa
        with app.app_context():
            assert mfa.available() is False

    def test_the_default_test_app_has_a_valid_key(self, app):
        from cryptography.fernet import Fernet
        Fernet(app.config['TOTP_ENCRYPTION_KEY'])
