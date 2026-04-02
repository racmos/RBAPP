"""
Price routes module with Pydantic validation.
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from app import db
from app.models import RbSet
from app.schemas.validators import PriceGenerate
from app.schemas.validation import validate_json
from sqlalchemy import text

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
    
    # Build query with optional set filter
    if selected_sets:
        query = text(
            "SELECT st.rbset_name || ';' || car.rbcar_name || ';' || car.rbcar_id || ';N' "
            "FROM riftbound.rbcards car "
            "JOIN riftbound.rbset st ON car.rbcar_rbset_id = st.rbset_id "
            "WHERE st.rbset_id IN :sets"
        )
        params = {'sets': tuple(selected_sets)}
    else:
        query = text(
            "SELECT st.rbset_name || ';' || car.rbcar_name || ';' || car.rbcar_id || ';N' "
            "FROM riftbound.rbcards car "
            "JOIN riftbound.rbset st ON car.rbcar_rbset_id = st.rbset_id"
        )
        params = {}
    
    result = db.session.execute(query, params)
    return jsonify({'success': True, 'csv': '\n'.join([row[0] for row in result])})
