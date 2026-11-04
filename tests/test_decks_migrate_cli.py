"""F5-c S7-S10 (AC5): `flask decks migrate [--dry-run] [--strict]` copies the legacy `rbdecks`
rows into `rbdeckheads` / `rbdeckversions` (F5-R7): one head per (user, name) with the mode of
the latest row, one version per row with its seq, idempotent, `rbdecks` untouched, and a report
per deck the owner can review before the real run."""
from datetime import datetime

import pytest

from app import db
from app.models import RbCard, RbDeck, RbDeckHead, RbDeckVersion, RbSet
from app.services.deck_migration import load_catalog, route_deck


def day(n, hour=10):
    return datetime(2030, 1, n, hour, 0)


CATALOG = [
    ('OGN', 'L1', 'Emperor of the Sands', 'Legend', 'Calm, Order', 'Azir'),
    ('OGN', 'L2', 'The Exile', 'Legend', 'Fury, Body', 'Riven'),
    ('OGN', 'C1', 'Azir, Ascendant', 'Champion Unit', 'Calm', 'Azir, Shurima'),
    ('OGN', 'C2', 'Riven, Broken', 'Champion Unit', 'Fury', 'Riven'),
    ('OGN', 'U1', 'Shurima Guard', 'Unit', 'Calm', None),
    ('OGN', 'U2', 'Desert Scout', 'Unit', 'Order', None),
    ('OGN', 'R1', 'Calm Rune', 'Basic Rune', 'Calm', None),
    ('OGN', 'R2', 'Order Rune', 'Basic Rune', 'Order', None),
    ('OGN', 'T1', 'Sand Soldier', 'Token Unit', 'Calm', None),
    ('OGN', 'B1', 'Field 1', 'Battlefield', None, None),
    ('OGN', 'B2', 'Field 2', 'Battlefield', None, None),
    ('OGN', 'B3', 'Field 3', 'Battlefield', None, None),
]


def line(card_id, qty=1, set_id='OGN'):
    return {'set': set_id, 'id': card_id, 'qty': qty}


AZIR = {'main': [line('L1'), line('C1', 3), line('U1', 3), line('R1', 6), line('R2', 6),
                 line('B1'), line('B2'), line('B3')],
        'sideboard': [line('U2', 2)]}
RIVEN = {'main': [line('L2'), line('C2'), line('T1', 2), line('999')]}


@pytest.fixture
def cli(app):
    runner = app.test_cli_runner(mix_stderr=False)

    def _invoke(*args):
        return runner.invoke(args=['decks', 'migrate', *args])
    return _invoke


@pytest.fixture
def catalog(app):
    db.session.add(RbSet(rbset_id='OGN', rbset_name='Origins'))
    db.session.add_all([RbCard(rbcar_rbset_id=s, rbcar_id=i, rbcar_name=n, rbcar_type=t,
                               rbcar_domain=d, rbcar_tags=g) for s, i, n, t, d, g in CATALOG])
    db.session.commit()


def legacy(id, name, cards, *, user='ana', seq=1, mode='1v1', when=None, description=None):
    db.session.add(RbDeck(id=id, rbdck_user=user, rbdck_name=name, rbdck_seq=seq,
                          rbdck_snapshot=when or day(id), rbdck_mode=mode,
                          rbdck_description=description, rbdck_cards=cards))
    db.session.commit()


@pytest.fixture
def real_shape(catalog, make_user):
    """The dev data: 3 decks of one user, one version each."""
    make_user('ana')
    legacy(1, 'Azir Control', AZIR)
    legacy(2, 'Riven', RIVEN, mode='2v2')
    legacy(3, 'Draft', None, description='old notes')


def snapshot_legacy():
    return [(d.id, d.rbdck_user, d.rbdck_name, d.rbdck_seq, d.rbdck_mode, d.rbdck_cards)
            for d in RbDeck.query.order_by(RbDeck.id)]


REAL_REPORT = [
    'Deck ana / "Azir Control": new deck "Azir Control", mode 1v1, 1 version',
    '  seq 1 (rbdecks #1, 2030-01-01 10:00): legend OGN-L1 "Emperor of the Sands"; '
    'champion OGN-C1 "Azir, Ascendant"; main 5/39; runes 12/12; battlefields 3/3; '
    'sideboard 2/10; workbench 0',
    'Deck ana / "Draft": new deck "Draft", mode 1v1, 1 version',
    '  seq 1 (rbdecks #3, 2030-01-03 10:00): legend none; champion none; main 0/39; '
    'runes 0/12; battlefields 0/3; sideboard 0/10; workbench 0',
    '    - no cards',
    '    - description not copied (it stays in rbdecks)',
    'Deck ana / "Riven": new deck "Riven", mode 2v2, 1 version',
    '  seq 1 (rbdecks #2, 2030-01-02 10:00): legend OGN-L2 "The Exile"; '
    'champion OGN-C2 "Riven, Broken"; main 0/39; runes 0/12; battlefields 0/3; '
    'sideboard 0/10; workbench 2',
    '    - token OGN-T1 "Sand Soldier" x2 (main) -> workbench',
    '    - unresolved OGN-999 x1 (main): not in the catalog, left out',
    'Total: 3 decks (3 new, 0 updated, 0 up to date, 0 skipped), 3 versions, '
    '1 unresolved line.',
]


