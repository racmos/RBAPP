"""F5-d S1-S6: GET/POST /decks, GET/PATCH/DELETE /decks/<id> (owner only, legality on read)."""
import pytest

from app import db
from app.models import RbCardBan, RbCollection, RbDeckHead, RbDeckVersion
from app.schemas.deck_content import empty_content
from tests.deck_api_helpers import (AZIR, BASE, NOT_FOUND, content, data, error, head_row,
                                    line, make_deck, ref, seed_catalog, user_id, versions)
from tests.product_helpers import count_statements

HEAD_KEYS = ['id', 'name', 'mode', 'visibility', 'created_at', 'updated_at']
LIST_KEYS = HEAD_KEYS + ['legend', 'champion', 'domains', 'counts', 'value', 'value_unpriced',
                         'legal', 'issues']
DETAIL_KEYS = HEAD_KEYS + ['current_seq', 'content', 'cards', 'unknown_cards', 'domains',
                           'counts', 'value', 'value_unpriced', 'legality']
CARD_KEYS = ['set_id', 'card_id', 'key', 'name', 'domains', 'type', 'supertype', 'rarity',
             'image_src', 'image_thumb_src', 'is_base', 'market', 'owned_total', 'tags']
EMPTY_COUNTS = {'main': 0, 'runes': 0, 'battlefields': 0, 'sideboard': 0, 'workbench': 0}
AZIR_COUNTS = {'main': 6, 'runes': 12, 'battlefields': 2, 'sideboard': 2, 'workbench': 4}


@pytest.fixture
def api(app, authenticated_client, make_user):
    make_user('otheruser')
    seed_catalog()
    return authenticated_client


def _ban(name, mode):
    from datetime import date
    from app.services.bans import name_key
    db.session.add(RbCardBan(rbban_name_key=name_key(name), rbban_name=name, rbban_mode=mode,
                             rbban_since=date(2026, 1, 1)))
    db.session.commit()


class TestCreate:
    def test_creates_an_empty_deck_with_version_1(self, api, frozen_clock):
        deck = data(api.post(BASE, json={'name': '  Azir ', 'mode': '2v2'}), 201)
        assert list(deck) == DETAIL_KEYS
        assert deck['name'] == 'Azir' and deck['mode'] == '2v2'
        assert deck['visibility'] == 'private' and deck['current_seq'] == 1
        assert deck['created_at'] == deck['updated_at'] == '2030-01-01T12:00:00Z'
        assert deck['content'] == empty_content() and deck['cards'] == {}
        assert deck['counts'] == EMPTY_COUNTS and deck['domains'] == []
        assert deck['value'] == 0 and deck['value_unpriced'] == 0
        assert list(deck['legality']) == ['1v1', '2v2']
        assert [i['code'] for i in deck['legality']['1v1']['issues']] == [
            'legend_missing', 'champion_missing', 'main_size', 'runes_count',
            'battlefields_count', 'sideboard_size']
        head = head_row(deck['id'])
        assert head.rbdkh_user_id == user_id() and head.rbdkh_legacy_name is None
        assert versions(deck['id']) == [(1, empty_content(), None)]
        assert db.session.get(RbDeckVersion, head.rbdkh_current_version_id).rbdkv_seq == 1

    def test_a_duplicate_name_of_the_same_user_is_409(self, api):
        make_deck('Azir')
        body = error(api.post(BASE, json={'name': 'Azir', 'mode': '1v1'}), 409,
                     'already_exists')
        assert body['message'] == 'You already have a deck with that name.'
        assert RbDeckHead.query.count() == 1

    def test_another_users_name_is_free(self, api):
        make_deck('Azir', user='otheruser')
        data(api.post(BASE, json={'name': 'Azir', 'mode': '1v1'}), 201)
        assert RbDeckHead.query.count() == 2

    @pytest.mark.parametrize('body, field, code', [
        ({'name': '', 'mode': '1v1'}, 'name', 'too_short'),
        ({'name': '   ', 'mode': '1v1'}, 'name', 'too_short'),
        ({'name': 'x' * 81, 'mode': '1v1'}, 'name', 'too_long'),
        ({'name': 'Azir', 'mode': '3v3'}, 'mode', 'invalid_value'),
        ({'mode': '1v1'}, 'name', 'required'),
        ({'name': 'Azir'}, 'mode', 'required'),
    ])
    def test_invalid_bodies_are_400_and_store_nothing(self, api, body, field, code):
        resp = error(api.post(BASE, json=body), 400, 'validation_error')
        assert [(d['field'], d['code']) for d in resp['details']] == [(field, code)]
        assert RbDeckHead.query.count() == 0 and RbDeckVersion.query.count() == 0


