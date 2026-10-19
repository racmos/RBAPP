"""
Deck routes module.
"""
from types import SimpleNamespace
from urllib.parse import urlencode
from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user
from sqlalchemy import func
from app import db
from app.models import RbDeck, RbSet, RbCard, RbCollection
from app.schemas.validators import DeckSave
from app.schemas.validation import validate_json
from app.services.pricing import latest_price_for_card
from datetime import datetime


deck_bp = Blueprint('deck', __name__, url_prefix='/riftbound/deck')


# ---------------------------------------------------------------------------
# Helpers de enriquecimiento
# ---------------------------------------------------------------------------

def _legend_for_deck(rbdeck):
    """Devuelve (legend_image, legend_name, legend_tags) buscando la primera
    carta de tipo Legend en el JSON `rbdck_cards.main`. Si no hay, None."""
    cards = (rbdeck.rbdck_cards or {}).get('main', [])
    if not cards:
        return (None, None, None)
    # Carga las cartas referenciadas en bloque para evitar N+1
    keys = [(c.get('set'), c.get('id')) for c in cards if c.get('set') and c.get('id')]
    if not keys:
        return (None, None, None)
    rbcards = RbCard.query.filter(
        db.tuple_(RbCard.rbcar_rbset_id, RbCard.rbcar_id).in_(keys)
    ).all()
    by_key = {(c.rbcar_rbset_id, c.rbcar_id): c for c in rbcards}
    for c in cards:
        rbc = by_key.get((c.get('set'), c.get('id')))
        if rbc and (rbc.rbcar_type or '').lower() == 'legend':
            img = rbc.image_src
            return (img, rbc.rbcar_name, rbc.rbcar_tags)
    return (None, None, None)


def _row_for_listing(rbdeck):
    """Adapta un RbDeck a un SimpleNamespace con los atributos que espera la
    plantilla `deck.html` (incluye `legend_*` y `seq` para construir URLs)."""
    legend_image, legend_name, legend_tags = _legend_for_deck(rbdeck)
    return SimpleNamespace(
        id=rbdeck.id,
        name=rbdeck.rbdck_name,
        user=rbdeck.rbdck_user,
        snapshot=rbdeck.rbdck_snapshot,
        format=rbdeck.rbdck_format,
        mode=rbdeck.rbdck_mode,
        seq=rbdeck.rbdck_seq or 1,
        legend_image=legend_image,
        legend_name=legend_name,
        legend_tags=legend_tags,
    )


def _owned_quantities(username, keys):
    """{(set_id, card_id): total copies} the user owns, all foil variants and
    collection lines added up. `keys` is an iterable of (set_id, card_id)."""
    keys = list(keys)
    owned = {}
    if not keys or not username:
        return owned
    rows = RbCollection.query.filter(
        RbCollection.rbcol_user == username,
        db.tuple_(RbCollection.rbcol_rbset_id, RbCollection.rbcol_rbcar_id).in_(keys),
    ).all()
    for r in rows:
        key = (r.rbcol_rbset_id, r.rbcol_rbcar_id)
        owned[key] = owned.get(key, 0) + r.rbcol_quantity
    return owned


def _enrich_cards_for_view(rbdeck, viewer_username):
    """Construye la lista plana de cartas para `deck_view.html` con los campos
    que la plantilla espera: set_id, card_id, card_name, quantity, sideboard
    ('N'/'S'), image, have, missing, price.
    `have` = min(copias que tiene el USUARIO QUE MIRA, copias necesarias): se
    calcula con la colección del visitante, nunca con la del propietario del
    deck (DECK-1).
    """
    raw = rbdeck.rbdck_cards or {}
    main = raw.get('main', []) or []
    side = raw.get('sideboard', []) or []

    # Bloque de claves para hacer fetch en lote (evita N+1)
    keys = list({(c.get('set'), c.get('id')) for c in (main + side)
                 if c.get('set') and c.get('id')})
    rbcards = RbCard.query.filter(
        db.tuple_(RbCard.rbcar_rbset_id, RbCard.rbcar_id).in_(keys)
    ).all() if keys else []
    cards_by_key = {(c.rbcar_rbset_id, c.rbcar_id): c for c in rbcards}

    owned_by_key = _owned_quantities(viewer_username, keys)

    def _build(c, sideboard_flag):
        set_id = c.get('set') or ''
        card_id = c.get('id') or ''
        qty = int(c.get('qty') or 0)
        rbc = cards_by_key.get((set_id, card_id))
        image = rbc.image_src if rbc else None
        have = min(owned_by_key.get((set_id, card_id), 0), qty)
        missing = max(0, qty - have)
        # Deck cards are priced as non-foil with the same chain as the collection (PRC-2).
        price = latest_price_for_card(set_id, card_id,
                                      rarity=rbc.rbcar_rarity if rbc else None, foil='N')
        return {
            'set_id': set_id,
            'card_id': card_id,
            'card_name': rbc.rbcar_name if rbc else card_id,
            'quantity': qty,
            'sideboard': sideboard_flag,   # 'N' o 'S' tal y como lo usa la plantilla
            'image': image,
            'have': have,
            'missing': missing,
            'price': price,
        }

    enriched = [_build(c, 'N') for c in main] + [_build(c, 'S') for c in side]
    return enriched


