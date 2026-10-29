"""Admin API schemas (F13-b): sets and cards writes, card list query; products (F14-d).

Bodies use `validate_json` (extra fields are forbidden everywhere); the card
list query uses `validate_query` with the same error body.
"""
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

from app.models.cardmarket import PRODUCT_KINDS

STRIPPED = ConfigDict(extra='forbid', str_strip_whitespace=True)


def _empty_to_none(value):
    """Blank strings (even whitespace-only) become None before any other check."""
    if isinstance(value, str) and value.strip() == '':
        return None
    return value


class AdminSetCreate(BaseModel):
    """POST /admin/sets body (S3). `id` is upper-cased."""

    model_config = STRIPPED

    id: str = Field(min_length=2, max_length=10, pattern=r'^[A-Za-z0-9]{2,10}$')
    name: str = Field(min_length=1, max_length=100)
    release_date: date
    declared_count: Optional[int] = Field(default=None, ge=0, le=999)

    @field_validator('id', mode='after')
    @classmethod
    def _upper_id(cls, value: str) -> str:
        return value.upper()


class AdminSetPatch(BaseModel):
    """PATCH /admin/sets/<id> body (S4): any subset; explicit null date is refused in the view."""

    model_config = STRIPPED

    id: Optional[str] = Field(default=None, min_length=2, max_length=10,
                              pattern=r'^[A-Za-z0-9]{2,10}$')
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    release_date: Optional[date] = None
    declared_count: Optional[int] = Field(default=None, ge=0, le=999)

    @field_validator('id', mode='after')
    @classmethod
    def _upper_id(cls, value):
        return value.upper() if value is not None else None


class AdminCardBase(BaseModel):
    """Shared card fields (S7-S8): trimmed, blank becomes null, numbers 0-99."""

    model_config = STRIPPED

    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    domain: Optional[str] = Field(default=None, max_length=100)
    type: Optional[str] = Field(default=None, max_length=100)
    tags: Optional[str] = Field(default=None, max_length=500)
    energy: Optional[int] = Field(default=None, ge=0, le=99)
    power: Optional[int] = Field(default=None, ge=0, le=99)
    might: Optional[int] = Field(default=None, ge=0, le=99)
    ability: Optional[str] = Field(default=None, max_length=2000)
    rarity: Optional[str] = Field(default=None, max_length=50)
    artist: Optional[str] = Field(default=None, max_length=100)
    image: Optional[str] = Field(default=None, max_length=500)
    image_url: Optional[str] = Field(default=None, max_length=500)

    @field_validator('name', 'domain', 'type', 'tags', 'ability', 'rarity', 'artist',
                     'image', 'image_url', mode='before')
    @classmethod
    def _blank_is_null(cls, value):
        return _empty_to_none(value)


class AdminCardCreate(AdminCardBase):
    """POST /admin/cards body (S7)."""

    set_id: str = Field(min_length=1)
    card_id: str = Field(min_length=1, max_length=10, pattern=r'^[A-Za-z0-9]{1,10}$')
    name: str = Field(min_length=1, max_length=200)

    @field_validator('card_id', mode='after')
    @classmethod
    def _lower_card_id(cls, value: str) -> str:
        return value.lower()


class AdminCardPatch(AdminCardBase):
    """PATCH /admin/cards/<set>/<id> body (S8): no keys (`set_id`/`card_id` are unknown here)."""


class AdminRiotSyncBody(BaseModel):
    """POST /admin/riot/sync body (S1): codes are upper-cased, then checked."""

    model_config = ConfigDict(extra='forbid')

    sets: list[str] = Field(default_factory=list)

    @field_validator('sets', mode='before')
    @classmethod
    def _one_or_many(cls, value):
        if isinstance(value, str):
            return [value]
        return value

    @field_validator('sets', mode='after')
    @classmethod
    def _upper_codes(cls, value: list) -> list:
        return [code.strip().upper() for code in value if code.strip()]


