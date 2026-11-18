"""Riot sync imports every gallery card (owner requirement 2026-11-18).

The gallery card ids the three historical patterns did not know (runes `rad-r01`, their
variants `rad-r01a`, the special prints `rad-sp1-005`) were dropped with a log line. Now:
the set comes from the gallery's `set.value.id` (the id prefix only when it is missing), the
historical patterns keep their exact results, runes and special prints get their own rule
(lower case, like tokens and admin-created ids) and any other `<set>-<rest>` id falls back to
the rest. Only an item with no recognisable set is skipped, and it is counted and named.
No network: gallery items are dicts (`tests/riot_gallery_helpers.py`).
"""
from datetime import date, datetime

import pytest

from app import db
from app.models.audit import RbAdminAudit
from app.models.card import RbCard
from app.models.card_change import RbCardChange
from app.models.set import RbSet
from app.services import catalog, riot_sync
from app.services.card_images import card_image_path
from app.services.riot_scraper import _parse_card
from tests.import_helpers import PREVIEW
from tests.riot_gallery_helpers import REAL_NEW_IDS, REAL_NEW_ITEMS, gallery_item

PNG = b'\x89PNG\r\n\x1a\nimage-bytes'
MONTHLY_RELEASE = date(2025, 1, 1)      # long before the run: monthly window
RUN_AT = datetime(2026, 11, 18, 9, 0)


def ids_of(item):
    parsed = _parse_card(item)
    return None if parsed is None else (
        parsed['rbcar_rbset_id'], parsed['rbcar_id'], parsed['image'])


# --- the historical patterns keep their exact results -------------------------------------

# Every shape the live gallery uses for the 1379 cards that parsed before (2026-11-18):
# `<set>-<n>-<total>`, `<set>-<n><letter>-<total>`, `<set>-<n>-star-<total>`, `<set>-t<n>`.
PINNED = {
    'ogn-001-298': ('OGN', '1', 'ogn_1.png'),
    'ogn-066-298': ('OGN', '66', 'ogn_66.png'),
    'ogn-298-298': ('OGN', '298', 'ogn_298.png'),
    'ogn-079a-298': ('OGN', '79a', 'ogn_79a.png'),
    'ogs-024-024': ('OGS', '24', 'ogs_24.png'),
    'sfd-138-221': ('SFD', '138', 'sfd_138.png'),
    'sfd-050b-221': ('SFD', '50b', 'sfd_50b.png'),
    'sfd-227-star-221': ('SFD', '227s', 'sfd_227s.png'),
    'sfd-t03': ('SFD', 't03', 'sfd_t03.png'),
    'unl-t10': ('UNL', 't10', 'unl_t10.png'),
    'unl-100-219': ('UNL', '100', 'unl_100.png'),
    'ven-189-star-221': ('VEN', '189s', 'ven_189s.png'),
    'ven-005-221': ('VEN', '5', 'ven_5.png'),
    'rad-007-219': ('RAD', '7', 'rad_7.png'),
}


class TestHistoricalPatternsArePinned:
    @pytest.mark.parametrize('raw_id', sorted(PINNED))
    def test_without_a_set_key_the_prefix_decides(self, raw_id):
        assert ids_of(gallery_item(raw_id, 'Card')) == PINNED[raw_id]

    @pytest.mark.parametrize('raw_id', sorted(PINNED))
    def test_with_the_gallery_set_the_result_is_the_same(self, raw_id):
        set_id = raw_id.split('-')[0].upper()
        assert ids_of(gallery_item(raw_id, 'Card', set_id=set_id)) == PINNED[raw_id]

    def test_the_other_fields_are_unchanged(self):
        parsed = _parse_card(gallery_item(
            'ogn-079a-298', 'Jinx', subtitle='Loose Cannon', set_id='OGN',
            supertypes=('Champion',), rarity='Rare', domain='Chaos', energy='4', power='1',
            might='3', text='<p>Deal 2 &amp; draw.</p>'))
        assert parsed == {
            'rbcar_rbset_id': 'OGN', 'rbcar_id': '79a', 'rbcar_name': 'Jinx, Loose Cannon',
            'rbcar_domain': 'Chaos', 'rbcar_type': 'Champion Unit', 'rbcar_tags': '',
            'rbcar_energy': 4, 'rbcar_power': 1, 'rbcar_might': 3,
            'rbcar_ability': 'Deal 2 & draw.', 'rbcar_rarity': 'Rare',
            'rbcar_artist': 'An Artist',
            'image_url': 'https://img.test/ogn-079a-298.png?accountingTag=RB',
            'image': 'ogn_79a.png'}


