"""
Price routes module with Pydantic validation.
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from sqlalchemy import func
from app import db
from app.models import RbSet, RbCard
from app.models.cardmarket import (
    RbcmExpansion, RbcmProduct, RbcmPrice, RbcmProductCardMap, RbProducts
)
from app.schemas.validators import PriceGenerate, CardmarketLoad, RiotExtract
from app.schemas.validation import validate_json
from app.services.cardmarket_loader import CARDMARKET_URLS

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
    rbpcm_foil = data.get('rbpcm_foil')  # 'N' | 'S' | None
    if rbpcm_foil not in (None, 'N', 'S', ''):
        return jsonify({'success': False, 'message': "rbpcm_foil debe ser 'N', 'S' o vacío"}), 400
    if rbpcm_foil == '':
        rbpcm_foil = None

    if not all([id_product, rbset_id, rbcar_id]):
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400

    # No permitir que (rbset_id, rbcar_id, foil) sea usado por OTRO id_product.
    # Cada (carta, foil) debe estar mapeada como máximo a 1 producto Cardmarket.
    # Comparación robusta a NULL: dos NULL se consideran iguales.
    conflict_query = RbcmProductCardMap.query.filter(
        RbcmProductCardMap.rbpcm_rbset_id == rbset_id,
        RbcmProductCardMap.rbpcm_rbcar_id == rbcar_id,
        RbcmProductCardMap.rbpcm_id_product != id_product,
    )
    if rbpcm_foil is None:
        conflict_query = conflict_query.filter(RbcmProductCardMap.rbpcm_foil.is_(None))
    else:
        conflict_query = conflict_query.filter(RbcmProductCardMap.rbpcm_foil == rbpcm_foil)
    conflict = conflict_query.first()

    if conflict:
        foil_label = {'N': ' (normal)', 'S': ' (foil)'}.get(rbpcm_foil or '', '')
        return jsonify({
            'success': False,
            'message': (
                f'La carta {rbset_id}-{rbcar_id}{foil_label} ya está mapeada al idProduct '
                f'{conflict.rbpcm_id_product}. Si esa otra entrada está mal, libérala primero '
                f'o elige una variante distinta (p.ej. {rbcar_id}a, {rbcar_id}s, '
                f'el set promo terminado en X, o cambia el foil).'
            ),
            'conflict_id_product': conflict.rbpcm_id_product,
        }), 409

    # Check if mapping already exists para ESTE id_product
    existing = RbcmProductCardMap.query.filter_by(
        rbpcm_id_product=id_product
    ).first()

    if existing:
        existing.rbpcm_rbset_id = rbset_id
        existing.rbpcm_rbcar_id = rbcar_id
        existing.rbpcm_foil = rbpcm_foil
        existing.rbpcm_match_type = 'manual'
        existing.rbpcm_confidence = 1.0
    else:
        db.session.add(RbcmProductCardMap(
            rbpcm_id_product=id_product,
            rbpcm_rbset_id=rbset_id,
            rbpcm_rbcar_id=rbcar_id,
            rbpcm_foil=rbpcm_foil,
            rbpcm_match_type='manual',
            rbpcm_confidence=1.0,
        ))

    db.session.commit()
    return jsonify({'success': True, 'message': 'Mapping saved'})


# =========================================================================
# EXPANSION MAPPING (Cardmarket rbcm_expansions -> riftbound rbset)
# =========================================================================

@price_bp.route('/cardmarket-unmapped-expansions')
@login_required
def cardmarket_unmapped_expansions():
    """Devuelve expansiones Cardmarket con rbexp_rbset_id NULL (sin mapear a
    un set interno), con el conteo de productos asociados. También devuelve
    los sets internos disponibles para poder hacer el mapping desde la UI y
    las URLs de descarga como referencia."""
    latest_date = db.session.query(func.max(RbcmProduct.rbprd_date)).scalar()

    # Count de productos por expansión en la última carga
    count_map = {}
    if latest_date:
        rows = db.session.query(
            RbcmProduct.rbprd_id_expansion,
            func.count(RbcmProduct.rbprd_id_product)
        ).filter(
            RbcmProduct.rbprd_date == latest_date
        ).group_by(RbcmProduct.rbprd_id_expansion).all()
        count_map = {r[0]: r[1] for r in rows if r[0] is not None}

    unmapped = RbcmExpansion.query.filter(
        RbcmExpansion.rbexp_rbset_id.is_(None)
    ).order_by(RbcmExpansion.rbexp_id).all()

    sets = RbSet.query.order_by(RbSet.rbset_id).all()

    return jsonify({
        'success': True,
        'count': len(unmapped),
        'expansions': [{
            'rbexp_id': e.rbexp_id,
            'rbexp_name': e.rbexp_name,
            'products_count': count_map.get(e.rbexp_id, 0),
        } for e in unmapped],
        'existing_sets': [{
            'rbset_id': s.rbset_id,
            'rbset_name': s.rbset_name,
        } for s in sets],
        'download_urls': CARDMARKET_URLS,
    })


@price_bp.route('/cardmarket-map-expansion', methods=['POST'])
@login_required
def cardmarket_map_expansion():
    """Mapea una expansión Cardmarket a un set interno.

    Body: {
      rbexp_id:       int            (requerido)
      rbexp_name:     str | None     (opcional, para rellenar rbcm_expansions.rbexp_name)
      rbset_id:       str            (requerido, FK a rbset)
      rbset_name:     str | None     (si el rbset_id no existe, se crea con este nombre)
      rbset_ncard:    int | None
    }
    """
    data = request.get_json() or {}
    rbexp_id = data.get('rbexp_id')
    rbset_id = (data.get('rbset_id') or '').strip()
    rbset_name = (data.get('rbset_name') or '').strip()
    rbexp_name = (data.get('rbexp_name') or '').strip() or None

    if not rbexp_id or not rbset_id:
        return jsonify({'success': False, 'message': 'rbexp_id y rbset_id son obligatorios'}), 400

    exp = RbcmExpansion.query.get(rbexp_id)
    if not exp:
        return jsonify({'success': False, 'message': f'Expansión {rbexp_id} no encontrada'}), 404

    # Crear el set interno si no existe y se ha proporcionado nombre
    rbset = RbSet.query.get(rbset_id)
    if not rbset:
        if not rbset_name:
            return jsonify({
                'success': False,
                'message': f'El set interno {rbset_id} no existe. Indica rbset_name para crearlo.'
            }), 400
        rbset = RbSet(
            rbset_id=rbset_id,
            rbset_name=rbset_name,
            rbset_ncard=data.get('rbset_ncard'),
        )
        db.session.add(rbset)

    exp.rbexp_rbset_id = rbset_id
    if rbexp_name:
        exp.rbexp_name = rbexp_name

    db.session.commit()
    return jsonify({'success': True})


# =========================================================================
# UPSERT DE CARTAS Y PRODUCTOS desde "Revisar carga"
# =========================================================================

_CARD_FIELDS = (
    'rbcar_rbset_id', 'rbcar_id', 'rbcar_name', 'rbcar_domain', 'rbcar_type',
    'rbcar_tags', 'rbcar_energy', 'rbcar_power', 'rbcar_might', 'rbcar_ability',
    'rbcar_rarity', 'rbcar_artist', 'rbcar_banned', 'image_url', 'image',
)

_INT_CARD_FIELDS = {'rbcar_energy', 'rbcar_power', 'rbcar_might'}


def _card_to_dict(card):
    return {f: getattr(card, f) for f in _CARD_FIELDS}


@price_bp.route('/cardmarket-card-detail')
@login_required
def cardmarket_card_detail():
    """Devuelve los campos completos de una carta existente para editar."""
    rbset_id = request.args.get('rbset_id', '').strip()
    rbcar_id = request.args.get('rbcar_id', '').strip()
    if not rbset_id or not rbcar_id:
        return jsonify({'success': False, 'message': 'rbset_id y rbcar_id requeridos'}), 400
    card = RbCard.query.filter_by(rbcar_rbset_id=rbset_id, rbcar_id=rbcar_id).first()
    if not card:
        return jsonify({'success': True, 'exists': False, 'card': None})
    return jsonify({'success': True, 'exists': True, 'card': _card_to_dict(card)})


@price_bp.route('/cardmarket-card-search-full')
@login_required
def cardmarket_card_search_full():
    """Busca cartas por nombre devolviendo campos completos para autorrelleno."""
    q = (request.args.get('q') or '').strip()
    if len(q) < 3:
        return jsonify({'success': True, 'cards': []})
    cards = RbCard.query.filter(
        RbCard.rbcar_name.ilike(f'%{q}%')
    ).order_by(RbCard.rbcar_name).limit(20).all()
    return jsonify({'success': True, 'cards': [_card_to_dict(c) for c in cards]})


@price_bp.route('/cardmarket-upsert-card', methods=['POST'])
@login_required
def cardmarket_upsert_card():
    """Crea o actualiza una fila de rbcards.
    - Si la PK (rbset_id, rbcar_id) ya existe, actualiza los campos no-clave.
    - Si no existe, inserta.
    Devuelve el estado final ('created' | 'updated') y los campos de la PK."""
    data = request.get_json() or {}
    rbset_id = (data.get('rbcar_rbset_id') or '').strip()
    rbcar_id = (data.get('rbcar_id') or '').strip()
    rbcar_name = (data.get('rbcar_name') or '').strip()

    if not rbset_id or not rbcar_id or not rbcar_name:
        return jsonify({'success': False, 'message': 'rbcar_rbset_id, rbcar_id y rbcar_name son obligatorios'}), 400

    # Validar que el set existe (rbset es FK de rbcards)
    if not RbSet.query.get(rbset_id):
        return jsonify({'success': False, 'message': f'El set "{rbset_id}" no existe. Créalo primero en "Nueva expansión".'}), 400

    def _coerce(field, value):
        if value in (None, ''):
            return None
        if field in _INT_CARD_FIELDS:
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
        return value

    existing = RbCard.query.filter_by(rbcar_rbset_id=rbset_id, rbcar_id=rbcar_id).first()
    status = 'updated' if existing else 'created'

    if not existing:
        existing = RbCard(rbcar_rbset_id=rbset_id, rbcar_id=rbcar_id, rbcar_name=rbcar_name)
        db.session.add(existing)

    for f in _CARD_FIELDS:
        if f in ('rbcar_rbset_id', 'rbcar_id'):
            continue  # PK no mutable
        if f in data:
            setattr(existing, f, _coerce(f, data.get(f)))

    if not existing.rbcar_name:
        existing.rbcar_name = rbcar_name

    db.session.commit()
    return jsonify({
        'success': True,
        'status': status,
        'rbset_id': rbset_id,
        'rbcar_id': rbcar_id,
        'rbcar_name': existing.rbcar_name,
    })


_PRODUCT_FIELDS = (
    'rbpdt_id_set', 'rbpdt_id_product', 'rbpdt_name', 'rbpdt_description',
    'rbpdt_type', 'rbpdt_image_url', 'rbpdt_image',
)


def _product_to_dict(p):
    return {f: getattr(p, f) for f in _PRODUCT_FIELDS}


@price_bp.route('/cardmarket-product-detail')
@login_required
def cardmarket_product_detail():
    rbpdt_id_set = request.args.get('rbpdt_id_set', '').strip()
    try:
        rbpdt_id_product = int(request.args.get('rbpdt_id_product', ''))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'rbpdt_id_product inválido'}), 400
    if not rbpdt_id_set:
        return jsonify({'success': False, 'message': 'rbpdt_id_set requerido'}), 400
    p = RbProducts.query.filter_by(
        rbpdt_id_set=rbpdt_id_set, rbpdt_id_product=rbpdt_id_product
    ).first()
    if not p:
        return jsonify({'success': True, 'exists': False, 'product': None})
    return jsonify({'success': True, 'exists': True, 'product': _product_to_dict(p)})


@price_bp.route('/cardmarket-product-search')
@login_required
def cardmarket_product_search():
    """Busca en rbproducts por nombre."""
    q = (request.args.get('q') or '').strip()
    if len(q) < 3:
        return jsonify({'success': True, 'products': []})
    prods = RbProducts.query.filter(
        RbProducts.rbpdt_name.ilike(f'%{q}%')
    ).order_by(RbProducts.rbpdt_name).limit(20).all()
    return jsonify({'success': True, 'products': [_product_to_dict(p) for p in prods]})


@price_bp.route('/cardmarket-unmap', methods=['POST'])
@login_required
def cardmarket_unmap():
    """Elimina un mapeo. Acepta uno de:
       - id_product:  borra el mapeo por idProduct.
       - rbset_id + rbcar_id [+ rbpcm_foil]: borra el(los) mapeo(s) que apunten
         a esa carta (y opcionalmente a esa variante de foil).
    Devuelve cuántos mappings se borraron."""
    data = request.get_json() or {}
    id_product = data.get('id_product')
    rbset_id = (data.get('rbset_id') or '').strip()
    rbcar_id = (data.get('rbcar_id') or '').strip()
    foil = data.get('rbpcm_foil')

    if id_product:
        try:
            id_product = int(id_product)
        except (TypeError, ValueError):
            return jsonify({'success': False, 'message': 'id_product inválido'}), 400
        deleted = RbcmProductCardMap.query.filter_by(rbpcm_id_product=id_product).delete()
    elif rbset_id and rbcar_id:
        q = RbcmProductCardMap.query.filter_by(
            rbpcm_rbset_id=rbset_id, rbpcm_rbcar_id=rbcar_id
        )
        if foil in ('N', 'S'):
            q = q.filter(RbcmProductCardMap.rbpcm_foil == foil)
        deleted = q.delete()
    else:
        return jsonify({'success': False, 'message': 'Debes indicar id_product o (rbset_id + rbcar_id)'}), 400

    db.session.commit()
    return jsonify({'success': True, 'deleted': deleted})


@price_bp.route('/cardmarket-mappings')
@login_required
def cardmarket_mappings():
    """Listado UNIFICADO mapped + unmapped del último snapshot.

    Filtros opcionales (todos por substring case-insensitive):
       q_product:    nombre del producto (o id_product literal)
       q_card:       nombre de la carta interna o card_id
       q_set:        rbset_id
       only:         all | mapped | unmapped (default all)
       include_nonsingles: '1' incluye boosters/displays (default '0')

    Reglas de filtrado (importante):
       - q_product: aplica SIEMPRE (sobre el producto Cardmarket).
       - q_card / q_set: aplican SÓLO sobre productos mapeados.
         Si only=unmapped y se ha escrito q_card o q_set, esos filtros
         se IGNORAN (no tiene sentido buscar carta/set en algo sin mapear).
         Si only=all y se escribe q_card/q_set, los unmapped NO se filtran:
         se mantienen en el resultado para que el usuario pueda mapearlos.

    Orden: nombre_producto, rbcar_id, id_product, precio, rbset_id.
    """
    q_product = (request.args.get('q_product') or '').strip()
    q_card = (request.args.get('q_card') or '').strip()
    q_set = (request.args.get('q_set') or '').strip()
    only = request.args.get('only', 'all')  # all | mapped | unmapped
    include_nonsingles = request.args.get('include_nonsingles', '0') == '1'

    latest_date = db.session.query(func.max(RbcmProduct.rbprd_date)).scalar()
    if not latest_date:
        return jsonify({'success': True, 'rows': [], 'count': 0,
                        'message': 'No hay datos cargados'})

    # Última fecha de precio por producto + lookup de precio low.
    latest_price_per_prod = dict(
        db.session.query(
            RbcmPrice.rbprc_id_product,
            func.max(RbcmPrice.rbprc_date),
        ).group_by(RbcmPrice.rbprc_id_product).all()
    )
    low_lookup = {}
    if latest_price_per_prod:
        for p in RbcmPrice.query.all():
            if latest_price_per_prod.get(p.rbprc_id_product) == p.rbprc_date:
                low_lookup[p.rbprc_id_product] = (
                    float(p.rbprc_low) if p.rbprc_low is not None else None
                )

    # Productos del último día. Si include_nonsingles=False, sólo singles.
    products_q = RbcmProduct.query.filter(RbcmProduct.rbprd_date == latest_date)
    if not include_nonsingles:
        products_q = products_q.filter(RbcmProduct.rbprd_type == 'single')
    if q_product:
        like = f'%{q_product}%'
        products_q = products_q.filter(
            (RbcmProduct.rbprd_name.ilike(like)) |
            (db.cast(RbcmProduct.rbprd_id_product, db.Text).ilike(like))
        )
    products = products_q.all()

    mappings = {
        m.rbpcm_id_product: m
        for m in RbcmProductCardMap.query.all()
    }
    cards_idx = {
        (c.rbcar_rbset_id, c.rbcar_id): c
        for c in RbCard.query.all()
    }

    q_card_l = q_card.lower() if q_card else ''
    q_set_l = q_set.lower() if q_set else ''

    rows = []
    for p in products:
        m = mappings.get(p.rbprd_id_product)
        is_mapped = m is not None

        # Filtro mapped/unmapped (siempre aplica)
        if only == 'mapped' and not is_mapped:
            continue
        if only == 'unmapped' and is_mapped:
            continue

        rbset_id = m.rbpcm_rbset_id if m else None
        rbcar_id = m.rbpcm_rbcar_id if m else None
        rbpcm_foil = m.rbpcm_foil if m else None
        match_type = m.rbpcm_match_type if m else None
        card = cards_idx.get((rbset_id, rbcar_id)) if rbset_id and rbcar_id else None
        card_name = card.rbcar_name if card else None

        # q_card y q_set sólo se aplican a filas mapeadas. Las no mapeadas
        # se mantienen siempre que pasen q_product (ya filtrado en SQL).
        if is_mapped and q_card_l:
            in_card = (
                (rbcar_id or '').lower().find(q_card_l) >= 0
                or (card_name or '').lower().find(q_card_l) >= 0
            )
            if not in_card:
                continue
        if is_mapped and q_set_l:
            if (rbset_id or '').lower().find(q_set_l) < 0:
                continue

        rows.append({
            'id_product': p.rbprd_id_product,
            'product_name': p.rbprd_name,
            'product_type': p.rbprd_type,
            'low_price': low_lookup.get(p.rbprd_id_product),
            'rbset_id': rbset_id,
            'rbcar_id': rbcar_id,
            'rbcar_name': card_name,
            'rbpcm_foil': rbpcm_foil,
            'match_type': match_type,
            'mapped': is_mapped,
        })

    rows.sort(key=lambda r: (
        (r['product_name'] or '').lower(),
        (r['rbcar_id'] or ''),
        r['id_product'],
        (r['low_price'] if r['low_price'] is not None else 9_999_999),
        (r['rbset_id'] or ''),
    ))

    # Stats globales (independientes de filtros) para mostrar en header
    total_products = len(products)
    total_mapped = sum(1 for p in products if p.rbprd_id_product in mappings)
    total_unmapped = total_products - total_mapped

    return jsonify({
        'success': True,
        'count': len(rows),
        'rows': rows,
        'stats': {
            'total_in_snapshot': total_products,
            'mapped': total_mapped,
            'unmapped': total_unmapped,
            'snapshot_date': latest_date,
        },
    })


@price_bp.route('/cardmarket-auto-match', methods=['POST'])
@login_required
def cardmarket_auto_match():
    """Lanza el auto-matcher. Body opcional:
       {dry_run: bool=false, max_groups: int=null}
    Devuelve stats y muestras de los emparejamientos propuestos."""
    from app.services.cardmarket_matcher import auto_match
    body = request.get_json(silent=True) or {}
    dry_run = bool(body.get('dry_run', False))
    max_groups = body.get('max_groups')
    try:
        max_groups = int(max_groups) if max_groups is not None else None
    except (TypeError, ValueError):
        max_groups = None
    try:
        result = auto_match(dry_run=dry_run, max_groups=max_groups)
        return jsonify(result)
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@price_bp.route('/cardmarket-upsert-product', methods=['POST'])
@login_required
def cardmarket_upsert_product():
    """Crea o actualiza una fila de rbproducts.
    PK: (rbpdt_id_set, rbpdt_id_product)."""
    data = request.get_json() or {}
    rbpdt_id_set = (data.get('rbpdt_id_set') or '').strip()
    try:
        rbpdt_id_product = int(data.get('rbpdt_id_product'))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'rbpdt_id_product inválido'}), 400
    rbpdt_name = (data.get('rbpdt_name') or '').strip()

    if not rbpdt_id_set or not rbpdt_name:
        return jsonify({'success': False, 'message': 'rbpdt_id_set y rbpdt_name son obligatorios'}), 400

    existing = RbProducts.query.filter_by(
        rbpdt_id_set=rbpdt_id_set, rbpdt_id_product=rbpdt_id_product
    ).first()
    status = 'updated' if existing else 'created'

    if not existing:
        existing = RbProducts(
            rbpdt_id_set=rbpdt_id_set,
            rbpdt_id_product=rbpdt_id_product,
            rbpdt_name=rbpdt_name,
        )
        db.session.add(existing)

    for f in _PRODUCT_FIELDS:
        if f in ('rbpdt_id_set', 'rbpdt_id_product'):
            continue
        if f in data:
            value = data.get(f)
            setattr(existing, f, value if value not in ('',) else None)

    if not existing.rbpdt_name:
        existing.rbpdt_name = rbpdt_name

    db.session.commit()
    return jsonify({
        'success': True,
        'status': status,
        'rbpdt_id_set': rbpdt_id_set,
        'rbpdt_id_product': rbpdt_id_product,
        'rbpdt_name': existing.rbpdt_name,
    })
