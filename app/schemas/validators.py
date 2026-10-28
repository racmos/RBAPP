"""
Pydantic schemas for request validation.
"""
import re
from datetime import date
from typing import Annotated, Literal, Optional, List

from pydantic import (BaseModel, Field, StrictBool, StrictInt, ValidationError, field_validator,
                      model_validator)
from pydantic_core import PydanticCustomError

from app.schemas.prefs_domain import (ACCENTS, BG_INTENSITY_MAX, BG_INTENSITY_MIN,
                                      COLLECTION_VIEWS, DENSITIES, LANGS)

# One rule for every way of choosing a password: profile update, CLI, registration.
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


# ============== Ban Schemas ==============

class BanListQuery(BaseModel, extra='ignore'):
    """GET /bans query parameters (F2-c S1)."""
    mode: Optional[Literal['1v1', '2v2']] = None

    @field_validator('mode', mode='before')
    @classmethod
    def _mode_literal(cls, v):
        if v is None or v == '':
            return None
        if v not in ('1v1', '2v2'):
            raise PydanticCustomError('literal_error', 'mode must be 1v1 or 2v2')
        return v


# ============== Card List Query ==============

ShortStr = Annotated[str, Field(max_length=50)]


class CardListQuery(BaseModel, extra='ignore'):
    """GET /cards query parameters (F2-c S2)."""
    q: Optional[str] = Field(None, max_length=100)
    text: Optional[str] = Field(None, max_length=100)
    set: List[ShortStr] = Field(default_factory=list)
    domain: List[ShortStr] = Field(default_factory=list)
    type: List[ShortStr] = Field(default_factory=list)
    supertype: List[ShortStr] = Field(default_factory=list)
    exclude_supertype: List[ShortStr] = Field(default_factory=list)
    rarity: List[ShortStr] = Field(default_factory=list)
    tag: List[ShortStr] = Field(default_factory=list)
    domain_match: Literal['any', 'all', 'subset'] = 'any'
    energy_min: Optional[int] = Field(None, ge=0, le=99)
    energy_max: Optional[int] = Field(None, ge=0, le=99)
    power_min: Optional[int] = Field(None, ge=0, le=99)
    power_max: Optional[int] = Field(None, ge=0, le=99)
    might_min: Optional[int] = Field(None, ge=0, le=99)
    might_max: Optional[int] = Field(None, ge=0, le=99)
    price_min: Optional[float] = Field(None, ge=0, le=100000)
    price_max: Optional[float] = Field(None, ge=0, le=100000)
    owned: Literal['any', 'owned', 'missing'] = 'any'
    banned_in: Optional[Literal['1v1', '2v2', 'any']] = None
    base_only: bool = False
    sort: Literal['number', 'name', 'price', 'trend_7d', 'trend_30d',
                  'rarity', 'energy', 'power', 'might'] = 'number'
    dir: Literal['asc', 'desc'] = 'asc'
    page: int = Field(default=1, ge=1, le=10000)
    per_page: int = Field(default=48, ge=1, le=192)

    @field_validator('set', 'domain', 'type', 'supertype', 'exclude_supertype',
                     'rarity', 'tag', mode='after')
    @classmethod
    def _limit_repeated(cls, v):
        if len(v) > 50:
            raise PydanticCustomError(
                'too_long', 'at most 50 values', {'max_length': 50})
        return v


class CollectionListQuery(BaseModel, extra='ignore'):
    """GET /collection query parameters (F3-b S1)."""
    q: Optional[str] = Field(None, max_length=100)
    set: List[ShortStr] = Field(default_factory=list)
    domain: List[ShortStr] = Field(default_factory=list)
    type: List[ShortStr] = Field(default_factory=list)
    rarity: List[ShortStr] = Field(default_factory=list)
    condition: List[ShortStr] = Field(default_factory=list)
    language: List[ShortStr] = Field(default_factory=list)
    foil: Literal['any', 'foil', 'nonfoil'] = 'any'
    selling: Literal['any', 'yes', 'no'] = 'any'
    has_purchase: Literal['any', 'yes', 'no'] = 'any'
    sort: Literal['number', 'name', 'price', 'qty', 'value', 'pl', 'trend_7d', 'updated',
                  'rarity'] = 'number'
    dir: Literal['asc', 'desc'] = 'asc'
    page: int = Field(default=1, ge=1, le=10000)
    per_page: int = Field(default=50, ge=25, le=200)

    @field_validator('set', 'domain', 'type', 'rarity', 'condition', 'language', mode='after')
    @classmethod
    def _limit_repeated(cls, v):
        if len(v) > 50:
            raise PydanticCustomError(
                'too_long', 'at most 50 values', {'max_length': 50})
        return v


