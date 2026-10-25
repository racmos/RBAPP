"""`flask images import-legacy [--source PATH]` (M-d, S7).

The source and CARD_IMAGES_DIR are temporary folders: the real images are never
read or written.
"""
import os

import pytest

PNG = b'\x89PNG\r\n\x1a\n' + b'legacy' * 8


@pytest.fixture
def cli(app):
    runner = app.test_cli_runner(mix_stderr=False)

    def _invoke(*args):
        return runner.invoke(args=['images', *args])
    return _invoke


@pytest.fixture
def source(tmp_path):
    """A legacy cards folder: 3 good files, 1 .gitkeep and assorted unsafe entries."""
    src = tmp_path / 'legacy'
    (src / 'ogn').mkdir(parents=True)
    (src / 'ogn' / 'ogn_1.png').write_bytes(PNG + b'1')
    (src / 'ogn' / 'ogn_2.png').write_bytes(PNG + b'2')
    (src / 'sfd').mkdir()
    (src / 'sfd' / 'sfd_1.png').write_bytes(PNG + b'3')
    (src / '.gitkeep').write_bytes(b'')                         # not in a folder
    (src / 'loose.png').write_bytes(PNG)                        # not in a folder
    (src / 'Bad-Folder').mkdir()
    (src / 'Bad-Folder' / 'x_1.png').write_bytes(PNG)           # unsafe folder
    (src / 'ogn' / 'deeper').mkdir()
    (src / 'ogn' / 'deeper' / 'ogn_9.png').write_bytes(PNG)     # too deep
    (tmp_path / 'secret.txt').write_bytes(b'secret')
    (src / 'ogn' / 'link.png').symlink_to(tmp_path / 'secret.txt')   # not a plain file
    return src


def _tree(root):
    """{relative path: bytes} of every file under `root`."""
    found = {}
    for folder, _dirs, files in os.walk(root):
        for name in files:
            path = os.path.join(folder, name)
            with open(path, 'rb') as handle:
                found[os.path.relpath(path, root)] = handle.read()
    return found


class TestImportLegacy:
    def test_it_copies_folder_and_file_and_reports(self, cli, source, card_images_dir):
        result = cli('import-legacy', '--source', str(source))
        assert result.exit_code == 0, result.output
        assert result.stdout == 'Copied 3, skipped 0 existing, ignored 5.\n'
        assert result.stderr == ''
        assert _tree(card_images_dir) == {
            os.path.join('ogn', 'ogn_1.png'): PNG + b'1',
            os.path.join('ogn', 'ogn_2.png'): PNG + b'2',
            os.path.join('sfd', 'sfd_1.png'): PNG + b'3',
        }

    def test_the_source_is_left_untouched(self, cli, source, card_images_dir):
        before = _tree(source)
        cli('import-legacy', '--source', str(source))
        assert _tree(source) == before

    def test_an_existing_file_is_never_overwritten(self, cli, source, card_images_dir):
        (card_images_dir / 'ogn').mkdir(parents=True)
        (card_images_dir / 'ogn' / 'ogn_1.png').write_bytes(b'newer')
        result = cli('import-legacy', '--source', str(source))
        assert result.exit_code == 0
        assert result.stdout == 'Copied 2, skipped 1 existing, ignored 5.\n'
        assert (card_images_dir / 'ogn' / 'ogn_1.png').read_bytes() == b'newer'

    def test_a_second_run_copies_nothing(self, cli, source, card_images_dir):
        cli('import-legacy', '--source', str(source))
        copied = _tree(card_images_dir)
        result = cli('import-legacy', '--source', str(source))
        assert result.exit_code == 0
        assert result.stdout == 'Copied 0, skipped 3 existing, ignored 5.\n'
        assert _tree(card_images_dir) == copied

    def test_the_default_source_is_the_static_cards_folder(self, app, cli, tmp_path,
                                                          card_images_dir):
        static = tmp_path / 'static'
        (static / 'images' / 'cards' / 'ogs').mkdir(parents=True)
        (static / 'images' / 'cards' / '.gitkeep').write_bytes(b'')
        (static / 'images' / 'cards' / 'ogs' / 'ogs_1.png').write_bytes(PNG)
        app.static_folder = str(static)
        result = cli('import-legacy')
        assert result.exit_code == 0, result.output
        assert result.stdout == 'Copied 1, skipped 0 existing, ignored 1.\n'
        assert (card_images_dir / 'ogs' / 'ogs_1.png').read_bytes() == PNG

    def test_an_empty_source_copies_nothing(self, cli, tmp_path, card_images_dir):
        (tmp_path / 'empty').mkdir()
        result = cli('import-legacy', '--source', str(tmp_path / 'empty'))
        assert result.exit_code == 0
        assert result.stdout == 'Copied 0, skipped 0 existing, ignored 0.\n'

    def test_a_missing_source_is_a_usage_error(self, cli, tmp_path, card_images_dir):
        result = cli('import-legacy', '--source', str(tmp_path / 'nope'))
        assert result.exit_code == 2
        assert 'does not exist' in result.stderr
        assert not card_images_dir.exists()

    def test_the_group_is_listed_in_the_help(self, app):
        runner = app.test_cli_runner(mix_stderr=False)
        result = runner.invoke(args=['images', '--help'])
        assert result.exit_code == 0
        assert 'import-legacy' in result.stdout
