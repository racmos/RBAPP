"""F5-c S4-S6 (AC4): `route_deck` turns one legacy `rbdck_cards` value into v2 content
(F5-R7). Nothing is dropped silently: overflow goes to the workbench with a note, cards that
cannot be stored are listed as unresolved, hard limits the result still breaks are noted."""
from copy import deepcopy

from app.schemas.deck_content import empty_content, validate_content
from app.services.deck_migration import route_deck


def card(name, type_, supertype=None, domains=('Calm',), tags=()):
    return {'name': name, 'type': type_, 'supertype': supertype, 'domains': list(domains),
            'tags': list(tags)}


CARDS = {
    ('OGN', 'L1'): card('Emperor of the Sands', 'Legend', 'Champion', ('Calm', 'Order'), ('Azir',)),
    ('OGN', 'L2'): card('The Exile', 'Legend', 'Champion', ('Fury', 'Body'), ('Riven',)),
    ('OGN', 'C1'): card('Azir, Ascendant', 'Unit', 'Champion', tags=('Azir', 'Shurima')),
    ('OGN', 'C2'): card('Riven, Broken', 'Unit', 'Champion', ('Fury',), ('Riven',)),
    ('OGN', 'U1'): card('Shurima Guard', 'Unit'),
    ('OGN', 'U2'): card('Desert Scout', 'Unit'),
    ('OGN', 'U3'): card('Sun Disc Keeper', 'Unit'),
    ('OGN', 'S1'): card('Sandstorm', 'Spell'),
    ('OGN', 'R1'): card('Calm Rune', 'Rune', 'Basic', ('Calm',)),
    ('OGN', 'R2'): card('Order Rune', 'Rune', 'Basic', ('Order',)),
    ('OGN', 'T1'): card('Sand Soldier', 'Unit', 'Token'),
    ('OGNX', 'B1'): card('Field 1', 'Battlefield', domains=()),
    **{('OGN', f'B{n}'): card(f'Field {n}', 'Battlefield', domains=()) for n in range(1, 6)},
}


def line(set_id, card_id, qty=1):
    return {'set': set_id, 'id': card_id, 'qty': qty}


def ref(set_id, card_id):
    return {'set': set_id, 'id': card_id}


def content(**zones):
    out = empty_content()
    out.update(zones)
    return out


def test_a_normal_deck_is_routed_by_type():
    raw = {'main': [line('OGN', 'B1'), line('OGN', 'L1'), line('OGN', 'U1', 3),
                    line('OGN', 'C1', 3), line('OGN', 'R1', 6), line('OGN', 'B2'),
                    line('OGN', 'S1', 2), line('OGN', 'R2', 6), line('OGN', 'B3')],
           'sideboard': [line('OGN', 'U2', 2)]}
    out = route_deck(raw, CARDS)
    assert out['content'] == content(
        legend=ref('OGN', 'L1'), champion=ref('OGN', 'C1'),
        main=[line('OGN', 'U1', 3), line('OGN', 'C1', 2), line('OGN', 'S1', 2)],
        runes=[line('OGN', 'R1', 6), line('OGN', 'R2', 6)],
        battlefields=[ref('OGN', 'B1'), ref('OGN', 'B2'), ref('OGN', 'B3')],
        sideboard=[line('OGN', 'U2', 2)])
    assert out['notes'] == []
    assert out['unresolved'] == []
    assert validate_content(out['content']) == out['content']


def test_two_legends_keep_the_first_and_send_the_rest_to_the_workbench():
    out = route_deck({'main': [line('OGN', 'L1', 2), line('OGN', 'L2')]}, CARDS)
    assert out['content']['legend'] == ref('OGN', 'L1')
    assert out['content']['workbench'] == [line('OGN', 'L1'), line('OGN', 'L2')]
    assert out['notes'] == ['extra legend OGN-L1 "Emperor of the Sands" x1 -> workbench',
                            'extra legend OGN-L2 "The Exile" x1 -> workbench',
                            'no Champion Unit shares a tag with the legend: champion left empty']


def test_the_champion_is_the_first_champion_unit_sharing_a_tag_with_the_legend():
    out = route_deck({'main': [line('OGN', 'C2', 2), line('OGN', 'L1'), line('OGN', 'C1')]},
                     CARDS)
    assert out['content']['champion'] == ref('OGN', 'C1')
    assert out['content']['main'] == [line('OGN', 'C2', 2)]     # the other champion stays
    assert out['notes'] == []


def test_a_champion_without_a_shared_tag_stays_in_the_main_deck():
    out = route_deck({'main': [line('OGN', 'L1'), line('OGN', 'C2', 2)]}, CARDS)
    assert out['content']['champion'] is None
    assert out['content']['main'] == [line('OGN', 'C2', 2)]
    assert out['notes'] == ['no Champion Unit shares a tag with the legend: champion left empty']


def test_without_a_legend_no_champion_is_chosen():
    out = route_deck({'main': [line('OGN', 'C1', 2), line('OGN', 'U1')]}, CARDS)
    assert (out['content']['legend'], out['content']['champion']) == (None, None)
    assert out['content']['main'] == [line('OGN', 'C1', 2), line('OGN', 'U1')]
    assert out['notes'] == ['no legend: champion left empty']


