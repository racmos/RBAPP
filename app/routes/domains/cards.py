"""
Cards routes module with Pydantic validation.
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from app import db
from app.models import RbSet, RbCard
from app.schemas.validators import CardCreate, CardUpdate
from app.schemas.validation import validate_json
from sqlalchemy import or_, func, cast, Integer
import os
from werkzeug.utils import secure_filename

cards_bp = Blueprint('cards', __name__, url_prefix='/riftbound/card')


@cards_bp.route('')
@login_required
def cards():
    """List all cards with filters and pagination."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    search_name = request.args.get('search_name', '')
    search_set = request.args.get('search_set', '')
    search_id = request.args.get('search_id', '')
    
    search_domains = request.args.getlist('search_domains')
    search_types = request.args.getlist('search_types')
    search_tags_filter = request.args.get('search_tags_text', '')
    search_rarities = request.args.getlist('search_rarities')
    search_ability = request.args.get('search_ability', '')
    search_banned = request.args.get('search_banned', '')
    
    query = RbCard.query
    
    if search_name:
        query = query.filter(RbCard.rbcar_name.ilike(f'%{search_name}%'))
    if search_set:
        query = query.filter(RbCard.rbcar_rbset_id == search_set)
    if search_id:
        query = query.filter(
            or_(
                RbCard.rbcar_id == search_id,
                RbCard.rbcar_id.op('~')(f'^{search_id}[a-z]$'),
                RbCard.rbcar_id == f'{search_id}*'
            )
        )
    
    if search_domains:
        for domain in search_domains:
            query = query.filter(RbCard.rbcar_domain.ilike(f'%{domain}%'))
    
    if search_types:
        type_filters = []
        for card_type in search_types:
            type_filters.append(RbCard.rbcar_type.ilike(f'%{card_type}%'))
        query = query.filter(or_(*type_filters))
    
    if search_tags_filter:
        query = query.filter(RbCard.rbcar_tags.ilike(f'%{search_tags_filter}%'))
    
    if search_rarities:
        query = query.filter(RbCard.rbcar_rarity.in_(search_rarities))
    
    if search_ability:
        query = query.filter(RbCard.rbcar_ability.ilike(f'%{search_ability}%'))
    
    if search_banned:
        query = query.filter(RbCard.rbcar_banned == search_banned)
    
    energy_min = request.args.get('energy_min', type=int)
    energy_max = request.args.get('energy_max', type=int)
    power_min = request.args.get('power_min', type=int)
    power_max = request.args.get('power_max', type=int)
    might_min = request.args.get('might_min', type=int)
    might_max = request.args.get('might_max', type=int)
    
    if energy_min is not None:
        query = query.filter(RbCard.rbcar_energy >= energy_min)
    if energy_max is not None:
        query = query.filter(RbCard.rbcar_energy <= energy_max)
    
    if power_min is not None:
        query = query.filter(RbCard.rbcar_power >= power_min)
    if power_max is not None:
        query = query.filter(RbCard.rbcar_power <= power_max)
    
    if might_min is not None:
        query = query.filter(RbCard.rbcar_might >= might_min)
    if might_max is not None:
        query = query.filter(RbCard.rbcar_might <= might_max)
    
    query = query.order_by(
        RbCard.rbcar_rbset_id,
        cast(
            func.regexp_replace(RbCard.rbcar_id, r'[^0-9]', '', 'g'),
            Integer
        ),
        RbCard.rbcar_id
    )
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    sets = RbSet.query.order_by(RbSet.rbset_id).all()
    
    cards_dict = []
    for card in pagination.items:
        cards_dict.append({
            'rbcar_rbset_id': card.rbcar_rbset_id,
            'rbcar_id': card.rbcar_id,
            'rbcar_name': card.rbcar_name,
            'rbcar_domain': card.rbcar_domain,
            'rbcar_type': card.rbcar_type,
            'rbcar_tags': card.rbcar_tags,
            'rbcar_energy': card.rbcar_energy,
            'rbcar_power': card.rbcar_power,
            'rbcar_might': card.rbcar_might,
            'rbcar_ability': card.rbcar_ability,
            'rbcar_rarity': card.rbcar_rarity,
            'rbcar_artist': card.rbcar_artist,
            'rbcar_banned': card.rbcar_banned,
            'image_url': card.image_url,
            'image': card.image
        })
    
    def get_page_url(page_num):
        args = request.args.copy()
        args['page'] = page_num
        return '&'.join([f'{k}={v}' for k, v in args.items()])
    
    return render_template('cards.html', 
                         cards=pagination.items,
                         cards_json=cards_dict,
                         pagination=pagination,
                         sets=sets,
                         per_page=per_page,
                         get_page_url=get_page_url,
                         min=min)


