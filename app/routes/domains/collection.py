"""
Collection routes module with Pydantic validation.
"""
import csv
import io
import re
from urllib.parse import urlencode
from flask import Blueprint, render_template, request, jsonify, Response
from flask_login import login_required, current_user
from sqlalchemy import func
from app import db
from app.models import RbCollection, RbCard, RbSet
from app.models.cardmarket import RbcmPrice, RbcmProductCardMap, RbcmProduct
from app.schemas.validators import (
    CollectionAdd, CollectionUpdateQuantity,
    CollectionDelete, CollectionUpdateSelling, CollectionUpdatePlayset,
    CollectionUpdateSellPrice, CollectionUpdateCondition, CollectionUpdateLanguage,
    CollectionExport,
)
from app.schemas.validation import validate_json
from datetime import datetime

collection_bp = Blueprint('collection', __name__, url_prefix='/riftbound/collection')


def _sanitize_filename_part(value: str) -> str:
    """Normaliza strings para poder usarlos en nombres de fichero."""
    if not value:
        return 'ALL'
    cleaned = re.sub(r'[^A-Za-z0-9]+', '_', value).strip('_')
    return cleaned or 'ALL'


def _qty_int(raw) -> int:
    """rbcol_quantity se guarda como TEXT; convertir a int de forma tolerante."""
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def _collection_query():
    """Query base con el último precio por producto en Cardmarket.

    Notas de diseño:
      1. La ventana "último precio" se calcula por producto
         (func.max(rbprc_date) agrupado por rbprc_id_product) porque no todos
         los productos se refrescan en la misma fecha de carga.
      2. `rbcm_product_card_map` puede tener N productos mapeados a la misma
         carta interna (el auto-match genera duplicados para distintas
         impresiones). Para evitar que ese N*M multiplique las filas de la
         colección, se reduce a UN producto canónico por (rbset_id, rbcar_id)
         usando `MIN(rbpcm_id_product)` — criterio determinista y estable.
      3. Fallback de precios: si no existe mapeo exacto por foil (p.ej.
         mapeo foil='S' para una carta común foil), se usa cualquier mapeo
         disponible para esa carta como aproximación.  Así es preferible mostrar
         un precio aproximado a no mostrar nada.
    """
    # Preferred mapping: exact foil match per (rbset_id, rbcar_id, foil_key).
    # Si el mapping no clasifica el foil (rbpcm_foil NULL — caso rare/epic o
    # legacy), se agrupa bajo la "ranura sin foil" usando '_' como centinela.
    foil_key = func.coalesce(RbcmProductCardMap.rbpcm_foil, '_')
    preferred_map_sq = db.session.query(
        RbcmProductCardMap.rbpcm_rbset_id.label('rbset_id'),
        RbcmProductCardMap.rbpcm_rbcar_id.label('rbcar_id'),
        foil_key.label('foil_key'),
        func.min(RbcmProductCardMap.rbpcm_id_product).label('id_product'),
    ).group_by(
        RbcmProductCardMap.rbpcm_rbset_id,
        RbcmProductCardMap.rbpcm_rbcar_id,
        foil_key,
    ).subquery('pm')

    # Fallback mapping: ANY mapping per (rbset_id, rbcar_id), regardless of foil.
    # Used when no exact foil match exists — shows approximate price instead of none.
    fallback_map_sq = db.session.query(
        RbcmProductCardMap.rbpcm_rbset_id.label('rbset_id'),
        RbcmProductCardMap.rbpcm_rbcar_id.label('rbcar_id'),
        func.min(RbcmProductCardMap.rbpcm_id_product).label('id_product'),
    ).group_by(
        RbcmProductCardMap.rbpcm_rbset_id,
        RbcmProductCardMap.rbpcm_rbcar_id,
    ).subquery('fm')

    # Effective id_product: prefer preferred (exact-foil), fall back to any mapping.
    effective_id_product = func.coalesce(preferred_map_sq.c.id_product, fallback_map_sq.c.id_product)

    latest_price_sq = db.session.query(
        RbcmPrice.rbprc_id_product,
        func.max(RbcmPrice.rbprc_date).label('max_date')
    ).group_by(RbcmPrice.rbprc_id_product).subquery('lp')

    latest_product_sq = db.session.query(
        RbcmProduct.rbprd_id_product,
        func.max(RbcmProduct.rbprd_date).label('max_date')
    ).group_by(RbcmProduct.rbprd_id_product).subquery('lpd')

    return db.session.query(RbCollection, RbCard, RbcmPrice, RbcmProduct).join(
        RbCard,
        (RbCollection.rbcol_rbset_id == RbCard.rbcar_rbset_id) &
        (RbCollection.rbcol_rbcar_id == RbCard.rbcar_id)
    ).outerjoin(
        preferred_map_sq,
        (RbCollection.rbcol_rbset_id == preferred_map_sq.c.rbset_id) &
        (RbCollection.rbcol_rbcar_id == preferred_map_sq.c.rbcar_id) &
        # Mappings clasificados deben coincidir foil-con-foil; los legacy
        # (foil_key='_') matchean siempre (compatibilidad hacia atrás).
        ((preferred_map_sq.c.foil_key == RbCollection.rbcol_foil) |
         (preferred_map_sq.c.foil_key == '_'))
    ).outerjoin(
        fallback_map_sq,
        (RbCollection.rbcol_rbset_id == fallback_map_sq.c.rbset_id) &
        (RbCollection.rbcol_rbcar_id == fallback_map_sq.c.rbcar_id)
    ).outerjoin(
        latest_price_sq,
        effective_id_product == latest_price_sq.c.rbprc_id_product
    ).outerjoin(
        RbcmPrice,
        (effective_id_product == RbcmPrice.rbprc_id_product) &
        (RbcmPrice.rbprc_date == latest_price_sq.c.max_date)
    ).outerjoin(
        latest_product_sq,
        effective_id_product == latest_product_sq.c.rbprd_id_product
    ).outerjoin(
        RbcmProduct,
        (effective_id_product == RbcmProduct.rbprd_id_product) &
        (RbcmProduct.rbprd_date == latest_product_sq.c.max_date)
    )


