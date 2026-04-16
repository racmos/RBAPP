"""
Deck routes module.
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import RbDeck, RbSet
from app.schemas.validators import DeckSave
from app.schemas.validation import validate_json
from datetime import datetime


deck_bp = Blueprint('deck', __name__, url_prefix='/riftbound/deck')


@deck_bp.route('')
@login_required
def deck():
    """List all decks for current user."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    search_name = request.args.get('search_name', '')
    search_mode = request.args.get('search_mode', '')
    search_format = request.args.get('search_format', '')
    
    query = RbDeck.query.filter_by(rbdck_user=current_user.username)
    
    if search_name:
        query = query.filter(RbDeck.rbdck_name.ilike(f'%{search_name}%'))
    if search_mode:
        query = query.filter(RbDeck.rbdck_mode == search_mode)
    if search_format:
        query = query.filter(RbDeck.rbdck_format == search_format)
    
    # Ordenar por nombre y snapshot (más reciente primero)
    try:
        query = query.order_by(RbDeck.rbdck_name, RbDeck.rbdck_snapshot.desc())
    except Exception:
        # Si rbdck_seq no existe, usar solo nombre
        query = query.order_by(RbDeck.rbdck_name)
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    sets = RbSet.query.order_by(RbSet.rbset_id).all()
    
    # Formatos y modos disponibles
    formats = ['Standard', 'Expanded', 'Classic', 'Commander']
    modes = ['1v1', 'Commander', 'Team', 'Draft']
    
    return render_template('deck.html', 
                           decks=pagination.items,
                           pagination=pagination,
                           sets=sets,
                           formats=formats,
                           modes=modes,
                           get_page_url=lambda p: f'?page={p}')


@deck_bp.route('/view/<set_id>/<card_id>')
@login_required
def view_deck_legacy(set_id, card_id):
    """View specific deck using legacy composite key (for backwards compatibility)."""
    # Buscar por clave primaria compuesta
    rbdeck = RbDeck.query.filter_by(
        rbdck_rbset_id=set_id,
        rbdck_rbcar_id=card_id,
        rbdck_user=current_user.username
    ).first()
    
    if not rbdeck:
        from flask import abort
        abort(404)
    
    return render_template('deck_view.html', deck=rbdeck)


@deck_bp.route('/view/<name>')
@login_required
def view_deck_by_name(name):
    """View latest version of a deck by name."""
    rbdeck = RbDeck.get_by_user_and_name(current_user.username, name)
    
    if not rbdeck:
        from flask import abort
        abort(404)
    
    return render_template('deck_view.html', deck=rbdeck)


@deck_bp.route('/view/<name>/<int:seq>')
@login_required
def view_deck_by_name_and_seq(name, seq):
    """View specific version of a deck by name and sequence number."""
    rbdeck = RbDeck.get_by_user_and_name(current_user.username, name, seq)
    
    if not rbdeck:
        from flask import abort
        abort(404)
    
    return render_template('deck_view.html', deck=rbdeck)


@deck_bp.route('/versions/<name>')
@login_required
def deck_versions(name):
    """Get all versions of a deck."""
    decks = RbDeck.get_versions(current_user.username, name)
    
    return jsonify({
        'success': True,
        'versions': [{
            'set_id': d.rbdck_rbset_id,
            'card_id': d.rbdck_rbcar_id,
            'name': d.rbdck_name,
            'seq': getattr(d, 'rbdck_seq', 1) or 1,
            'snapshot': d.rbdck_snapshot.isoformat(),
            'mode': d.rbdck_mode,
            'format': d.rbdck_format,
            'ncards': d.rbdck_ncards
        } for d in decks]
    })


@deck_bp.route('/save', methods=['POST'])
@login_required
@validate_json(DeckSave)
def save_deck():
    """Save new deck or new version of existing deck.
    
    If deck_name exists, create new row with same name (different snapshot).
    """
    data = request.validated_data
    
    # Calcular total de cartas
    total_cards = 0
    cards_json = None
    if data.rbdck_cards:
        main_cards = data.rbdck_cards.main or []
        sideboard = data.rbdck_cards.sideboard or []
        for card in main_cards + sideboard:
            total_cards += card.qty
        cards_json = {
            'main': [{'set': c.set, 'id': c.id, 'qty': c.qty} for c in main_cards],
            'sideboard': [{'set': c.set, 'id': c.id, 'qty': c.qty} for c in sideboard]
        }
    
    # Usar set_id y card_id basados en el nombre
    set_id = 'DECK'
    card_id = f"{data.rbdck_name[:3].upper()}{datetime.utcnow().strftime('%m%d%H%M')}"
    
    # Crear deck sin los campos nuevos
    new_deck = RbDeck(
        rbdck_user=current_user.username,
        rbdck_name=data.rbdck_name,
        rbdck_snapshot=datetime.utcnow(),
        rbdck_rbset_id=set_id,
        rbdck_rbcar_id=card_id,
        rbdck_description=data.rbdck_description,
        rbdck_mode=data.rbdck_mode or '1v1',
        rbdck_format=data.rbdck_format or 'Standard',
        rbdck_max_set=data.rbdck_max_set,
        rbdck_ncards=total_cards or 1
    )
    
    # Solo intentar asignar si las columnas existen
    try:
        if cards_json:
            new_deck.rbdck_cards = cards_json
    except Exception:
        pass
    
    try:
        new_deck.rbdck_seq = 1
    except Exception:
        pass
    
    db.session.add(new_deck)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'set_id': set_id, 
        'card_id': card_id
    })


