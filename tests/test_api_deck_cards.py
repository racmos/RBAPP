"""F5-i step 1: every `DeckCard` of the decks API carries energy, power, might, rarity,
`variants` (printings of the name) and `keywords` (from the ability text, approximate)."""
import pytest

from app import db
from app.models import RbCard, RbSet
from tests.deck_api_helpers import AZIR, BASE, data, make_deck, seed_catalog
from tests.product_helpers import count_statements

PUBLIC = '/riftbound/api/v1/public/decks'
NEW_KEYS = ['energy', 'power', 'might', 'variants', 'keywords']


@pytest.fixture
def api(app, authenticated_client):
    seed_catalog()
    guard = db.session.get(RbCard, ('OGN', 'U1'))
    guard.rbcar_energy, guard.rbcar_power, guard.rbcar_might = 2, 1, 3
    guard.rbcar_ability = ('[Tank] [Accelerate] (You may pay :rb_energy_1: to have me enter '
                           'ready with [Tank].) [tank] I have +1 :rb_might: here.')
    # A third printing of the name in a third set, written in another case.
    db.session.add(RbSet(rbset_id='UNL', rbset_name='Unleashed'))
    db.session.add(RbCard(rbcar_rbset_id='UNL', rbcar_id='U7', rbcar_name='SHURIMA  guard',
                          rbcar_type='Unit', rbcar_domain='Calm', rbcar_rarity='Showcase'))
    db.session.commit()
    return authenticated_client


@pytest.fixture
def anon(app):
    return app.test_client()


def _fields(card):
    return {key: card[key] for key in ['rarity'] + NEW_KEYS}


GUARD = {'rarity': 'Common', 'energy': 2, 'power': 1, 'might': 3, 'variants': 3,
         'keywords': ['Tank', 'Accelerate']}
SCOUT = {'rarity': 'Common', 'energy': None, 'power': None, 'might': None, 'variants': 1,
         'keywords': []}


class TestDeckCardFields:
    def test_detail_cards_carry_the_new_fields_after_the_old_ones(self, api):
        deck = data(api.get(f'{BASE}/{make_deck("Azir", AZIR)}'))
        cards = deck['cards']
        assert list(cards['OGN-U1'])[-len(NEW_KEYS):] == NEW_KEYS
        assert _fields(cards['OGN-U1']) == GUARD
        assert _fields(cards['SFD-U1']) == {**SCOUT, 'variants': 3}
        assert _fields(cards['OGN-U2']) == SCOUT
        assert cards['OGN-S1']['rarity'] == 'Uncommon'

    def test_list_legend_and_champion_carry_them(self, api):
        make_deck('Azir', AZIR)
        item = data(api.get(BASE))['items'][0]
        assert _fields(item['legend']) == {**SCOUT, 'rarity': 'Rare'}

    def test_created_and_previewed_decks_carry_them(self, api):
        deck = data(api.post(BASE, json={'name': 'New', 'mode': '1v1'}), 201)
        assert deck['cards'] == {}
        body = data(api.post(f'{BASE}/import/preview',
                             json={'text': 'MainDeck:\n3 Shurima Guard\n'}))
        cards = body['deck_preview']['cards']
        assert _fields(cards['OGN-U1']) == GUARD

    def test_the_public_deck_carries_them_and_nothing_else_new(self, api, anon):
        deck_id = make_deck('Azir', AZIR)
        slug = data(api.post(f'{BASE}/{deck_id}/share'))['slug']
        mine = data(api.get(f'{BASE}/{deck_id}'))['cards']
        cards = data(anon.get(f'{PUBLIC}/{slug}'))['cards']
        assert _fields(cards['OGN-U1']) == GUARD
        for key, card in cards.items():
            assert card == {**mine[key], 'owned_total': None}

    def test_sql_statements_stay_the_same(self, app, api, anon):
        deck_id = make_deck('Azir', AZIR)
        _, listed = count_statements(app, lambda: api.get(BASE))
        slug = data(api.post(f'{BASE}/{deck_id}/share'))['slug']
        _, public = count_statements(app, lambda: anon.get(f'{PUBLIC}/{slug}'))
        assert (listed, public) == (9, 7)
