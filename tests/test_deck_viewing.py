"""
Deck viewing (DECK-1..DECK-4, D19).

All decks stay listed for every logged-in user; what changes is what is
computed from the VIEWER (have / missing), how names are resolved (the
viewer's own decks only), the versions endpoint, and the removal of two routes
that never worked.
"""
from contextlib import contextmanager

import pytest
from flask import template_rendered

from app import db
from app.models import RbCard, RbCollection, RbDeck, RbSet
from tests.conftest import login_as

VERSION_KEYS = {'id', 'name', 'seq', 'snapshot', 'mode', 'format', 'ncards'}


@contextmanager
def captured_templates(app):
    recorded = []

    def record(sender, template, context, **extra):
        recorded.append((template, context))

    template_rendered.connect(record, app)
    try:
        yield recorded
    finally:
        template_rendered.disconnect(record, app)


def add_deck(user, name, seq=1, cards=None):
    cards = cards if cards is not None else [{'set': 'OGN', 'id': '1', 'qty': 3}]
    deck = RbDeck(rbdck_user=user, rbdck_name=name, rbdck_seq=seq,
                  rbdck_cards={'main': cards, 'sideboard': []},
                  rbdck_ncards=sum(c['qty'] for c in cards))
    db.session.add(deck)
    db.session.commit()
    return deck


def own(user, quantity, set_id='OGN', card_id='1', foil='N'):
    db.session.add(RbCollection(rbcol_user=user, rbcol_rbset_id=set_id, rbcol_rbcar_id=card_id,
                                rbcol_foil=foil, rbcol_quantity=quantity, rbcol_selling='N'))
    db.session.commit()


def view(app, client, path):
    """GET `path`; returns (response, deck namespace or None)."""
    with captured_templates(app) as rendered:
        resp = client.get(path)
    decks = [ctx['deck'] for tpl, ctx in rendered if tpl.name == 'deck_view.html']
    return resp, (decks[0] if decks else None)


def have_missing(deck):
    [card] = deck.cards
    return card['have'], card['missing']


@pytest.fixture
def world(app, make_user):
    """Catalog OGN/1 plus users alice (owner, 4 copies), bob (1 copy), carol (none)."""
    db.session.add(RbSet(rbset_id='OGN', rbset_name='Origins'))
    db.session.add(RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='Ahri'))
    db.session.commit()
    for name in ('alice', 'bob', 'carol'):
        make_user(name)
    own('alice', 4)
    own('bob', 1)
    return {name: login_as(app.test_client(), name) for name in ('alice', 'bob', 'carol')}


# ---------------------------------------------------------------------------
# DECK-1 have / missing come from the viewer
# ---------------------------------------------------------------------------

class TestHaveMissingUseTheViewer:
    def test_another_user_sees_their_own_copies_not_the_owners(self, app, world):
        deck = add_deck('alice', 'Foo')
        resp, shown = view(app, world['bob'], f'/riftbound/deck/view/{deck.id}')
        assert resp.status_code == 200
        assert have_missing(shown) == (1, 2)

    def test_a_viewer_with_no_copies_has_nothing(self, app, world):
        deck = add_deck('alice', 'Foo')
        resp, shown = view(app, world['carol'], f'/riftbound/deck/view/{deck.id}')
        assert resp.status_code == 200
        assert have_missing(shown) == (0, 3)

    def test_the_owner_has_it_capped_at_the_needed_quantity(self, app, world):
        deck = add_deck('alice', 'Foo')
        resp, shown = view(app, world['alice'], f'/riftbound/deck/view/{deck.id}')
        assert have_missing(shown) == (3, 0)             # owns 4, needs 3

    def test_copies_of_every_foil_variant_are_added_up(self, app, world):
        own('carol', 1, foil='N')
        own('carol', 1, foil='S')
        deck = add_deck('alice', 'Foo')
        _, shown = view(app, world['carol'], f'/riftbound/deck/view/{deck.id}')
        assert have_missing(shown) == (2, 1)

    def test_several_collection_lines_of_the_same_card_are_added_up(self, app, world):
        own('carol', 1)
        own('carol', 1)
        deck = add_deck('alice', 'Foo')
        _, shown = view(app, world['carol'], f'/riftbound/deck/view/{deck.id}')
        assert have_missing(shown) == (2, 1)

    def test_other_cards_and_other_users_do_not_count(self, app, world):
        own('carol', 9, card_id='2')
        own('bob', 5)
        deck = add_deck('alice', 'Foo')
        _, shown = view(app, world['carol'], f'/riftbound/deck/view/{deck.id}')
        assert have_missing(shown) == (0, 3)

    @pytest.mark.parametrize('path', ['/riftbound/deck/view/Foo', '/riftbound/deck/view/Foo/1'])
    def test_the_name_routes_also_use_the_viewers_collection(self, app, world, path):
        add_deck('alice', 'Foo')
        add_deck('bob', 'Foo')                            # bob's own copy of the deck
        resp, shown = view(app, world['bob'], path)
        assert resp.status_code == 200
        assert shown.user == 'bob'
        assert have_missing(shown) == (1, 2)             # bob owns 1, not alice's 4

    def test_sideboard_cards_are_counted_the_same_way(self, app, world):
        deck = add_deck('alice', 'Foo')
        deck.rbdck_cards = {'main': [], 'sideboard': [{'set': 'OGN', 'id': '1', 'qty': 2}]}
        db.session.commit()
        _, shown = view(app, world['bob'], f'/riftbound/deck/view/{deck.id}')
        [card] = shown.cards
        assert (card['sideboard'], card['have'], card['missing']) == ('S', 1, 1)