class TestDryRun:
    def test_prints_the_routing_and_writes_nothing(self, cli, real_shape):
        before = snapshot_legacy()
        result = cli('--dry-run')
        assert result.exit_code == 0, result.output
        assert result.output.splitlines() == REAL_REPORT + ['Dry run: nothing was changed.']
        assert (RbDeckHead.query.count(), RbDeckVersion.query.count()) == (0, 0)
        assert snapshot_legacy() == before

    def test_strict_fails_on_unresolved_lines(self, cli, real_shape):
        result = cli('--dry-run', '--strict')
        assert result.exit_code == 1
        assert result.output.splitlines() == REAL_REPORT + ['Dry run: nothing was changed.']
        assert result.stderr == 'Strict: 1 unresolved line; nothing was changed.\n'


class TestRealRun:
    def test_copies_the_three_decks(self, cli, real_shape, frozen_clock):
        before = snapshot_legacy()
        result = cli()
        assert result.exit_code == 0, result.output
        assert result.output.splitlines() == REAL_REPORT + [
            'Done: 3 decks created, 0 updated, 3 versions copied.']
        assert snapshot_legacy() == before
        heads = RbDeckHead.query.order_by(RbDeckHead.rbdkh_name).all()
        ana_id = heads[0].rbdkh_user_id
        assert [(h.rbdkh_user_id, h.rbdkh_name, h.rbdkh_mode, h.rbdkh_visibility,
                 h.rbdkh_share_slug, h.rbdkh_legacy_name, h.rbdkh_created_at,
                 h.rbdkh_updated_at) for h in heads] == [
            (ana_id, 'Azir Control', '1v1', 'private', None, 'Azir Control', day(1), day(1)),
            (ana_id, 'Draft', '1v1', 'private', None, 'Draft', day(3), day(3)),
            (ana_id, 'Riven', '2v2', 'private', None, 'Riven', day(2), day(2))]
        versions = {v.rbdkv_legacy_id: v for v in RbDeckVersion.query}
        assert sorted(versions) == [1, 2, 3]
        for head, legacy_id in zip(heads, (1, 3, 2)):
            version = versions[legacy_id]
            assert head.rbdkh_current_version_id == version.rbdkv_id
            assert (version.rbdkv_deck_id, version.rbdkv_seq, version.rbdkv_created_at) == (
                head.rbdkh_id, 1, day(legacy_id))
        cards = load_catalog()
        assert versions[1].rbdkv_content == route_deck(AZIR, cards)['content']
        assert versions[2].rbdkv_content == route_deck(RIVEN, cards)['content']
        assert versions[1].rbdkv_note == 'Migrated from rbdecks #1.'
        assert versions[2].rbdkv_note == 'Migrated from rbdecks #2. Left out: OGN-999 x1.'

    def test_a_second_run_copies_nothing(self, cli, real_shape):
        cli()
        heads = [(h.rbdkh_id, h.rbdkh_current_version_id) for h in RbDeckHead.query]
        result = cli()
        assert result.exit_code == 0, result.output
        assert result.output.splitlines() == [
            'Deck ana / "Azir Control": up to date',
            'Deck ana / "Draft": up to date',
            'Deck ana / "Riven": up to date',
            'Total: 3 decks (0 new, 0 updated, 3 up to date, 0 skipped), 0 versions, '
            '0 unresolved lines.',
            'Done: 0 decks created, 0 updated, 0 versions copied.']
        assert [(h.rbdkh_id, h.rbdkh_current_version_id) for h in RbDeckHead.query] == heads
        assert RbDeckVersion.query.count() == 3

    def test_strict_with_unresolved_lines_writes_nothing(self, cli, real_shape):
        result = cli('--strict')
        assert result.exit_code == 1
        assert result.output.splitlines() == REAL_REPORT
        assert result.stderr == 'Strict: 1 unresolved line; nothing was changed.\n'
        assert (RbDeckHead.query.count(), RbDeckVersion.query.count()) == (0, 0)

    def test_strict_without_unresolved_lines_runs(self, cli, catalog, make_user):
        make_user('ana')
        legacy(1, 'Azir Control', AZIR)
        result = cli('--strict')
        assert result.exit_code == 0, result.stderr
        assert RbDeckHead.query.count() == 1