def _resolve_price(col, price_obj, card=None):
    """Elige el precio correcto según la rareza de la carta y el tipo de foil:

      - rare / epic / showcase → avg7_foil (fallback avg7)
      - common / uncommon + foil='S' → avg7_foil (fallback avg7)
      - common / uncommon + foil='N' → avg7 (fallback avg7_foil)

    Fuente de verdad: Riftbound sólo tiene foil para common/uncommon; las rare,
    epic y showcase siempre se cotizan con el campo "foil" de Cardmarket (que en
    realidad representa la versión única de esas rarezas).

    Cuando el campo preferido es NULL, se usa el alternativo como aproximación.
    Es mejor mostrar un precio aproximado que ningún precio.
    """
    if not price_obj:
        return None

    rarity = (card.rbcar_rarity if card else '') or ''
    rarity_lower = rarity.lower()
    is_premium = rarity_lower in ('rare', 'epic', 'showcase')

    if is_premium or col.rbcol_foil == 'S':
        raw = price_obj.rbprc_avg7_foil or price_obj.rbprc_avg7
    else:
        raw = price_obj.rbprc_avg7 or price_obj.rbprc_avg7_foil

    return float(raw) if raw is not None else None


@collection_bp.route('')
@login_required
def collection():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    sort_by = request.args.get('sort_by', 'set')
    sort_order = request.args.get('sort_order', 'asc')
    view_mode = request.args.get('view', 'list')

    query = _collection_query().filter(RbCollection.rbcol_user == current_user.username)

    search_set = request.args.get('search_set')
    if search_set:
        query = query.filter(RbCollection.rbcol_rbset_id == search_set)
    search_card_id = request.args.get('search_card_id')
    if search_card_id:
        query = query.filter(RbCollection.rbcol_rbcar_id.ilike(f'%{search_card_id}%'))
    search_card_name = request.args.get('search_card_name')
    if search_card_name:
        query = query.filter(RbCard.rbcar_name.ilike(f'%{search_card_name}%'))
    search_domains = request.args.getlist('search_domains')
    if search_domains:
        query = query.filter(RbCard.rbcar_domain.in_(search_domains))
    search_types = request.args.getlist('search_types')
    if search_types:
        query = query.filter(RbCard.rbcar_type.in_(search_types))
    search_rarities = request.args.getlist('search_rarities')
    if search_rarities:
        query = query.filter(RbCard.rbcar_rarity.in_(search_rarities))
    search_tags_text = request.args.get('search_tags_text')
    if search_tags_text:
        query = query.filter(RbCard.rbcar_tags.ilike(f'%{search_tags_text}%'))

    # Para ordenar por card_id de forma "natural" (1,2,...,7,7a,8) extraemos
    # el prefijo numérico y lo casteamos a INT, con la cadena completa como
    # desempate alfabético (lo que pone 7a justo después de 7).
    card_id_num = func.coalesce(
        db.cast(
            func.substring(RbCollection.rbcol_rbcar_id, r'^(\d+)'),
            db.Integer,
        ),
        0,
    )

    sort_map = {
        'set': [RbCollection.rbcol_rbset_id, card_id_num, RbCollection.rbcol_rbcar_id, RbCollection.rbcol_foil, RbCollection.rbcol_id],
        'card_id': [card_id_num, RbCollection.rbcol_rbcar_id, RbCollection.rbcol_rbset_id, RbCollection.rbcol_foil, RbCollection.rbcol_id],
        'name': [RbCard.rbcar_name, RbCollection.rbcol_rbset_id, card_id_num, RbCollection.rbcol_foil, RbCollection.rbcol_id],
        'quantity': [RbCollection.rbcol_quantity, RbCollection.rbcol_rbset_id, card_id_num, RbCollection.rbcol_id],
        'price': [RbcmPrice.rbprc_avg7, RbCollection.rbcol_rbset_id, card_id_num, RbCollection.rbcol_id],
    }
    sort_cols = sort_map.get(sort_by, sort_map['set'])
    if sort_order == 'desc':
        query = query.order_by(*[c.desc() for c in sort_cols])
    else:
        query = query.order_by(*[c.asc() for c in sort_cols])

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    sets = RbSet.query.order_by(RbSet.rbset_id).all()

    # Orden canónico de rarezas Riftbound (resto al final alfabéticamente)
    rarity_order = ['Common', 'Uncommon', 'Rare', 'Epic', 'Showcase']
    raw_rarities = [r[0] for r in db.session.query(RbCard.rbcar_rarity)
                    .filter(RbCard.rbcar_rarity.isnot(None))
                    .distinct().all()]
    rarities = [r for r in rarity_order if r in raw_rarities]
    rarities += sorted(r for r in raw_rarities if r not in rarity_order)

    collections_data = [
        {
            'collection': c,
            'card': cd,
            'price': _resolve_price(c, p, cd),
            'product_name': prod.rbprd_name if prod else None,
        }
        for c, cd, p, prod in pagination.items
    ]

    def get_page_url(p):
        args = request.args.to_dict(flat=False)
        args['page'] = [str(p)]
        return urlencode(args, doseq=True)

    return render_template('collection.html',
                           collections_data=collections_data,
                           pagination=pagination,
                           sets=sets,
                           rarities=rarities,
                           view_mode=view_mode,
                           per_page=per_page,
                           get_page_url=get_page_url)