# ---------------------------------------------------------------------------
# DECK-2 name lookups are scoped to the viewer
# ---------------------------------------------------------------------------

class TestNameLookupsAreScopedToTheViewer:
    def test_name_route_shows_the_viewers_highest_seq(self, app, world):
        add_deck('alice', 'Foo', seq=1)
        a2 = add_deck('alice', 'Foo', seq=2)
        b1 = add_deck('bob', 'Foo', seq=1)
        b2 = add_deck('bob', 'Foo', seq=2)
        b3 = add_deck('bob', 'Foo', seq=3)
        resp, shown = view(app, world['bob'], '/riftbound/deck/view/Foo')
        assert resp.status_code == 200
        assert (shown.id, shown.user, shown.seq) == (b3.id, 'bob', 3)
        _, shown = view(app, world['alice'], '/riftbound/deck/view/Foo')
        assert (shown.id, shown.user, shown.seq) == (a2.id, 'alice', 2)
        assert {b1.id, b2.id}.isdisjoint({shown.id})

    def test_name_and_seq_route_shows_the_exact_seq(self, app, world):
        add_deck('alice', 'Foo', seq=1)
        add_deck('alice', 'Foo', seq=2)
        b1 = add_deck('bob', 'Foo', seq=1)
        b2 = add_deck('bob', 'Foo', seq=2)
        _, shown = view(app, world['bob'], '/riftbound/deck/view/Foo/1')
        assert (shown.id, shown.user) == (b1.id, 'bob')
        _, shown = view(app, world['bob'], '/riftbound/deck/view/Foo/2')
        assert (shown.id, shown.user) == (b2.id, 'bob')

    @pytest.mark.parametrize('path', ['/riftbound/deck/view/Foo', '/riftbound/deck/view/Foo/1'])
    def test_someone_elses_deck_name_is_a_404_even_though_it_exists(self, app, world, path):
        add_deck('alice', 'Foo')
        resp, shown = view(app, world['carol'], path)
        assert resp.status_code == 404
        assert shown is None

    def test_a_seq_the_viewer_does_not_have_is_a_404(self, app, world):
        add_deck('alice', 'Foo', seq=1)
        add_deck('alice', 'Foo', seq=2)
        add_deck('bob', 'Foo', seq=1)
        assert world['bob'].get('/riftbound/deck/view/Foo/2').status_code == 404

    @pytest.mark.parametrize('path', ['/riftbound/deck/view/Nope', '/riftbound/deck/view/Nope/1'])
    def test_an_unknown_name_is_a_404(self, app, world, path):
        assert world['alice'].get(path).status_code == 404

    def test_other_users_decks_stay_reachable_by_id(self, app, world):
        deck = add_deck('alice', 'Foo')
        resp, shown = view(app, world['carol'], f'/riftbound/deck/view/{deck.id}')
        assert resp.status_code == 200 and shown.user == 'alice'

    def test_an_unknown_id_is_a_404(self, app, world):
        assert world['alice'].get('/riftbound/deck/view/9999').status_code == 404


# ---------------------------------------------------------------------------
# DECK-3 versions
# ---------------------------------------------------------------------------