# ============== Card Prices Query ==============


class CardPricesQuery(BaseModel, extra='ignore'):
    """GET /cards/<set>/<id>/prices query parameters (F2-d S8)."""
    range: Literal['30d', '90d', '1y', 'all'] = '90d'


# ============== Set Schemas ==============

class SetCreate(BaseModel):
    """Schema for creating a new set."""
    rbset_id: str = Field(..., min_length=1, max_length=50, description="Unique set identifier")
    rbset_name: str = Field(..., min_length=1, max_length=200, description="Set name")
    rbset_ncard: Optional[int] = Field(None, ge=0, le=10000, description="Number of cards in set")
    rbset_outdat: Optional[date] = Field(None, description="Set release date")
    
    @field_validator('rbset_id', 'rbset_name')
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        """Strip leading/trailing whitespace."""
        return v.strip()


class SetUpdate(BaseModel):
    """Schema for updating a set."""
    rbset_name: Optional[str] = Field(None, min_length=1, max_length=200)
    rbset_ncard: Optional[int] = Field(None, ge=0, le=10000)
    rbset_outdat: Optional[date] = None


# ============== Card Schemas ==============

class CardCreate(BaseModel):
    """Schema for creating a new card."""
    rbcar_rbset_id: str = Field(..., min_length=1, description="Set ID")
    rbcar_id: str = Field(..., min_length=1, max_length=50, description="Card ID within set")
    rbcar_name: str = Field(..., min_length=1, max_length=200, description="Card name")
    rbcar_domain: Optional[str] = Field(None, max_length=100)
    rbcar_type: Optional[str] = Field(None, max_length=100)
    rbcar_tags: Optional[str] = Field(None, max_length=500)
    rbcar_energy: Optional[int] = Field(None, ge=-99, le=99)
    rbcar_power: Optional[int] = Field(None, ge=-99, le=999)
    rbcar_might: Optional[int] = Field(None, ge=-99, le=999)
    rbcar_ability: Optional[str] = Field(None, max_length=2000)
    rbcar_rarity: Optional[str] = Field(None, max_length=50)
    rbcar_artist: Optional[str] = Field(None, max_length=200)
    rbcar_banned: Optional[str] = Field('N', max_length=1)
    image_url: Optional[str] = Field(None, max_length=500)
    image: Optional[str] = Field(None, max_length=500)
    
    @field_validator('rbcar_id', 'rbcar_name')
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()
    
    @field_validator('rbcar_banned')
    @classmethod
    def validate_banned(cls, v: str) -> str:
        if v not in ('Y', 'N'):
            return 'N'
        return v


class CardUpdate(BaseModel):
    """Schema for updating a card."""
    rbcar_name: Optional[str] = Field(None, min_length=1, max_length=200)
    rbcar_domain: Optional[str] = None
    rbcar_type: Optional[str] = None
    rbcar_tags: Optional[str] = None
    rbcar_energy: Optional[int] = Field(None, ge=-99, le=99)
    rbcar_power: Optional[int] = Field(None, ge=-99, le=999)
    rbcar_might: Optional[int] = Field(None, ge=-99, le=999)
    rbcar_ability: Optional[str] = None
    rbcar_rarity: Optional[str] = None
    rbcar_artist: Optional[str] = None
    rbcar_banned: Optional[str] = Field(None, max_length=1)
    image_url: Optional[str] = None
    image: Optional[str] = None


# ============== Collection Schemas ==============

