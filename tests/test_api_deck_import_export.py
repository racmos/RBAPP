"""F5-e S5-S9: POST /decks/import/preview, POST /decks/import, GET /decks/<id>/export."""
from pathlib import Path

import pytest

from app import db
from app.models import RbCard, RbDeckHead, RbDeckVersion, RbSet
from tests.deck_api_helpers import (BASE, NOT_FOUND, content, data, error, line, make_deck, ref,
                                    versions)

SAMPLE = (Path(__file__).resolve().parents[1]
          / 'docs/requirements/F5/samples/deck-export-text-1.txt').read_bytes()
PREVIEW_KEYS = ['deck_preview', 'warnings', 'counts']
DECK_PREVIEW_KEYS = ['content', 'cards', 'unknown_cards', 'domains', 'counts', 'value',
                     'value_unpriced', 'legality']
DETAIL_KEYS = ['id', 'name', 'mode', 'visibility', 'created_at', 'updated_at', 'share',
               'current_seq', 'content', 'cards', 'unknown_cards', 'domains', 'counts', 'value',
               'value_unpriced', 'legality', 'warnings']

# The owner's sample deck as a synthetic catalog: (id, name, type, domains, tags).
_SAMPLE_CARDS = [
    ('1', 'The Exile', 'Champion Legend', 'Chaos Calm', 'Riven'),
    ('2', 'Riven, Broken Blade', 'Champion Unit', 'Chaos', 'Riven'),
    ('3', 'Discipline', 'Spell', 'Calm', ''),
    ('4', "Zhonya's Hourglass", 'Gear', 'Calm', ''),
    ('5', 'Traveling Merchant', 'Unit', 'Chaos', ''),
    ('6', 'Tideturner', 'Unit', 'Chaos', ''),
    ('7', 'Stellacorn Herder', 'Unit', 'Calm', ''),
    ('8', 'Astral Heron', 'Unit', 'Calm', ''),
    ('9', 'Blade of the Exile', 'Gear', 'Chaos', ''),
    ('10', 'Defy', 'Spell', 'Calm', ''),
    ('11', 'Gust', 'Spell', 'Chaos', ''),
    ('12', 'Switcheroo', 'Spell', 'Chaos', ''),
    ('13', 'Battle Preparations', 'Spell', 'Calm', ''),
    ('14', 'Reckless Innovator', 'Unit', 'Chaos', ''),
    ('15', 'Bedeviling Stranger', 'Unit', 'Chaos', ''),
    ('16', 'Rebuke', 'Spell', 'Calm', ''),
    ('17', 'Not So Fast', 'Spell', 'Calm', ''),
    ('18', 'Star-Crossed', 'Spell', 'Chaos', ''),
    ('19', 'Baron Nashor', 'Unit', 'Chaos', ''),
    ('20', 'Blitzcrank, Impassive', 'Unit', 'Calm', ''),
    ('21', 'Star Spring', 'Battlefield', '', ''),
    ('22', "Hunters' Circle", 'Battlefield', '', ''),
    ('23', 'Rakelstake', 'Battlefield', '', ''),
    ('24', 'Chaos Rune', 'Basic Rune', 'Chaos', ''),
    ('25', 'Calm Rune', 'Basic Rune', 'Calm', ''),
    ('26', 'Decree of Focus', 'Spell', 'Calm', ''),
    ('27', "An Offer You Can't Refuse", 'Spell', 'Chaos', ''),
    ('28', 'Vex, Apathetic', 'Unit', 'Chaos', ''),
    ('29', 'Hush', 'Spell', 'Calm', ''),
    ('30', 'Sand Soldier', 'Token Unit', 'Calm', ''),
]


def _card(set_id, card_id, name, type_, domains, tags):
    return RbCard(rbcar_rbset_id=set_id, rbcar_id=card_id, rbcar_name=name, rbcar_type=type_,
                  rbcar_domain=domains, rbcar_tags=tags, rbcar_rarity='Common')


@pytest.fixture
def api(app, authenticated_client, make_user):
    make_user('otheruser')
    db.session.add_all([RbSet(rbset_id='OGN', rbset_name='Origins'),
                        RbSet(rbset_id='SFD', rbset_name='Spiritforged')])
    db.session.add_all([_card('OGN', *row) for row in _SAMPLE_CARDS])
    # A later printing of Discipline: the import prefers the base printing (OGN-3).
    db.session.add(_card('SFD', '200', 'Discipline', 'Spell', 'Calm', ''))
    db.session.commit()
    return authenticated_client


