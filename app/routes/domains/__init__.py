"""
Routes domain modules.
"""
from .sets import sets_bp
from .cards import cards_bp
from .collection import collection_bp
from .deck import deck_bp
from .price import price_bp
from .profile import profile_bp

__all__ = [
    'sets_bp',
    'cards_bp',
    'collection_bp',
    'deck_bp',
    'price_bp',
    'profile_bp',
]
