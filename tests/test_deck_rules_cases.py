"""F5-a S2-S12 (F5-R3): every shared case of `tests/fixtures/deck_rules_cases.json` runs
against the Python engine (`app/services/deck_rules.py`). The TypeScript port (F5-b) runs
the same file; the cases are the contract between the two.

File shape: `{"catalog": [card], "cases": [case]}`. A card is `{set, id, name, type,
supertype, domains, tags}` (the `CardSummary` fields the rules read). A case is `{id,
description, op, mode?, deck, catalog, bans?, args, expected}`: `catalog` lists the
`"<set>-<id>"` keys of the cards the engine receives, in that order (auto_runes picks the
first rune of a colour in catalog order).
"""
import json
from pathlib import Path

import pytest

from app.schemas.game_domain import GAME_MODES
from app.services import deck_rules

CASES_PATH = Path(__file__).parent / 'fixtures' / 'deck_rules_cases.json'


def _reject_constant(name):
    raise ValueError(f'not plain JSON: {name}')


DATA = json.loads(CASES_PATH.read_text(encoding='utf-8'), parse_constant=_reject_constant)
CATALOG = {f"{card['set']}-{card['id']}": card for card in DATA['catalog']}
CASES = DATA['cases']

OPS = ('validate', 'can_add', 'can_move', 'auto_runes', 'apply_legend', 'apply_champion',
       'deck_domains', 'hard_limits', 'sort_names')


def _cards(case):
    return {(CATALOG[key]['set'], CATALOG[key]['id']): CATALOG[key] for key in case['catalog']}


def _run(case):
    deck, cards, args = case['deck'], _cards(case), case['args']
    op = case['op']
    if op == 'validate':
        return deck_rules.validate(deck, cards, case['bans'], case['mode'])
    if op == 'can_add':
        return deck_rules.can_add(deck, cards, args['card'], args['zone'])
    if op == 'can_move':
        return deck_rules.can_move(deck, cards, args['card'], args['from'], args['to'])
    if op == 'auto_runes':
        return deck_rules.auto_runes(deck, cards)
    if op == 'apply_legend':
        return deck_rules.apply_legend(deck, cards, args['legend'])
    if op == 'apply_champion':
        return deck_rules.apply_champion(deck, cards, args['champion'])
    if op == 'deck_domains':
        return deck_rules.deck_domains(deck, cards)
    if op == 'hard_limits':
        return deck_rules.hard_limit_violations(deck, cards)
    if op == 'sort_names':
        return deck_rules.sort_names(args['names'])
    raise AssertionError(f'unknown op {op}')


@pytest.mark.parametrize('case', CASES, ids=[case['id'] for case in CASES])
def test_shared_case(case):
    assert _run(case) == case['expected']


# --- the file itself -------------------------------------------------------------------

def test_cases_are_well_formed():
    ids = [case['id'] for case in CASES]
    assert len(ids) == len(set(ids))
    for case in CASES:
        assert set(case) <= {'id', 'description', 'op', 'mode', 'deck', 'catalog', 'bans',
                             'args', 'expected'}, case['id']
        assert case['op'] in OPS, case['id']
        assert case['description'].strip(), case['id']
        assert all(key in CATALOG for key in case['catalog']), case['id']
        if case['op'] == 'validate':
            assert case['mode'] in GAME_MODES and isinstance(case['bans'], dict), case['id']
        if case['op'] != 'sort_names':
            assert set(case['deck']) == {'v', 'legend', 'champion', 'main', 'runes',
                                         'battlefields', 'sideboard', 'workbench'}, case['id']


def test_every_op_has_cases():
    assert {case['op'] for case in CASES} == set(OPS)


def test_every_issue_code_positive_and_negative():
    """Each issue code is expected at least once, and the real deck is legal (no code)."""
    seen = {issue['code'] for case in CASES if case['op'] == 'validate'
            for issue in case['expected']['issues']}
    assert seen == set(deck_rules.ISSUE_CODES)
    legal = [case for case in CASES if case['op'] == 'validate' and case['expected']['legal']]
    assert any(case['id'] == 'validate-real-deck-legal-1v1' for case in legal)


def test_every_hard_rule_at_its_boundary():
    seen = {item['rule'] for case in CASES if case['op'] == 'hard_limits'
            for item in case['expected']}
    assert seen == set(deck_rules.HARD_RULES)
    empty = [case for case in CASES if case['op'] == 'hard_limits' and not case['expected']]
    assert len(empty) >= len(deck_rules.HARD_RULES)
