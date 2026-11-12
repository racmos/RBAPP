"""POST /decks/<id>/duplicate (U): a new private deck of the caller holding the current
content of one of their decks, with its own version 1 and a free `(copy)` name."""
from datetime import datetime

import pytest

from app import db
from app.models import RbDeckHead, RbDeckVersion
from tests.deck_api_helpers import (AZIR, BASE, NOT_FOUND, content, data, error, head_row,
                                    line, make_deck, ref, seed_catalog, user_id, versions)
from tests.product_helpers import count_statements

DETAIL_KEYS = ['id', 'name', 'mode', 'visibility', 'created_at', 'updated_at', 'share',
               'current_seq', 'content', 'cards', 'unknown_cards', 'domains', 'counts', 'value',
               'value_unpriced', 'legality']
OLD = datetime(2026, 9, 1, 8, 0)


@pytest.fixture
def api(app, authenticated_client, make_user):
    make_user('otheruser')
    seed_catalog()
    return authenticated_client


def _dup(api, deck_id, body=None, status=201):
    url = f'{BASE}/{deck_id}/duplicate'
    resp = api.post(url) if body is None else api.post(url, json=body)
    return data(resp, status)


class TestDuplicate:
    def test_copies_the_current_content_and_mode_into_a_new_private_deck(self, api,
                                                                         frozen_clock):
        source = make_deck('Azir', AZIR, mode='2v2', seqs=(1, 2, 3))
        deck = _dup(api, source)
        assert list(deck) == DETAIL_KEYS
        assert deck['id'] != source
        assert (deck['name'], deck['mode'], deck['visibility']) == ('Azir (copy)', '2v2',
                                                                    'private')
        assert deck['share'] is None and deck['current_seq'] == 1
        assert deck['content'] == AZIR
        assert deck['created_at'] == deck['updated_at'] == '2030-01-01T12:00:00Z'
        assert deck == data(api.get(f"{BASE}/{deck['id']}"))
        head = head_row(deck['id'])
        assert head.rbdkh_user_id == user_id() and head.rbdkh_share_slug is None
        assert versions(deck['id']) == [(1, AZIR, None)]

    def test_copies_the_current_version_not_the_newest_and_no_version_note(self, api):
        source = make_deck('Azir', AZIR, seqs=(1, 2))
        head = head_row(source)
        current = RbDeckVersion.query.filter_by(rbdkv_deck_id=source, rbdkv_seq=1).one()
        current.rbdkv_content = content(main=[line('OGN', 'U1', 2)])
        current.rbdkv_note = 'A note of the source'
        head.rbdkh_current_version_id = current.rbdkv_id
        db.session.commit()
        deck = _dup(api, source)
        assert versions(deck['id']) == [(1, content(main=[line('OGN', 'U1', 2)]), None)]

    def test_a_shared_public_source_gives_a_private_unshared_copy(self, api):
        source = make_deck('Azir', AZIR)
        data(api.post(f'{BASE}/{source}/share'))
        data(api.patch(f'{BASE}/{source}', json={'visibility': 'public'}))
        deck = _dup(api, source)
        assert deck['visibility'] == 'private' and deck['share'] is None
        head = head_row(deck['id'])
        assert (head.rbdkh_visibility, head.rbdkh_share_slug) == ('private', None)

    def test_the_source_is_untouched(self, api, frozen_clock):
        source = make_deck('Azir', AZIR, at=OLD, seqs=(1, 2))
        before = head_row(source)
        snapshot = (before.rbdkh_name, before.rbdkh_mode, before.rbdkh_visibility,
                    before.rbdkh_share_slug, before.rbdkh_current_version_id,
                    before.rbdkh_updated_at, before.rbdkh_created_at)
        _dup(api, source)
        after = head_row(source)
        assert (after.rbdkh_name, after.rbdkh_mode, after.rbdkh_visibility,
                after.rbdkh_share_slug, after.rbdkh_current_version_id,
                after.rbdkh_updated_at, after.rbdkh_created_at) == snapshot
        assert versions(source) == [(1, AZIR, None), (2, AZIR, None)]

    def test_cards_missing_from_the_catalog_are_kept_as_stored(self, api):
        ghost = content(legend=ref('XXX', 'L'), main=[line('OGN', 'U1', 1), line('XXX', '9', 2)])
        source = make_deck('Ghost', ghost)
        deck = _dup(api, source)
        assert deck['content'] == ghost
        assert deck['unknown_cards'] == [{'zone': 'legend', 'set': 'XXX', 'id': 'L'},
                                         {'zone': 'main', 'set': 'XXX', 'id': '9'}]
        assert versions(deck['id']) == [(1, ghost, None)]

    def test_hard_limits_of_the_source_are_copied_as_stored(self, api):
        over = content(main=[line('OGN', 'U2', 4)], runes=[line('OGN', 'R1', 13)])
        source = make_deck('Over', over)
        deck = _dup(api, source)
        assert deck['content'] == over

    def test_the_copy_appears_in_the_list(self, api):
        source = make_deck('Azir', AZIR, at=OLD)
        deck = _dup(api, source)
        items = data(api.get(BASE))['items']
        assert [(i['id'], i['name']) for i in items] == [(deck['id'], 'Azir (copy)'),
                                                        (source, 'Azir')]
        assert items[0]['counts'] == items[1]['counts']
        assert items[0]['legend']['key'] == 'OGN-L1'

    def test_an_empty_json_body_is_the_default_name(self, api):
        source = make_deck('Azir')
        assert _dup(api, source, {})['name'] == 'Azir (copy)'

    @pytest.mark.parametrize('name', [None, '', '   '])
    def test_a_blank_or_null_name_is_the_default_name(self, api, name):
        source = make_deck('Azir')
        assert _dup(api, source, {'name': name})['name'] == 'Azir (copy)'


