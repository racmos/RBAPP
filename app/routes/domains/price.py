"""
Price routes module with Pydantic validation.
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from app import db
from app.models import RbSet, RbCard
from app.schemas.validators import PriceGenerate, CardmarketLoad, RiotExtract
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


@price_bp.route('/cardmarket-load', methods=['POST'])
@login_required
def cardmarket_load():
    """Load Cardmarket data tables (price guide + products)."""
    from app.services.cardmarket_loader import CardmarketLoader, CARDMARKET_URLS
    
    try:
        # Build URLs dict with optional overrides from request
        data = request.get_json(silent=True) or {}
        urls = dict(CARDMARKET_URLS)
        if data.get('singles_url'):
            urls['singles'] = data['singles_url']
        if data.get('nonsingles_url'):
            urls['nonsingles'] = data['nonsingles_url']
        if data.get('price_guide_url'):
            urls['price_guide'] = data['price_guide_url']
        
        loader = CardmarketLoader()
        result = loader.run(urls=urls)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'steps': [],
            'errors': [str(e)]
        }), 500


@price_bp.route('/cardmarket-unmatched')
@login_required
def cardmarket_unmatched():
    """Get products not yet mapped to internal cards."""
    from app.models.cardmarket import RbcmProduct, RbcmProductCardMap, RbcmPrice
    from sqlalchemy import func

    # Get latest date with products
    latest_date = db.session.query(func.max(RbcmProduct.rbprd_date)).scalar()
    if not latest_date:
        return jsonify({'success': True, 'unmatched': [], 'count': 0})

    # Get all product IDs that ARE mapped
    mapped_ids = db.session.query(RbcmProductCardMap.rbpcm_id_product).subquery()

    # Get products NOT in mapped_ids, ordered by name then id_product
    unmatched = RbcmProduct.query.filter(
        RbcmProduct.rbprd_date == latest_date,
        ~RbcmProduct.rbprd_id_product.in_(db.session.query(mapped_ids))
    ).order_by(RbcmProduct.rbprd_name, RbcmProduct.rbprd_id_product).all()

    # Get latest price date for low prices
    latest_price_date = db.session.query(func.max(RbcmPrice.rbprc_date)).scalar()

    # Build price lookup {id_product: low_price}
    price_map = {}
    if latest_price_date:
        prices = RbcmPrice.query.filter_by(rbprc_date=latest_price_date).all()
        price_map = {p.rbprc_id_product: float(p.rbprc_low) if p.rbprc_low is not None else None for p in prices}

    return jsonify({
        'success': True,
        'count': len(unmatched),
        'unmatched': [{
            'id_product': p.rbprd_id_product,
            'name': p.rbprd_name,
            'type': p.rbprd_type,
            'category': p.rbprd_category_name,
            'low_price': price_map.get(p.rbprd_id_product),
        } for p in unmatched]
    })


@price_bp.route('/cardmarket-search-cards')
@login_required
def cardmarket_search_cards():
    """Search internal cards by name for manual mapping."""
    q = request.args.get('q', '').strip()
    if len(q) < 3:
        return jsonify({'success': True, 'cards': []})

    cards = RbCard.query.filter(
        RbCard.rbcar_name.ilike(f'%{q}%')
    ).order_by(RbCard.rbcar_name).limit(20).all()

    return jsonify({
        'success': True,
        'cards': [{
            'rbset_id': c.rbcar_rbset_id,
            'rbcar_id': c.rbcar_id,
            'name': c.rbcar_name,
        } for c in cards]
    })


@price_bp.route('/cardmarket-map', methods=['POST'])
@login_required
def cardmarket_map():
    """Save a manual product-to-card mapping."""
    from app.models.cardmarket import RbcmProductCardMap

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400

    id_product = data.get('id_product')
    rbset_id = data.get('rbset_id')
    rbcar_id = data.get('rbcar_id')

    if not all([id_product, rbset_id, rbcar_id]):
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400

    # Check if mapping already exists
    existing = RbcmProductCardMap.query.filter_by(
        rbpcm_id_product=id_product
    ).first()

    if existing:
        existing.rbpcm_rbset_id = rbset_id
        existing.rbpcm_rbcar_id = rbcar_id
        existing.rbpcm_match_type = 'manual'
        existing.rbpcm_confidence = 1.0
    else:
        db.session.add(RbcmProductCardMap(
            rbpcm_id_product=id_product,
            rbpcm_rbset_id=rbset_id,
            rbpcm_rbcar_id=rbcar_id,
            rbpcm_match_type='manual',
            rbpcm_confidence=1.0,
        ))

    db.session.commit()
    return jsonify({'success': True, 'message': 'Mapping saved'})
