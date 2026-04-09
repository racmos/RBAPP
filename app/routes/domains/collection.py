"""
Collection routes module with Pydantic validation.
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import RbCollection, RbCard, RbSet
from app.schemas.validators import CollectionAdd, CollectionUpdateQuantity
from app.schemas.validation import validate_json
from datetime import datetime

collection_bp = Blueprint('collection', __name__, url_prefix='/riftbound/collection')


@collection_bp.route('')
@login_required
def collection():
    """List user's collection with pagination."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    query = db.session.query(RbCollection, RbCard).join(
        RbCard, (RbCollection.rbcol_rbset_id == RbCard.rbcar_rbset_id) & (RbCollection.rbcol_rbcar_id == RbCard.rbcar_id)
    ).filter(RbCollection.rbcol_user == current_user.username)
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    sets = RbSet.query.order_by(RbSet.rbset_id).all()
    
    return render_template('collection.html', 
                          collections_data=[{'collection': c, 'card': cd} for c, cd in pagination.items], 
                          pagination=pagination, 
                          sets=sets, 
                          get_page_url=lambda p: f'?page={p}')


@collection_bp.route('/add', methods=['POST'])
@login_required
@validate_json(CollectionAdd)
def add_collection():
    """Add card to collection."""
    data = request.validated_data
    
    card = RbCard.query.filter_by(rbcar_rbset_id=data.rbcol_rbset_id, rbcar_id=data.rbcol_rbcar_id).first()
    if not card:
        return jsonify({'success': False, 'message': 'Card does not exist'}), 400
    
    existing = RbCollection.query.filter_by(
        rbcol_rbset_id=data.rbcol_rbset_id, 
        rbcol_rbcar_id=data.rbcol_rbcar_id,
        rbcol_foil=data.rbcol_foil, 
        rbcol_user=current_user.username
    ).first()
    
    if existing:
        existing.rbcol_quantity = str(int(existing.rbcol_quantity) + data.rbcol_quantity)
        existing.rbcol_chadat = datetime.utcnow()
    else:
        db.session.add(RbCollection(
            rbcol_rbset_id=data.rbcol_rbset_id, 
            rbcol_rbcar_id=data.rbcol_rbcar_id, 
            rbcol_foil=data.rbcol_foil, 
            rbcol_quantity=data.rbcol_quantity, 
            rbcol_chadat=datetime.utcnow(), 
            rbcol_user=current_user.username
        ))
    db.session.commit()
    return jsonify({'success': True})


@collection_bp.route('/update_quantity', methods=['POST'])
@login_required
@validate_json(CollectionUpdateQuantity)
def update_collection_quantity():
    """Update quantity of a card in collection."""
    data = request.validated_data
    
    collection = RbCollection.query.filter_by(
        rbcol_rbset_id=data.rbcol_rbset_id, 
        rbcol_rbcar_id=data.rbcol_rbcar_id,
        rbcol_foil=data.rbcol_foil, 
        rbcol_user=current_user.username
    ).first_or_404()
    
    if data.quantity == 0:
        db.session.delete(collection)
    else:
        collection.rbcol_quantity = str(data.quantity)
        collection.rbcol_chadat = datetime.utcnow()
    
    db.session.commit()
    return jsonify({'success': True})


@collection_bp.route('/import_csv', methods=['POST'])
@login_required
def import_collection_csv():
    """Import collection from CSV."""
    data = request.get_json()
    for line in data.get('csv_data', '').strip().split('\n'):
        parts = line.split(';')
        if len(parts) != 4:
            continue
        rbset_id, rbcar_id, rbcol_foil, rbcol_quantity = parts
        
        existing = RbCollection.query.filter_by(
            rbcol_rbset_id=rbset_id, 
            rbcol_rbcar_id=rbcar_id, 
            rbcol_foil=rbcol_foil, 
            rbcol_user=current_user.username
        ).first()
        
        if existing:
            existing.rbcol_quantity = rbcol_quantity
            existing.rbcol_chadat = datetime.utcnow()
        else:
            db.session.add(RbCollection(
                rbcol_rbset_id=rbset_id, 
                rbcar_id=rbcar_id, 
                rbcol_foil=rbcol_foil, 
                rbcol_quantity=rbcol_quantity, 
                rbcol_chadat=datetime.utcnow(), 
                rbcol_user=current_user.username
            ))
    db.session.commit()
    return jsonify({'success': True})