def _null_safe_eq(col, val):
    """NULL-safe equality for SQLAlchemy filters.

    NULL == NULL → True (IS NULL check)
    value == value → normal == comparison

    Works on both PostgreSQL (prod) and SQLite (tests).
    """
    if val is None:
        return col.is_(None)
    return col == val


def _find_exact_duplicate(user, rbset_id, rbcar_id, foil, selling, sell_price, condition, language):
    """Busca una fila exacta en la colección del usuario (8-field NULL-safe match).

    Devuelve la fila encontrada o None.
    """
    return RbCollection.query.filter(
        RbCollection.rbcol_user == user,
        RbCollection.rbcol_rbset_id == rbset_id,
        RbCollection.rbcol_rbcar_id == rbcar_id,
        RbCollection.rbcol_foil == foil,
        RbCollection.rbcol_selling == selling,
        _null_safe_eq(RbCollection.rbcol_sell_price, sell_price),
        _null_safe_eq(RbCollection.rbcol_condition, condition),
        _null_safe_eq(RbCollection.rbcol_language, language),
    ).first()


def _get_owned_row(rbcol_id):
    """Carga una fila de la colección verificando que pertenece al usuario actual.
    Devuelve la fila o aborta con 404."""
    return RbCollection.query.filter_by(
        rbcol_id=rbcol_id, rbcol_user=current_user.username
    ).first_or_404()


