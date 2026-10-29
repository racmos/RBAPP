"""F13-c S3-S7 (AC2): the sync engine. No network: the gallery and the image
bytes come from fixtures and a fake session."""
from datetime import date, datetime

import pytest
import requests

from app import db
from app.jobs.registry import JobFailed
from app.models.audit import RbAdminAudit
from app.models.card import RbCard
from app.models.card_change import RbCardChange
from app.models.job import RbJob
from app.models.set import RbSet
from app.services import riot_sync

GALLERY = {'cards': [
    {'rbcar_rbset_id': 'OGN', 'rbcar_id': '1', 'rbcar_name': 'Alpha Unit',
     'rbcar_domain': 'fury', 'rbcar_type': 'Unit', 'rbcar_tags': '',
     'rbcar_energy': 2, 'rbcar_power': 3, 'rbcar_might': 4,
     'rbcar_ability': 'Strike.', 'rbcar_rarity': 'Common',
     'rbcar_artist': 'An Artist', 'image_url': 'https://img.test/ogn_1.png',
     'image': 'ogn_1.png'},
    {'rbcar_rbset_id': 'OGN', 'rbcar_id': '2', 'rbcar_name': 'Beta Spell',
     'rbcar_domain': 'calm', 'rbcar_type': 'Spell', 'rbcar_tags': '',
     'rbcar_energy': 1, 'rbcar_power': None, 'rbcar_might': None,
     'rbcar_ability': '', 'rbcar_rarity': 'Common', 'rbcar_artist': 'An Artist',
     'image_url': 'https://img.test/ogn_2.png', 'image': 'ogn_2.png'},
    {'rbcar_rbset_id': 'OGS', 'rbcar_id': '5', 'rbcar_name': 'Gamma Legend',
     'rbcar_domain': 'mind', 'rbcar_type': 'Legend', 'rbcar_tags': '',
     'rbcar_energy': None, 'rbcar_power': None, 'rbcar_might': None,
     'rbcar_ability': '', 'rbcar_rarity': 'Rare', 'rbcar_artist': 'An Artist',
     'image_url': 'https://img.test/ogs_5.png', 'image': 'ogs_5.png'},
], 'set_codes': ['OGN', 'OGS'], 'unparsed': 0}

PNG = b'\x89PNG\r\n\x1a\nimage-bytes'

ACTIVE_DAY = datetime(2026, 10, 10)   # OGN released 2026-10-01: post_release (R+9)
ACTIVE_RELEASE = date(2026, 10, 1)
MONTHLY_RELEASE = date(2025, 1, 1)    # long ago: monthly


class FakeResponse:
    def __init__(self, content=b''):
        self.content = content

    def raise_for_status(self):
        pass


class FakeSession:
    """Serves image bytes; records every downloaded URL."""

    def __init__(self, fail=()):
        self.urls = []
        self.fail = set(fail)

    def get(self, url, timeout=None):
        self.urls.append(url)
        if url in self.fail:
            raise requests.ConnectionError('down')
        return FakeResponse(PNG)


@pytest.fixture(autouse=True)
def _images_root(card_images_dir):
    """Every sync here writes images under a temporary root, never the repo."""
    return card_images_dir


