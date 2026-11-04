"""Game enumerations (F2-R5): the single source of game enumerations.

Every layer that needs a game value (database CHECKs, request schemas, services,
the `/meta/game` payload) imports it from here, never repeats it. F2-a starts
with the game modes; F2-b adds domains, types and rarities; F5 adds the deck
rule values.
"""
# Game modes, in display order. Bans are per mode (product.md → "Game rules").
GAME_MODES = ('1v1', '2v2')

# Card domains, in display order. Read from the dev database on 2026-10-26
# (GROUP BY rbcar_domain): every value below exists there, so the tuple is
# unchanged; multi-word rows ("Fury Chaos") are split by parse_domains.
DOMAINS = ('Fury', 'Calm', 'Mind', 'Body', 'Chaos', 'Order', 'Colorless')

# Card types: the last word of `rbcar_type`, in display order. Read from the
# dev database on 2026-10-26 (GROUP BY rbcar_type): every value below exists
# there ("Champion Unit" → Unit, "Token Battlefield" → Battlefield, …).
CARD_TYPES = ('Legend', 'Unit', 'Spell', 'Gear', 'Rune', 'Battlefield')

# Leading words of `rbcar_type` that name a supertype.
SUPERTYPES = ('Champion', 'Signature', 'Token', 'Basic')

# Card rarities, lowest first. Read from the dev database on 2026-10-26
# (GROUP BY rbcar_rarity): every value below exists there.
RARITIES = ('Common', 'Uncommon', 'Rare', 'Epic', 'Showcase')

# Card conditions, best to worst (F3-b, D-F3-4).
CONDITIONS = ('MT', 'NM', 'EX', 'GD', 'LP', 'PL', 'PO')

# Card languages offered by the collection (F3-b, D-F3-4); the data may hold others.
LANGUAGES = ('English', 'French', 'German', 'Spanish', 'Italian', 'Simplified Chinese',
             'Japanese', 'Portuguese', 'Russian', 'Korean', 'Traditional Chinese')

# Deck rule values (F5-R1, product.md → "Game rules"): the engine
# (`app/services/deck_rules.py`) and `/meta/game` (`rules.deck`) read them here.
DECK_RULES = {
    'main_size': 39,             # main-deck cards, the chosen champion apart
    'total_with_champion': 40,   # main deck + chosen champion
    'runes': 12,                 # exactly, only of the legend's domains
    'battlefields': 3,           # distinct, not counted in the deck
    'sideboard': 10,             # at most
    'copies_max': 3,             # per name across main + sideboard + workbench + champion
    'workbench_max': 100,        # distinct names
}