# --- the new id forms -----------------------------------------------------------------------

class TestNewIdForms:
    def test_the_29_real_cards_the_old_patterns_dropped(self):
        assert len(REAL_NEW_ITEMS) == 29
        assert {item['id']: ids_of(item) for item in REAL_NEW_ITEMS} == REAL_NEW_IDS

    def test_special_prints_are_unique_within_a_set(self):
        keys = [ids_of(item)[:2] for item in REAL_NEW_ITEMS]
        assert len(keys) == len(set(keys)) == 29

    @pytest.mark.parametrize('raw_id, expected', [
        ('rad-r01', 'r01'), ('rad-R01A', 'r01a'), ('rad-r12b', 'r12b'),
        ('rad-sp1-005', 'sp1'), ('rad-SP10-012', 'sp10'),
    ])
    def test_runes_and_special_prints_are_lower_case(self, raw_id, expected):
        assert ids_of(gallery_item(raw_id, 'Card'))[1] == expected

    def test_the_set_comes_from_the_gallery_filter_not_the_id(self):
        assert ids_of(gallery_item('ogn-012-298', 'Card', set_id='OGNX')) == (
            'OGNX', '12', 'ognx_12.png')
        assert ids_of(gallery_item('xyz-r02', 'Calm Rune', set_id='RAD')) == (
            'RAD', 'r02', 'rad_r02.png')

    def test_a_set_value_is_trimmed_and_upper_cased(self):
        assert ids_of(gallery_item('rad-r03', 'Mind Rune', set_id=' rad ')) == (
            'RAD', 'r03', 'rad_r03.png')

    def test_an_unusable_set_value_falls_back_to_the_prefix(self):
        item = gallery_item('ven-r04', 'Body Rune')
        item['set'] = {'value': {'id': 'V N!'}}
        assert ids_of(item) == ('VEN', 'r04', 'ven_r04.png')
        item['set'] = {'value': None}
        assert ids_of(item) == ('VEN', 'r04', 'ven_r04.png')

    @pytest.mark.parametrize('raw_id, expected', [
        ('rad-promo-007', 'promo-7'),
        ('rad-x07-b-005', 'x07-b-5'),
        ('rad-Alt_Art.01', 'altart01'),
        ('rad-000', '0'),
        ('rad-0042x', '42x'),
        ('rad--9-', '9'),
    ])
    def test_any_other_shape_keeps_the_rest_of_the_id(self, raw_id, expected):
        set_id, card_id, image = ids_of(gallery_item(raw_id, 'Card', set_id='RAD'))
        assert (set_id, card_id, image) == ('RAD', expected, f'rad_{expected}.png')

    def test_an_id_without_a_prefix_uses_the_whole_id_when_the_set_is_known(self):
        assert ids_of(gallery_item('Promo12', 'Card', set_id='RAD')) == (
            'RAD', 'promo12', 'rad_promo12.png')

    @pytest.mark.parametrize('item', [
        {'id': 'nomatch', 'name': 'No set at all'},
        {'id': '', 'name': 'No id'},
        {'name': 'No id key'},
        {'id': '-005', 'name': 'Empty prefix'},
        {'id': '!!!-5', 'name': 'Prefix of symbols'},
        {'id': 'rad-!!!', 'name': 'Nothing left of the card part'},
    ])
    def test_only_an_item_without_a_set_or_a_card_part_is_skipped(self, item):
        assert _parse_card(item) is None


# --- downstream: images, Showcase rule, natural sort ----------------------------------------

class TestImagesOfTheNewIds:
    @pytest.mark.parametrize('image, folder', [
        ('rad_r01.png', 'rad'), ('rad_r01a.png', 'rad'), ('ven_sp6.png', 'ven'),
        ('rad_promo-7.png', 'rad'),
    ])
    def test_path_and_url(self, app, card_images_dir, image, folder):
        set_id = folder.upper()
        assert card_image_path(image, set_id) == str(
            (card_images_dir / folder / image).resolve())
        card = RbCard(rbcar_rbset_id=set_id, rbcar_id='x', rbcar_name='Card', image=image)
        assert card.image_src == f'/riftbound/media/cards/{folder}/{image}'


