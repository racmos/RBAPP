"""F5-a: engine behaviour that the shared cases cannot express (errors, purity, the
rule values as the single source). The rules themselves are in
`tests/test_deck_rules_cases.py`."""
import copy

import pytest

from app.schemas import game_domain
from app.services import deck_rules
from tests.test_deck_rules_cases import CASES, _cards


def _case(case_id):
    return next(case for case in CASES if case['id'] == case_id)


REAL = _case('validate-real-deck-legal-1v1')


def test_no_app_context_needed():
    """Pure functions: no Flask app, request or database (this test has no `app` fixture)."""
    assert deck_rules.validate(REAL['deck'], _cards(REAL), {}, '1v1')['legal'] is True


def test_inputs_are_never_mutated():
    for case in CASES:
        deck, cards = copy.deepcopy(case['deck']), _cards(case)
        frozen = copy.deepcopy((deck, cards, case['args']))
        if case['op'] == 'apply_legend':
            result = deck_rules.apply_legend(deck, cards, case['args']['legend'])
        elif case['op'] == 'apply_champion':
            result = deck_rules.apply_champion(deck, cards, case['args']['champion'])
        elif case['op'] == 'auto_runes':
            result = deck_rules.auto_runes(deck, cards)
        else:
            continue
        assert (deck, cards, case['args']) == frozen, case['id']
        returned = result.get('deck', result) if isinstance(result, dict) else result
        assert returned is not deck, case['id']


def test_unknown_mode_is_an_error():
    with pytest.raises(ValueError, match='unknown game mode: ffa'):
        deck_rules.validate(REAL['deck'], _cards(REAL), {}, 'ffa')


def test_unknown_card_is_an_error():
    deck = copy.deepcopy(REAL['deck'])
    deck['main'].append({'set': 'ZZZ', 'id': '1', 'qty': 1})
    with pytest.raises(deck_rules.UnknownCard) as raised:
        deck_rules.validate(deck, _cards(REAL), {}, '1v1')
    assert raised.value.args[0] == ('ZZZ', '1')
    with pytest.raises(deck_rules.UnknownCard):
        deck_rules.can_add(REAL['deck'], _cards(REAL), {'set': 'ZZZ', 'id': '1'}, 'main')


def test_unknown_zone_and_move_are_errors():
    cards = _cards(REAL)
    card = {'set': 'OGN', 'id': '17'}  # Defy, in the main deck
    with pytest.raises(ValueError, match='unknown zone: legend'):
        deck_rules.can_add(REAL['deck'], cards, card, 'legend')
    with pytest.raises(ValueError, match='unknown move'):
        deck_rules.can_move(REAL['deck'], cards, card, 'main', 'main')
    with pytest.raises(ValueError, match='unknown move'):
        deck_rules.can_move(REAL['deck'], cards, card, 'main', 'runes')
    with pytest.raises(ValueError, match='card not in sideboard'):
        deck_rules.can_move(REAL['deck'], cards, card, 'sideboard', 'main')


def test_rule_values_come_from_deck_rules(monkeypatch):
    """The engine reads DECK_RULES (the values `/meta/game` serves), never its own copy."""
    monkeypatch.setitem(game_domain.DECK_RULES, 'sideboard', 9)
    result = deck_rules.validate(REAL['deck'], _cards(REAL), {}, '1v1')
    assert result['issues'] == [{'code': 'sideboard_size',
                                 'params': {'have': 10, 'need': 9, 'missing': 0, 'over': 1}}]
    assert deck_rules.hard_limit_violations(REAL['deck'], _cards(REAL)) == [
        {'rule': 'sideboard', 'max': 9}]


def test_card_summary_shaped_cards_are_accepted():
    """F5-d passes `CardSummary` dicts: extra keys are ignored."""
    cards = {key: dict(card, set_id=card['set'], card_id=card['id'], price=None, bans={})
             for key, card in _cards(REAL).items()}
    assert deck_rules.validate(REAL['deck'], cards, {}, '2v2')['legal'] is True