@collection_bp.route('/add', methods=['POST'])
@login_required
@validate_json(CollectionAdd)
def add_collection():
    """Añade a la colección. Si ya existe una fila exactamente igual (mismo
    set/card/foil/selling/sell_price/condition/language) la cantidad se suma
    (merge). Si difiere en cualquier campo, se inserta una nueva fila.

    Response incluye `merged: bool` para que el frontend muestre el toast adecuado."""
    data = request.validated_data

    card = RbCard.query.filter_by(
        rbcar_rbset_id=data.rbcol_rbset_id, rbcar_id=data.rbcol_rbcar_id
    ).first()
    if not card:
        return jsonify({'success': False, 'message': 'Card does not exist'}), 400

    # REQ-2: foil restriction for Rare/Epic/Showcase
    if data.rbcol_foil == 'S' and (card.rbcar_rarity or '').lower() in ('rare', 'epic', 'showcase'):
        return jsonify({
            'success': False,
            'message': f'Foil not allowed for {card.rbcar_rarity} cards',
        }), 400

    selling = data.rbcol_selling or 'N'

    # REQ-1: auto-merge exact duplicate
    existing = _find_exact_duplicate(
        user=current_user.username,
        rbset_id=data.rbcol_rbset_id,
        rbcar_id=data.rbcol_rbcar_id,
        foil=data.rbcol_foil,
        selling=selling,
        sell_price=data.rbcol_sell_price,
        condition=data.rbcol_condition,
        language=data.rbcol_language,
    )

    if existing:
        existing.rbcol_quantity = str(_qty_int(existing.rbcol_quantity) + data.rbcol_quantity)
        existing.rbcol_chadat = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True, 'rbcol_id': existing.rbcol_id, 'merged': True})

    new_row = RbCollection(
        rbcol_rbset_id=data.rbcol_rbset_id,
        rbcol_rbcar_id=data.rbcol_rbcar_id,
        rbcol_foil=data.rbcol_foil,
        rbcol_quantity=str(data.rbcol_quantity),
        rbcol_selling=selling,
        rbcol_sell_price=data.rbcol_sell_price,
        rbcol_condition=data.rbcol_condition,
        rbcol_language=data.rbcol_language,
        rbcol_chadat=datetime.utcnow(),
        rbcol_user=current_user.username,
    )
    db.session.add(new_row)
    db.session.commit()
    return jsonify({'success': True, 'rbcol_id': new_row.rbcol_id, 'merged': False})


@collection_bp.route('/update_quantity', methods=['POST'])
@login_required
@validate_json(CollectionUpdateQuantity)
def update_collection_quantity():
    data = request.validated_data
    col = _get_owned_row(data.rbcol_id)

    if data.quantity == 0:
        db.session.delete(col)
        db.session.commit()
        return jsonify({'success': True, 'deleted': True})

    col.rbcol_quantity = str(data.quantity)
    col.rbcol_chadat = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True})


@collection_bp.route('/delete', methods=['POST'])
@login_required
@validate_json(CollectionDelete)
def delete_collection():
    data = request.validated_data
    col = _get_owned_row(data.rbcol_id)
    db.session.delete(col)
    db.session.commit()
    return jsonify({'success': True})


