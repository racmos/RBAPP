"""Application settings (unit a, specs CFG-1..7).

Settings come ONLY from environment variables (a git-ignored `.env` is read in
development; see `app/__init__.py`). Everything here is a pure function of the
environment mapping it receives, so it is trivially testable:

    resolve_env(environ)          -> 'development' | 'testing' | 'production'
    load_settings(env, environ)   -> dict of Flask config values
    validate_settings(cfg, env)   -> raises ConfigError (names only, never values)
    engine_options(db_uri)        -> SQLAlchemy engine options for that URI

Nothing in this module may hold a credential or a default secret.
"""
import hashlib
import logging
import secrets
from typing import Any, Mapping, Optional

logger = logging.getLogger(__name__)

ENVIRONMENTS = ('development', 'testing', 'production')
DEFAULT_ENV = 'production'          # an unconfigured host must never start insecure

SECRET_KEY_MIN_LENGTH = 32
# Substrings (case-insensitive) that mark a placeholder key.
_WEAK_KEY_MARKERS = ('change-me', 'changeme')
# sha256 of known-bad keys, compared against key.strip().lower(). Stored as
# digests so the legacy default never appears as a literal in tracked code
# (CFG-1). Entries: the legacy hard-coded default and the old .env.example value.
SECRET_KEY_DENYLIST_SHA256 = frozenset({
    'ce7ca3d53a67c65f0c8f18d34041d17107e345ac7f831627ef805c69eae77155',
    '192f0a7b20fac1f96c28c62fc6a1a0f998b9efb97ad76e020445b46789289a3c',
})

# Hosts the admin may point the Cardmarket loader at (ACL-7). Default: the host
# of the built-in download URLs. Override with a comma-separated list in
# CARDMARKET_ALLOWED_HOSTS.
CARDMARKET_ALLOWED_HOSTS = ('downloads.s3.cardmarket.com',)

# Trusted reverse-proxy hops (CFG-7): name -> default
_PROXY_FIX_DEFAULTS = {
    'PROXY_FIX_X_FOR': 1,
    'PROXY_FIX_X_PROTO': 1,
    'PROXY_FIX_X_HOST': 1,
}


class ConfigError(RuntimeError):
    """Invalid configuration. Messages name variables, NEVER their values."""


def resolve_env(environ: Mapping[str, str]) -> str:
    """Effective environment from RB_ENV (CFG-2). Unset or blank means production."""
    raw = (environ.get('RB_ENV') or '').strip().lower()
    if not raw:
        return DEFAULT_ENV
    if raw not in ENVIRONMENTS:
        raise ConfigError(
            f"RB_ENV={raw!r} is not valid; allowed values: {', '.join(ENVIRONMENTS)}"
        )
    return raw


def _int_setting(environ: Mapping[str, str], name: str, default: int) -> int:
    text = (environ.get(name) or '').strip()
    if not text:
        return default
    if not (text.isascii() and text.isdigit()):
        raise ConfigError(f'{name} must be a non-negative integer')
    return int(text)


def _host_list(environ: Mapping[str, str], name: str, default: tuple) -> tuple:
    """A comma-separated list of host names, lower-cased; blank keeps `default`."""
    hosts = tuple(h.strip().lower() for h in (environ.get(name) or '').split(',') if h.strip())
    return hosts or default


def load_settings(env: str, environ: Mapping[str, str]) -> dict[str, Any]:
    """Read the Flask config values that come from the environment (CFG-1, CFG-7).

    Missing SECRET_KEY / DATABASE_URL stay None here; `validate_settings` turns
    that into an error AFTER test overrides are applied. In development a
    missing SECRET_KEY gets a random per-process key (D2).
    """
    secret_key = environ.get('SECRET_KEY') or None
    if secret_key is None and env == 'development':
        secret_key = secrets.token_urlsafe(48)
        logger.warning(
            'SECRET_KEY is not set: using a random key for this process '
            '(sessions will not survive a restart)'
        )

    settings: dict[str, Any] = {
        'RB_ENV': env,
        'SECRET_KEY': secret_key,
        'SQLALCHEMY_DATABASE_URI': environ.get('DATABASE_URL') or None,
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
    }
    for name, default in _PROXY_FIX_DEFAULTS.items():
        settings[name] = _int_setting(environ, name, default)
    settings['CARDMARKET_ALLOWED_HOSTS'] = _host_list(
        environ, 'CARDMARKET_ALLOWED_HOSTS', CARDMARKET_ALLOWED_HOSTS)
    return settings


def _secret_key_problem(key: Optional[str]) -> Optional[str]:
    """Why `key` is unacceptable (never includes the key), or None if it is fine."""
    if not key:
        return 'is missing'
    normalized = key.strip().lower()
    if (any(marker in normalized for marker in _WEAK_KEY_MARKERS)
            or hashlib.sha256(normalized.encode()).hexdigest() in SECRET_KEY_DENYLIST_SHA256):
        return 'is a known default or placeholder'
    if len(key) < SECRET_KEY_MIN_LENGTH:
        return f'is too short (minimum {SECRET_KEY_MIN_LENGTH} characters)'
    return None


def validate_settings(cfg: Mapping[str, Any], env: str) -> None:
    """Fail fast on an unsafe configuration (CFG-3, D2).

    Called by `create_app` AFTER test overrides are applied. `TESTING=True`
    skips every check. The error lists the offending variable NAMES only.
    """
    if cfg.get('TESTING'):
        return

    problems = []
    if env != 'development':
        reason = _secret_key_problem(cfg.get('SECRET_KEY'))
        if reason:
            problems.append(f'SECRET_KEY {reason}')
    if not cfg.get('SQLALCHEMY_DATABASE_URI'):
        problems.append('DATABASE_URL is missing')
    if env == 'production' and cfg.get('DEBUG'):
        problems.append('DEBUG must be off in production (unset FLASK_DEBUG)')

    if problems:
        raise ConfigError(
            f'Invalid configuration for RB_ENV={env}: ' + '; '.join(problems)
            + '. Set them in the process environment (see .env.example).'
        )


def engine_options(db_uri: Optional[str]) -> dict[str, Any]:
    """SQLAlchemy engine options for the effective URI (CFG-5).

    SQLite (tests) does not accept client_encoding; PostgreSQL gets utf8.
    """
    if (db_uri or '').startswith('sqlite'):
        return {'pool_pre_ping': True}
    return {
        'connect_args': {'client_encoding': 'utf8'},
        'pool_pre_ping': True,
    }
