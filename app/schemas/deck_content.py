"""Content v2 of a deck version (F5-R6, F5-c): the shape of `rbdeckversions.rbdkv_content`.

`{"v": 2, "legend": ref|null, "champion": ref|null, "main": [line], "runes": [line],
"battlefields": [ref], "sideboard": [line], "workbench": [line]}` with `ref = {set, id}` and
`line = {set, id, qty}`. Printings are kept (a ref names one printing). Only the shape is
checked here: sizes, copies, types and identity are the rules engine's
(`app/services/deck_rules.py`), so an incomplete or wrong deck is still valid content.
"""
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# `rbdeckheads.rbdkh_visibility` domain (model CHECK and later the decks API).
VISIBILITIES = ('private', 'public')


class CardRef(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    set: str = Field(..., min_length=1, max_length=64)
    id: str = Field(..., min_length=1, max_length=64)


class CardLine(CardRef):
    qty: int = Field(..., ge=1)


class DeckContentV2(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    v: Literal[2]
    legend: Optional[CardRef] = None
    champion: Optional[CardRef] = None
    main: list[CardLine] = Field(default_factory=list)
    runes: list[CardLine] = Field(default_factory=list)
    battlefields: list[CardRef] = Field(default_factory=list)
    sideboard: list[CardLine] = Field(default_factory=list)
    workbench: list[CardLine] = Field(default_factory=list)


def validate_content(data) -> dict:
    """`data` checked and returned as a plain dict with every key, in contract order;
    raises `pydantic.ValidationError` on a bad shape."""
    return DeckContentV2.model_validate(data).model_dump()


def empty_content() -> dict:
    return DeckContentV2(v=2).model_dump()
