"""Every variable of `.env.example` is documented in `README.md` (re-created by F9-c S12).

Only variable names are compared, never values. The files keep their CRLF endings
(conventions section 8).
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / '.env.example'
README = ROOT / 'README.md'
# `NAME=value` or a commented default `# NAME=value`.
ASSIGNMENT = re.compile(r'^\s*#?\s*([A-Z][A-Z0-9_]*)\s*=', re.MULTILINE)


def _example_variables():
    return set(ASSIGNMENT.findall(EXAMPLE.read_text(encoding='utf-8')))


def _readme_variables():
    return set(re.findall(r'`([A-Z][A-Z0-9_]*)`', README.read_text(encoding='utf-8')))


def test_the_example_lists_variables():
    assert {'RB_ENV', 'SECRET_KEY', 'DATABASE_URL'} <= _example_variables()


def test_every_variable_of_the_example_is_in_the_readme():
    missing = sorted(_example_variables() - _readme_variables())
    assert not missing, f'README.md does not document: {missing}'


def test_the_avatar_dir_is_in_both():
    """F9-c S2."""
    assert 'AVATAR_DIR' in _example_variables()
    assert 'AVATAR_DIR' in _readme_variables()


def test_both_files_keep_crlf_endings():
    for path in (EXAMPLE, README):
        data = path.read_bytes()
        assert data.count(b'\n') == data.count(b'\r\n'), f'{path.name} is not CRLF throughout'


def test_the_totp_encryption_key_is_in_both():
    """F9-d S2: an empty value and a comment on how to generate one."""
    assert 'TOTP_ENCRYPTION_KEY' in _example_variables()
    assert 'TOTP_ENCRYPTION_KEY' in _readme_variables()
    lines = EXAMPLE.read_text(encoding='utf-8').splitlines()
    assert 'TOTP_ENCRYPTION_KEY=' in lines
    assert 'Fernet.generate_key()' in EXAMPLE.read_text(encoding='utf-8')
