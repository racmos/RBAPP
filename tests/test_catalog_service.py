"""F2-b S2-S4, S7 (AC1): parsing, ordering, base printings, card_summary."""
from app.models.card import RbCard
from app.services import catalog
from app.services.bans import name_key


def _card(set_id='OGN', card_id='1', **fields):
    values = dict(rbcar_rbset_id=set_id, rbcar_id=card_id, rbcar_name='X',
                  rbcar_domain=None, rbcar_type=None, rbcar_tags=None,
                  rbcar_energy=None, rbcar_power=None, rbcar_might=None,
                  rbcar_ability=None, rbcar_rarity=None, rbcar_artist=None,
                  image=None, image_url=None)
    values.update(fields)
    return RbCard(**values)


# --- S2: parsing -------------------------------------------------------------

def test_parse_domains_examples():
    assert catalog.parse_domains('fury  CHAOS') == ['Fury', 'Chaos']


def test_parse_domains_splits_commas_and_dedupes():
    assert catalog.parse_domains('Fury, fury ,Mind') == ['Fury', 'Mind']
    assert catalog.parse_domains('') == []
    assert catalog.parse_domains(None) == []


def test_parse_type_examples():
    assert catalog.parse_type('Champion Unit') == ('Unit', 'Champion')
    assert catalog.parse_type('Signature Spell') == ('Spell', 'Signature')
    assert catalog.parse_type('basic rune') == ('Rune', 'Basic')
    assert catalog.parse_type('Token Unit') == ('Unit', 'Token')
    assert catalog.parse_type('Legend') == ('Legend', None)
    assert catalog.parse_type('Creature') == ('Creature', None)
    assert catalog.parse_type('') == (None, None)
    assert catalog.parse_type(None) == (None, None)


def test_parse_tags_example():
    assert catalog.parse_tags('Aphelios, Mount Targon') == ['Aphelios', 'Mount Targon']
    assert catalog.parse_tags('a,,a, b ') == ['a', 'b']
    assert catalog.parse_tags(None) == []


def test_card_number():
    assert catalog.card_number('79a') == 79
    assert catalog.card_number('227s') == 227
    assert catalog.card_number('t03') is None
    assert catalog.card_number('10') == 10


def test_is_foilable():
    assert catalog.is_foilable('Unit', 'common') is True
    assert catalog.is_foilable('Unit', 'UNCOMMON') is True
    assert catalog.is_foilable('Legend', 'Common') is True
    assert catalog.is_foilable('Unit', 'Rare') is False
    assert catalog.is_foilable('Rune', 'Common') is False
    assert catalog.is_foilable('Spell', 'Showcase') is False
    assert catalog.is_foilable('Unit', None) is False
    assert catalog.is_foilable('Unit', '') is False


# --- S3: ordering ------------------------------------------------------------

def test_set_order_nulls_last_then_id():
    from datetime import date

    class S:
        def __init__(self, i, d):
            self.rbset_id = i
            self.rbset_outdat = d

    order = catalog.set_order([S('B', date(2026, 1, 2)), S('A', None),
                               S('C', date(2026, 1, 1)), S('D', None)])
    assert order == {'C': 0, 'B': 1, 'A': 2, 'D': 3}


def test_natural_key_orders_numbers_naturally():
    rank = {'OGN': 0}
    ids = ['t01', '10', '2', '1', '7', '7a']
    assert sorted(ids, key=lambda c: catalog.natural_key(rank['OGN'], c)) == [
        '1', '2', '7', '7a', '10', 't01']


def test_rarity_rank():
    assert [catalog.rarity_rank(r) for r in
            ('common', 'Uncommon', 'RARE', 'epic', 'showcase')] == [0, 1, 2, 3, 4]
    assert catalog.rarity_rank('Mythic') == 5
    assert catalog.rarity_rank(None) == 5


# --- S4: base printings ------------------------------------------------------

def test_base_printing_prefers_lowest_number_then_set():
    cards = [
        _card('OGNX', '257', rbcar_name='Jinx, Loose Cannon'),
        _card('OGN', '79', rbcar_name='Jinx, Loose Cannon'),
        _card('OGN', '79a', rbcar_name='Jinx, Loose Cannon'),
    ]
    rank = {'OGN': 0, 'OGNX': 1}
    assert catalog.base_printing_keys(cards, rank) == {('OGN', '79')}


def test_base_printing_token_group_uses_first_id():
    cards = [_card('OGN', 't02', rbcar_name='Pawn'), _card('OGN', 't01', rbcar_name='Pawn')]
    assert catalog.base_printing_keys(cards, {'OGN': 0}) == {('OGN', 't01')}


def test_base_printing_all_printings_of_each_name():
    cards = [_card('OGN', '1', rbcar_name='A'), _card('SFD', '5', rbcar_name='B')]
    assert catalog.base_printing_keys(cards, {'OGN': 0, 'SFD': 1}) == {
        ('OGN', '1'), ('SFD', '5')}


# --- S7: card_summary --------------------------------------------------------

def test_card_summary_shape_order_and_values(app):
    card = _card('OGN', '79a', rbcar_name='Jinx, Loose Cannon',
                 rbcar_domain='Chaos Fury', rbcar_type='Champion Unit',
                 rbcar_tags='Jinx, Zaun', rbcar_energy=3, rbcar_power=1,
                 rbcar_might=4, rbcar_rarity='Rare', rbcar_artist='A',
                 image='ogn_79a.png')
    summary = catalog.card_summary(
        card, set_rank={'OGN': 0}, base_keys={('OGN', '79a')},
        price={'market': 1.21, 'market_source': 'avg7_foil'},
        bans={name_key('Jinx, Loose Cannon'): {'2v2': object()}},
        owned={'total': 2, 'foil': 1})
    assert list(summary) == ['set_id', 'card_id', 'key', 'number', 'name', 'domains',
                             'type', 'supertype', 'type_raw', 'tags', 'energy', 'power',
                             'might', 'rarity', 'artist', 'image_src', 'image_thumb_src',
                             'foilable', 'is_base', 'price', 'bans', 'owned']
    assert summary['key'] == 'OGN-79a'
    assert summary['number'] == 79
    assert summary['domains'] == ['Chaos', 'Fury']
    assert (summary['type'], summary['supertype']) == ('Unit', 'Champion')
    assert summary['type_raw'] == 'Champion Unit'
    assert summary['tags'] == ['Jinx', 'Zaun']
    assert summary['image_src'] == '/riftbound/media/cards/ogn/ogn_79a.png'
    assert summary['image_thumb_src'] is None
    assert summary['foilable'] is False
    assert summary['is_base'] is True
    assert summary['price'] == {'market': 1.21, 'market_source': 'avg7_foil'}
    assert summary['bans'] == {'1v1': False, '2v2': True}
    assert summary['owned'] == {'total': 2, 'foil': 1}


def test_card_summary_defaults(app):
    card = _card()
    summary = catalog.card_summary(card, set_rank={}, base_keys=set())
    assert summary['owned'] == {'total': 0, 'foil': 0}
    assert summary['price'] is None
    assert summary['bans'] == {'1v1': False, '2v2': False}
    assert summary['is_base'] is False


def test_card_summary_uses_name_key_grouping(app):
    card = _card('OGN', '1', rbcar_name='  Kai’Sa,  Daughter of the Void ')
    assert name_key(card.rbcar_name) == "kai'sa, daughter of the void"