def preview(api, text, **extra):
    return api.post(f'{BASE}/import/preview', json={'text': text, **extra})


def do_import(api, text, **extra):
    return api.post(f'{BASE}/import', json={'text': text, **extra})


def sample():
    return SAMPLE.decode('utf-8')


def o(card_id, qty=None):
    return ref('OGN', card_id) if qty is None else line('OGN', card_id, qty)


SAMPLE_CONTENT = content(
    legend=o('1'), champion=o('2'),
    main=[o('3', 3), o('4', 3), o('5', 3), o('6', 3), o('7', 3), o('8', 3), o('9', 3),
          o('10', 2), o('11', 2), o('12', 2), o('13', 2), o('14', 2), o('15', 2), o('16', 1),
          o('17', 1), o('18', 1), o('19', 1), o('20', 2)],
    runes=[o('24', 7), o('25', 5)], battlefields=[o('21'), o('22'), o('23')],
    sideboard=[o('26', 2), o('27', 2), o('16', 1), o('17', 1), o('18', 1), o('28', 1),
               o('29', 1), o('14', 1)])


def heads():
    db.session.expire_all()
    return RbDeckHead.query.count(), RbDeckVersion.query.count()


class TestPreview:
    def test_the_owner_sample_is_a_legal_deck_and_nothing_is_stored(self, api):
        body = data(preview(api, sample()))
        assert list(body) == PREVIEW_KEYS
        deck = body['deck_preview']
        assert list(deck) == DECK_PREVIEW_KEYS
        assert deck['content'] == SAMPLE_CONTENT
        assert deck['cards']['OGN-1']['name'] == 'The Exile'
        assert deck['counts'] == {'main': 39, 'runes': 12, 'battlefields': 3, 'sideboard': 10,
                                  'workbench': 0}
        assert deck['domains'] == ['Calm', 'Chaos']
        for mode in ('1v1', '2v2'):
            assert deck['legality'][mode]['legal'] is True, deck['legality'][mode]
            assert deck['legality'][mode]['completeness']['main'] == {
                'have': 39, 'need': 39, 'missing': 0}
        assert body['warnings'] == []
        assert body['counts'] == {'lines': 33, 'copies': 66, 'unresolved': 0}
        assert heads() == (0, 0)

    def test_format_auto_and_text_are_the_same(self, api):
        auto = data(preview(api, sample(), format='auto'))
        assert data(preview(api, sample(), format='text')) == auto

    @pytest.mark.parametrize('fmt', ['riftdecks', 'piltover', 'rbapp', 'TEXT', ''])
    def test_other_formats_are_unknown(self, api, fmt):
        body = error(preview(api, sample(), format=fmt), 400, 'import_format_unknown')
        assert body['message'] == 'The deck format is not recognised. Use the text format.'

    def test_an_incomplete_deck_with_problems_still_loads(self, api):
        text = 'Legend:\n1 Riven, The Exile\nMainDeck:\n2 Nope\n2 Star Spring\n3x Discipline\n'
        body = data(preview(api, text))
        deck = body['deck_preview']
        assert deck['content'] == content(legend=o('1'),
                                          main=[o('21', 2), o('3', 3)])
        assert [(w['line'], w['reason_code']) for w in body['warnings']] == [
            (4, 'unknown_card'), (5, 'wrong_zone')]
        assert body['warnings'][0] == {'line': 4, 'text': '2 Nope',
                                       'reason_code': 'unknown_card', 'params': {}}
        legality = deck['legality']['1v1']
        assert legality['legal'] is False
        assert legality['completeness']['main'] == {'have': 5, 'need': 39, 'missing': 34}
        assert legality['completeness']['champion'] == {'have': 0, 'need': 1, 'missing': 1}
        assert {'code': 'card_off_identity',
                'params': {'name': 'Star Spring', 'zone': 'main', 'reason': 'type'}} \
            in legality['issues']
        assert body['counts'] == {'lines': 4, 'copies': 6, 'unresolved': 2}


    def test_bracket_printings_owner_feedback_2026_11_05(self, api):
        text = ('Legend:\n1 Riven, The Exile [OGN-001]\n\nChampion:\n'
                '1 Riven, Broken Blade [ogn-002]\n\nMainDeck:\n3 Discipline [SFD-200]\n'
                '2 Defy [OGN-999]\n1 Nope [OGN-998]\n1 Gust [OGN-008]\n')
        body = data(preview(api, text))
        assert body['deck_preview']['content'] == content(
            legend=o('1'), champion=o('2'),
            main=[line('SFD', '200', 3), o('10', 2), o('8', 1)])
        assert body['warnings'] == [
            {'line': 9, 'text': '2 Defy [OGN-999]', 'reason_code': 'printing_unknown',
             'params': {'id': 'OGN-999', 'name': 'Defy'}},
            {'line': 10, 'text': '1 Nope [OGN-998]', 'reason_code': 'unknown_card',
             'params': {'id': 'OGN-998'}},
            {'line': 11, 'text': '1 Gust [OGN-008]', 'reason_code': 'name_mismatch',
             'params': {'written': 'Gust', 'found': 'Astral Heron'}}]
        assert body['counts'] == {'lines': 6, 'copies': 8, 'unresolved': 1}