class TestVersions:
    def test_one_head_per_name_seqs_kept_mode_from_the_latest(self, cli, catalog, make_user):
        make_user('ana')
        make_user('bo')
        legacy(1, 'Azir', AZIR, seq=1, mode='2v2')
        legacy(2, 'Azir', {'main': [line('U1')]}, seq=2, mode='1v1')
        legacy(3, 'Azir', AZIR, user='bo', seq=4, mode='2v2')
        result = cli()
        assert result.exit_code == 0, result.output
        assert result.output.splitlines()[0] == 'Deck ana / "Azir": new deck "Azir", mode 1v1, ' \
                                                '2 versions'
        ana = RbDeckHead.query.filter_by(rbdkh_mode='1v1').one()
        bo = RbDeckHead.query.filter_by(rbdkh_mode='2v2').one()
        seqs = {v.rbdkv_legacy_id: (v.rbdkv_deck_id, v.rbdkv_seq) for v in RbDeckVersion.query}
        assert seqs == {1: (ana.rbdkh_id, 1), 2: (ana.rbdkh_id, 2), 3: (bo.rbdkh_id, 4)}
        assert (ana.rbdkh_created_at, ana.rbdkh_updated_at) == (day(1), day(2))
        latest = RbDeckVersion.query.filter_by(rbdkv_legacy_id=2).one()
        assert ana.rbdkh_current_version_id == latest.rbdkv_id

    def test_a_legacy_version_saved_after_the_run_is_added(self, cli, catalog, make_user):
        make_user('ana')
        legacy(1, 'Azir', AZIR, seq=1, mode='1v1')
        cli()
        legacy(2, 'Azir', {'main': [line('U1')]}, seq=2, mode='2v2')
        result = cli()
        assert result.output.splitlines()[:2] == [
            'Deck ana / "Azir": 1 new version for deck "Azir"',
            '  seq 2 (rbdecks #2, 2030-01-02 10:00): legend none; champion none; main 1/39; '
            'runes 0/12; battlefields 0/3; sideboard 0/10; workbench 0']
        assert result.output.splitlines()[-1] == 'Done: 0 decks created, 1 updated, ' \
                                                 '1 version copied.'
        head = RbDeckHead.query.one()
        new = RbDeckVersion.query.filter_by(rbdkv_legacy_id=2).one()
        assert (new.rbdkv_seq, head.rbdkh_current_version_id) == (2, new.rbdkv_id)
        assert head.rbdkh_mode == '1v1'          # set once, when the deck is created
        assert head.rbdkh_updated_at == day(2)

    def test_jinja_saving_still_works_and_a_rerun_copies_it(self, cli, catalog,
                                                             authenticated_client):
        # F5-c S11: `POST /deck/save` stays enabled until the v2 editor exists (F5-d/h).
        save = {'rbdck_name': 'Azir', 'rbdck_mode': '1v1', 'rbdck_cards': AZIR}
        assert authenticated_client.post('/riftbound/deck/save', json=save).get_json()[
            'seq'] == 1
        cli()
        response = authenticated_client.post('/riftbound/deck/save', json=save)
        assert response.status_code == 200
        assert (response.get_json()['success'], response.get_json()['seq']) == (True, 2)
        result = cli()
        assert result.output.splitlines()[0] == 'Deck testuser / "Azir": 1 new version for ' \
                                                'deck "Azir"'
        assert sorted(v.rbdkv_seq for v in RbDeckVersion.query) == [1, 2]

    def test_repeated_seqs_get_the_next_free_one(self, cli, catalog, make_user):
        make_user('ana')
        legacy(1, 'Azir', AZIR, seq=1)
        legacy(2, 'Azir', AZIR, seq=2)
        db.session.execute(db.text('UPDATE riftbound.rbdecks SET rbdck_seq = NULL'))  # nullable
        db.session.commit()
        result = cli()
        assert '    - seq 1 taken: stored as 2' in result.output.splitlines()
        assert sorted(v.rbdkv_seq for v in RbDeckVersion.query) == [1, 2]


class TestHeads:
    def test_long_names_and_unknown_modes(self, cli, catalog, make_user):
        make_user('ana')
        legacy(1, 'A' * 85, None, mode='Standard')
        legacy(2, 'A' * 90, None)
        result = cli()
        assert result.exit_code == 0, result.output
        lines = result.output.splitlines()
        assert lines[:3] == [f'Deck ana / "{"A" * 85}": new deck "{"A" * 80}", mode 1v1, '
                             '1 version',
                             '  - name longer than 80 characters: shortened',
                             '  - mode "Standard" is not a game mode: 1v1']
        renamed = 'A' * 76 + ' (2)'
        assert f'  - name taken: renamed to "{renamed}"' in lines
        names = sorted((h.rbdkh_name, h.rbdkh_legacy_name) for h in RbDeckHead.query)
        assert names == sorted([('A' * 80, 'A' * 85), (renamed, 'A' * 90)])

    def test_a_deck_of_an_unknown_user_is_skipped(self, cli, catalog, make_user):
        make_user('ana')
        legacy(1, 'Azir', AZIR, user='ghost')     # SQLite does not enforce the FK
        result = cli()
        assert result.output.splitlines()[:2] == [
            'Deck ghost / "Azir": user not found, skipped',
            'Total: 1 deck (0 new, 0 updated, 0 up to date, 1 skipped), 0 versions, '
            '0 unresolved lines.']
        assert RbDeckHead.query.count() == 0


def test_the_group_is_listed_in_the_help(app):
    runner = app.test_cli_runner(mix_stderr=False)
    result = runner.invoke(args=['decks', '--help'])
    assert result.exit_code == 0
    assert 'migrate' in result.stdout
    result = runner.invoke(args=['decks', 'migrate', '--help'])
    assert '--dry-run' in result.stdout and '--strict' in result.stdout