def _wrap_deck_for_view(rbdeck, viewer_username):
    """Devuelve un SimpleNamespace con la forma que `deck_view.html` espera:
       deck.name, .user, .mode, .format, .description, .max_set, .max_set_name,
       .cards (plana, enriquecida con have/missing del visitante)."""
    max_set = rbdeck.rbdck_max_set
    max_set_name = None
    if max_set:
        s = RbSet.query.get(max_set)
        max_set_name = s.rbset_name if s else None
    return SimpleNamespace(
        id=rbdeck.id,
        name=rbdeck.rbdck_name,
        user=rbdeck.rbdck_user,
        mode=rbdeck.rbdck_mode,
        format=rbdeck.rbdck_format,
        description=rbdeck.rbdck_description,
        max_set=max_set,
        max_set_name=max_set_name,
        seq=rbdeck.rbdck_seq or 1,
        cards=_enrich_cards_for_view(rbdeck, viewer_username),
    )


# ---------------------------------------------------------------------------
# Listado
# ---------------------------------------------------------------------------

def _deck_uses_any_set(rbdeck, sets_filter):
    """True si el deck contiene al menos UNA carta perteneciente a alguno de
    los sets del filtro."""
    if not sets_filter:
        return True
    raw = rbdeck.rbdck_cards or {}
    for c in (raw.get('main', []) or []) + (raw.get('sideboard', []) or []):
        if c.get('set') in sets_filter:
            return True
    return False


def _deck_has_legend(rbdeck, legend_name, legends_index):
    """True si el deck contiene una carta tipo Legend cuyo `rbcar_name` matchea
    `legend_name` (case-insensitive). `legends_index` es {(set,id) -> name}.
    """
    if not legend_name:
        return True
    target = legend_name.strip().lower()
    raw = rbdeck.rbdck_cards or {}
    for c in (raw.get('main', []) or []):
        n = legends_index.get((c.get('set'), c.get('id')))
        if n and n.lower() == target:
            return True
    return False


def _legends_index():
    """Diccionario {(rbset_id, rbcar_id): rbcar_name} de TODAS las cartas
    tipo Legend. Usado para post-filtrar decks por legend en Python."""
    rows = RbCard.query.filter(
        func.lower(RbCard.rbcar_type) == 'legend'
    ).all()
    return {(c.rbcar_rbset_id, c.rbcar_id): c.rbcar_name for c in rows}


