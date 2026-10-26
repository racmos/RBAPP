"""F2-b S1: game enumerations from `app/schemas/game_domain.py`.

The value sets were read from the dev database on 2026-10-26
(`SELECT rbcar_domain|rbcar_type|rbcar_rarity, count(*) ... GROUP BY 1`):
every draft value exists there, so the tuples below are unchanged.
"""
from app.schemas import game_domain


def test_domains_in_rank_order():
    assert game_domain.DOMAINS == (
        'Fury', 'Calm', 'Mind', 'Body', 'Chaos', 'Order', 'Colorless',
    )


def test_card_types_in_rank_order():
    assert game_domain.CARD_TYPES == (
        'Legend', 'Unit', 'Spell', 'Gear', 'Rune', 'Battlefield',
    )


def test_supertypes():
    assert game_domain.SUPERTYPES == ('Champion', 'Signature', 'Token', 'Basic')


def test_rarities_lowest_first():
    assert game_domain.RARITIES == ('Common', 'Uncommon', 'Rare', 'Epic', 'Showcase')