@pytest.fixture
def network(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(riot_sync, '_get_session', lambda: session)
    return session


@pytest.fixture
def gallery(monkeypatch):
    import copy

    def _fake():
        return copy.deepcopy(GALLERY)
    monkeypatch.setattr(riot_sync, 'fetch_gallery', _fake)


def make_set(set_id, release, ncard=None):
    db.session.add(RbSet(rbset_id=set_id, rbset_name=set_id, rbset_ncard=ncard,
                         rbset_outdat=release))
    db.session.commit()


def seed_gallery_card(set_id, card_id, **overrides):
    """A stored card identical to the gallery one, except the overrides."""
    parsed = next(c for c in GALLERY['cards']
                  if c['rbcar_rbset_id'] == set_id and c['rbcar_id'] == card_id)
    data = dict(parsed)
    data.pop('rbcar_banned', None)
    data.update(overrides)
    db.session.add(RbCard(**{k: v for k, v in data.items()
                              if k in RbCard.__table__.columns}))
    db.session.commit()


def run(**kwargs):
    kwargs.setdefault('trigger', 'manual')
    kwargs.setdefault('now', ACTIVE_DAY)
    return riot_sync.sync(**kwargs)


class FakePage:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


class FakePageSession(FakeSession):
    def __init__(self, text):
        super().__init__()
        self._text = text

    def get(self, url, timeout=None):
        self.urls.append(url)
        return FakePage(self._text)


class TestFetchGallery:
    def _page(self):
        with open('tests/fixtures/riot/gallery.html') as handle:
            return handle.read()

    def test_parses_cards_codes_and_unparsed(self, monkeypatch):
        from app.services import riot_sync as rs
        monkeypatch.setattr(rs, '_get_session', lambda: FakePageSession(self._page()))
        gallery = rs.fetch_gallery()
        assert gallery['set_codes'] == ['OGN', 'OGS']
        assert gallery['unparsed'] == 1
        by_id = {(c['rbcar_rbset_id'], c['rbcar_id']): c for c in gallery['cards']}
        assert set(by_id) == {('OGN', '1'), ('OGN', '2'), ('OGS', '5')}
        assert by_id[('OGN', '1')]['rbcar_name'] == 'Alpha Unit'
        assert by_id[('OGN', '1')]['image'] == 'ogn_1.png'

    def test_missing_script_is_a_gallery_error(self, monkeypatch):
        from app.services import riot_sync as rs
        monkeypatch.setattr(rs, '_get_session',
                            lambda: FakePageSession('<html><body>no data</body></html>'))
        with pytest.raises(rs.GalleryError):
            rs.fetch_gallery()

    def test_network_failure_hides_the_url(self, monkeypatch):
        from app.services import riot_sync as rs
        session = FakeSession(fail={'https://x.invalid/'})
        monkeypatch.setattr(rs, '_get_session', lambda: session)
        with pytest.raises(rs.GalleryError) as caught:
            rs.fetch_gallery()
        assert 'x.invalid' not in str(caught.value)


class TestInserts:
    def test_new_cards_are_inserted_with_images(self, app, network, gallery):
        make_set('OGN', ACTIVE_RELEASE)
        result = run()

        assert RbCard.query.count() == 3
        card = RbCard.query.filter_by(rbcar_rbset_id='OGN', rbcar_id='1').one()
        assert card.rbcar_name == 'Alpha Unit'
        assert card.rbcar_banned == 'N'
        assert sorted(network.urls) == ['https://img.test/ogn_1.png',
                                        'https://img.test/ogn_2.png',
                                        'https://img.test/ogs_5.png']
        ogn = next(s for s in result['sets'] if s['set_id'] == 'OGN')
        assert ogn['inserted'] == 2 and ogn['unchanged'] == 0
        assert ogn['images'] == {'downloaded': 2, 'existing': 0, 'failed': 0}

    def test_result_shape(self, app, network, gallery):
        make_set('OGN', ACTIVE_RELEASE)
        result = run(set_codes=['OGN'])
        assert result['trigger'] == 'manual'
        assert result['today'] == '2026-10-10'
        assert result['gallery'] == {'cards': 3, 'unparsed': 0,
                                     'set_codes': ['OGN', 'OGS']}
        assert result['placeholder_sets'] == []
        assert set(result) == {'trigger', 'today', 'gallery', 'placeholder_sets', 'sets'}
        ogn = next(s for s in result['sets'] if s['set_id'] == 'OGN')
        assert set(ogn) == {'set_id', 'window', 'inserted', 'applied', 'proposed',
                            'unchanged', 'missing_from_gallery', 'images', 'error'}

    def test_missing_sets_become_placeholders(self, app, network, gallery):
        make_set('OGN', ACTIVE_RELEASE)
        result = run()
        ogs = RbSet.query.get('OGS')
        assert (ogs.rbset_name, ogs.rbset_outdat, ogs.rbset_ncard) == ('OGS', None, 1)
        assert result['placeholder_sets'] == ['OGS']
        assert RbAdminAudit.query.filter_by(rbaud_action='set.create').count() == 1

    def test_ncard_is_written_only_when_null(self, app, network, gallery):
        make_set('OGN', ACTIVE_RELEASE, ncard=99)
        run(set_codes=['OGN'])
        assert RbSet.query.get('OGN').rbset_ncard == 99

    def test_insert_audit_is_one_row_per_set(self, app, network, gallery):
        make_set('OGN', ACTIVE_RELEASE)
        run(set_codes=['OGN'])
        rows = RbAdminAudit.query.filter_by(rbaud_action='riot.insert').all()
        assert len(rows) == 1 and rows[0].rbaud_target_id == 'OGN'
        assert rows[0].rbaud_actor_username == 'system'


class TestActiveWindow:
    def test_changed_values_are_applied(self, app, network, gallery, monkeypatch):
        make_set('OGN', ACTIVE_RELEASE)
        seed_gallery_card('OGN', '1', rbcar_energy=9)

        import copy
        changed = copy.deepcopy(GALLERY)
        changed['cards'] = [c for c in changed['cards']
                            if c['rbcar_rbset_id'] == 'OGN' and c['rbcar_id'] == '1']
        changed['set_codes'] = ['OGN']
        monkeypatch.setattr(riot_sync, 'fetch_gallery', lambda: changed)
        result = run(set_codes=['OGN'])

        card = RbCard.query.filter_by(rbcar_rbset_id='OGN', rbcar_id='1').one()
        assert card.rbcar_energy == 2
        ogn = next(s for s in result['sets'] if s['set_id'] == 'OGN')
        assert ogn['applied'] == 1 and ogn['proposed'] == 0
        row = RbAdminAudit.query.filter_by(rbaud_action='riot.apply').one()
        assert row.rbaud_details == {'fields': {'rbcar_energy': [9, 2]}}

    def test_null_and_empty_count_as_equal(self, app, network, gallery, monkeypatch):
        make_set('OGN', ACTIVE_RELEASE)
        seed_gallery_card('OGN', '1')
        seed_gallery_card('OGN', '2', rbcar_ability=None)

        import copy
        only_ogn = copy.deepcopy(GALLERY)
        only_ogn['cards'] = [c for c in only_ogn['cards'] if c['rbcar_rbset_id'] == 'OGN']
        only_ogn['set_codes'] = ['OGN']
        monkeypatch.setattr(riot_sync, 'fetch_gallery', lambda: only_ogn)
        result = run(set_codes=['OGN'])

        ogn = next(s for s in result['sets'] if s['set_id'] == 'OGN')
        assert ogn['unchanged'] == 2 and ogn['applied'] == 0

    def test_banned_is_never_written(self, app, network, gallery, monkeypatch):
        make_set('OGN', ACTIVE_RELEASE)
        seed_gallery_card('OGN', '1', rbcar_banned='Y')
        seed_gallery_card('OGN', '2', rbcar_banned='Y')

        import copy
        only_ogn = copy.deepcopy(GALLERY)
        only_ogn['cards'] = [c for c in only_ogn['cards'] if c['rbcar_rbset_id'] == 'OGN']
        only_ogn['set_codes'] = ['OGN']
        monkeypatch.setattr(riot_sync, 'fetch_gallery', lambda: only_ogn)
        run(set_codes=['OGN'])

        assert {c.rbcar_banned for c in RbCard.query.all()} == {'Y'}


class TestMonthlyWindow:
    def test_differences_become_pending_rows_and_cards_stay(self, app, network, gallery,
                                                            monkeypatch):
        make_set('OGN', MONTHLY_RELEASE)
        seed_gallery_card('OGN', '1', rbcar_energy=9)

        import copy
        only_ogn = copy.deepcopy(GALLERY)
        only_ogn['cards'] = [c for c in only_ogn['cards'] if c['rbcar_rbset_id'] == 'OGN'
                             and c['rbcar_id'] == '1']
        only_ogn['set_codes'] = ['OGN']
        monkeypatch.setattr(riot_sync, 'fetch_gallery', lambda: only_ogn)
        result = run(set_codes=['OGN'])

        card = RbCard.query.filter_by(rbcar_rbset_id='OGN', rbcar_id='1').one()
        assert card.rbcar_energy == 9
        rows = RbCardChange.query.all()
        assert len(rows) == 1
        assert (rows[0].rbchg_field, rows[0].rbchg_old_value, rows[0].rbchg_new_value,
                rows[0].rbchg_status) == ('rbcar_energy', '9', '2', 'pending')
        ogn = next(s for s in result['sets'] if s['set_id'] == 'OGN')
        assert ogn['proposed'] == 1 and ogn['applied'] == 0

    def test_existing_pending_row_is_updated(self, app, network, gallery, monkeypatch):
        make_set('OGN', MONTHLY_RELEASE)
        seed_gallery_card('OGN', '1', rbcar_energy=9)
        db.session.add(RbCardChange(rbchg_rbset_id='OGN', rbchg_rbcar_id='1',
                                    rbchg_field='rbcar_energy', rbchg_old_value='9',
                                    rbchg_new_value='7', rbchg_status='pending',
                                    rbchg_detected_at=datetime(2026, 1, 1)))
        db.session.commit()

        import copy
        only_ogn = copy.deepcopy(GALLERY)
        only_ogn['cards'] = [c for c in only_ogn['cards'] if c['rbcar_rbset_id'] == 'OGN'
                             and c['rbcar_id'] == '1']
        only_ogn['set_codes'] = ['OGN']
        monkeypatch.setattr(riot_sync, 'fetch_gallery', lambda: only_ogn)
        run(set_codes=['OGN'], job_id=3)

        rows = RbCardChange.query.all()
        assert len(rows) == 1
        assert (rows[0].rbchg_new_value, rows[0].rbchg_job_id) == ('2', 3)

    def test_rejected_value_is_not_proposed_again(self, app, network, gallery, monkeypatch):
        make_set('OGN', MONTHLY_RELEASE)
        seed_gallery_card('OGN', '1', rbcar_energy=9)
        db.session.add(RbCardChange(rbchg_rbset_id='OGN', rbchg_rbcar_id='1',
                                    rbchg_field='rbcar_energy', rbchg_old_value='9',
                                    rbchg_new_value='2', rbchg_status='rejected',
                                    rbchg_detected_at=datetime(2026, 1, 1)))
        db.session.commit()

        import copy
        only_ogn = copy.deepcopy(GALLERY)
        only_ogn['cards'] = [c for c in only_ogn['cards'] if c['rbcar_rbset_id'] == 'OGN'
                             and c['rbcar_id'] == '1']
        only_ogn['set_codes'] = ['OGN']
        monkeypatch.setattr(riot_sync, 'fetch_gallery', lambda: only_ogn)
        result = run(set_codes=['OGN'])

        assert RbCardChange.query.filter_by(rbchg_status='pending').count() == 0
        ogn = next(s for s in result['sets'] if s['set_id'] == 'OGN')
        assert ogn['proposed'] == 0


class TestRobustness:
    def test_missing_from_gallery_are_counted_not_touched(self, app, network, gallery,
                                                          monkeypatch):
        make_set('OGN', ACTIVE_RELEASE)
        db.session.add(RbCard(rbcar_rbset_id='OGN', rbcar_id='99', rbcar_name='Gone',
                              rbcar_energy=1))
        db.session.add(RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='Alpha Unit',
                              rbcar_energy=2, rbcar_power=3, rbcar_might=4,
                              rbcar_domain='fury', rbcar_type='Unit', rbcar_tags='',
                              rbcar_rarity='Common', rbcar_artist='An Artist',
                              image_url='https://img.test/ogn_1.png', image='ogn_1.png'))
        db.session.add(RbCard(rbcar_rbset_id='OGN', rbcar_id='2', rbcar_name='Beta Spell',
                              rbcar_domain='calm', rbcar_type='Spell', rbcar_tags='',
                              rbcar_energy=1, rbcar_power=None, rbcar_might=None,
                              rbcar_ability='', rbcar_rarity='Common',
                              rbcar_artist='An Artist',
                              image_url='https://img.test/ogn_2.png', image='ogn_2.png'))
        db.session.commit()

        import copy
        only_ogn = copy.deepcopy(GALLERY)
        only_ogn['cards'] = [c for c in only_ogn['cards'] if c['rbcar_rbset_id'] == 'OGN']
        only_ogn['set_codes'] = ['OGN']
        monkeypatch.setattr(riot_sync, 'fetch_gallery', lambda: only_ogn)
        result = run(set_codes=['OGN'])

        gone = RbCard.query.filter_by(rbcar_rbset_id='OGN', rbcar_id='99').one()
        assert gone.rbcar_name == 'Gone'
        ogn = next(s for s in result['sets'] if s['set_id'] == 'OGN')
        assert ogn['missing_from_gallery'] == 1

    def test_one_failing_set_does_not_roll_back_the_other(self, app, network, gallery,
                                                          monkeypatch):
        make_set('OGN', ACTIVE_RELEASE)
        make_set('OGS', ACTIVE_RELEASE)

        import copy
        broken = copy.deepcopy(GALLERY)
        for card in broken['cards']:
            if card['rbcar_rbset_id'] == 'OGS':
                card['rbcar_name'] = None  # NOT NULL violation inside the OGS set
        monkeypatch.setattr(riot_sync, 'fetch_gallery', lambda: broken)
        result = run()

        assert RbCard.query.filter_by(rbcar_rbset_id='OGN').count() == 2
        assert RbCard.query.filter_by(rbcar_rbset_id='OGS').count() == 0
        ogs = next(s for s in result['sets'] if s['set_id'] == 'OGS')
        assert ogs['error'] is not None and 'IntegrityError' in ogs['error']

    def test_unknown_set_codes_fail_the_job(self, app, network, gallery):
        make_set('OGN', ACTIVE_RELEASE)
        with pytest.raises(JobFailed, match='unknown set'):
            run(set_codes=['OGN', 'NOPE'])
        assert RbCard.query.count() == 0

    def test_gallery_error_fails_and_writes_nothing(self, app, network, gallery,
                                                    monkeypatch):
        make_set('OGN', ACTIVE_RELEASE)

        def _down():
            raise riot_sync.GalleryError('gallery is down')
        monkeypatch.setattr(riot_sync, 'fetch_gallery', _down)
        with pytest.raises(JobFailed):
            run()
        assert RbCard.query.count() == 0
        assert RbAdminAudit.query.count() == 0


