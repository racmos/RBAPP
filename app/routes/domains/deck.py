"""
Deck routes module.
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required

deck_bp = Blueprint('deck', __name__, url_prefix='/riftbound/deck')


@deck_bp.route('')
@login_required
def deck():
    """List all decks."""
    return render_template('deck.html', sets=[])  # TODO: pass actual sets


@deck_bp.route('/view/<timestamp>')
@login_required
def view_deck(timestamp):
    """View specific deck."""
    return render_template('deck_view.html', timestamp=timestamp)


@deck_bp.route('/save', methods=['POST'])
@login_required
def save_deck():
    """Save new deck."""
    # TODO: Implement deck saving logic
    return jsonify({'success': True})