@collection_bp.route('/update_selling', methods=['POST'])
@login_required
@validate_json(CollectionUpdateSelling)
def update_selling():
    data = request.validated_data
    col = _get_owned_row(data.rbcol_id)
    col.rbcol_selling = data.rbcol_selling
    col.rbcol_chadat = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True})


@collection_bp.route('/update_playset', methods=['POST'])
@login_required
@validate_json(CollectionUpdatePlayset)
def update_playset():
    data = request.validated_data
    col = _get_owned_row(data.rbcol_id)
    col.rbcol_playset = data.rbcol_playset

    # Auto-selling según sobrante de playset
    qty = _qty_int(col.rbcol_quantity)
    if data.rbcol_playset is None:
        pass  # no tocamos el selling manual
    elif qty > data.rbcol_playset:
        col.rbcol_selling = 'Y'
    else:
        col.rbcol_selling = 'N'

    col.rbcol_chadat = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True})


@collection_bp.route('/update_sell_price', methods=['POST'])
@login_required
@validate_json(CollectionUpdateSellPrice)
def update_sell_price():
    data = request.validated_data
    col = _get_owned_row(data.rbcol_id)
    col.rbcol_sell_price = data.rbcol_sell_price
    col.rbcol_chadat = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True})


@collection_bp.route('/update_condition', methods=['POST'])
@login_required
@validate_json(CollectionUpdateCondition)
def update_condition():
    data = request.validated_data
    col = _get_owned_row(data.rbcol_id)
    col.rbcol_condition = data.rbcol_condition
    col.rbcol_chadat = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True})


@collection_bp.route('/update_language', methods=['POST'])
@login_required
@validate_json(CollectionUpdateLanguage)
def update_language():
    data = request.validated_data
    col = _get_owned_row(data.rbcol_id)
    col.rbcol_language = data.rbcol_language
    col.rbcol_chadat = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True})


