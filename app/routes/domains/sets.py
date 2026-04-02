"""
Sets routes module with Pydantic validation.
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from app import db
from app.models import RbSet
from app.schemas.validators import SetCreate, SetUpdate
from app.schemas.validation import validate_json

sets_bp = Blueprint('sets', __name__, url_prefix='/riftbound/set')


@sets_bp.route('')
@login_required
def sets():
    """List all sets with search."""
    search_id = request.args.get('search_id', '')
    search_name = request.args.get('search_name', '')
    
    query = RbSet.query
    if search_id:
        query = query.filter(RbSet.rbset_id.ilike(f'%{search_id}%'))
    if search_name:
        query = query.filter(RbSet.rbset_name.ilike(f'%{search_name}%'))
    
    sets = query.all()
    return render_template('sets.html', sets=sets)


@sets_bp.route('/add', methods=['POST'])
@login_required
@validate_json(SetCreate)
def add_set():
    """Add a new set."""
    data = request.validated_data
    
    if RbSet.query.filter_by(rbset_id=data.rbset_id).first():
        return jsonify({'success': False, 'message': 'Set ID already exists'}), 400
    
    if RbSet.query.filter_by(rbset_name=data.rbset_name).first():
        return jsonify({'success': False, 'message': 'Set name already exists'}), 400
    
    new_set = RbSet(
        rbset_id=data.rbset_id,
        rbset_name=data.rbset_name,
        rbset_ncard=data.rbset_ncard,
        rbset_outdat=data.rbset_outdat
    )
    
    db.session.add(new_set)
    db.session.commit()
    
    return jsonify({'success': True})


@sets_bp.route('/update/<set_id>', methods=['POST'])
@login_required
@validate_json(SetUpdate)
def update_set(set_id):
    """Update an existing set."""
    data = request.validated_data
    rbset = RbSet.query.get_or_404(set_id)
    
    if data.rbset_name is not None:
        rbset.rbset_name = data.rbset_name
    if data.rbset_ncard is not None:
        rbset.rbset_ncard = data.rbset_ncard
    if data.rbset_outdat is not None:
        rbset.rbset_outdat = data.rbset_outdat
    
    db.session.commit()
    
    return jsonify({'success': True})
