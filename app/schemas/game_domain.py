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