class CollectionAdd(BaseModel):
    """Schema for adding to collection."""
    rbcol_rbset_id: str = Field(..., min_length=1, description="Set ID")
    rbcol_rbcar_id: str = Field(..., min_length=1, description="Card ID")
    rbcol_foil: Optional[str] = Field('N', max_length=1)
    rbcol_quantity: int = Field(1, ge=1, le=9999, description="Quantity to add")
    rbcol_selling: Optional[str] = Field('N', max_length=1)
    rbcol_sell_price: Optional[float] = Field(None, ge=0)
    rbcol_condition: Optional[str] = Field(None, max_length=8)
    rbcol_language: Optional[str] = Field(None, max_length=40)

    @field_validator('rbcol_foil')
    @classmethod
    def validate_foil(cls, v: Optional[str]) -> str:
        # Convención del proyecto: 'S' (foil) | 'N' (no foil). Cualquier otro valor
        # se normaliza a 'N'.
        return 'S' if v == 'S' else 'N'

    @field_validator('rbcol_selling')
    @classmethod
    def validate_selling(cls, v: Optional[str]) -> str:
        return 'Y' if v == 'Y' else 'N'

    @field_validator('rbcol_condition')
    @classmethod
    def validate_condition(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        allowed = {'MT', 'NM', 'EX', 'GD', 'LP', 'PL', 'PO'}
        if v not in allowed:
            raise ValueError(f'Condition must be one of {sorted(allowed)}')
        return v

    @field_validator('rbcol_language')
    @classmethod
    def validate_language(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v or None


class CollectionUpdateQuantity(BaseModel):
    """Schema for updating collection quantity. Identifica la fila por rbcol_id."""
    rbcol_id: int = Field(..., ge=1)
    quantity: int = Field(..., ge=0, le=9999, description="New quantity (0 to remove)")


class CollectionDelete(BaseModel):
    """Schema for deleting a collection entry."""
    rbcol_id: int = Field(..., ge=1)


class CollectionUpdateSelling(BaseModel):
    """Schema for updating selling status."""
    rbcol_id: int = Field(..., ge=1)
    rbcol_selling: str = Field(..., max_length=1)

    @field_validator('rbcol_selling')
    @classmethod
    def validate_selling(cls, v: str) -> str:
        if v not in ('Y', 'N'):
            raise ValueError('Must be Y or N')
        return v


class CollectionUpdatePlayset(BaseModel):
    """Schema for updating playset value."""
    rbcol_id: int = Field(..., ge=1)
    rbcol_playset: Optional[int] = Field(None)

    @field_validator('rbcol_playset')
    @classmethod
    def validate_playset(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v not in (1, 2, 3):
            raise ValueError('Must be 1, 2, or 3')
        return v


class CollectionUpdateSellPrice(BaseModel):
    """Schema for updating sell price."""
    rbcol_id: int = Field(..., ge=1)
    rbcol_sell_price: Optional[float] = Field(None, ge=0)


class CollectionUpdateCondition(BaseModel):
    """Schema for updating card condition."""
    rbcol_id: int = Field(..., ge=1)
    rbcol_condition: Optional[str] = Field(None, max_length=8)

    @field_validator('rbcol_condition')
    @classmethod
    def validate_condition(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == '':
            return None
        allowed = {'MT', 'NM', 'EX', 'GD', 'LP', 'PL', 'PO'}
        if v not in allowed:
            raise ValueError(f'Condition must be one of {sorted(allowed)}')
        return v


class CollectionUpdateLanguage(BaseModel):
    """Schema for updating card language."""
    rbcol_id: int = Field(..., ge=1)
    rbcol_language: Optional[str] = Field(None, max_length=40)

    @field_validator('rbcol_language')
    @classmethod
    def normalize_language(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v or None


class CollectionExport(BaseModel):
    """Schema for CSV export filter."""
    rbset_id: str = Field(..., min_length=1, description="Expansion/Set ID (required)")
    rarity: str = Field(..., min_length=1, description="Card rarity (required)")


QUANTITY_MIN, QUANTITY_MAX = 1, 9999


class CollectionImport(BaseModel):
    """Body of POST /collection/import_csv: `{"csv_data": "<lines>"}` (QTY-4)."""
    csv_data: str


class CollectionImportRow(BaseModel):
    """One `set;card;foil;quantity` line of the CSV import (QTY-4).

    Use `CollectionImportRow.from_line(text)`: it raises ValueError with a short
    human reason, which the importer reports per line. Whether the card exists
    is checked by the route (it needs the database)."""
    rbset_id: str = Field(..., min_length=1)
    rbcar_id: str = Field(..., min_length=1)
    rbcol_foil: str
    rbcol_quantity: int

    @field_validator('rbset_id', 'rbcar_id', mode='before')
    @classmethod
    def required_text(cls, v):
        if not isinstance(v, str) or not v.strip():
            raise ValueError('set and card are required')
        return v.strip()

    @field_validator('rbcol_foil', mode='before')
    @classmethod
    def foil_is_n_or_s(cls, v):
        if v not in ('N', 'S'):
            raise ValueError("foil must be 'N' or 'S'")
        return v

    @field_validator('rbcol_quantity', mode='before')
    @classmethod
    def quantity_in_range(cls, v):
        # ASCII digits only (no sign, no decimals, no other scripts), then the range.
        if (not isinstance(v, str) or not re.fullmatch(r'[0-9]+', v)
                or not QUANTITY_MIN <= int(v) <= QUANTITY_MAX):
            raise ValueError(
                f'quantity must be a whole number between {QUANTITY_MIN} and {QUANTITY_MAX}')
        return int(v)

    @classmethod
    def from_line(cls, line: str) -> 'CollectionImportRow':
        parts = [part.strip() for part in line.split(';')]
        if len(parts) != 4:
            raise ValueError('expected 4 fields (set;card;foil;quantity)')
        try:
            return cls(rbset_id=parts[0], rbcar_id=parts[1],
                       rbcol_foil=parts[2], rbcol_quantity=parts[3])
        except ValidationError as exc:
            raise ValueError(str(exc.errors()[0]['ctx']['error'])) from None


# ============== Auth Schemas ==============

USERNAME_PATTERN = re.compile(r'[A-Za-z0-9_.-]{3,32}')
EMAIL_MAX_LENGTH = 120
_EMAIL_PATTERN = re.compile(r'[^@\s]+@[^@\s]+\.[^@\s]+')


class LoginRequest(BaseModel):
    """Login input (LOGIN-9): only non-empty. No username pattern, so legacy names such as
    'Old User (1)' keep working; the upper bounds only stop absurd inputs."""
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=1024)
    # API only (API-5): the SPA sends true by default. StrictBool refuses "yes" and 1.
    # The Jinja form has no such field and drops it before validating.
    remember: StrictBool = False


class RegisterRequest(BaseModel):
    """Register input (LOGIN-9), shared by the Jinja form and the API. Extra fields (for
    example `is_admin`) are ignored by Pydantic and never reach the model."""
    username: str = Field(...)
    email: str = Field(...)
    password: str = Field(..., min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not USERNAME_PATTERN.fullmatch(v):
            raise PydanticCustomError(
                'invalid_format', 'Username must be 3-32 characters: letters, digits, ".", "_" or "-"')
        return v

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip()
        if len(v) > EMAIL_MAX_LENGTH:
            raise PydanticCustomError(
                'string_too_long', 'Email must have at most {max_length} characters',
                {'max_length': EMAIL_MAX_LENGTH})
        if not _EMAIL_PATTERN.fullmatch(v):
            raise PydanticCustomError('invalid_format', 'Invalid email format')
        return v


# ============== Preferences Schemas ==============

def _one_of(values: tuple[str, ...]):
    """`Literal[...]` over a domain tuple (PREF-2)."""
    return Literal[values]          # a tuple subscript means Literal['a', 'b']


class PrefsUpdate(BaseModel):
    """PATCH /me/prefs body (PREF-4, D7, R12).

    Every field is optional and `None` means Auto. The caller applies only
    `model_fields_set`: absent = unchanged, `null` = reset. Unknown fields are
    ignored (never stored), so an older server tolerates a newer client.
    `bg_intensity` is a strict integer: `true`, `50.0` and `"50"` are refused.
    """
    lang: Optional[_one_of(LANGS)] = None
    density: Optional[_one_of(DENSITIES)] = None
    accent: Optional[_one_of(ACCENTS)] = None
    bg_intensity: Optional[Annotated[StrictInt, Field(ge=BG_INTENSITY_MIN,
                                                      le=BG_INTENSITY_MAX)]] = None
    collection_view: Optional[_one_of(COLLECTION_VIEWS)] = None


# ============== Profile Schemas ==============

class ProfileUpdate(BaseModel):
    """Schema for updating profile.

    Changing the password needs the current one (PROF-2); an email-only update
    does not.
    """
    email: Optional[str] = Field(None, max_length=120)
    password: Optional[str] = Field(None, min_length=PASSWORD_MIN_LENGTH,
                                    max_length=PASSWORD_MAX_LENGTH)
    # Generous bound: it only has to fit whatever password the account already has.
    current_password: Optional[str] = Field(None, max_length=1024)

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if '@' not in v:
                raise ValueError('Invalid email format')
        return v

    @model_validator(mode='after')
    def current_password_goes_with_a_new_password(self):
        if self.password is not None and not self.current_password:
            raise ValueError('current_password is required to change the password')
        return self


# ============== Price Schemas ==============

class PriceGenerate(BaseModel):
    """Schema for price generation request."""
    sets: Optional[List[str]] = Field(default_factory=list, description="List of set IDs to include")


# ============== Riot Extract Schemas ==============

class RiotExtract(BaseModel):
    """Schema for Riot card extraction request."""
    sets: Optional[List[str]] = Field(default_factory=list, description="List of set IDs to extract (empty = all)")


# ============== Deck Schemas ==============

class DeckCard(BaseModel):
    """Schema for a single card in deck."""
    set: str = Field(..., description="Set ID")
    id: str = Field(..., description="Card ID")
    qty: int = Field(1, ge=1, le=99, description="Quantity")


class DeckCards(BaseModel):
    """Schema for deck cards structure."""
    main: List[DeckCard] = Field(default_factory=list, description="Main deck cards")
    sideboard: List[DeckCard] = Field(default_factory=list, description="Sideboard cards")


class DeckSave(BaseModel):
    """Schema for saving a deck."""
    rbdck_name: str = Field(..., min_length=1, max_length=200, description="Deck name")
    rbdck_description: Optional[str] = Field(None, max_length=1000)
    rbdck_mode: Optional[str] = Field('1v1', max_length=50)
    rbdck_format: Optional[str] = Field('Standard', max_length=50)
    rbdck_max_set: Optional[str] = Field(None, max_length=100)
    rbdck_cards: Optional[DeckCards] = None
    
    @field_validator('rbdck_name')
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


# ============== Cardmarket Schemas ==============

class CardmarketLoad(BaseModel):
    """Schema for Cardmarket data load request."""
    singles_url: Optional[str] = Field(None, description="Override URL for products_singles JSON")
    nonsingles_url: Optional[str] = Field(None, description="Override URL for products_nonsingles JSON")
    price_guide_url: Optional[str] = Field(None, description="Override URL for price_guide JSON")

    @field_validator('singles_url', 'nonsingles_url', 'price_guide_url')
    @classmethod
    def validate_allowed_url(cls, v: Optional[str]) -> Optional[str]:
        """ACL-7: an override must be https on an allow-listed Cardmarket host.
        Empty means "no override"."""
        if not v:
            return None
        from flask import current_app
        from app.services.cardmarket_loader import validate_override_url
        return validate_override_url(v, current_app.config['CARDMARKET_ALLOWED_HOSTS'])


class IgnoredAdd(BaseModel):
    """Schema for adding a product to the ignored list."""
    id_product: int = Field(..., ge=1, description="Cardmarket idProduct")
    name: str = Field(..., min_length=1, description="Product name")


class IgnoredRestore(BaseModel):
    """Schema for removing a product from the ignored list."""
    id_product: int = Field(..., ge=1, description="Cardmarket idProduct")
    name: str = Field(..., min_length=1, description="Product name")


class AutoMatchPairing(BaseModel):
    """Schema for a single pairing in the selective auto-match apply."""
    id_product: int = Field(..., ge=1, description="Cardmarket idProduct")
    rbset_id: str = Field(..., min_length=1, description="Internal set ID")
    rbcar_id: str = Field(..., min_length=1, description="Internal card ID")
    foil: Optional[str] = Field(None, description="'N' | 'S' | null")

    @field_validator('foil')
    @classmethod
    def validate_foil(cls, v: Optional[str]) -> Optional[str]:
        if v in (None, '', 'null'):
            return None
        if v not in ('N', 'S'):
            raise ValueError("foil must be 'N', 'S', or null")
        return v


class AutoMatchApply(BaseModel):
    """Schema for the selective auto-match apply request."""
    pairings: List[AutoMatchPairing] = Field(..., min_length=1, description="List of pairings to apply")