def test_five_battlefields_keep_three_distinct_and_the_rest_go_to_the_workbench():
    raw = {'main': [line('OGN', 'B1', 2), line('OGNX', 'B1'), line('OGN', 'B2'),
                    line('OGN', 'B3'), line('OGN', 'B4'), line('OGN', 'B5')]}
    out = route_deck(raw, CARDS)
    assert out['content']['battlefields'] == [ref('OGN', 'B1'), ref('OGN', 'B2'),
                                              ref('OGN', 'B3')]
    assert out['content']['workbench'] == [line('OGN', 'B1'), line('OGNX', 'B1'),
                                           line('OGN', 'B4'), line('OGN', 'B5')]
    assert out['notes'] == ['battlefield OGN-B1 "Field 1" x1 -> workbench',
                            'battlefield OGNX-B1 "Field 1" x1 -> workbench',
                            'battlefield OGN-B4 "Field 4" x1 -> workbench',
                            'battlefield OGN-B5 "Field 5" x1 -> workbench']


def test_tokens_go_to_the_workbench_from_any_zone():
    out = route_deck({'main': [line('OGN', 'T1', 2), line('OGN', 'U1')],
                      'sideboard': [line('OGN', 'T1')]}, CARDS)
    assert out['content']['workbench'] == [line('OGN', 'T1', 3)]
    assert out['content']['main'] == [line('OGN', 'U1')]
    assert out['content']['sideboard'] == []
    assert out['notes'] == ['token OGN-T1 "Sand Soldier" x2 (main) -> workbench',
                            'token OGN-T1 "Sand Soldier" x1 (sideboard) -> workbench']


def test_unknown_and_invalid_lines_are_left_out_and_listed():
    raw = {'main': [line('OGN', '999', 2), line('OGN', 'U1'), {'set': 'OGN'},
                    line('OGN', 'U2', 0), line('OGN', 'S1', 'x')],
           'sideboard': [line('ZZZ', '1')]}
    out = route_deck(raw, CARDS)
    assert out['content'] == content(main=[line('OGN', 'U1')])
    assert out['unresolved'] == [
        {'zone': 'main', 'label': 'OGN-999 x2'},
        {'zone': 'main', 'label': 'invalid line {"set": "OGN"}'},
        {'zone': 'main', 'label': 'invalid line {"id": "U2", "qty": 0, "set": "OGN"}'},
        {'zone': 'main', 'label': 'invalid line {"id": "S1", "qty": "x", "set": "OGN"}'},
        {'zone': 'sideboard', 'label': 'ZZZ-1 x1'}]
    assert out['notes'] == [
        'unresolved OGN-999 x2 (main): not in the catalog, left out',
        'unresolved invalid line {"set": "OGN"} (main): left out',
        'unresolved invalid line {"id": "U2", "qty": 0, "set": "OGN"} (main): left out',
        'unresolved invalid line {"id": "S1", "qty": "x", "set": "OGN"} (main): left out',
        'unresolved ZZZ-1 x1 (sideboard): not in the catalog, left out']


def test_a_quantity_written_as_digits_is_read():
    out = route_deck({'main': [line('OGN', 'U1', '2')]}, CARDS)
    assert out['content']['main'] == [line('OGN', 'U1', 2)]
    assert out['unresolved'] == []


def test_an_empty_deck_gives_empty_content():
    for raw in (None, {}, {'main': [], 'sideboard': []}):
        out = route_deck(raw, CARDS)
        assert out == {'content': empty_content(), 'notes': ['no cards'], 'unresolved': []}


def test_a_cards_value_of_another_shape_is_listed():
    out = route_deck([line('OGN', 'U1')], CARDS)
    assert out['content'] == empty_content()
    assert out['unresolved'] == [{'zone': 'deck', 'label': 'cards are not an object'}]
    out = route_deck({'main': [line('OGN', 'U1')], 'extra': [line('OGN', 'U2')]}, CARDS)
    assert out['content']['main'] == [line('OGN', 'U1')]
    assert out['unresolved'] == [{'zone': 'extra', 'label': 'unknown key "extra"'}]
    assert out['notes'] == ['unresolved unknown key "extra" (extra): left out']


def test_runes_over_twelve_go_to_the_workbench():
    out = route_deck({'main': [line('OGN', 'L1'), line('OGN', 'R1', 10), line('OGN', 'R2', 4)]},
                     CARDS)
    assert out['content']['runes'] == [line('OGN', 'R1', 10), line('OGN', 'R2', 2)]
    assert out['content']['workbench'] == [line('OGN', 'R2', 2)]
    assert 'rune over 12: OGN-R2 "Order Rune" x2 -> workbench' in out['notes']


def test_the_legacy_sideboard_keeps_ten_and_the_rest_goes_to_the_workbench():
    raw = {'sideboard': [line('OGN', 'S1', 3), line('OGN', 'U1', 3), line('OGN', 'U2', 3),
                         line('OGN', 'U3', 3)]}
    out = route_deck(raw, CARDS)
    assert out['content']['sideboard'] == [line('OGN', 'S1', 3), line('OGN', 'U1', 3),
                                           line('OGN', 'U2', 3), line('OGN', 'U3', 1)]
    assert out['content']['workbench'] == [line('OGN', 'U3', 2)]
    assert out['notes'] == ['sideboard over 10: OGN-U3 "Sun Disc Keeper" x2 -> workbench']


def test_lines_of_one_printing_are_merged_and_hard_limits_are_noted():
    out = route_deck({'main': [line('OGN', 'U1', 1), line('OGN', 'U1', 2), line('OGNX', 'B1'),
                               line('OGN', 'U1', 1)]}, CARDS)
    assert out['content']['main'] == [line('OGN', 'U1', 4)]
    assert out['notes'] == ['hard limit copies (max 3): "Shurima Guard"']


def test_the_inputs_are_not_mutated():
    raw = {'main': [line('OGN', 'L1'), line('OGN', 'C1', 2), line('OGN', 'T1')],
           'sideboard': [line('OGN', 'U1')]}
    raw_before, cards_before = deepcopy(raw), deepcopy(CARDS)
    route_deck(raw, CARDS)
    assert (raw, CARDS) == (raw_before, cards_before)