class AdminChangesQuery(BaseModel):
    """GET /admin/riot/changes query (S3)."""

    model_config = ConfigDict(extra='forbid')

    status: str = 'pending'
    set: Optional[str] = None
    field: Optional[str] = None
    q: Optional[str] = None
    page: int = Field(default=1, ge=1)
    per_page: Literal[50, 100, 200] = 50

    @field_validator('status', mode='after')
    @classmethod
    def _known_status(cls, value: str) -> str:
        if value not in ('pending', 'approved', 'rejected', 'obsolete', 'all'):
            raise ValueError('status must be pending, approved, rejected, obsolete or all')
        return value

    @field_validator('page', 'per_page', mode='before')
    @classmethod
    def _to_int(cls, value):
        if isinstance(value, str) and value.lstrip('-').isdigit():
            return int(value)
        return value


class AdminJobsQuery(BaseModel):
    """GET /admin/jobs query (S2)."""

    model_config = ConfigDict(extra='forbid')

    kind: Optional[str] = None
    status: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=100)


class AdminBulkBody(BaseModel):
    """POST /admin/riot/changes/bulk body (S6)."""

    model_config = ConfigDict(extra='forbid')

    ids: list[int] = Field(min_length=1, max_length=500)
    action: Literal['approve', 'reject']


class AdminCardQuery(BaseModel):
    """GET /admin/cards query (S6). Repeatable params accept one value or many."""

    model_config = ConfigDict(extra='forbid')

    set: list[str] = Field(default_factory=list)
    rarity: list[str] = Field(default_factory=list)
    type: Optional[str] = None
    domain: Optional[str] = None
    missing_image: bool = False
    q: Optional[str] = None
    sort: Literal['number', 'name'] = 'number'
    dir: Literal['asc', 'desc'] = 'asc'
    page: int = Field(default=1, ge=1)
    per_page: Literal[50, 100, 200] = 50

    @field_validator('set', 'rarity', mode='before')
    @classmethod
    def _one_or_many(cls, value):
        if isinstance(value, str):
            return [value]
        return value

    @field_validator('page', 'per_page', mode='before')
    @classmethod
    def _to_int(cls, value):
        if isinstance(value, str) and value.lstrip('-').isdigit():
            return int(value)
        return value

    @field_validator('missing_image', mode='before')
    @classmethod
    def _to_bool(cls, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            if value.lower() == 'true':
                return True
            if value.lower() == 'false':
                return False
        return value


def _query_bool(value):
    """`true` / `false` (any case) of a query string; anything else is left to Pydantic."""
    if isinstance(value, str) and value.lower() in ('true', 'false'):
        return value.lower() == 'true'
    return value


class AdminProductQuery(BaseModel):
    """GET /admin/products query (F14-d S2). `kind` is repeatable."""

    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    q: Optional[str] = Field(default=None, max_length=100)
    kind: list[Literal[PRODUCT_KINDS]] = Field(default_factory=list)
    hidden: Literal['any', 'yes', 'no'] = 'any'
    listed: Literal['any', 'yes', 'no'] = 'any'
    no_set: bool = False
    no_image: bool = False
    sort: Literal['name', 'updated'] = 'name'
    dir: Literal['asc', 'desc'] = 'asc'
    page: int = Field(default=1, ge=1)
    per_page: Literal[50, 100, 200] = 50

    @field_validator('kind', mode='before')
    @classmethod
    def _one_or_many(cls, value):
        if isinstance(value, str):
            return [value]
        return value

    @field_validator('page', 'per_page', mode='before')
    @classmethod
    def _to_int(cls, value):
        if isinstance(value, str) and value.lstrip('-').isdigit():
            return int(value)
        return value

    @field_validator('no_set', 'no_image', mode='before')
    @classmethod
    def _to_bool(cls, value):
        return _query_bool(value)


class AdminProductPatch(BaseModel):
    """PATCH /admin/products/<id> body (F14-d S3): any of `hidden`, `kind`, `set_id`.

    A key that is absent is not touched (`model_fields_set`). `kind: null` unlocks
    the kind; `set_id` is a set id, null or `"auto"` (checked in the view).
    """

    model_config = ConfigDict(extra='forbid')

    hidden: Optional[StrictBool] = None
    kind: Optional[Literal[PRODUCT_KINDS]] = None
    set_id: Optional[str] = None

    @field_validator('hidden', mode='before')
    @classmethod
    def _hidden_not_null(cls, value):
        if value is None:
            raise ValueError('hidden must be true or false')
        return value