class TestVersionsEndpoint:
    def test_lists_the_current_users_versions_newest_first(self, app, world):
        v1 = add_deck('alice', 'Foo', seq=1)
        v2 = add_deck('alice', 'Foo', seq=2, cards=[{'set': 'OGN', 'id': '1', 'qty': 5}])
        resp = world['alice'].get('/riftbound/deck/versions/Foo')
        assert resp.status_code == 200
        assert resp.json['success'] is True
        versions = resp.json['versions']
        assert [v['seq'] for v in versions] == [2, 1]
        assert [v['id'] for v in versions] == [v2.id, v1.id]
        for version in versions:
            assert set(version) == VERSION_KEYS
            assert version['name'] == 'Foo'
        assert versions[0]['ncards'] == 5 and versions[1]['ncards'] == 3

    def test_snapshot_is_iso_8601_and_mode_format_come_through(self, app, world):
        from datetime import datetime
        deck = add_deck('alice', 'Foo')
        deck.rbdck_mode, deck.rbdck_format = '2v2', 'Limited'
        db.session.commit()
        [version] = world['alice'].get('/riftbound/deck/versions/Foo').json['versions']
        assert datetime.fromisoformat(version['snapshot']) == deck.rbdck_snapshot
        assert (version['mode'], version['format']) == ('2v2', 'Limited')

    def test_another_users_deck_is_hidden(self, app, world):
        add_deck('bob', 'Foo')
        resp = world['alice'].get('/riftbound/deck/versions/Foo')
        assert resp.status_code == 200
        assert resp.json == {'success': True, 'versions': []}

    def test_only_the_viewers_own_versions_are_listed_when_both_have_the_name(self, app, world):
        add_deck('alice', 'Foo', seq=1)
        add_deck('bob', 'Foo', seq=1)
        add_deck('bob', 'Foo', seq=2)
        versions = world['alice'].get('/riftbound/deck/versions/Foo').json['versions']
        assert [v['seq'] for v in versions] == [1]

    def test_decks_with_missing_optional_fields_never_cause_a_500(self, app, world):
        deck = add_deck('alice', 'Foo')
        deck.rbdck_mode = deck.rbdck_format = None
        deck.rbdck_ncards = None
        deck.rbdck_seq = None
        db.session.commit()
        resp = world['alice'].get('/riftbound/deck/versions/Foo')
        assert resp.status_code == 200
        [version] = resp.json['versions']
        assert version['seq'] == 1                      # NULL seq reads as the first version
        assert version['mode'] is None and version['ncards'] is None

    def test_anonymous_callers_are_sent_to_login(self, app, world, client):
        assert client.get('/riftbound/deck/versions/Foo').status_code == 302


# ---------------------------------------------------------------------------
# DECK-4 dead routes removed, save still works
# ---------------------------------------------------------------------------

class TestDeadRoutesAreGone:
    def test_update_and_delete_return_404(self, app, world):
        deck = add_deck('alice', 'Foo')
        assert world['alice'].post('/riftbound/deck/update/OGN/1', json={'rbdck_name': 'X'}
                                   ).status_code == 404
        assert world['alice'].delete('/riftbound/deck/delete/OGN/1').status_code == 404
        assert RbDeck.query.get(deck.id) is not None        # nothing was deleted

    def test_they_are_not_in_the_url_map(self, app):
        rules = {(r.rule, m) for r in app.url_map.iter_rules() for m in r.methods}
        assert not [r for r, _m in rules if r.startswith('/riftbound/deck/update/')]
        assert not [r for r, _m in rules if r.startswith('/riftbound/deck/delete/')]
        endpoints = {r.endpoint for r in app.url_map.iter_rules()}
        assert {'deck.update_deck_legacy', 'deck.delete_deck_legacy'}.isdisjoint(endpoints)

    def test_save_still_creates_the_next_seq(self, app, world):
        body = {'rbdck_name': 'Fresh', 'rbdck_cards': {
            'main': [{'set': 'OGN', 'id': '1', 'qty': 2}], 'sideboard': []}}
        first = world['alice'].post('/riftbound/deck/save', json=body)
        second = world['alice'].post('/riftbound/deck/save', json=body)
        assert (first.status_code, second.status_code) == (200, 200)
        assert (first.json['seq'], second.json['seq']) == (1, 2)
        assert sorted((d.rbdck_user, d.rbdck_name, d.rbdck_seq)
                      for d in RbDeck.query.filter_by(rbdck_name='Fresh')) == [
            ('alice', 'Fresh', 1), ('alice', 'Fresh', 2)]

    def test_seq_is_counted_per_user(self, app, world):
        body = {'rbdck_name': 'Shared', 'rbdck_cards': {
            'main': [{'set': 'OGN', 'id': '1', 'qty': 1}]}}
        world['alice'].post('/riftbound/deck/save', json=body)
        resp = world['bob'].post('/riftbound/deck/save', json=body)
        assert resp.json['seq'] == 1
