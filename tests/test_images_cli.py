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
        # <app package>/static/images/cards, read from disk: the app serves no static URL.
        static = tmp_path / 'static'
        (static / 'images' / 'cards' / 'ogs').mkdir(parents=True)
        (static / 'images' / 'cards' / '.gitkeep').write_bytes(b'')
        (static / 'images' / 'cards' / 'ogs' / 'ogs_1.png').write_bytes(PNG)
        app.root_path = str(tmp_path)
        result = cli('import-legacy')
        assert result.exit_code == 0, result.output
        assert result.stdout == 'Copied 1, skipped 0 existing, ignored 1.\n'
        assert (card_images_dir / 'ogs' / 'ogs_1.png').read_bytes() == PNG

    def test_the_app_root_is_the_app_package_and_nothing_is_served_from_static(self, app,
                                                                               client):
        assert app.root_path == os.path.dirname(os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', 'app', '__init__.py')))
        assert app.static_folder is None
        assert client.get('/riftbound/static/images/cards/.gitkeep').status_code == 404

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


class TestPruneOrphans:
    """F13-h S7: `flask images prune-orphans [--dry-run]` lists or deletes the image files no
    row references; both roots are the fixtures' temporary folders."""

    @pytest.fixture
    def world(self, app, card_images_dir, product_images_dir, tmp_path):
        from app import db
        from app.models.card import RbCard
        from app.models.set import RbSet
        from tests.product_helpers import add_product
        db.session.add(RbSet(rbset_id='OGN', rbset_name='Origen', rbset_ncard=2))
        db.session.add_all([
            RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='A', image='ogn_1.png'),
            RbCard(rbcar_rbset_id='OGN', rbcar_id='2', rbcar_name='B', image='ogn_2.webp')])
        add_product(100, 'Booster', image='100.webp')
        db.session.commit()
        (card_images_dir / 'ogn').mkdir(parents=True)
        for name in ('ogn_1.png', 'ogn_2.webp', 'ogn_2.png', 'ogn_3.jpg', 'notes.txt'):
            (card_images_dir / 'ogn' / name).write_bytes(PNG)
        (card_images_dir / 'sfd').mkdir()
        (card_images_dir / 'sfd' / 'sfd_1.png').write_bytes(PNG)
        (card_images_dir / 'Bad-Folder').mkdir()
        (card_images_dir / 'Bad-Folder' / 'x_1.png').write_bytes(PNG)
        (tmp_path / 'outside.png').write_bytes(b'keep me')
        (card_images_dir / 'ogn' / 'ogn_9.png').symlink_to(tmp_path / 'outside.png')
        product_images_dir.mkdir()
        for name in ('100.webp', '100.png', '101.png', '.upload-x.tmp'):
            (product_images_dir / name).write_bytes(PNG)
        return card_images_dir, product_images_dir

    ORPHANS = ('cards/ogn/ogn_2.png\ncards/ogn/ogn_3.jpg\ncards/sfd/sfd_1.png\n'
               'products/100.png\nproducts/101.png\n')

    def test_dry_run_lists_and_deletes_nothing(self, cli, world):
        before = [_tree(root) for root in world]
        result = cli('prune-orphans', '--dry-run')
        assert result.exit_code == 0, result.output
        assert result.stdout == self.ORPHANS + '5 orphan files (dry run, nothing deleted).\n'
        assert result.stderr == ''
        assert [_tree(root) for root in world] == before

    def test_it_deletes_only_the_orphan_images(self, cli, world, tmp_path):
        cards, products = world
        result = cli('prune-orphans')
        assert result.exit_code == 0, result.output
        assert result.stdout == self.ORPHANS + 'Deleted 5 orphan files.\n'
        assert sorted(_tree(cards)) == sorted([
            os.path.join('ogn', 'ogn_1.png'), os.path.join('ogn', 'ogn_2.webp'),
            os.path.join('ogn', 'notes.txt'), os.path.join('ogn', 'ogn_9.png'),
            os.path.join('Bad-Folder', 'x_1.png')])
        assert sorted(_tree(products)) == ['.upload-x.tmp', '100.webp']
        assert (tmp_path / 'outside.png').read_bytes() == b'keep me'

    def test_missing_roots_find_nothing(self, cli, card_images_dir, product_images_dir):
        result = cli('prune-orphans')
        assert result.exit_code == 0
        assert result.stdout == 'Deleted 0 orphan files.\n'

    def test_it_is_listed_in_the_help(self, app):
        result = app.test_cli_runner(mix_stderr=False).invoke(args=['images', '--help'])
        assert 'prune-orphans' in result.stdout
