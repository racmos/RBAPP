"""Owner feedback 2026-10-29 S12, S13, S15, S16: the sync compares the gallery with
the stored card under the owner's rules. No network: the gallery and the image bytes
come from fixtures and a fake session (see `tests/test_riot_sync.py`)."""
from datetime import date, datetime

import pytest

from app import db
from app.models.card import RbCard
from app.models.card_change import RbCardChange
from app.models.set import RbSet
from app.services import riot_sync
from app.services.riot_scraper import _parse_card
from tests.test_riot_sync import FakeSession

ACTIVE_DAY = datetime(2026, 10, 10)
ACTIVE_RELEASE = date(2026, 10, 1)
MONTHLY_RELEASE = date(2025, 1, 1)


@pytest.fixture(autouse=True)
def _images_root(card_images_dir):
    return card_images_dir


@pytest.fixture
def network(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(riot_sync, '_get_session', lambda: session)
    return session


def gallery_card(set_id, card_id, **overrides):
    card = {'rbcar_rbset_id': set_id, 'rbcar_id': card_id, 'rbcar_name': 'Card',
            'rbcar_domain': 'Fury', 'rbcar_type': 'Unit', 'rbcar_tags': '',
            'rbcar_energy': 2, 'rbcar_power': 1, 'rbcar_might': 3,
            'rbcar_ability': '', 'rbcar_rarity': 'Common', 'rbcar_artist': 'An Artist',
            'image_url': f'https://img.test/{set_id.lower()}_{card_id}.png',
            'image': f'{set_id.lower()}_{card_id}.png'}
    card.update(overrides)
    return card


def serve(monkeypatch, *cards):
    codes = sorted({c['rbcar_rbset_id'] for c in cards})
    monkeypatch.setattr(riot_sync, 'fetch_gallery',
                        lambda: {'cards': [dict(c) for c in cards], 'set_codes': codes,
                                 'unparsed': 0})


def make_set(set_id, release, ncard=None):
    db.session.add(RbSet(rbset_id=set_id, rbset_name=set_id, rbset_ncard=ncard,
                         rbset_outdat=release))
    db.session.commit()


def store(card):
    db.session.add(RbCard(**{k: v for k, v in card.items() if k in RbCard.__table__.columns}))
    db.session.commit()


def run(set_id, now=ACTIVE_DAY):
    result = riot_sync.sync(set_codes=[set_id], trigger='manual', now=now)
    return next(s for s in result['sets'] if s['set_id'] == set_id)


def card(set_id, card_id):
    return RbCard.query.filter_by(rbcar_rbset_id=set_id, rbcar_id=card_id).one()


def proposals():
    return sorted((r.rbchg_rbcar_id, r.rbchg_field, r.rbchg_old_value, r.rbchg_new_value)
                  for r in RbCardChange.query.filter_by(rbchg_status='pending'))


def real_item(item_id, name, supertypes, types, subtitle=None, tags=()):
    """A gallery item with the shape of the live page (2026-10-29), trimmed."""
    def labels(values):
        return [{'id': v.lower(), 'label': v} for v in values]
    item = {'id': item_id, 'collectorNumber': int(item_id.split('-')[1][:3]),
            'name': name,
            'cardType': {'label': 'Card Type', 'type': labels(types),
                         'superType': labels(supertypes)},
            'tags': {'label': 'Tags', 'tags': list(tags)},
            'rarity': {'label': 'Rarity', 'value': {'id': 'rare', 'label': 'Rare'}},
            'cardImage': {'type': 'image',
                          'url': f'https://img.test/{item_id}.png?accountingTag=RB'}}
    if subtitle is not None:
        item['subtitle'] = subtitle
    return item


class TestParsedName:
    """S12: the gallery sends `name` and `subtitle` apart; only Legends store the
    bare name. Signature cards carry the champion as subtitle, not in the name."""

    def test_champion_unit_gets_name_and_subtitle(self):
        parsed = _parse_card(real_item('ogn-066-298', 'Ahri', ['Champion'], ['Unit'],
                                       subtitle='Alluring', tags=['Ahri', 'Ionia']))
        assert parsed['rbcar_name'] == 'Ahri, Alluring'

    def test_champion_legend_keeps_the_bare_name(self):
        parsed = _parse_card(real_item('ogs-017-024', 'Dark Child', ['Champion'],
                                       ['Legend'], subtitle='Starter', tags=['Annie']))
        assert (parsed['rbcar_name'], parsed['rbcar_type']) == ('Dark Child', 'Legend')

    def test_legend_without_subtitle(self):
        parsed = _parse_card(real_item('rad-175-167', "Agony's Embrace", [], ['Legend'],
                                       tags=['Evelynn']))
        assert parsed['rbcar_name'] == "Agony's Embrace"

    def test_signature_cards_keep_the_bare_name(self):
        spell = _parse_card(real_item('ogn-268-298', 'Bullet Time', ['Signature'],
                                      ['Spell'], subtitle='Miss Fortune'))
        unit = _parse_card(real_item('ogs-018-024', 'Tibbers', ['Signature'], ['Unit'],
                                     subtitle='Annie'))
        assert (spell['rbcar_name'], unit['rbcar_name']) == ('Bullet Time', 'Tibbers')

    def test_cards_without_subtitle_keep_the_name(self):
        plain = _parse_card(real_item('unl-041-219', 'Allay, Eager Admirer', [], ['Unit']))
        empty = _parse_card(real_item('ogn-001-298', 'Blazing Scorcher', [], ['Unit'],
                                      subtitle=''))
        assert (plain['rbcar_name'], empty['rbcar_name']) == (
            'Allay, Eager Admirer', 'Blazing Scorcher')


class TestNameRule:
    """S12: only Legend cards have their name split from the tag. The sync also
    reads a bare gallery name as the stored full one (the shape the pending
    proposals of the old parser have; `flask riot recheck-pending` uses it)."""

    def test_unit_full_name_matches_the_short_gallery_name(self, app, network, monkeypatch):
        make_set('OGN', MONTHLY_RELEASE)
        store(gallery_card('OGN', '66', rbcar_name='Ahri, Alluring',
                           rbcar_type='Champion Unit'))
        serve(monkeypatch, gallery_card('OGN', '66', rbcar_name='Ahri',
                                        rbcar_type='Champion Unit'))
        summary = run('OGN')
        assert (summary['unchanged'], summary['proposed']) == (1, 0)
        assert proposals() == []
        assert card('OGN', '66').rbcar_name == 'Ahri, Alluring'

    def test_active_window_keeps_the_full_name(self, app, network, monkeypatch):
        make_set('OGN', ACTIVE_RELEASE)
        store(gallery_card('OGN', '66', rbcar_name='Riven, Shattered'))
        serve(monkeypatch, gallery_card('OGN', '66', rbcar_name='Riven'))
        summary = run('OGN')
        assert (summary['unchanged'], summary['applied']) == (1, 0)
        assert card('OGN', '66').rbcar_name == 'Riven, Shattered'

    def test_a_really_different_name_is_still_proposed(self, app, network, monkeypatch):
        make_set('OGN', MONTHLY_RELEASE)
        store(gallery_card('OGN', '66', rbcar_name='Riven, Shattered'))
        serve(monkeypatch, gallery_card('OGN', '66', rbcar_name='Rivenna'))
        run('OGN')
        assert proposals() == [('66', 'rbcar_name', 'Riven, Shattered', 'Rivenna')]

    def test_a_longer_gallery_name_is_still_proposed(self, app, network, monkeypatch):
        make_set('OGN', MONTHLY_RELEASE)
        store(gallery_card('OGN', '66', rbcar_name='Riven'))
        serve(monkeypatch, gallery_card('OGN', '66', rbcar_name='Riven, Shattered'))
        run('OGN')
        assert proposals() == [('66', 'rbcar_name', 'Riven', 'Riven, Shattered')]

    def test_legend_name_is_compared_as_today(self, app, network, monkeypatch):
        make_set('OGS', MONTHLY_RELEASE)
        store(gallery_card('OGS', '5', rbcar_name='Ahri, Nine-Tailed Fox',
                           rbcar_type='Legend'))
        serve(monkeypatch, gallery_card('OGS', '5', rbcar_name='Ahri', rbcar_type='Legend'))
        run('OGS')
        assert proposals() == [('5', 'rbcar_name', 'Ahri, Nine-Tailed Fox', 'Ahri')]


class TestTypeRule:
    """S13: the gallery's "Champion Legend" is the type "Legend"."""

    def test_parser_stores_champion_legend_as_legend(self):
        parsed = _parse_card({'id': 'ogs-005-024', 'name': 'Ahri',
                              'cardType': {'superType': [{'label': 'Champion'}],
                                           'type': [{'label': 'Legend'}]}})
        assert parsed['rbcar_type'] == 'Legend'

    def test_parser_keeps_the_other_supertypes(self):
        for supertype, kind in (('Champion', 'Unit'), ('Signature', 'Spell'),
                                ('Token', 'Unit'), ('Basic', 'Rune')):
            parsed = _parse_card({'id': 'ogn-001-298', 'name': 'X',
                                  'cardType': {'superType': [{'label': supertype}],
                                               'type': [{'label': kind}]}})
            assert parsed['rbcar_type'] == f'{supertype} {kind}'

    def test_sync_does_not_propose_champion_legend(self, app, network, monkeypatch):
        make_set('OGS', MONTHLY_RELEASE)
        store(gallery_card('OGS', '5', rbcar_type='Legend'))
        serve(monkeypatch, gallery_card('OGS', '5', rbcar_type='Champion Legend'))
        summary = run('OGS')
        assert (summary['unchanged'], summary['proposed']) == (1, 0)
        assert card('OGS', '5').rbcar_type == 'Legend'


class TestRarityRule:
    """S15: above the set's card count a card is Showcase; at or below it a gallery
    "Showcase" never replaces the stored rarity."""

    def test_alternate_art_at_or_below_the_count_keeps_its_rarity(self, app, network,
                                                                monkeypatch):
        make_set('VEN', MONTHLY_RELEASE, ncard=166)
        store(gallery_card('VEN', '69a', rbcar_rarity='Epic'))
        store(gallery_card('VEN', '166', rbcar_rarity='Rare'))
        serve(monkeypatch, gallery_card('VEN', '69a', rbcar_rarity='Showcase'),
              gallery_card('VEN', '166', rbcar_rarity='Showcase'))
        summary = run('VEN')
        assert (summary['unchanged'], summary['proposed']) == (2, 0)
        assert card('VEN', '69a').rbcar_rarity == 'Epic'

    def test_active_window_keeps_the_rarity_too(self, app, network, monkeypatch):
        make_set('VEN', ACTIVE_RELEASE, ncard=166)
        store(gallery_card('VEN', '21a', rbcar_rarity='Epic'))
        serve(monkeypatch, gallery_card('VEN', '21a', rbcar_rarity='Showcase'))
        summary = run('VEN')
        assert (summary['unchanged'], summary['applied']) == (1, 0)
        assert card('VEN', '21a').rbcar_rarity == 'Epic'

    def test_above_the_count_is_showcase(self, app, network, monkeypatch):
        make_set('VEN', MONTHLY_RELEASE, ncard=166)
        store(gallery_card('VEN', '189s', rbcar_rarity='Epic'))
        store(gallery_card('VEN', '167', rbcar_rarity='Rare'))
        store(gallery_card('VEN', '197', rbcar_rarity='Showcase'))
        serve(monkeypatch, gallery_card('VEN', '189s', rbcar_rarity='Showcase'),
              gallery_card('VEN', '167', rbcar_rarity='Rare'),
              gallery_card('VEN', '197', rbcar_rarity='Epic'))
        summary = run('VEN')
        assert (summary['unchanged'], summary['proposed']) == (1, 2)
        assert proposals() == [('167', 'rbcar_rarity', 'Rare', 'Showcase'),
                               ('189s', 'rbcar_rarity', 'Epic', 'Showcase')]

    def test_new_cards(self, app, network, monkeypatch):
        make_set('VEN', ACTIVE_RELEASE, ncard=166)
        serve(monkeypatch, gallery_card('VEN', '69a', rbcar_rarity='Showcase'),
              gallery_card('VEN', '197', rbcar_rarity='Epic'),
              gallery_card('VEN', '5', rbcar_rarity='Common'))
        summary = run('VEN')
        assert summary['inserted'] == 3
        assert card('VEN', '69a').rbcar_rarity == 'Showcase'
        assert card('VEN', '197').rbcar_rarity == 'Showcase'
        assert card('VEN', '5').rbcar_rarity == 'Common'

    def test_ids_without_a_number_are_unaffected(self, app, network, monkeypatch):
        make_set('VEN', MONTHLY_RELEASE, ncard=166)
        store(gallery_card('VEN', 't04', rbcar_rarity='Common'))
        serve(monkeypatch, gallery_card('VEN', 't04', rbcar_rarity='Showcase'))
        run('VEN')
        assert proposals() == [('t04', 'rbcar_rarity', 'Common', 'Showcase')]

    def test_without_a_card_count_the_gallery_rarity_is_proposed(self, app, network,
                                                                 monkeypatch):
        make_set('VEN', MONTHLY_RELEASE, ncard=None)
        store(gallery_card('VEN', '69a', rbcar_rarity='Epic'))
        serve(monkeypatch, gallery_card('VEN', '69a', rbcar_rarity='Showcase'))
        run('VEN')
        assert proposals() == [('69a', 'rbcar_rarity', 'Epic', 'Showcase')]

    def test_card_number(self):
        assert [riot_sync.card_number(i) for i in ('69a', '197', '189s', 't04', '')] == [
            69, 197, 189, None, None]


class TestImageUrlRule:
    """S16: the query string and the fragment of an image URL are not a change."""

    def test_query_only_difference_is_no_change(self, app, network, monkeypatch):
        make_set('OGN', MONTHLY_RELEASE)
        store(gallery_card('OGN', '1', image_url='https://img.test/a/ogn_1.png'))
        store(gallery_card('OGN', '2', image_url='https://img.test/a/ogn_2.png?x=1#top'))
        serve(monkeypatch,
              gallery_card('OGN', '1', image_url='https://img.test/a/ogn_1.png?accountingTag=RB'),
              gallery_card('OGN', '2', image_url='https://img.test/a/ogn_2.png'))
        summary = run('OGN')
        assert (summary['unchanged'], summary['proposed']) == (2, 0)
        assert card('OGN', '1').image_url == 'https://img.test/a/ogn_1.png'
        assert card('OGN', '2').image_url == 'https://img.test/a/ogn_2.png?x=1#top'

    def test_active_window_writes_nothing(self, app, network, monkeypatch):
        make_set('OGN', ACTIVE_RELEASE)
        store(gallery_card('OGN', '1', image_url='https://img.test/a/ogn_1.png'))
        serve(monkeypatch,
              gallery_card('OGN', '1', image_url='https://img.test/a/ogn_1.png?accountingTag=RB'))
        summary = run('OGN')
        assert (summary['unchanged'], summary['applied']) == (1, 0)
        assert card('OGN', '1').image_url == 'https://img.test/a/ogn_1.png'

    def test_a_different_path_is_still_a_change(self, app, network, monkeypatch):
        make_set('OGN', MONTHLY_RELEASE)
        store(gallery_card('OGN', '1', image_url='https://img.test/a/ogn_1.png'))
        serve(monkeypatch,
              gallery_card('OGN', '1', image_url='https://img.test/b/ogn_1.png?accountingTag=RB'))
        run('OGN')
        assert proposals() == [('1', 'image_url', 'https://img.test/a/ogn_1.png',
                                'https://img.test/b/ogn_1.png?accountingTag=RB')]
