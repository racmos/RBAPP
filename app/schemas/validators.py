"""
Pydantic schemas for request validation.
"""
from datetime import date
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


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
    
    @field_validator('rbcol_foil')
    @classmethod
    def validate_foil(cls, v: str) -> str:
        if v not in ('Y', 'N'):
            return 'N'
        return v


class CollectionUpdateQuantity(BaseModel):
    """Schema for updating collection quantity."""
    rbcol_rbset_id: str = Field(..., min_length=1)
    rbcol_rbcar_id: str = Field(..., min_length=1)
    rbcol_foil: str = Field(..., max_length=1)
    quantity: int = Field(..., ge=0, le=9999, description="New quantity (0 to remove)")


# ============== Profile Schemas ==============

class ProfileUpdate(BaseModel):
    """Schema for updating profile."""
    email: Optional[str] = Field(None, max_length=120)
    password: Optional[str] = Field(None, min_length=6, max_length=128)
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if '@' not in v:
                raise ValueError('Invalid email format')
        return v


# ============== Price Schemas ==============

class PriceGenerate(BaseModel):
    """Schema for price generation request."""
    sets: Optional[List[str]] = Field(default_factory=list, description="List of set IDs to include")


# ============== Deck Schemas ==============

class DeckCard(BaseModel):
    """Schema for a single card in deck."""
    set: str = Field(..., description="Set ID")
    id: str = Field(..., description="Card ID")
    qty: int = Field(1, ge=1, le=99, description="Quantity")


class DeckCards(BaseModel):
    """Schema for deck cards structure."""
    main: List[DeckCard] = Field(default_factory=list, description="Main deck cards")
    sideboard: List[DeckCard] = Field(default_factory=[], description="Sideboard cards")


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