@deck_bp.route('/update/<set_id>/<card_id>', methods=['POST'])
@login_required
def update_deck_legacy(set_id, card_id):
    """Update deck using legacy composite key."""
    rbdeck = RbDeck.query.filter_by(
        rbdck_rbset_id=set_id,
        rbdck_rbcar_id=card_id,
        rbdck_user=current_user.username
    ).first()
    
    if not rbdeck:
        from flask import abort
        abort(404)
    
    data = request.get_json() or {}
    
    if 'rbdck_name' in data:
        # Nombre cambiado -> crear nueva versión
        new_seq = RbDeck.get_next_seq(current_user.username, data['rbdck_name'])
        
        # Obtener datos actuales
        new_deck = RbDeck(
            rbdck_user=current_user.username,
            rbdck_name=data['rbdck_name'],
            rbdck_seq=new_seq,
            rbdck_snapshot=datetime.utcnow(),
            rbdck_rbset_id=set_id,
            rbdck_rbcar_id=card_id,
            rbdck_description=data.get('rbdck_description', rbdeck.rbdck_description),
            rbdck_mode=data.get('rbdck_mode', rbdeck.rbdck_mode),
            rbdck_format=data.get('rbdck_format', rbdeck.rbdck_format),
            rbdck_max_set=data.get('rbdck_max_set', rbdeck.rbdck_max_set),
            rbdck_ncards=rbdeck.rbdck_ncards,
            rbdck_cards=rbdeck.rbdck_cards
        )
        
        if 'rbdck_cards' in data:
            main = data['rbdck_cards'].get('main', [])
            sideboard = data['rbdck_cards'].get('sideboard', [])
            total = sum(c.get('qty', 1) for c in main + sideboard)
            new_deck.rbdck_ncards = total
            new_deck.rbdck_cards = data['rbdck_cards']
        
        db.session.add(new_deck)
    else:
        # Solo actualizar metadatos (sin crear nueva versión)
        if 'rbdck_description' in data:
            rbdeck.rbdck_description = data['rbdck_description']
        if 'rbdck_mode' in data:
            rbdeck.rbdck_mode = data['rbdck_mode']
        if 'rbdck_format' in data:
            rbdeck.rbdck_format = data['rbdck_format']
        if 'rbdck_max_set' in data:
            rbdeck.rbdck_max_set = data['rbdck_max_set']
        if 'rbdck_cards' in data:
            # Crear nueva versión al cambiar cartas
            new_seq = RbDeck.get_next_seq(current_user.username, rbdeck.rbdck_name)
            
            main = data['rbdck_cards'].get('main', [])
            sideboard = data['rbdck_cards'].get('sideboard', [])
            total = sum(c.get('qty', 1) for c in main + sideboard)
            
            new_deck = RbDeck(
                rbdck_user=current_user.username,
                rbdck_name=rbdeck.rbdck_name,
                rbdck_seq=new_seq,
                rbdck_snapshot=datetime.utcnow(),
                rbdck_rbset_id=set_id,
                rbdck_rbcar_id=card_id,
                rbdck_description=rbdeck.rbdck_description,
                rbdck_mode=rbdeck.rbdck_mode,
                rbdck_format=rbdeck.rbdck_format,
                rbdck_max_set=rbdeck.rbdck_max_set,
                rbdck_ncards=total,
                rbdck_cards=data['rbdck_cards']
            )
            db.session.add(new_deck)
    
    db.session.commit()
    
    return jsonify({'success': True})


@deck_bp.route('/delete/<set_id>/<card_id>', methods=['DELETE'])
@login_required
def delete_deck_legacy(set_id, card_id):
    """Delete a specific deck version using legacy composite key."""
    rbdeck = RbDeck.query.filter_by(
        rbdck_rbset_id=set_id,
        rbdck_rbcar_id=card_id,
        rbdck_user=current_user.username
    ).first()
    
    if not rbdeck:
        from flask import abort
        abort(404)
    
    db.session.delete(rbdeck)
    db.session.commit()
    
    return jsonify({'success': True})