class TestLimits:
    def test_text_over_64_kb_is_a_validation_error(self, api):
        text = 'MainDeck:\n' + '1 ' + 'x' * (64 * 1024)
        body = error(preview(api, text), 400, 'validation_error')
        assert body['details'][0]['field'] == 'text'
        assert body['details'][0]['code'] == 'too_long'
        assert body['details'][0]['params'] == {'max': 65536}
        assert error(do_import(api, text), 400, 'validation_error')
        assert heads() == (0, 0)

    def test_text_over_2000_lines_is_a_validation_error(self, api):
        text = '1 Gust\n' * 2001
        body = error(do_import(api, text), 400, 'validation_error')
        assert body['details'][0]['params'] == {'max': 2000}
        assert data(preview(api, '1 Gust\n' * 2000))['counts']['lines'] == 1
        assert heads() == (0, 0)

    def test_text_is_required(self, api):
        assert error(api.post(f'{BASE}/import/preview', json={}), 400, 'validation_error')


class TestImport:
    def test_creates_the_deck_with_version_1(self, api, frozen_clock):
        deck = data(do_import(api, sample()), 201)
        assert list(deck) == DETAIL_KEYS
        assert deck['name'] == 'Riven, The Exile' and deck['mode'] == '1v1'
        assert deck['visibility'] == 'private' and deck['current_seq'] == 1
        assert deck['content'] == SAMPLE_CONTENT and deck['warnings'] == []
        assert deck['legality']['1v1']['legal'] is True
        assert versions(deck['id']) == [(1, SAMPLE_CONTENT, None)]
        assert data(api.get(f'{BASE}/{deck["id"]}'))['content'] == SAMPLE_CONTENT

    def test_name_and_mode(self, api):
        deck = data(do_import(api, sample(), name='  Riven Calm ', mode='2v2'), 201)
        assert deck['name'] == 'Riven Calm' and deck['mode'] == '2v2'
        assert data(do_import(api, sample(), name='   '), 201)['name'] == 'Riven, The Exile'
        assert data(do_import(api, 'MainDeck:\n1 Gust\n'), 201)['name'] == 'Imported deck'
        assert error(do_import(api, sample(), mode='3v3'), 400, 'validation_error')

    def test_a_taken_name_gets_a_number(self, api):
        names = [data(do_import(api, sample()), 201)['name'] for _ in range(3)]
        assert names == ['Riven, The Exile', 'Riven, The Exile (2)', 'Riven, The Exile (3)']
        long = 'x' * 80
        assert data(do_import(api, sample(), name=long), 201)['name'] == long
        assert data(do_import(api, sample(), name=long), 201)['name'] == 'x' * 76 + ' (2)'

    def test_another_users_deck_name_is_free(self, api):
        make_deck('Riven, The Exile', user='otheruser')
        assert data(do_import(api, sample()), 201)['name'] == 'Riven, The Exile'

    def test_hard_limits_are_imported_as_is_and_reported(self, api):
        text = ('MainDeck:\n5 Discipline\n1 Sand Soldier\nSideboard:\n'
                '11 Gust\n')
        deck = data(do_import(api, text), 201)
        stored = content(main=[o('3', 5), o('30', 1)], sideboard=[o('11', 11)])
        assert deck['content'] == stored and versions(deck['id'])[0][1] == stored
        assert [w['params'] for w in deck['warnings']] == [
            {'rule': 'copies', 'max': 3, 'name': 'Discipline'},
            {'rule': 'copies', 'max': 3, 'name': 'Gust'},
            {'rule': 'sideboard', 'max': 10},
            {'rule': 'token', 'max': 0, 'name': 'Sand Soldier'}]
        assert {w['reason_code'] for w in deck['warnings']} == {'hard_limit'}
        codes = [i['code'] for i in deck['legality']['1v1']['issues']]
        assert 'copies_over' in codes and 'token_in_deck' in codes
        # Decision (A): the editor's save keeps refusing it until every limit is fixed.
        error(api.put(f'{BASE}/{deck["id"]}/content', json={'content': stored}), 400,
              'deck_limit_exceeded')

    def test_unknown_format_creates_nothing(self, api):
        error(do_import(api, sample(), format='piltover'), 400, 'import_format_unknown')
        assert heads() == (0, 0)