def _only(monkeypatch, set_id, card_ids=None):
    """Serve only the gallery cards of `set_id` (optionally only `card_ids`)."""
    import copy
    subset = copy.deepcopy(GALLERY)
    subset['cards'] = [c for c in subset['cards'] if c['rbcar_rbset_id'] == set_id
                       and (card_ids is None or c['rbcar_id'] in card_ids)]
    subset['set_codes'] = [set_id]
    monkeypatch.setattr(riot_sync, 'fetch_gallery', lambda: subset)


def _summary(result, set_id):
    return next(s for s in result['sets'] if s['set_id'] == set_id)


class TestMissingImages:
    """Owner feedback S4: a sync fills every missing image of the synced set."""

    def test_unchanged_card_without_file_is_downloaded(self, app, network, gallery,
                                                       monkeypatch, card_images_dir):
        make_set('OGN', ACTIVE_RELEASE)
        seed_gallery_card('OGN', '1')
        _only(monkeypatch, 'OGN', ['1'])
        result = run(set_codes=['OGN'])

        ogn = _summary(result, 'OGN')
        assert ogn['unchanged'] == 1
        assert network.urls == ['https://img.test/ogn_1.png']
        assert ogn['images'] == {'downloaded': 1, 'existing': 0, 'failed': 0}
        assert (card_images_dir / 'ogn' / 'ogn_1.png').read_bytes() == PNG

        again = run(set_codes=['OGN'])
        assert network.urls == ['https://img.test/ogn_1.png']
        assert _summary(again, 'OGN')['images'] == {'downloaded': 0, 'existing': 1,
                                                     'failed': 0}

    def test_proposed_card_gets_its_stored_image(self, app, network, gallery,
                                                 monkeypatch, card_images_dir):
        make_set('OGN', MONTHLY_RELEASE)
        seed_gallery_card('OGN', '1', rbcar_energy=9,
                          image_url='https://img.test/old_ogn_1.png')
        _only(monkeypatch, 'OGN', ['1'])
        result = run(set_codes=['OGN'])

        ogn = _summary(result, 'OGN')
        assert ogn['proposed'] == 2
        card = RbCard.query.filter_by(rbcar_rbset_id='OGN', rbcar_id='1').one()
        assert (card.rbcar_energy, card.image_url) == (9, 'https://img.test/old_ogn_1.png')
        assert network.urls == ['https://img.test/old_ogn_1.png']
        assert ogn['images'] == {'downloaded': 1, 'existing': 0, 'failed': 0}
        assert (card_images_dir / 'ogn' / 'ogn_1.png').exists()

    def test_proposed_card_without_stored_image_uses_the_gallery(
            self, app, network, gallery, monkeypatch, card_images_dir):
        make_set('OGN', MONTHLY_RELEASE)
        seed_gallery_card('OGN', '1', image=None, image_url=None)
        _only(monkeypatch, 'OGN', ['1'])
        result = run(set_codes=['OGN'])

        ogn = _summary(result, 'OGN')
        assert ogn['proposed'] == 2
        card = RbCard.query.filter_by(rbcar_rbset_id='OGN', rbcar_id='1').one()
        assert (card.image, card.image_url) == (None, None)
        assert network.urls == ['https://img.test/ogn_1.png']
        assert ogn['images'] == {'downloaded': 1, 'existing': 0, 'failed': 0}
        assert (card_images_dir / 'ogn' / 'ogn_1.png').exists()

    def test_applied_card_without_file_is_downloaded(self, app, network, gallery,
                                                     monkeypatch, card_images_dir):
        make_set('OGN', ACTIVE_RELEASE)
        seed_gallery_card('OGN', '1', rbcar_energy=9)
        _only(monkeypatch, 'OGN', ['1'])
        result = run(set_codes=['OGN'])

        ogn = _summary(result, 'OGN')
        assert ogn['applied'] == 1
        assert network.urls == ['https://img.test/ogn_1.png']
        assert ogn['images'] == {'downloaded': 1, 'existing': 0, 'failed': 0}

    def test_stored_card_missing_from_gallery_gets_its_image(
            self, app, network, gallery, monkeypatch, card_images_dir):
        make_set('OGN', ACTIVE_RELEASE)
        db.session.add(RbCard(rbcar_rbset_id='OGN', rbcar_id='99', rbcar_name='Gone',
                              image='ogn_99.png', image_url='https://img.test/ogn_99.png'))
        db.session.add(RbCard(rbcar_rbset_id='OGN', rbcar_id='98', rbcar_name='No URL',
                              image='ogn_98.png'))
        db.session.commit()
        _only(monkeypatch, 'OGN', [])
        result = run(set_codes=['OGN'])

        ogn = _summary(result, 'OGN')
        assert ogn['missing_from_gallery'] == 2
        assert network.urls == ['https://img.test/ogn_99.png']
        assert ogn['images'] == {'downloaded': 1, 'existing': 0, 'failed': 0}

    def test_failed_download_is_counted(self, app, monkeypatch, gallery, card_images_dir):
        session = FakeSession(fail={'https://img.test/ogn_1.png'})
        monkeypatch.setattr(riot_sync, '_get_session', lambda: session)
        make_set('OGN', ACTIVE_RELEASE)
        seed_gallery_card('OGN', '1')
        seed_gallery_card('OGN', '2')
        _only(monkeypatch, 'OGN')
        result = run(set_codes=['OGN'])

        assert _summary(result, 'OGN')['images'] == {'downloaded': 1, 'existing': 0,
                                                      'failed': 1}
        assert not (card_images_dir / 'ogn' / 'ogn_1.png').exists()

    def test_other_sets_are_not_touched(self, app, network, gallery, monkeypatch):
        make_set('OGN', ACTIVE_RELEASE)
        make_set('OGS', ACTIVE_RELEASE)
        seed_gallery_card('OGN', '1')
        seed_gallery_card('OGS', '5')
        result = run(set_codes=['OGN'])

        assert 'https://img.test/ogs_5.png' not in network.urls
        assert [s['set_id'] for s in result['sets']] == ['OGN']


class TestVenImageNames:
    """Owner feedback S4: VEN cards map to `ven/ven_<id>.png`."""

    def test_parsed_gallery_card_names_the_ven_file(self):
        from app.services.riot_scraper import _parse_card
        parsed = _parse_card({'id': 'ven-005-221', 'name': 'Card',
                              'cardImage': {'url': 'https://img.test/v5.png'}})
        assert (parsed['rbcar_rbset_id'], parsed['rbcar_id'], parsed['image']) == (
            'VEN', '5', 'ven_5.png')
        showcase = _parse_card({'id': 'ven-189-star-221', 'name': 'Card'})
        assert showcase['image'] == 'ven_189s.png'

    def test_image_src_and_disk_path(self, app, card_images_dir):
        from app.services.card_images import card_image_path
        card = RbCard(rbcar_rbset_id='VEN', rbcar_id='5', rbcar_name='Card',
                      image='ven_5.png')
        assert card.image_src == '/riftbound/media/cards/ven/ven_5.png'
        assert card_image_path('ven_5.png', 'VEN') == str(
            (card_images_dir / 'ven' / 'ven_5.png').resolve())