@cards_bp.route('/upload_image', methods=['POST'])
@login_required
def upload_card_image():
    """Upload card image."""
    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'message': 'No file uploaded'}), 400
        
        file = request.files['image']
        set_id = request.form.get('set_id', '')
        
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'}), 400
        
        file.seek(0, os.SEEK_END)
        file_length = file.tell()
        if file_length > 2 * 1024 * 1024:
            return jsonify({'success': False, 'message': 'File size exceeds 2MB limit'}), 400
        file.seek(0)
        
        allowed_extensions = {'jpg', 'jpeg', 'png', 'webp'}
        filename = secure_filename(file.filename)
        if '.' not in filename or filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
            return jsonify({'success': False, 'message': 'Invalid file type. Allowed: jpg, jpeg, png, webp'}), 400
        
        upload_dir = os.path.join('app', 'static', 'images', 'cards', set_id.lower())
        os.makedirs(upload_dir, exist_ok=True)
        
        file_path = os.path.join(upload_dir, filename)
        file.save(file_path)
        
        return jsonify({'success': True, 'filename': filename})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@cards_bp.route('/add', methods=['POST'])
@login_required
@validate_json(CardCreate)
def add_card():
    """Add a new card."""
    data = request.validated_data
    
    if RbCard.query.filter_by(rbcar_rbset_id=data.rbcar_rbset_id, rbcar_id=data.rbcar_id).first():
        return jsonify({'success': False, 'message': 'Card already exists'}), 400
    
    new_card = RbCard(
        rbcar_rbset_id=data.rbcar_rbset_id,
        rbcar_id=data.rbcar_id,
        rbcar_name=data.rbcar_name,
        rbcar_domain=data.rbcar_domain,
        rbcar_type=data.rbcar_type,
        rbcar_tags=data.rbcar_tags,
        rbcar_energy=data.rbcar_energy,
        rbcar_power=data.rbcar_power,
        rbcar_might=data.rbcar_might,
        rbcar_ability=data.rbcar_ability,
        rbcar_rarity=data.rbcar_rarity,
        rbcar_artist=data.rbcar_artist,
        rbcar_banned=data.rbcar_banned,
        image_url=data.image_url,
        image=data.image
    )
    
    db.session.add(new_card)
    db.session.commit()
    
    return jsonify({'success': True})


@cards_bp.route('/update/<set_id>/<card_id>', methods=['POST'])
@login_required
@validate_json(CardUpdate)
def update_card(set_id, card_id):
    """Update an existing card."""
    data = request.validated_data
    card = RbCard.query.filter_by(rbcar_rbset_id=set_id, rbcar_id=card_id).first_or_404()
    
    if data.rbcar_name is not None:
        card.rbcar_name = data.rbcar_name
    if data.rbcar_domain is not None:
        card.rbcar_domain = data.rbcar_domain
    if data.rbcar_type is not None:
        card.rbcar_type = data.rbcar_type
    if data.rbcar_tags is not None:
        card.rbcar_tags = data.rbcar_tags
    if data.rbcar_energy is not None:
        card.rbcar_energy = data.rbcar_energy
    if data.rbcar_power is not None:
        card.rbcar_power = data.rbcar_power
    if data.rbcar_might is not None:
        card.rbcar_might = data.rbcar_might
    if data.rbcar_ability is not None:
        card.rbcar_ability = data.rbcar_ability
    if data.rbcar_rarity is not None:
        card.rbcar_rarity = data.rbcar_rarity
    if data.rbcar_artist is not None:
        card.rbcar_artist = data.rbcar_artist
    if data.rbcar_banned is not None:
        card.rbcar_banned = data.rbcar_banned
    if data.image_url is not None:
        card.image_url = data.image_url
    if data.image is not None:
        card.image = data.image
    
    db.session.commit()
    
    return jsonify({'success': True})
