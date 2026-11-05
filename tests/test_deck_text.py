"""F5-e S1-S4: the common deck text format, pure (parse, resolve, place, format)."""
import pytest

from app.services import deck_text
from app.services.deck_text import Resolver, build_content, format_text, parse_text


def card(name, type_, domains=(), tags=(), supertype=None):
    return {'name': name, 'type': type_, 'supertype': supertype, 'domains': list(domains),
            'tags': list(tags)}


CARDS = {
    ('OGN', 'L1'): card('The Exile', 'Legend', ['Chaos', 'Calm'], ['Riven'], 'Champion'),
    ('OGN', 'C1'): card('Riven, Broken Blade', 'Unit', ['Chaos'], ['Riven'], 'Champion'),
    ('OGN', 'U1'): card('Shurima Guard', 'Unit', ['Calm']),
    ('OGN', 'U1a'): card('Shurima Guard', 'Unit', ['Calm']),
    ('SFD', 'U1'): card('Shurima Guard', 'Unit', ['Calm']),
    ('OGN', 'S1'): card("Zhonya's Hourglass", 'Gear', ['Calm']),
    ('OGN', 'S2'): card('Star-Crossed', 'Spell', ['Chaos']),
    ('OGN', 'S3'): card('Pokémon', 'Spell', ['Chaos']),
    ('OGN', 'S4'): card('Pokèmon', 'Spell', ['Chaos']),
    ('OGN', 'R1'): card('Chaos Rune', 'Rune', ['Chaos']),
    ('OGN', 'R2'): card('Calm Rune', 'Rune', ['Calm']),
    ('OGN', 'B1'): card('Star Spring', 'Battlefield'),
    ('OGN', 'B2'): card("Hunters' Circle", 'Battlefield'),
    ('OGN', 'B3'): card('Rakelstake', 'Battlefield'),
    ('OGN', 'B4'): card('Field Four', 'Battlefield'),
    ('OGN', 'T1'): card('Sand Soldier', 'Unit', ['Calm'], supertype='Token'),
}
BASE = {('OGN', 'L1'), ('OGN', 'C1'), ('OGN', 'U1'), ('OGN', 'S1'), ('OGN', 'S2'),
        ('OGN', 'S3'), ('OGN', 'S4'), ('OGN', 'R1'), ('OGN', 'R2'), ('OGN', 'B1'),
        ('OGN', 'B2'), ('OGN', 'B3'), ('OGN', 'B4'), ('OGN', 'T1')}


def resolver():
    return Resolver(CARDS, BASE)


def lines(text):
    return [(item['line'], item['zone'], item['qty'], item['name'])
            for item in parse_text(text)['lines']]


def codes(warnings):
    return [(w['line'], w['reason_code']) for w in warnings]


