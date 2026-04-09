"""
Main routes module - registers all domain blueprints.
"""
from flask import Blueprint, render_template
from flask_login import login_required

main_bp = Blueprint('main', __name__, url_prefix='/riftbound')


@main_bp.route('/')
@login_required
def dashboard():
    """Main dashboard page."""
    return render_template('dashboard.html')


# Register domain blueprints
from app.routes.domains import (
    sets_bp,
    cards_bp,
    collection_bp,
    deck_bp,
    price_bp,
    profile_bp,
)

__all__ = [
    'main_bp',
    'sets_bp',
    'cards_bp',
    'collection_bp',
    'deck_bp',
    'price_bp',
    'profile_bp',
]