@deck_bp.route('')
@login_required
def deck():
    """Listado My Decks + All Public Decks con filtros, paginación independiente
    y enriquecimiento de legend.

    Los filtros f_set y f_legend NO se pueden traducir a SQL puro porque las
    cartas viven en `rbdck_cards` (columna JSON). Se aplican post-fetch en
    Python; la paginación se hace después del filtrado para que las páginas
    contengan exactamente per_page resultados ya filtrados.
    """
    f_name = (request.args.get('filter_name') or '').strip()
    f_user = (request.args.get('filter_user') or '').strip()
    f_format = (request.args.get('filter_format') or '').strip()
    f_mode = (request.args.get('filter_mode') or '').strip()
    f_set_csv = (request.args.get('filter_set') or '').strip()
    f_legend = (request.args.get('filter_legend') or '').strip()
    sort_by = request.args.get('sort_by', 'date_desc')
    page_user = request.args.get('page_user', 1, type=int)
    page_all = request.args.get('page_all', 1, type=int)
    per_page = 20

    sets_filter = {s.strip() for s in f_set_csv.split(',') if s.strip()} if f_set_csv else set()

    def _apply_sql(q, scope):
        if f_name:
            q = q.filter(RbDeck.rbdck_name.ilike(f'%{f_name}%'))
        if scope == 'all' and f_user:
            q = q.filter(RbDeck.rbdck_user.ilike(f'%{f_user}%'))
        if f_format:
            q = q.filter(RbDeck.rbdck_format == f_format)
        if f_mode:
            q = q.filter(RbDeck.rbdck_mode == f_mode)
        return q

    user_q = _apply_sql(
        RbDeck.query.filter(RbDeck.rbdck_user == current_user.username), 'user'
    )
    all_q = _apply_sql(RbDeck.query, 'all')

    if sort_by == 'date_asc':
        user_q = user_q.order_by(RbDeck.rbdck_snapshot.asc())
        all_q = all_q.order_by(RbDeck.rbdck_snapshot.asc())
    else:
        user_q = user_q.order_by(RbDeck.rbdck_snapshot.desc())
        all_q = all_q.order_by(RbDeck.rbdck_snapshot.desc())

    # Post-filtros JSON (set + legend). Carga en memoria los candidatos que ya
    # han pasado los filtros SQL, los reduce y luego pagina manualmente.
    legends_idx = _legends_index() if f_legend else {}

    def _materialize_filtered(query):
        items = query.all()
        if sets_filter:
            items = [d for d in items if _deck_uses_any_set(d, sets_filter)]
        if f_legend:
            items = [d for d in items if _deck_has_legend(d, f_legend, legends_idx)]
        return items

    user_items = _materialize_filtered(user_q)
    all_items = _materialize_filtered(all_q)

    user_pagination = _SimplePagination(user_items, page_user, per_page)
    all_pagination = _SimplePagination(all_items, page_all, per_page)

    user_decks = [_row_for_listing(d) for d in user_pagination.items]
    all_decks = [_row_for_listing(d) for d in all_pagination.items]

    sets = RbSet.query.order_by(RbSet.rbset_id).all()
    formats = ['Standard', 'Limited']
    modes = ['1v1', '2v2']

    def get_page_url(page_key, page_num):
        args = request.args.to_dict(flat=False)
        args[page_key] = [str(page_num)]
        return urlencode(args, doseq=True)

    return render_template(
        'deck.html',
        user_decks=user_decks,
        all_decks=all_decks,
        user_pagination=user_pagination,
        all_pagination=all_pagination,
        sets=sets,
        formats=formats,
        modes=modes,
        get_page_url=get_page_url,
    )