class TestParse:
    def test_blocks_and_lines_of_the_owner_layout(self):
        parsed = parse_text('Legend:\n1 Riven, The Exile\n\nChampion:\n1 Riven, Broken Blade\n\n'
                            'MainDeck:\n3 Zhonya\'s Hourglass\n\nBattlefields:\n1 Star Spring\n\n'
                            'Rune Pool:\n7 Chaos Rune\n\nSideboard:\n2 Star-Crossed\n')
        assert parsed['blocks'] == ['legend', 'champion', 'main', 'battlefields', 'runes',
                                    'sideboard']
        assert lines('Legend:\n1 Riven, The Exile\nMainDeck:\n3 Zhonya\'s Hourglass\n') == [
            (2, 'legend', 1, 'Riven, The Exile'), (4, 'main', 3, "Zhonya's Hourglass")]
        assert parsed['warnings'] == []

    @pytest.mark.parametrize('header,zone', [
        ('legend', 'legend'), ('LEGENDS', 'legend'), ('Champion', 'champion'),
        ('Main Deck:', 'main'), ('maindeck', 'main'), ('Main', 'main'),
        ('Battlefield', 'battlefields'), ('Rune Pool', 'runes'), ('Runes:', 'runes'),
        ('rune', 'runes'), ('Sideboard：', 'sideboard'), ('  side  board ', 'sideboard')])
    def test_headers_ignore_case_colon_and_aliases(self, header, zone):
        assert lines(f'{header}\n2 Foo\n') == [(2, zone, 2, 'Foo')]

    def test_crlf_blank_lines_and_spaces_are_ignored(self):
        assert lines('\r\n  MainDeck:  \r\n\r\n   3   Foo  Bar  \r\n\t\r\n') == [
            (4, 'main', 3, 'Foo  Bar')]
        assert lines('MainDeck:\x0b\n1 Foo\u2028\n') == [(2, 'main', 1, 'Foo')]

    @pytest.mark.parametrize('text,qty,name', [
        ('3x Foo', 3, 'Foo'), ('3 x Foo', 3, 'Foo'), ('3X Foo', 3, 'Foo'), ('Foo', 1, 'Foo'),
        ('1 Riven, The Exile', 1, 'Riven, The Exile'), ('2 Foo (OGN-247)', 2, 'Foo (OGN-247)')])
    def test_quantity_variants(self, text, qty, name):
        assert lines(f'MainDeck:\n{text}\n') == [(2, 'main', qty, name)]

    @pytest.mark.parametrize('text', ['0 Foo', '100 Foo', '0x Foo'])
    def test_an_invalid_quantity_is_a_warning_and_no_line(self, text):
        parsed = parse_text(f'MainDeck:\n{text}\n')
        assert parsed['lines'] == []
        assert parsed['warnings'] == [{'line': 2, 'text': text, 'reason_code': 'quantity_invalid',
                                       'params': {}}]

    def test_lines_before_any_header_have_no_zone(self):
        parsed = parse_text('2 Foo\nMainDeck:\n1 Bar\n')
        assert lines('2 Foo\nMainDeck:\n1 Bar\n') == [(1, None, 2, 'Foo'), (3, 'main', 1, 'Bar')]
        assert codes(parsed['warnings']) == [(1, 'no_zone')]

    def test_an_unknown_header_is_a_warning_and_its_lines_have_no_zone(self):
        parsed = parse_text('MainDeck:\n1 Bar\nWorkbench:\n2 Foo\n')
        assert lines('MainDeck:\n1 Bar\nWorkbench:\n2 Foo\n') == [
            (2, 'main', 1, 'Bar'), (4, None, 2, 'Foo')]
        assert parsed['warnings'][0] == {'line': 3, 'text': 'Workbench:',
                                         'reason_code': 'zone_unknown', 'params': {}}
        assert codes(parsed['warnings']) == [(3, 'zone_unknown'), (4, 'no_zone')]

    def test_duplicated_names_merge_per_block(self):
        assert lines('MainDeck:\n2 Foo\n1 Bar\n1 foo\nSideboard:\n1 Foo\n') == [
            (2, 'main', 3, 'Foo'), (3, 'main', 1, 'Bar'), (6, 'sideboard', 1, 'Foo')]


class TestResolve:
    @pytest.mark.parametrize('name,key', [
        ("Zhonya's Hourglass", ('OGN', 'S1')), ('zhonya’s  hourglass', ('OGN', 'S1')),
        ('Riven, The Exile', ('OGN', 'L1')), ('riven, the exile', ('OGN', 'L1')),
        ('The Exile', ('OGN', 'L1')), ('Riven, Broken Blade', ('OGN', 'C1')),
        ('Shurima Guard', ('OGN', 'U1')), ('SFD-U1', ('SFD', 'U1')), ('ogn u1a', ('OGN', 'U1a')),
        ('Shurima Guard (SFD-U1)', ('SFD', 'U1')), ('Star-Crossed', ('OGN', 'S2')),
        ('Star-Crossed (XXX-1)', ('OGN', 'S2'))])
    def test_resolves_names_ids_and_legends(self, name, key):
        assert resolver().resolve(name) == (key, None)

    def test_unknown_and_ambiguous(self):
        assert resolver().resolve('Nope') == (None, 'unknown_card')
        assert resolver().resolve('Other, The Exile') == (None, 'unknown_card')
        assert resolver().resolve('Pokemon') == (None, 'ambiguous_card')
        assert resolver().resolve('Pokémon') == (('OGN', 'S3'), None)


def build(text):
    return build_content(parse_text(text), resolver(), CARDS)