class TestNames:
    def test_taken_copy_names_get_the_first_free_number(self, api):
        source = make_deck('Azir')
        assert _dup(api, source)['name'] == 'Azir (copy)'
        assert _dup(api, source)['name'] == 'Azir (copy 2)'
        make_deck('Azir (copy 4)')
        assert _dup(api, source)['name'] == 'Azir (copy 3)'
        assert _dup(api, source)['name'] == 'Azir (copy 5)'

    def test_another_users_copy_name_is_free(self, api):
        make_deck('Azir (copy)', user='otheruser')
        assert _dup(api, make_deck('Azir'))['name'] == 'Azir (copy)'

    def test_duplicating_a_copy_appends_a_new_suffix(self, api):
        copy = _dup(api, make_deck('Azir'))
        assert _dup(api, copy['id'])['name'] == 'Azir (copy) (copy)'

    def test_long_names_are_cut_so_the_suffix_fits_80(self, api):
        name = 'x' * 79 + 'y'
        source = make_deck(name)
        first = _dup(api, source)['name']
        assert first == 'x' * 73 + ' (copy)' and len(first) == 80
        second = _dup(api, source)['name']
        assert second == 'x' * 71 + ' (copy 2)' and len(second) == 80

    def test_the_cut_drops_trailing_spaces(self, api):
        name = 'x' * 72 + ' ' + 'y' * 7
        source = make_deck(name)
        assert _dup(api, source)['name'] == 'x' * 72 + ' (copy)'

    def test_an_explicit_name_is_trimmed_and_used(self, api):
        source = make_deck('Azir', AZIR)
        deck = _dup(api, source, {'name': '  Azir tournament  '})
        assert deck['name'] == 'Azir tournament' and deck['content'] == AZIR

    def test_an_explicit_taken_name_is_409_like_create(self, api):
        source = make_deck('Azir')
        make_deck('Jinx')
        body = error(api.post(f'{BASE}/{source}/duplicate', json={'name': 'Jinx'}), 409,
                     'already_exists')
        assert body['message'] == 'You already have a deck with that name.'
        assert RbDeckHead.query.count() == 2 and RbDeckVersion.query.count() == 2

    def test_an_explicit_name_equal_to_the_source_is_409(self, api):
        source = make_deck('Azir')
        error(api.post(f'{BASE}/{source}/duplicate', json={'name': 'Azir'}), 409,
              'already_exists')
        assert RbDeckHead.query.count() == 1

    @pytest.mark.parametrize('body, code', [
        ({'name': 'x' * 81}, 'too_long'),
        ({'name': 5}, 'invalid_value'),
    ])
    def test_an_invalid_name_is_400_and_stores_nothing(self, api, body, code):
        source = make_deck('Azir')
        resp = error(api.post(f'{BASE}/{source}/duplicate', json=body), 400,
                     'validation_error')
        assert [(d['field'], d['code']) for d in resp['details']] == [('name', code)]
        assert RbDeckHead.query.count() == 1 and RbDeckVersion.query.count() == 1

    def test_a_non_json_body_is_400(self, api):
        source = make_deck('Azir')
        resp = api.post(f'{BASE}/{source}/duplicate', data='name=x',
                        content_type='application/x-www-form-urlencoded')
        assert resp.status_code == 400
        assert RbDeckHead.query.count() == 1


class TestAccess:
    def test_another_users_deck_and_unknown_ids_are_404(self, api):
        theirs = make_deck('Azir', user='otheruser')
        for deck_id in (theirs, theirs + 100):
            resp = api.post(f'{BASE}/{deck_id}/duplicate')
            assert resp.status_code == 404 and resp.get_json() == NOT_FOUND
        assert RbDeckHead.query.count() == 1 and RbDeckVersion.query.count() == 1

    def test_anonymous_is_401(self, app, api):
        source = make_deck('Azir')
        resp = app.test_client().post(f'{BASE}/{source}/duplicate')
        assert resp.status_code == 401
        assert resp.get_json()['code'] == 'unauthenticated'
        assert RbDeckHead.query.count() == 1

    def test_csrf_is_required(self, api, csrf_app):
        source = make_deck('Azir')
        error(api.post(f'{BASE}/{source}/duplicate'), 400, 'csrf_invalid')
        assert RbDeckHead.query.count() == 1
        token = data(api.get('/riftbound/api/v1/auth/session'))['csrf_token']
        deck = data(api.post(f'{BASE}/{source}/duplicate', headers={'X-CSRFToken': token}),
                    201)
        assert deck['name'] == 'Azir (copy)'

    def test_sql_statements(self, app, api):
        source = make_deck('Azir', AZIR)
        make_deck('Azir (copy)')
        resp, count = count_statements(app, lambda: api.post(f'{BASE}/{source}/duplicate'))
        assert resp.status_code == 201 and resp.get_json()['data']['name'] == 'Azir (copy 2)'
        # user, source head, current version, names, insert head, insert version, update head,
        # cards, sets, bans, then the rows the commit expired (user, version, head), prices (2)
        # and owned copies; never one per card (the catalog is read after the commit)
        assert count == 16