class _SimplePagination:
    """Pagination ligero compatible con la API que usa la plantilla
    (items, page, pages, has_prev, has_next, prev_num, next_num)."""

    def __init__(self, items, page, per_page):
        page = max(1, int(page or 1))
        self.total = len(items)
        self.per_page = per_page
        self.pages = max(1, (self.total + per_page - 1) // per_page)
        self.page = min(page, self.pages)
        start = (self.page - 1) * per_page
        self.items = items[start:start + per_page]
        self.has_prev = self.page > 1
        self.has_next = self.page < self.pages
        self.prev_num = self.page - 1 if self.has_prev else None
        self.next_num = self.page + 1 if self.has_next else None


@deck_bp.route('/api/legends')
@login_required
def api_legends():
    """Devuelve las cartas tipo Legend para alimentar el dropdown del filtro.

    Sólo se incluyen leyendas de SETS NO PROMO. Convención del proyecto:
    los sets promo terminan en 'X' (OGNX, SFDX, ...). Una legend del set
    promo es la misma carta que la del set base, así que mostrarla en el
    dropdown sería ruido visual.

    El matching de decks por legend (`_deck_has_legend`) se hace por NOMBRE,
    así que aunque un deck use la versión promo de la legend, el filtro
    seguirá funcionando.

    Forma esperada por el JS:
      { legends: [{name, tags, set_id, card_id, image}, ...] }
    """
    legends = RbCard.query.filter(
        func.lower(RbCard.rbcar_type) == 'legend',
        # Excluir sets promo (terminados en X o x)
        ~RbCard.rbcar_rbset_id.ilike('%X'),
    ).order_by(RbCard.rbcar_name, RbCard.rbcar_rbset_id).all()

    # Dedup por nombre. Si hay varias copias en sets no-promo distintos
    # (raro), nos quedamos con la primera con imagen.
    seen = {}
    for c in legends:
        prev = seen.get(c.rbcar_name)
        if prev is None:
            seen[c.rbcar_name] = c
            continue
        # Sustituye la previa si la actual tiene imagen y la previa no
        if c.image and not prev.image:
            seen[c.rbcar_name] = c

    out = []
    for c in sorted(seen.values(), key=lambda x: (x.rbcar_name or '').lower()):
        image = c.image_src
        out.append({
            'name': c.rbcar_name,
            'tags': c.rbcar_tags or '',
            'set_id': c.rbcar_rbset_id,
            'card_id': c.rbcar_id,
            'image': image,
        })
    return jsonify({'legends': out})


@deck_bp.route('/view/<int:deck_id>')
@login_required
def view_deck_by_id(deck_id):
    """View a deck by primary key. Decks are visible to every logged-in user
    (this is how shared decks are reached); have/missing come from the viewer."""
    rbdeck = RbDeck.query.get(deck_id)
    if not rbdeck:
        abort(404)
    return render_template('deck_view.html',
                           deck=_wrap_deck_for_view(rbdeck, current_user.username))


@deck_bp.route('/view/<name>')
@login_required
def view_deck_by_name(name):
    """View the viewer's latest version of a deck by name. Only the viewer's own
    decks are looked up, so a name never reveals who else has it (D19)."""
    rbdeck = (
        RbDeck.query.filter(RbDeck.rbdck_user == current_user.username,
                            RbDeck.rbdck_name == name)
                    .order_by(RbDeck.rbdck_seq.desc())
                    .first()
    )
    if not rbdeck:
        abort(404)
    return render_template('deck_view.html',
                           deck=_wrap_deck_for_view(rbdeck, current_user.username))


@deck_bp.route('/view/<name>/<int:seq>')
@login_required
def view_deck_by_name_and_seq(name, seq):
    """View one of the viewer's own versions (name + seq); 404 if they have none (D19)."""
    rbdeck = (
        RbDeck.query.filter(RbDeck.rbdck_user == current_user.username,
                            RbDeck.rbdck_name == name,
                            RbDeck.rbdck_seq == seq).first()
    )
    if not rbdeck:
        abort(404)
    return render_template('deck_view.html',
                           deck=_wrap_deck_for_view(rbdeck, current_user.username))


@deck_bp.route('/versions/<name>')
@login_required
def deck_versions(name):
    """The current user's versions of a deck, newest first (DECK-3)."""
    decks = RbDeck.get_versions(current_user.username, name)

    return jsonify({
        'success': True,
        'versions': [{
            'id': d.id,
            'name': d.rbdck_name,
            'seq': d.rbdck_seq or 1,
            'snapshot': d.rbdck_snapshot.isoformat(),
            'mode': d.rbdck_mode,
            'format': d.rbdck_format,
            'ncards': d.rbdck_ncards,
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

    # Calcular total de cartas y construir el JSON de cartas
    total_cards = 0
    cards_json = None
    sets_in_deck = set()
    if data.rbdck_cards:
        main_cards = data.rbdck_cards.main or []
        sideboard = data.rbdck_cards.sideboard or []
        for card in main_cards + sideboard:
            total_cards += card.qty
            if card.set:
                sets_in_deck.add(card.set)
        cards_json = {
            'main': [{'set': c.set, 'id': c.id, 'qty': c.qty} for c in main_cards],
            'sideboard': [{'set': c.set, 'id': c.id, 'qty': c.qty} for c in sideboard]
        }

    # rbdck_max_set es opcional en el modelo actual; si no viene lo deducimos
    # como el mayor (alfabéticamente) de los sets usados en el deck. Sirve
    # como referencia del set más reciente con el que se construyó.
    max_set = data.rbdck_max_set
    if not max_set:
        max_set = max(sets_in_deck) if sets_in_deck else None

    # Calcula el siguiente seq para permitir varias versiones del mismo nombre
    next_seq = RbDeck.get_next_seq(current_user.username, data.rbdck_name)

    new_deck = RbDeck(
        rbdck_user=current_user.username,
        rbdck_name=data.rbdck_name,
        rbdck_seq=next_seq,
        rbdck_snapshot=datetime.utcnow(),
        rbdck_description=data.rbdck_description,
        rbdck_mode=data.rbdck_mode or '1v1',
        rbdck_format=data.rbdck_format or 'Standard',
        rbdck_max_set=max_set,
        rbdck_ncards=total_cards or 1,
        rbdck_cards=cards_json,
    )

    db.session.add(new_deck)
    db.session.commit()

    return jsonify({
        'success': True,
        'id': new_deck.id,
        'name': new_deck.rbdck_name,
        'seq': new_deck.rbdck_seq,
    })