class TestBuild:
    def test_places_each_block(self):
        content, warnings, counts = build(
            'Legend:\n1 Riven, The Exile\nChampion:\n1 Riven, Broken Blade\nMainDeck:\n'
            '2 Shurima Guard\n1 SFD-U1\nBattlefields:\n1 Star Spring\n1 Rakelstake\n'
            'Rune Pool:\n7 Chaos Rune\n5 Calm Rune\nSideboard:\n1 Star-Crossed\n')
        assert content == {
            'v': 2, 'legend': {'set': 'OGN', 'id': 'L1'},
            'champion': {'set': 'OGN', 'id': 'C1'},
            'main': [{'set': 'OGN', 'id': 'U1', 'qty': 2}, {'set': 'SFD', 'id': 'U1', 'qty': 1}],
            'runes': [{'set': 'OGN', 'id': 'R1', 'qty': 7}, {'set': 'OGN', 'id': 'R2', 'qty': 5}],
            'battlefields': [{'set': 'OGN', 'id': 'B1'}, {'set': 'OGN', 'id': 'B3'}],
            'sideboard': [{'set': 'OGN', 'id': 'S2', 'qty': 1}], 'workbench': []}
        assert warnings == []
        assert counts == {'lines': 9, 'copies': 20, 'unresolved': 0}

    def test_unknown_cards_are_warnings_and_not_in_the_content(self):
        content, warnings, counts = build('MainDeck:\n2 Nope\n1 Pokemon\n3 Shurima Guard\n')
        assert content['main'] == [{'set': 'OGN', 'id': 'U1', 'qty': 3}]
        assert warnings == [
            {'line': 2, 'text': '2 Nope', 'reason_code': 'unknown_card', 'params': {}},
            {'line': 3, 'text': '1 Pokemon', 'reason_code': 'ambiguous_card', 'params': {}}]
        assert counts == {'lines': 3, 'copies': 3, 'unresolved': 3}

    def test_a_card_in_the_wrong_block_stays_there_with_a_warning(self):
        content, warnings, _ = build('MainDeck:\n1 Star Spring\nRunes:\n2 Shurima Guard\n'
                                     'Legend:\n1 Chaos Rune\n')
        assert content['main'] == [{'set': 'OGN', 'id': 'B1', 'qty': 1}]
        assert content['runes'] == [{'set': 'OGN', 'id': 'U1', 'qty': 2}]
        assert content['legend'] == {'set': 'OGN', 'id': 'R1'}
        assert warnings == [
            {'line': 2, 'text': '1 Star Spring', 'reason_code': 'wrong_zone',
             'params': {'name': 'Star Spring', 'zone': 'main'}},
            {'line': 4, 'text': '2 Shurima Guard', 'reason_code': 'wrong_zone',
             'params': {'name': 'Shurima Guard', 'zone': 'runes'}},
            {'line': 6, 'text': '1 Chaos Rune', 'reason_code': 'wrong_zone',
             'params': {'name': 'Chaos Rune', 'zone': 'legend'}}]

    def test_lines_without_a_block_are_placed_by_type(self):
        content, warnings, _ = build('1 The Exile\n1 Riven, Broken Blade\n2 Shurima Guard\n'
                                     '1 Star Spring\n6 Calm Rune\n')
        assert content['legend'] == {'set': 'OGN', 'id': 'L1'}
        assert content['champion'] == {'set': 'OGN', 'id': 'C1'}
        assert content['main'] == [{'set': 'OGN', 'id': 'U1', 'qty': 2}]
        assert content['battlefields'] == [{'set': 'OGN', 'id': 'B1'}]
        assert content['runes'] == [{'set': 'OGN', 'id': 'R2', 'qty': 6}]
        assert codes(warnings) == [(n, 'no_zone') for n in range(1, 6)]

    def test_extra_legend_goes_to_the_workbench_and_extra_champion_to_main(self):
        content, warnings, _ = build('Legend:\n2 The Exile\nChampion:\n1 Riven, Broken Blade\n'
                                     '1 Shurima Guard\n')
        assert content['legend'] == {'set': 'OGN', 'id': 'L1'}
        assert content['workbench'] == [{'set': 'OGN', 'id': 'L1', 'qty': 1}]
        assert content['champion'] == {'set': 'OGN', 'id': 'C1'}
        assert content['main'] == [{'set': 'OGN', 'id': 'U1', 'qty': 1}]
        assert warnings == [
            {'line': 2, 'text': '2 The Exile', 'reason_code': 'slot_taken',
             'params': {'name': 'The Exile', 'zone': 'legend', 'to': 'workbench', 'qty': 1}},
            {'line': 5, 'text': '1 Shurima Guard', 'reason_code': 'wrong_zone',
             'params': {'name': 'Shurima Guard', 'zone': 'champion'}},
            {'line': 5, 'text': '1 Shurima Guard', 'reason_code': 'slot_taken',
             'params': {'name': 'Shurima Guard', 'zone': 'champion', 'to': 'main', 'qty': 1}}]

    def test_battlefield_copies_are_kept(self):
        content, _, _ = build('Battlefields:\n2 Star Spring\n')
        assert content['battlefields'] == [{'set': 'OGN', 'id': 'B1'}] * 2

    def test_hard_limits_are_kept_and_reported(self):
        content, warnings, _ = build('MainDeck:\n5 Shurima Guard\n1 Sand Soldier\n'
                                     'Rune Pool:\n13 Chaos Rune\n')
        assert content['main'] == [{'set': 'OGN', 'id': 'U1', 'qty': 5},
                                   {'set': 'OGN', 'id': 'T1', 'qty': 1}]
        assert content['runes'] == [{'set': 'OGN', 'id': 'R1', 'qty': 13}]
        assert warnings == [
            {'line': None, 'text': 'copies (max 3): Shurima Guard', 'reason_code': 'hard_limit',
             'params': {'rule': 'copies', 'max': 3, 'name': 'Shurima Guard'}},
            {'line': None, 'text': 'runes (max 12)', 'reason_code': 'hard_limit',
             'params': {'rule': 'runes', 'max': 12}},
            {'line': None, 'text': 'token (max 0): Sand Soldier', 'reason_code': 'hard_limit',
             'params': {'rule': 'token', 'max': 0, 'name': 'Sand Soldier'}}]