class TestShowcaseRule:
    """S15 forces Showcase on a card numbered above the set count; runes and special
    prints have no number, so they keep the rarity the gallery gives."""

    @pytest.mark.parametrize('card_id, gallery, expected', [
        ('r01', 'Common', 'Common'), ('r01a', 'Showcase', 'Showcase'),
        ('sp1', 'Showcase', 'Showcase'), ('sp1', 'Rare', 'Rare'),
    ])
    def test_ids_without_a_number_keep_the_gallery_rarity(self, card_id, gallery, expected):
        assert riot_sync.card_number(card_id) is None
        assert riot_sync.gallery_value('rbcar_rarity', None, gallery, card_id=card_id,
                                       ncard=0, legend=False) == expected

    def test_numbered_cards_still_follow_the_rule(self):
        assert riot_sync.gallery_value('rbcar_rarity', None, 'Common', card_id='7',
                                       ncard=5, legend=False) == 'Showcase'


class TestNaturalSort:
    def test_runes_and_special_prints_sort_after_the_numbered_cards(self):
        ids = ['t01', 'sp10', 'r01a', 'sp2', '10', 'r01', '2', 'r02', '7a', '7', 'sp1']
        assert sorted(ids, key=lambda c: catalog.natural_key(0, c)) == [
            '2', '7', '7a', '10', 'r01', 'r01a', 'r02', 'sp1', 'sp2', 'sp10', 't01']

    def test_the_historical_order_is_kept(self):
        ids = ['t01', '10', '2', '1', '7', '7a', '227s', '227', 't10', 't02']
        assert sorted(ids, key=lambda c: catalog.natural_key(0, c)) == [
            '1', '2', '7', '7a', '10', '227', '227s', 't01', 't02', 't10']


# --- fetch_gallery: skipped items are counted and named -------------------------------------

class FakeResponse:
    def __init__(self, content=b''):
        self.content = content

    def raise_for_status(self):
        pass


class FakeSession:
    def __init__(self):
        self.urls = []

    def get(self, url, timeout=None):
        self.urls.append(url)
        return FakeResponse(PNG)


