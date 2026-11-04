"""F5-c S3 (AC3): the v2 content model (F5-R6) checks the shape only, keeps printings and
never applies a deck rule."""
import pytest
from pydantic import ValidationError

from app.schemas.deck_content import DeckContentV2, empty_content, validate_content

ZONES = ('v', 'legend', 'champion', 'main', 'runes', 'battlefields', 'sideboard', 'workbench')


def test_a_full_deck_round_trips_in_key_order():
    data = {'v': 2, 'legend': {'set': 'OGN', 'id': '1'},
            'champion': {'set': 'OGNX', 'id': '2'},
            'main': [{'set': 'OGN', 'id': '10', 'qty': 3}, {'set': 'OGNX', 'id': '10', 'qty': 1}],
            'runes': [{'set': 'OGN', 'id': '90', 'qty': 12}],
            'battlefields': [{'set': 'OGN', 'id': '80'}],
            'sideboard': [{'set': 'OGN', 'id': '11', 'qty': 2}],
            'workbench': [{'set': 'OGN', 'id': '12', 'qty': 1}]}
    out = validate_content(data)
    assert out == data
    assert tuple(out) == ZONES


def test_missing_zones_are_empty_and_the_empty_deck_is_valid():
    assert validate_content({'v': 2}) == empty_content()
    assert empty_content() == {'v': 2, 'legend': None, 'champion': None, 'main': [], 'runes': [],
                               'battlefields': [], 'sideboard': [], 'workbench': []}


def test_rules_are_not_enforced_here():
    # 5 battlefields, 4 copies, 40 runes, a sideboard of 30: shape is fine, rules live in deck_rules.
    data = {'v': 2, 'battlefields': [{'set': 'OGN', 'id': str(n)} for n in range(5)],
            'main': [{'set': 'OGN', 'id': '10', 'qty': 4}],
            'runes': [{'set': 'OGN', 'id': '90', 'qty': 40}],
            'sideboard': [{'set': 'OGN', 'id': '11', 'qty': 30}]}
    assert len(validate_content(data)['battlefields']) == 5


@pytest.mark.parametrize('data', [
    {},                                                         # no version
    {'v': 1},
    {'v': '2'},
    {'v': 2, 'extra': []},                                      # unknown key
    {'v': 2, 'legend': {'set': 'OGN'}},                         # ref without id
    {'v': 2, 'legend': {'set': 'OGN', 'id': '1', 'qty': 1}},    # a ref has no qty
    {'v': 2, 'battlefields': [{'set': 'OGN', 'id': '1', 'qty': 1}]},
    {'v': 2, 'main': [{'set': 'OGN', 'id': '1'}]},              # a line needs qty
    {'v': 2, 'main': [{'set': 'OGN', 'id': '1', 'qty': 0}]},
    {'v': 2, 'main': [{'set': 'OGN', 'id': '1', 'qty': '2'}]},
    {'v': 2, 'main': [{'set': 'OGN', 'id': '1', 'qty': True}]},
    {'v': 2, 'main': [{'set': '', 'id': '1', 'qty': 1}]},
    {'v': 2, 'runes': [{'set': 'OGN', 'id': 5, 'qty': 1}]},
    {'v': 2, 'sideboard': None},
])
def test_bad_shapes_are_refused(data):
    with pytest.raises(ValidationError):
        DeckContentV2.model_validate(data)
