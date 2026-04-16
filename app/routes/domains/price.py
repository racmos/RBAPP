"""
Price routes module with Pydantic validation.
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from app import db
from app.models import RbSet, RbCard
from app.schemas.validators import PriceGenerate, RiotExtract
from app.schemas.validation import validate_json

price_bp = Blueprint('price', __name__, url_prefix='/riftbound/price')


@price_bp.route('')
@login_required
def price():
    """Price generation page."""
    return render_template('price.html', sets=RbSet.query.all())


@price_bp.route('/generate', methods=['POST'])
@login_required
@validate_json(PriceGenerate)
def generate_price():
    """Generate price CSV."""
    data = request.validated_data
    selected_sets = data.sets if data.sets else []
    
    # Build query with optional set filter using ORM
    query = db.session.query(RbSet.rbset_name, RbCard.rbcar_name, RbCard.rbcar_id).join(
        RbCard, RbCard.rbcar_rbset_id == RbSet.rbset_id
    )
    
    if selected_sets:
        query = query.filter(RbSet.rbset_id.in_(selected_sets))
    
    results = query.order_by(RbSet.rbset_name, RbCard.rbcar_id).all()
    
    csv_lines = [f"{set_name};{card_name};{card_id};N" for set_name, card_name, card_id in results]
    
    return jsonify({'success': True, 'csv': '\n'.join(csv_lines)})


@price_bp.route('/refresh-riot-sets', methods=['POST'])
@login_required
def refresh_riot_sets():
    """Fetch available sets from Riot card gallery."""
    from app.services.riot_scraper import refresh_riot_sets as _refresh
    try:
        result = _refresh()
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e), 'sets': []}), 500


@price_bp.route('/extract-riot-cards', methods=['POST'])
@login_required
@validate_json(RiotExtract)
def extract_riot_cards():
    """Scrape Riot gallery, extract cards + images, insert to DB."""
    from app.services.riot_scraper import extract_riot_cards as _extract
    data = request.validated_data
    filter_sets = data.sets if data.sets else []
    try:
        result = _extract(filter_sets=filter_sets if filter_sets else None)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'steps': [],
            'stats': {},
            'errors': [str(e)]
        }), 500