class TestExport:
    def test_the_owner_sample_round_trips_byte_identical(self, api):
        deck_id = data(do_import(api, sample()), 201)['id']
        resp = api.get(f'{BASE}/{deck_id}/export?format=text')
        assert resp.status_code == 200
        assert resp.headers['Content-Type'] == 'text/plain; charset=utf-8'
        assert resp.headers['Content-Disposition'] == \
            'attachment; filename="riven-the-exile.txt"'
        assert resp.data == SAMPLE
        assert api.get(f'{BASE}/{deck_id}/export').data == SAMPLE

    def test_export_then_import_gives_the_same_content(self, api):
        body = content(legend=o('1'), champion=o('2'),
                       main=[line('SFD', '200', 1), o('3', 2), o('20', 1)],
                       battlefields=[o('22')], runes=[o('25', 12)],
                       sideboard=[o('29', 1)], workbench=[o('5', 3)])
        deck_id = make_deck('Mine', body)
        text = api.get(f'{BASE}/{deck_id}/export').data.decode('utf-8')
        assert text == ('Legend:\n1 Riven, The Exile\n\nChampion:\n1 Riven, Broken Blade\n\n'
                        'MainDeck:\n3 Discipline\n1 Blitzcrank, Impassive\n\n'
                        "Battlefields:\n1 Hunters' Circle\n\nRune Pool:\n12 Calm Rune\n\n"
                        'Sideboard:\n1 Hush\n')
        again = data(preview(api, text))['deck_preview']['content']
        # Printings of one name collapse to the base printing; the workbench is not exported.
        assert again == content(legend=o('1'), champion=o('2'), main=[o('3', 3), o('20', 1)],
                                battlefields=[o('22')], runes=[o('25', 12)],
                                sideboard=[o('29', 1)])

    def test_filename_slug(self, api):
        deck_id = make_deck('  Ñandú / Fury!! ')
        resp = api.get(f'{BASE}/{deck_id}/export')
        assert resp.headers['Content-Disposition'] == 'attachment; filename="nandu-fury.txt"'
        assert resp.data == b''
        deck_id = make_deck('***')
        assert api.get(f'{BASE}/{deck_id}/export').headers['Content-Disposition'] == \
            'attachment; filename="deck.txt"'

    def test_other_formats_and_other_users(self, api):
        deck_id = make_deck('Mine')
        error(api.get(f'{BASE}/{deck_id}/export?format=piltover'), 400,
              'import_format_unknown')
        other = make_deck('Theirs', user='otheruser')
        resp = api.get(f'{BASE}/{other}/export')
        assert resp.status_code == 404 and resp.get_json() == NOT_FOUND
        assert api.get(f'{BASE}/999/export').status_code == 404


@pytest.mark.parametrize('method,path', [
    ('post', '/import/preview'), ('post', '/import'), ('get', '/1/export')])
def test_anonymous_is_401(client, method, path):
    resp = getattr(client, method)(f'{BASE}{path}', json={'text': '1 Gust'}) \
        if method == 'post' else client.get(f'{BASE}{path}')
    assert resp.status_code == 401