class TestDetail:
    def test_the_current_content_comes_with_its_cards_and_both_legalities(self, api):
        _ban('Sandstorm', '2v2')
        db.session.add(RbCollection(rbcol_rbset_id='OGN', rbcol_rbcar_id='L1', rbcol_foil='N',
                                    rbcol_user='testuser', rbcol_quantity=2))
        db.session.commit()
        deck_id = make_deck('Azir', AZIR, seqs=(1, 2))
        deck = data(api.get(f'{BASE}/{deck_id}'))
        assert list(deck) == DETAIL_KEYS
        assert deck['current_seq'] == 2 and deck['content'] == AZIR
        assert deck['created_at'] == '2026-10-01T09:00:00Z'
        assert sorted(deck['cards']) == sorted({
            'OGN-L1', 'OGN-C1', 'OGN-U1', 'SFD-U1', 'OGN-S1', 'OGN-R1', 'OGN-R2', 'OGN-B1',
            'OGN-B2', 'OGN-U2', 'OGN-F1', 'OGN-T1'})
        legend = deck['cards']['OGN-L1']
        assert list(legend) == CARD_KEYS
        assert (legend['name'], legend['type'], legend['supertype'], legend['domains'],
                legend['tags'], legend['market'], legend['owned_total']) == (
            'Azir, Emperor', 'Legend', 'Champion', ['Calm', 'Order'], ['Azir'], 5, 2)
        assert deck['cards']['OGN-S1']['market'] is None
        assert deck['unknown_cards'] == []
        assert deck['domains'] == ['Calm', 'Order']
        assert deck['counts'] == AZIR_COUNTS
        assert deck['value'] == 21.8 and deck['value_unpriced'] == 10
        one, two = deck['legality']['1v1'], deck['legality']['2v2']
        assert list(one) == ['legal', 'issues', 'completeness']
        assert one['legal'] is False
        assert one['issues'] == [
            {'code': 'main_size', 'params': {'have': 6, 'need': 39, 'missing': 33, 'over': 0}},
            {'code': 'battlefields_count',
             'params': {'have': 2, 'need': 3, 'missing': 1, 'over': 0}},
            {'code': 'sideboard_size',
             'params': {'have': 2, 'need': 10, 'missing': 8, 'over': 0}}]
        assert two['issues'][-1] == {'code': 'banned',
                                     'params': {'name': 'Sandstorm', 'mode': '2v2'}}
        assert one['completeness']['main'] == {'have': 6, 'need': 39, 'missing': 33}

    def test_cards_missing_from_the_catalog_are_listed_apart(self, api):
        deck_id = make_deck('Ghost', content(main=[line('OGN', 'U1', 1), line('XXX', '9', 2)],
                                             legend=ref('XXX', 'L')))
        deck = data(api.get(f'{BASE}/{deck_id}'))
        assert deck['unknown_cards'] == [{'zone': 'legend', 'set': 'XXX', 'id': 'L'},
                                         {'zone': 'main', 'set': 'XXX', 'id': '9'}]
        assert sorted(deck['cards']) == ['OGN-U1']
        assert deck['counts']['main'] == 3
        assert deck['legality']['1v1']['issues'][0]['code'] == 'legend_missing'

    def test_another_users_deck_and_unknown_ids_are_404(self, api):
        theirs = make_deck('Azir', user='otheruser')
        for deck_id in (theirs, theirs + 100):
            resp = api.get(f'{BASE}/{deck_id}')
            assert resp.status_code == 404 and resp.get_json() == NOT_FOUND