@pytest.fixture
def network(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(riot_sync, '_get_session', lambda: session)
    return session


def serve(monkeypatch, items):
    monkeypatch.setattr(riot_sync, '_fetch_gallery_json', lambda session: list(items))


class TestFetchGallerySkipped:
    def test_new_ids_are_parsed_and_their_sets_listed(self, monkeypatch, network):
        serve(monkeypatch, REAL_NEW_ITEMS)
        gallery = riot_sync.fetch_gallery()
        assert gallery['unparsed'] == 0 and gallery['unparsed_ids'] == []
        assert gallery['set_codes'] == ['RAD', 'VEN']
        assert len(gallery['cards']) == 29

    def test_skipped_items_are_counted_and_named(self, monkeypatch, network):
        serve(monkeypatch, [gallery_item('ogn-001-298', 'Card', set_id='OGN'),
                            {'id': 'nomatch', 'name': 'X'}, {'id': '', 'name': 'Y'},
                            {'name': 'Z'}])
        gallery = riot_sync.fetch_gallery()
        assert len(gallery['cards']) == 1
        assert gallery['unparsed'] == 3
        assert gallery['unparsed_ids'] == ['nomatch']

    def test_at_most_ten_ids_are_named(self, monkeypatch, network):
        serve(monkeypatch, [{'id': f'nomatch{n}', 'name': 'X'} for n in range(12)])
        gallery = riot_sync.fetch_gallery()
        assert gallery['unparsed'] == 12
        assert gallery['unparsed_ids'] == [f'nomatch{n}' for n in range(10)]

    def test_a_second_item_with_the_same_card_is_skipped_and_named(self, monkeypatch,
                                                                    network):
        serve(monkeypatch, [gallery_item('ogn-001-298', 'First', set_id='OGN'),
                            gallery_item('ogn-1-298', 'Second', set_id='OGN')])
        gallery = riot_sync.fetch_gallery()
        assert [c['rbcar_name'] for c in gallery['cards']] == ['First']
        assert gallery['unparsed'] == 1 and gallery['unparsed_ids'] == ['ogn-1-298']

    def test_the_sync_result_reports_them(self, app, monkeypatch, network, card_images_dir):
        serve(monkeypatch, [gallery_item('ogn-001-298', 'Card', set_id='OGN'),
                            {'id': 'nomatch', 'name': 'X'}])
        db.session.add(RbSet(rbset_id='OGN', rbset_name='Origins',
                             rbset_outdat=MONTHLY_RELEASE))
        db.session.commit()
        result = riot_sync.sync(trigger='manual', now=RUN_AT)
        assert result['gallery'] == {'cards': 1, 'unparsed': 1, 'unparsed_ids': ['nomatch'],
                                     'set_codes': ['OGN']}


# --- the sync inserts the missing cards once, on an existing catalog ------------------------

EXISTING = [
    gallery_item('ogn-001-298', 'Alpha', set_id='OGN', energy='2', might='3'),
    gallery_item('ogn-002-298', 'Beta', set_id='OGN', card_type='Spell', energy='1'),
    gallery_item('rad-001-219', 'Gamma', set_id='RAD', rarity='Rare'),
    gallery_item('ven-t01', 'Token', set_id='VEN', supertypes=('Token',), rarity='Common'),
]


def seed_existing():
    db.session.add_all([
        RbSet(rbset_id='OGN', rbset_name='Origins', rbset_outdat=MONTHLY_RELEASE, rbset_ncard=298),
        RbSet(rbset_id='RAD', rbset_name='Radiance', rbset_outdat=MONTHLY_RELEASE, rbset_ncard=1),
        RbSet(rbset_id='VEN', rbset_name='Vendetta', rbset_outdat=MONTHLY_RELEASE, rbset_ncard=0),
    ])
    for item in EXISTING:
        parsed = _parse_card(item)
        db.session.add(RbCard(**{k: v for k, v in parsed.items()
                                 if k in RbCard.__table__.columns}))
    db.session.commit()


def by_set(result):
    return {s['set_id']: s for s in result['sets']}


class TestSyncInsertsTheNewCards:
    @pytest.fixture
    def catalog_and_gallery(self, app, monkeypatch, network, card_images_dir):
        seed_existing()
        serve(monkeypatch, EXISTING + REAL_NEW_ITEMS)
        return card_images_dir

    def test_first_run_inserts_the_29_cards_directly_and_proposes_nothing(
            self, catalog_and_gallery):
        result = riot_sync.sync(trigger='manual', now=RUN_AT)
        sets = by_set(result)
        assert {k: (s['window'], s['inserted'], s['applied'], s['proposed'], s['unchanged'],
                    s['error']) for k, s in sets.items()} == {
            'OGN': ('monthly', 0, 0, 0, 2, None),
            'RAD': ('monthly', 17, 0, 0, 1, None),
            'VEN': ('monthly', 12, 0, 0, 1, None),
        }
        assert result['gallery']['unparsed'] == 0
        assert result['placeholder_sets'] == []
        assert RbCardChange.query.count() == 0
        stored = {(c.rbcar_rbset_id, c.rbcar_id): c for c in RbCard.query.all()}
        assert len(stored) == 4 + 29
        for set_id, card_id, image in REAL_NEW_IDS.values():
            assert stored[(set_id, card_id)].image == image
            assert (catalog_and_gallery / set_id.lower() / image).read_bytes() == PNG

    def test_rarities_are_the_gallery_ones(self, catalog_and_gallery):
        riot_sync.sync(trigger='manual', now=RUN_AT)
        rarity = {(c.rbcar_rbset_id, c.rbcar_id): c.rbcar_rarity for c in RbCard.query.all()}
        assert rarity[('RAD', 'r01')] == 'Common'
        assert rarity[('VEN', 'r06')] == 'Common'
        assert rarity[('RAD', 'r01a')] == 'Showcase'
        assert rarity[('VEN', 'sp6')] == 'Showcase'
        assert rarity[('RAD', '1')] == 'Rare'

    def test_names_and_types(self, catalog_and_gallery):
        riot_sync.sync(trigger='manual', now=RUN_AT)
        rune = db.session.get(RbCard, ('RAD', 'r01a'))
        special = db.session.get(RbCard, ('VEN', 'sp1'))
        assert (rune.rbcar_name, rune.rbcar_type, rune.rbcar_domain) == (
            'Fury Rune', 'Basic Rune', 'Fury')
        assert (special.rbcar_name, special.rbcar_type) == ("Kai'Sa, Survivor", 'Champion Unit')

    def test_the_insert_audit_lists_the_new_ids(self, catalog_and_gallery):
        riot_sync.sync(trigger='manual', now=RUN_AT)
        rows = {row.rbaud_target_id: row.rbaud_details['cards'] for row in
                RbAdminAudit.query.filter_by(rbaud_action='riot.insert').all()}
        assert set(rows) == {'RAD', 'VEN'}
        assert sorted(rows['VEN']) == sorted(
            [f'r0{n}' for n in range(1, 7)] + [f'sp{n}' for n in range(1, 7)])

    def test_a_second_run_changes_nothing(self, catalog_and_gallery):
        riot_sync.sync(trigger='manual', now=RUN_AT)
        result = riot_sync.sync(trigger='manual', now=RUN_AT)
        sets = by_set(result)
        assert {k: (s['inserted'], s['applied'], s['proposed'], s['unchanged'])
                for k, s in sets.items()} == {
            'OGN': (0, 0, 0, 2), 'RAD': (0, 0, 0, 18), 'VEN': (0, 0, 0, 13)}
        assert sets['RAD']['images']['downloaded'] == 0
        assert RbCardChange.query.count() == 0
        assert RbCard.query.count() == 33
        assert RbAdminAudit.query.filter_by(rbaud_action='riot.insert').count() == 2


# --- downstream: catalog API, collection and CSV round trip ---------------------------------

@pytest.fixture
def new_cards(app, monkeypatch, network, card_images_dir):
    seed_existing()
    serve(monkeypatch, EXISTING + REAL_NEW_ITEMS)
    riot_sync.sync(trigger='manual', now=RUN_AT)


class TestTheNewIdsDownstream:
    def test_cards_list_sorts_them_after_the_numbered_cards(self, authenticated_client,
                                                             new_cards):
        response = authenticated_client.get('/riftbound/api/v1/cards?set=RAD&per_page=50')
        assert response.status_code == 200, response.get_data(as_text=True)
        ids = [item['card_id'] for item in response.get_json()['data']['items']]
        assert ids == (['1'] + [f'r0{n}{v}' for n in range(1, 7) for v in ('', 'a')]
                       + [f'sp{n}' for n in range(1, 6)])

    def test_card_detail_of_a_rune_and_a_special_print(self, authenticated_client, new_cards):
        for set_id, card_id in (('RAD', 'r01a'), ('VEN', 'sp3')):
            response = authenticated_client.get(f'/riftbound/api/v1/cards/{set_id}/{card_id}')
            assert response.status_code == 200, response.get_data(as_text=True)
            data = response.get_json()['data']
            assert (data['set_id'], data['card_id'], data['number']) == (set_id, card_id, None)
            assert data['image_src'] == (
                f'/riftbound/media/cards/{set_id.lower()}/{set_id.lower()}_{card_id}.png')

    def test_a_rune_is_never_foilable(self, authenticated_client, new_cards):
        data = authenticated_client.get('/riftbound/api/v1/cards/RAD/r01').get_json()['data']
        assert data['foilable'] is False

    def test_collection_csv_round_trip(self, authenticated_client, new_cards):
        for set_id, card_id in (('RAD', 'r01a'), ('VEN', 'sp6'), ('VEN', 'r02')):
            response = authenticated_client.post('/riftbound/api/v1/collection', json={
                'set_id': set_id, 'card_id': card_id, 'foil': False, 'qty': 2})
            assert response.status_code == 201, response.get_data(as_text=True)
        exported = authenticated_client.get('/riftbound/api/v1/collection/export')
        assert exported.status_code == 200
        text = exported.get_data(as_text=True).lstrip('﻿')
        assert 'RAD,r01a,' in text and 'VEN,sp6,' in text and 'VEN,r02,' in text
        preview = authenticated_client.post(PREVIEW, json={'text': text})
        assert preview.status_code == 200, preview.get_data(as_text=True)
        rows = preview.get_json()['data']['rows']
        assert sorted((r['set_id'], r['card_id'], r['status']) for r in rows) == [
            ('RAD', 'r01a', 'ok'), ('VEN', 'r02', 'ok'), ('VEN', 'sp6', 'ok')]