@collection_bp.route('/bulk_apply', methods=['POST'])
@login_required
def bulk_apply():
    """Aplica en un único request TODOS los campos que el usuario haya
    rellenado en el panel bulk. Un campo ausente del payload = no tocar.

    Campos aceptados (todos opcionales salvo `ids`):
      - ids:       lista de rbcol_id (OBLIGATORIO)
      - quantity:  int > 0
      - playset:   int ∈ {1,2,3} — se distribuye con prioridad foil y auto-marca selling
      - selling:   'Y' | 'N' — override manual. Si se envía junto con playset,
                   el playset MANDA (porque decide automáticamente el selling).
      - sell_price: float ≥ 0 o null
      - condition: str ∈ {MT, NM, EX, GD, LP, PL, PO} o null
      - language:  str libre o null
    """
    body = request.get_json()
    if not body:
        return jsonify({'success': False, 'message': 'No data'}), 400

    ids = body.get('ids') or [it.get('rbcol_id') for it in body.get('items', []) if isinstance(it, dict) and it.get('rbcol_id')]
    ids = [int(i) for i in ids if i is not None]
    if not ids:
        return jsonify({'success': False, 'message': 'No ids'}), 400

    # --- Validaciones previas (todo o nada) ---
    quantity = None
    if 'quantity' in body:
        try:
            quantity = int(body['quantity'])
            if quantity < 1:
                raise ValueError()
        except (TypeError, ValueError):
            return jsonify({'success': False, 'message': 'Invalid quantity'}), 400

    playset = None
    if 'playset' in body and body['playset'] is not None:
        try:
            playset = int(body['playset'])
            if playset not in (1, 2, 3):
                raise ValueError()
        except (TypeError, ValueError):
            return jsonify({'success': False, 'message': 'Invalid playset value'}), 400

    selling_override = None  # 'Y' | 'N' | None
    if 'selling' in body and body['selling'] is not None:
        v = str(body['selling']).upper()
        if v not in ('Y', 'N'):
            return jsonify({'success': False, 'message': "Invalid selling (use 'Y' or 'N')"}), 400
        selling_override = v

    sell_price = 'UNSET'
    if 'sell_price' in body:
        raw = body['sell_price']
        if raw in (None, ''):
            sell_price = None
        else:
            try:
                sell_price = float(raw)
                if sell_price < 0:
                    raise ValueError()
            except (TypeError, ValueError):
                return jsonify({'success': False, 'message': 'Invalid sell_price'}), 400

    condition = 'UNSET'
    if 'condition' in body:
        raw = body['condition']
        if raw in (None, ''):
            condition = None
        else:
            allowed = {'MT', 'NM', 'EX', 'GD', 'LP', 'PL', 'PO'}
            if raw not in allowed:
                return jsonify({'success': False, 'message': f'Invalid condition (allowed: {sorted(allowed)})'}), 400
            condition = raw

    language = 'UNSET'
    if 'language' in body:
        raw = body['language']
        if raw in (None, ''):
            language = None
        else:
            language = str(raw).strip() or None

    # --- Cargar filas (sólo del usuario actual) ---
    rows = RbCollection.query.filter(
        RbCollection.rbcol_id.in_(ids),
        RbCollection.rbcol_user == current_user.username,
    ).all()

    now = datetime.utcnow()

    # --- Aplicar campos simples ---
    for col in rows:
        if quantity is not None:
            col.rbcol_quantity = str(quantity)
        if sell_price != 'UNSET':
            col.rbcol_sell_price = sell_price
        if condition != 'UNSET':
            col.rbcol_condition = condition
        if language != 'UNSET':
            col.rbcol_language = language
        if selling_override is not None and playset is None:
            # 'selling' manual solo cuando no hay playset (playset lo recalcula)
            col.rbcol_selling = selling_override
        col.rbcol_chadat = now

    # --- Aplicar playset con prioridad foil (pisa al selling manual) ---
    if playset is not None:
        groups = {}
        for col in rows:
            groups.setdefault((col.rbcol_rbset_id, col.rbcol_rbcar_id), []).append(col)
        for cols in groups.values():
            # foil='S' primero — prioridad para playset
            cols.sort(key=lambda c: 0 if c.rbcol_foil == 'S' else 1)
            remaining = playset
            for col in cols:
                available = _qty_int(col.rbcol_quantity)
                assigned = min(available, remaining)
                col.rbcol_playset = assigned if assigned > 0 else None
                col.rbcol_selling = 'Y' if available > assigned else 'N'
                col.rbcol_chadat = now
                remaining -= assigned

    db.session.commit()
    return jsonify({'success': True, 'updated': len(rows)})


@collection_bp.route('/bulk_delete', methods=['POST'])
@login_required
def bulk_delete():
    """Borra filas por lista de rbcol_id (sólo las del usuario actual)."""
    body = request.get_json() or {}
    ids = body.get('ids') or [it.get('rbcol_id') for it in body.get('items', []) if isinstance(it, dict) and it.get('rbcol_id')]
    ids = [int(i) for i in ids if i is not None]
    if not ids:
        return jsonify({'success': False, 'message': 'No ids'}), 400

    deleted = RbCollection.query.filter(
        RbCollection.rbcol_id.in_(ids),
        RbCollection.rbcol_user == current_user.username,
    ).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({'success': True, 'deleted': deleted})


@collection_bp.route('/api/sets')
@login_required
def api_sets():
    """Devuelve todos los sets para los selects del frontend."""
    sets = RbSet.query.order_by(RbSet.rbset_id).all()
    return jsonify({
        'success': True,
        'sets': [{'id': s.rbset_id, 'name': s.rbset_name} for s in sets],
    })