class TestPatch:
    def test_changes_only_the_sent_fields(self, api, frozen_clock):
        deck_id = make_deck('Azir', AZIR)
        deck = data(api.patch(f'{BASE}/{deck_id}', json={'visibility': 'public'}))
        assert (deck['name'], deck['mode'], deck['visibility']) == ('Azir', '1v1', 'public')
        assert deck['updated_at'] == '2030-01-01T12:00:00Z'
        deck = data(api.patch(f'{BASE}/{deck_id}', json={'name': 'Azir 2', 'mode': '2v2'}))
        assert (deck['name'], deck['mode'], deck['visibility']) == ('Azir 2', '2v2', 'public')
        assert deck['content'] == AZIR
        head = head_row(deck_id)
        assert (head.rbdkh_name, head.rbdkh_mode, head.rbdkh_visibility,
                head.rbdkh_share_slug) == ('Azir 2', '2v2', 'public', None)
        assert versions(deck_id) == [(1, AZIR, None)]

    def test_renaming_to_a_taken_name_is_409(self, api):
        make_deck('Azir')
        deck_id = make_deck('Jinx')
        error(api.patch(f'{BASE}/{deck_id}', json={'name': 'Azir'}), 409, 'already_exists')
        assert head_row(deck_id).rbdkh_name == 'Jinx'
        data(api.patch(f'{BASE}/{deck_id}', json={'name': 'Jinx'}))     # its own name

    @pytest.mark.parametrize('body, field', [
        ({'name': None}, 'name'), ({'mode': None}, 'mode'), ({'visibility': None}, 'visibility'),
        ({'visibility': 'shared'}, 'visibility'), ({'mode': '3v3'}, 'mode'),
        ({'name': ''}, 'name'),
    ])
    def test_invalid_values_are_400_and_change_nothing(self, api, body, field):
        deck_id = make_deck('Azir')
        resp = error(api.patch(f'{BASE}/{deck_id}', json=body), 400, 'validation_error')
        assert resp['details'][0]['field'] == field
        head = head_row(deck_id)
        assert (head.rbdkh_name, head.rbdkh_mode, head.rbdkh_visibility) == (
            'Azir', '1v1', 'private')

    def test_another_users_deck_is_404(self, api):
        theirs = make_deck('Azir', user='otheruser')
        resp = api.patch(f'{BASE}/{theirs}', json={'name': 'Mine'})
        assert resp.status_code == 404 and resp.get_json() == NOT_FOUND
        assert head_row(theirs).rbdkh_name == 'Azir'


class TestDelete:
    def test_deletes_the_deck_and_its_versions(self, api):
        deck_id = make_deck('Azir', AZIR, seqs=(1, 2, 3))
        keep = make_deck('Jinx')
        deck = data(api.delete(f'{BASE}/{deck_id}'))['deleted']
        assert list(deck) == HEAD_KEYS
        assert (deck['id'], deck['name']) == (deck_id, 'Azir')
        assert head_row(deck_id) is None and versions(deck_id) == []
        assert versions(keep) == [(1, empty_content(), None)]

    def test_another_users_deck_is_404_and_stays(self, api):
        theirs = make_deck('Azir', user='otheruser')
        resp = api.delete(f'{BASE}/{theirs}')
        assert resp.status_code == 404 and resp.get_json() == NOT_FOUND
        assert head_row(theirs) is not None and len(versions(theirs)) == 1


class TestList:
    def test_empty(self, api):
        assert api.get(BASE).get_json() == {'success': True, 'data': {'items': []}}

    def test_my_decks_newest_change_first_with_their_summary(self, api):
        from datetime import datetime
        _ban('Sandstorm', '2v2')
        old = make_deck('Old', at=datetime(2026, 9, 1))
        azir = make_deck('Azir', AZIR, at=datetime(2026, 10, 2))
        make_deck('Theirs', AZIR, user='otheruser', at=datetime(2026, 11, 1))
        items = data(api.get(BASE))['items']
        assert [item['id'] for item in items] == [azir, old]
        item = items[0]
        assert list(item) == LIST_KEYS
        assert (item['name'], item['mode'], item['visibility']) == ('Azir', '1v1', 'private')
        assert list(item['legend']) == CARD_KEYS
        assert item['legend']['key'] == 'OGN-L1' and item['champion']['key'] == 'OGN-C1'
        assert item['domains'] == ['Calm', 'Order'] and item['counts'] == AZIR_COUNTS
        assert item['value'] == 21.8 and item['value_unpriced'] == 10
        assert item['legal'] == {'1v1': False, '2v2': False}
        assert item['issues'] == {'1v1': ['main_size', 'battlefields_count', 'sideboard_size'],
                                  '2v2': ['main_size', 'battlefields_count', 'sideboard_size',
                                          'banned']}
        assert item['updated_at'] == '2026-10-02T00:00:00Z'
        assert items[1]['legend'] is None and items[1]['champion'] is None
        assert items[1]['counts'] == EMPTY_COUNTS

    def test_sql_statements_do_not_grow_with_the_decks(self, app, api):
        make_deck('One', AZIR)
        _, one = count_statements(app, lambda: api.get(BASE))
        for n in range(2, 6):
            make_deck(f'Deck {n}', AZIR)
        resp, many = count_statements(app, lambda: api.get(BASE))
        assert len(resp.get_json()['data']['items']) == 5
        assert many == one
        assert many <= 10
