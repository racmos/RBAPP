"""Card bans per game mode (F2-a): name normalization, reads and writes.

A ban applies to a card NAME in one mode (`app.schemas.game_domain.GAME_MODES`)
and so to every printing of that name. Names are matched with `name_key` only
(F2-R3). Migration 0009 keeps a frozen copy of `name_key`; a test keeps the two
equal.
"""


def name_key(name: str) -> str:
    """The normalized form of a card name: typographic apostrophes become `'`,
    case is folded and runs of whitespace become one space (trimmed)."""
    return ' '.join(name.replace('\u2019', "'").replace('\u2018', "'").casefold().split())