class TestFormat:
    def test_owner_layout(self):
        content = {
            'v': 2, 'legend': {'set': 'OGN', 'id': 'L1'}, 'champion': {'set': 'OGN', 'id': 'C1'},
            'main': [{'set': 'OGN', 'id': 'S1', 'qty': 3}, {'set': 'OGN', 'id': 'U1', 'qty': 2},
                     {'set': 'SFD', 'id': 'U1', 'qty': 1}],
            'runes': [{'set': 'OGN', 'id': 'R1', 'qty': 7}, {'set': 'OGN', 'id': 'R2', 'qty': 5}],
            'battlefields': [{'set': 'OGN', 'id': 'B2'}, {'set': 'OGN', 'id': 'B1'}],
            'sideboard': [{'set': 'OGN', 'id': 'S2', 'qty': 2}, {'set': 'XXX', 'id': '9', 'qty': 1}],
            'workbench': [{'set': 'OGN', 'id': 'U1', 'qty': 1}]}
        assert format_text(content, CARDS) == (
            'Legend:\n1 Riven, The Exile\n\nChampion:\n1 Riven, Broken Blade\n\n'
            "MainDeck:\n3 Zhonya's Hourglass\n3 Shurima Guard\n\n"
            "Battlefields:\n1 Hunters' Circle\n1 Star Spring\n\n"
            'Rune Pool:\n7 Chaos Rune\n5 Calm Rune\n\nSideboard:\n2 Star-Crossed\n1 XXX-9\n')

    def test_empty_blocks_are_omitted(self):
        content = {'v': 2, 'legend': None, 'champion': None, 'main': [],
                   'runes': [{'set': 'OGN', 'id': 'R1', 'qty': 12}], 'battlefields': [],
                   'sideboard': [], 'workbench': [{'set': 'OGN', 'id': 'U1', 'qty': 1}]}
        assert format_text(content, CARDS) == 'Rune Pool:\n12 Chaos Rune\n'
        assert format_text({'v': 2, 'legend': None, 'champion': None, 'main': [], 'runes': [],
                            'battlefields': [], 'sideboard': [], 'workbench': []}, CARDS) == ''

    def test_a_legend_whose_name_already_has_the_tag_is_printed_as_is(self):
        cards = {('A', '1'): card('Azir, Emperor', 'Legend', tags=['Azir']),
                 ('A', '2'): card('Plain', 'Legend')}
        body = {'v': 2, 'legend': {'set': 'A', 'id': '1'}, 'champion': None, 'main': [],
                'runes': [], 'battlefields': [], 'sideboard': [], 'workbench': []}
        assert format_text(body, cards) == 'Legend:\n1 Azir, Emperor\n'
        body['legend'] = {'set': 'A', 'id': '2'}
        assert format_text(body, cards) == 'Legend:\n1 Plain\n'

    def test_text_round_trip(self):
        text = ('Legend:\n1 Riven, The Exile\n\nChampion:\n1 Riven, Broken Blade\n\n'
                "MainDeck:\n3 Zhonya's Hourglass\n2 Shurima Guard\n\n"
                "Battlefields:\n1 Hunters' Circle\n\nRune Pool:\n7 Chaos Rune\n\n"
                'Sideboard:\n2 Star-Crossed\n')
        content, warnings, _ = build(text)
        assert warnings == []
        assert format_text(content, CARDS) == text
        assert build(format_text(content, CARDS))[0] == content