@collection_bp.route('/api/cards')
@login_required
def api_cards():
    """Devuelve cartas filtradas para el selector de "Add to collection" y
    para el parser de decks por nombre.

    Query params:
      - set_id: filtra por set
      - search: filtra por nombre o card_id (ilike)
      - limit:  máx resultados (default 100, hard cap 2000)
    """
    set_id = request.args.get('set_id', '').strip()
    search = request.args.get('search', '').strip()
    try:
        limit = min(max(int(request.args.get('limit', 100)), 1), 2000)
    except ValueError:
        limit = 100

    q = RbCard.query
    if set_id:
        q = q.filter(RbCard.rbcar_rbset_id == set_id)
    if search:
        like = f'%{search}%'
        q = q.filter(
            (RbCard.rbcar_name.ilike(like)) |
            (RbCard.rbcar_id.ilike(like))
        )

    q = q.order_by(
        RbCard.rbcar_rbset_id,
        # Natural sort por número antes de letra (1, 2, ..., 7, 7a, 8)
        func.coalesce(
            db.cast(
                func.substring(RbCard.rbcar_id, r'^(\d+)'),
                db.Integer,
            ),
            0,
        ),
        RbCard.rbcar_id,
    ).limit(limit)

    cards = q.all()

    return jsonify({
        'success': True,
        'cards': [{
            'set_id': c.rbcar_rbset_id,
            'card_id': c.rbcar_id,
            'name': c.rbcar_name,
            'rarity': c.rbcar_rarity,
            'domain': c.rbcar_domain,
            'type': c.rbcar_type,
            'image': (
                f"/riftbound/static/images/cards/{c.rbcar_rbset_id.lower()}/{c.image}"
                if c.image else None
            ),
        } for c in cards],
    })


@collection_bp.route('/import_csv', methods=['POST'])
@login_required
def import_collection_csv():
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
                rbcol_rbcar_id=rbcar_id,
                rbcol_foil=rbcol_foil,
                rbcol_quantity=rbcol_quantity,
                rbcol_chadat=datetime.utcnow(),
                rbcol_user=current_user.username
            ))
    db.session.commit()
    return jsonify({'success': True})


@collection_bp.route('/export_csv', methods=['POST'])
@login_required
@validate_json(CollectionExport)
def export_csv():
    """Exporta a CSV las cartas puestas a la venta de la colección del usuario,
    filtradas por expansión y rareza.

    Formato:
      - Todos los campos entrecomillados y separados por coma.
      - Columnas: name, language, quantity, price.
      - `name` usa el nombre del producto en Cardmarket cuando está mapeado
        (rbprd_name); si no, hace fallback al nombre de la carta (rbcar_name).
      - `quantity` = rbcol_quantity - COALESCE(rbcol_playset, 0). Sólo filas
        con sobrante > 0 y rbcol_selling = 'Y' se incluyen.
      - Nombre del fichero: YYYYMMDDHH24MMSS_expansion_rareza.csv
    """
    data = request.validated_data

    query = _collection_query().filter(
        RbCollection.rbcol_user == current_user.username,
        RbCollection.rbcol_rbset_id == data.rbset_id,
        RbCard.rbcar_rarity == data.rarity,
        RbCollection.rbcol_selling == 'Y',
    ).order_by(RbCard.rbcar_name, RbCollection.rbcol_foil)

    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator='\n')
    writer.writerow(['name', 'language', 'quantity', 'price'])

    rows_written = 0
    for col, card, price_obj, product in query.all():
        qty_total = _qty_int(col.rbcol_quantity)
        qty_sell = qty_total - (col.rbcol_playset or 0)
        if qty_sell <= 0:
            continue

        # Nombre en formato Cardmarket si está mapeado, si no, nombre interno
        name = product.rbprd_name if product and product.rbprd_name else card.rbcar_name
        language = col.rbcol_language or ''

        # Precio: el fijado manualmente; si no, el de mercado (avg7 con foil si aplica)
        if col.rbcol_sell_price is not None:
            sell_price = float(col.rbcol_sell_price)
        else:
            market_price = _resolve_price(col, price_obj, card)
            sell_price = market_price if market_price is not None else 0.0

        writer.writerow([name, language, str(qty_sell), f'{sell_price:.2f}'])
        rows_written += 1

    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    filename = f'{timestamp}_{_sanitize_filename_part(data.rbset_id)}_{_sanitize_filename_part(data.rarity)}.csv'

    # Prepend BOM para que Excel detecte UTF-8 correctamente
    output = '\ufeff' + buf.getvalue()

    return Response(
        output,
        mimetype='text/csv; charset=utf-8',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'X-Rows-Exported': str(rows_written),
        }
    )
