"""Game enumerations (F2-R5): the single source of game enumerations.

Every layer that needs a game value (database CHECKs, request schemas, services,
the `/meta/game` payload) imports it from here, never repeats it. F2-a starts
with the game modes; F2-b adds domains, types and rarities; F5 adds the deck
rule values.
"""
# Game modes, in display order. Bans are per mode (product.md → "Game rules").
GAME_MODES = ('1v1', '2v2')