# Owner feedback 2026-11-05: a line may end with its printing in square brackets, the set code
# upper-case and the number zero-padded (`1 Riven, Broken Blade [RAD-043]`).
BR_CARDS = {
    ('RAD', '149'): card('The Exile', 'Legend', ['Chaos', 'Calm'], ['Riven'], 'Champion'),
    ('RAD', '43'): card('Riven, Broken Blade', 'Unit', ['Chaos'], ['Riven'], 'Champion'),
    ('OGN', '8'): card('Astral Heron', 'Unit', ['Calm']),
    ('VEN', '44'): card('Astral Heron', 'Unit', ['Calm']),
    ('VEN', '44a'): card('Astral Heron', 'Unit', ['Calm']),
    ('VEN', 't04'): card('Sand Soldier', 'Unit', ['Calm'], supertype='Token'),
    ('VEN', '007'): card('Old Padded', 'Spell', ['Calm']),
}
BR_BASE = {('RAD', '149'), ('RAD', '43'), ('OGN', '8'), ('VEN', 't04'), ('VEN', '007')}
OWNER_BRACKETS = ('Legend:\n1 Riven, The Exile [RAD-149]\n\n'
                  'Champion:\n1 Riven, Broken Blade [RAD-043]\n\n'
                  'MainDeck:\n3 Astral Heron [VEN-044]\n')


def br_match(text):
    return Resolver(BR_CARDS, BR_BASE).match(text)


def br_build(text):
    return build_content(parse_text(text), Resolver(BR_CARDS, BR_BASE), BR_CARDS)


class TestBracketPrinting:
    def test_the_owner_lines_load_the_written_printings(self):
        content, warnings, counts = br_build(OWNER_BRACKETS)
        assert content['legend'] == {'set': 'RAD', 'id': '149'}
        assert content['champion'] == {'set': 'RAD', 'id': '43'}
        # VEN-44 as written, not the base printing OGN-8
        assert content['main'] == [{'set': 'VEN', 'id': '44', 'qty': 3}]
        assert warnings == []
        assert counts == {'lines': 3, 'copies': 5, 'unresolved': 0}

    @pytest.mark.parametrize('text,key', [
        ('Riven, Broken Blade [RAD-043]', ('RAD', '43')),
        ('Riven, Broken Blade [rad-43]', ('RAD', '43')),
        ('riven, broken blade  [ RAD-0043 ] ', ('RAD', '43')),
        ('The Exile [RAD-149]', ('RAD', '149')),
        ('Riven, The Exile [RAD-149]', ('RAD', '149')),
        ('Astral Heron [VEN-044a]', ('VEN', '44a')),
        ('Astral Heron [VEN-44A]', ('VEN', '44a')),
        ('Astral Heron [VEN 044]', ('VEN', '44')),
        ('Sand Soldier [VEN-T04]', ('VEN', 't04')),
        ('Sand Soldier [ven-t04]', ('VEN', 't04')),
        ('Old Padded [VEN-007]', ('VEN', '007')),
        ('Old Padded [VEN-7]', ('VEN', '007')),
        ('[VEN-044]', ('VEN', '44')),
        ('Astral Heron (VEN-044)', ('VEN', '44')),
        ('VEN-044', ('VEN', '44'))])
    def test_set_case_and_leading_zeros_do_not_matter(self, text, key):
        assert br_match(text) == (key, None, {})

    def test_an_unknown_printing_of_a_known_name_loads_the_base_printing_with_a_warning(self):
        assert br_match('Astral Heron [VEN-999]') == (
            ('OGN', '8'), 'printing_unknown', {'id': 'VEN-999', 'name': 'Astral Heron'})
        assert br_match('Riven, The Exile [OGN-001]') == (
            ('RAD', '149'), 'printing_unknown', {'id': 'OGN-001', 'name': 'Riven, The Exile'})
        assert br_match('Astral Heron [foil]') == (
            ('OGN', '8'), 'printing_unknown', {'id': 'foil', 'name': 'Astral Heron'})

    def test_an_unknown_printing_of_an_unknown_name_is_left_out_with_the_id(self):
        assert br_match('Nope [VEN-999]') == (None, 'unknown_card', {'id': 'VEN-999'})
        assert br_match('[VEN-999]') == (None, 'unknown_card', {'id': 'VEN-999'})

    def test_a_known_printing_with_another_name_loads_the_printing_with_a_warning(self):
        assert br_match('Astral Heron [RAD-043]') == (
            ('RAD', '43'), 'name_mismatch',
            {'written': 'Astral Heron', 'found': 'Riven, Broken Blade'})
        assert br_match('Riven, Broken Blade [RAD-149]') == (
            ('RAD', '149'), 'name_mismatch',
            {'written': 'Riven, Broken Blade', 'found': 'Riven, The Exile'})

    def test_warnings_carry_the_line_and_unknown_cards_stay_out(self):
        content, warnings, counts = br_build(
            'MainDeck:\n2 Astral Heron [VEN-999]\n1 Nope [VEN-998]\n'
            '1 Astral Heron [RAD-043]\n')
        assert content['main'] == [{'set': 'OGN', 'id': '8', 'qty': 2},
                                   {'set': 'RAD', 'id': '43', 'qty': 1}]
        assert warnings == [
            {'line': 2, 'text': '2 Astral Heron [VEN-999]', 'reason_code': 'printing_unknown',
             'params': {'id': 'VEN-999', 'name': 'Astral Heron'}},
            {'line': 3, 'text': '1 Nope [VEN-998]', 'reason_code': 'unknown_card',
             'params': {'id': 'VEN-998'}},
            {'line': 4, 'text': '1 Astral Heron [RAD-043]', 'reason_code': 'name_mismatch',
             'params': {'written': 'Astral Heron', 'found': 'Riven, Broken Blade'}}]
        assert counts == {'lines': 3, 'copies': 3, 'unresolved': 1}

    def test_two_printings_of_a_name_stay_two_lines(self):
        content, warnings, _ = br_build('MainDeck:\n1 Astral Heron [VEN-044]\n'
                                        '1 Astral Heron [VEN-044a]\n1 Astral Heron [VEN-44]\n')
        assert content['main'] == [{'set': 'VEN', 'id': '44', 'qty': 2},
                                   {'set': 'VEN', 'id': '44a', 'qty': 1}]
        assert warnings == []

    def test_the_export_has_no_brackets(self):
        content, _, _ = br_build(OWNER_BRACKETS)
        assert format_text(content, BR_CARDS) == (
            'Legend:\n1 Riven, The Exile\n\nChampion:\n1 Riven, Broken Blade\n\n'
            'MainDeck:\n3 Astral Heron\n')

    def test_the_parenthesis_form_warns_a_name_mismatch_but_never_a_missing_printing(self):
        # A parenthesis may hold other words (`(Alt Art)`), so a missing id there is not a warning.
        assert resolver().match('Shurima Guard (OGN-S1)') == (
            ('OGN', 'S1'), 'name_mismatch',
            {'written': 'Shurima Guard', 'found': "Zhonya's Hourglass"})
        assert resolver().match('Star-Crossed (XXX-1)') == (('OGN', 'S2'), None, {})
        assert resolver().match('Shurima Guard (SFD-U1)') == (('SFD', 'U1'), None, {})

    def test_resolve_keeps_its_two_values(self):
        resolver = Resolver(BR_CARDS, BR_BASE)
        assert resolver.resolve('Astral Heron [VEN-044]') == (('VEN', '44'), None)
        assert resolver.resolve('Astral Heron [VEN-999]') == (('OGN', '8'), None)
        assert resolver.resolve('Nope [VEN-999]') == (None, 'unknown_card')


def test_module_constants():
    assert deck_text.FORMATS == ('auto', 'text')
    assert deck_text.REASON_CODES == ('no_zone', 'zone_unknown', 'quantity_invalid',
                                      'unknown_card', 'ambiguous_card', 'wrong_zone',
                                      'slot_taken', 'hard_limit', 'printing_unknown',
                                      'name_mismatch')
