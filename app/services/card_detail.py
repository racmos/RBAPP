"""Card detail and price history (F2-d S1-S9).

Reads only: the catalog (`rbcards`/`rbset`), the Cardmarket tables filled by
the daily load (F4-b), the user's collection rows and decks, and the ban table
(F2-a). One batched query per data need; filtering and ordering run in Python
(no PostgreSQL-only SQL), like `card_list`.
"""
import datetime as _datetime

from sqlalchemy import tuple_

from app import db
from app.models import RbCard, RbCollection, RbDeck, RbSet, RbcmPrice, RbcmProductCardMap
from app.services import bans as bans_service
from app.services import catalog
from app.services.pricing import price_summaries, resolve_price_with_source

_DETAIL_COLUMNS = (
    ('low', 'rbprc_low'),
    ('avg1', 'rbprc_avg1'),
    ('avg7', 'rbprc_avg7'),
    ('avg30', 'rbprc_avg30'),
    ('trend', 'rbprc_trend'),
    ('low_foil', 'rbprc_low_foil'),
    ('avg1_foil', 'rbprc_avg1_foil'),
    ('avg7_foil', 'rbprc_avg7_foil'),
    ('avg30_foil', 'rbprc_avg30_foil'),
    ('trend_foil', 'rbprc_trend_foil'),
    ('low_ex', 'rbprc_low_ex'),
)

_RANGE_DAYS = {'30d': 30, '90d': 90, '1y': 365}


def _float(value):
    return float(value) if value is not None else None


def _iso_day(text):
    """'YYYYMMDD' to 'YYYY-MM-DD'."""
    return f'{text[0:4]}-{text[4:6]}-{text[6:8]}' if text else None


def _iso_utc(moment):
    """Naive UTC datetime to 'YYYY-MM-DDTHH:MM:SSZ'."""
    return moment.strftime('%Y-%m-%dT%H:%M:%SZ') if moment is not None else None


def _canonical(products, foil_slot):
    """Lowest product id for one foil slot: exact, else unclassified, else any."""
    exact = unclassified = any_match = None
    for foil, product in products:
        if product is None:
            continue
        if foil == foil_slot and (exact is None or product < exact):
            exact = product
        if foil is None and (unclassified is None or product < unclassified):
            unclassified = product
        if any_match is None or product < any_match:
            any_match = product
    if exact is not None:
        return exact
    return unclassified if unclassified is not None else any_match


def _detail_columns(row):
    return {name: _float(getattr(row, column)) for name, column in _DETAIL_COLUMNS}


def _card_mini(card, *, market, owned_total, is_base):
    parsed_type, supertype = catalog.parse_type(card.rbcar_type)
    return {
        'set_id': card.rbcar_rbset_id,
        'card_id': card.rbcar_id,
        'key': f'{card.rbcar_rbset_id}-{card.rbcar_id}',
        'name': card.rbcar_name,
        'domains': catalog.parse_domains(card.rbcar_domain),
        'type': parsed_type,
        'supertype': supertype,
        'rarity': card.rbcar_rarity,
        'image_src': card.image_src,
        'image_thumb_src': None,
        'is_base': is_base,
        'market': market,
        'owned_total': owned_total,
    }


def _owned_aggregates(rows):
    totals = {}
    for row in rows:
        key = (row.rbcol_rbset_id, row.rbcol_rbcar_id)
        entry = totals.setdefault(key, {'total': 0, 'foil': 0})
        entry['total'] += row.rbcol_quantity or 0
        if row.rbcol_foil == 'S':
            entry['foil'] += row.rbcol_quantity or 0
    return totals


def get_card_detail(set_id, card_id, username):
    """The `CardDetail` of one printing, or None when the card is missing."""
    all_sets = db.session.query(RbSet).all()
    set_rank = catalog.set_order(all_sets)
    sets_by_id = {s.rbset_id: s for s in all_sets}
    all_cards = db.session.query(RbCard).all()
    card = next((c for c in all_cards
                 if c.rbcar_rbset_id == set_id and c.rbcar_id == card_id), None)
    if card is None:
        return None
    base_keys = catalog.base_printing_keys(all_cards, set_rank)
    bans = bans_service.ban_map()

    key = (set_id, card_id)
    wanted = catalog.name_key(card.rbcar_name)
    printings = sorted(
        (c for c in all_cards if catalog.name_key(c.rbcar_name) == wanted),
        key=lambda c: catalog.natural_key(set_rank.get(c.rbcar_rbset_id), c.rbcar_id),
    )
    summaries = price_summaries([
        (c.rbcar_rbset_id, c.rbcar_id, c.rbcar_rarity, _foilable(c))
        for c in printings
    ])

    mappings = db.session.query(
        RbcmProductCardMap.rbpcm_foil,
        RbcmProductCardMap.rbpcm_id_product,
    ).filter(
        RbcmProductCardMap.rbpcm_rbset_id == set_id,
        RbcmProductCardMap.rbpcm_rbcar_id == card_id,
    ).all()
    products = [(foil, product) for foil, product in mappings]
    product_n = _canonical(products, 'N')
    foilable = _foilable(card)
    product_s = _canonical(products, 'S') if foilable else None
    if product_s == product_n:
        product_s = None

    price_detail = None
    if product_n is not None:
        wanted_products = [product_n] + ([product_s] if product_s is not None else [])
        rows = db.session.query(RbcmPrice).filter(
            RbcmPrice.rbprc_id_product.in_(wanted_products),
        ).order_by(RbcmPrice.rbprc_date.desc()).all()
        latest = {}
        for row in rows:
            latest.setdefault(row.rbprc_id_product, row)
        row_n = latest.get(product_n)
        price_detail = {
            'date': _iso_day(row_n.rbprc_date),
            'product_id': product_n,
            'columns': _detail_columns(row_n),
            'foil_product_id': product_s,
            'foil_columns': (_detail_columns(latest[product_s])
                             if product_s is not None and product_s in latest
                             else None),
        }

    printing_keys = [(c.rbcar_rbset_id, c.rbcar_id) for c in printings]
    lines = db.session.query(RbCollection).filter(
        RbCollection.rbcol_user == username,
        tuple_(RbCollection.rbcol_rbset_id,
               RbCollection.rbcol_rbcar_id).in_(printing_keys),
    ).all() if username and printing_keys else []
    totals = _owned_aggregates(lines)

    my_lines = sorted(
        (row for row in lines
         if (row.rbcol_rbset_id, row.rbcol_rbcar_id) == key),
        key=lambda row: (row.rbcol_foil or '',
                         row.rbcol_condition or '',
                         row.rbcol_language or '',
                         row.rbcol_id or 0),
    )

    name_by_card = {(c.rbcar_rbset_id, c.rbcar_id): catalog.name_key(c.rbcar_name)
                    for c in all_cards}
    decks = db.session.query(RbDeck).filter(RbDeck.rbdck_user == username).all() \
        if username else []
    best = {}
    for deck in decks:
        known = best.get(deck.rbdck_name)
        if known is None or (deck.rbdck_seq or 0) > (known.rbdck_seq or 0):
            best[deck.rbdck_name] = deck
    in_decks = []
    for name in sorted(best):
        deck = best[name]
        payload = deck.rbdck_cards or {}
        total = 0
        for entry in list(payload.get('main') or []) + list(payload.get('sideboard') or []):
            if not isinstance(entry, dict):
                continue
            if name_by_card.get((entry.get('set'), entry.get('id'))) == wanted:
                total += entry.get('qty') or 0
        if total > 0:
            in_decks.append({'deck_id': deck.id, 'name': name, 'qty': total})

    tags = {t.casefold() for t in catalog.parse_tags(card.rbcar_tags)}
    candidates = []
    if tags:
        for other in all_cards:
            other_key = (other.rbcar_rbset_id, other.rbcar_id)
            if (catalog.name_key(other.rbcar_name) == wanted
                    or other_key not in base_keys):
                continue
            shared = tags & {t.casefold()
                             for t in catalog.parse_tags(other.rbcar_tags)}
            if shared:
                candidates.append((len(shared), other.rbcar_name.casefold(), other))
        candidates.sort(key=lambda item: (-item[0], item[1]))

    summary = catalog.card_summary(
        card, set_rank=set_rank, base_keys=base_keys,
        price=summaries.get(key), bans=bans,
        owned=totals.get(key, {'total': 0, 'foil': 0}),
    )
    the_set = sets_by_id.get(set_id)
    summary.update({
        'ability': card.rbcar_ability,
        'set': {
            'id': set_id,
            'name': the_set.rbset_name if the_set is not None else set_id,
            'released_on': (the_set.rbset_outdat.isoformat()
                            if the_set is not None and the_set.rbset_outdat else None),
        },
        'price_detail': price_detail,
        'printings': [
            _card_mini(c,
                       market=(summaries.get((c.rbcar_rbset_id, c.rbcar_id)) or {}).get('market'),
                       owned_total=totals.get(
                           (c.rbcar_rbset_id, c.rbcar_id),
                           {'total': 0})['total'],
                       is_base=(c.rbcar_rbset_id, c.rbcar_id) in base_keys)
            for c in printings
        ],
        'related': [
            _card_mini(c,
                       market=(summaries.get((c.rbcar_rbset_id, c.rbcar_id)) or {}).get('market'),
                       owned_total=totals.get(
                           (c.rbcar_rbset_id, c.rbcar_id),
                           {'total': 0})['total'],
                       is_base=True)
            for _, _, c in candidates[:12]
        ],
        'ban_info': bans_service.ban_info(card.rbcar_name, bans),
        'my_lines': [{
            'id': row.rbcol_id,
            'foil': row.rbcol_foil == 'S',
            'qty': row.rbcol_quantity,
            'condition': row.rbcol_condition,
            'language': row.rbcol_language,
            'selling': (row.rbcol_selling or 'N') in ('Y', 'S'),
            'sell_price': _float(row.rbcol_sell_price),
            'purchase_price': _float(row.rbcol_purchase_price),
            'sell_qty': row.rbcol_sell_qty,
            'playset': row.rbcol_playset,
            'updated_at': _iso_utc(row.rbcol_chadat),
        } for row in my_lines],
        'in_decks': in_decks,
    })
    return summary


def _foilable(card):
    parsed_type, _ = catalog.parse_type(card.rbcar_type)
    return catalog.is_foilable(parsed_type, card.rbcar_rarity)


def get_card_prices(set_id, card_id, range_):
    """The price history of one card, or None when the card is missing."""
    card = db.session.query(RbCard).filter(
        RbCard.rbcar_rbset_id == set_id,
        RbCard.rbcar_id == card_id,
    ).first()
    if card is None:
        return None
    parsed_type, _ = catalog.parse_type(card.rbcar_type)
    foilable = catalog.is_foilable(parsed_type, card.rbcar_rarity)

    mappings = db.session.query(
        RbcmProductCardMap.rbpcm_foil,
        RbcmProductCardMap.rbpcm_id_product,
    ).filter(
        RbcmProductCardMap.rbpcm_rbset_id == set_id,
        RbcmProductCardMap.rbpcm_rbcar_id == card_id,
    ).all()
    products = [(foil, product) for foil, product in mappings]
    product_n = _canonical(products, 'N')
    product_s = _canonical(products, 'S') if foilable else None
    if product_s == product_n:
        product_s = None

    points = []
    if product_n is not None:
        wanted_products = [product_n] + ([product_s] if product_s is not None else [])
        rows = db.session.query(RbcmPrice).filter(
            RbcmPrice.rbprc_id_product.in_(wanted_products),
        ).order_by(RbcmPrice.rbprc_date.asc()).all()
        n_rows = [row for row in rows if row.rbprc_id_product == product_n]
        s_by_date = {row.rbprc_date: row for row in rows
                     if product_s is not None and row.rbprc_id_product == product_s}
        days = _RANGE_DAYS.get(range_)
        cutoff = None
        if days is not None and n_rows:
            latest_day = _datetime.date(int(n_rows[-1].rbprc_date[0:4]),
                                        int(n_rows[-1].rbprc_date[4:6]),
                                        int(n_rows[-1].rbprc_date[6:8]))
            cutoff = (latest_day - _datetime.timedelta(days=days)).strftime('%Y%m%d')
        for row in n_rows:
            if cutoff is not None and (row.rbprc_date or '') < cutoff:
                continue
            market, _ = resolve_price_with_source(row, rarity=card.rbcar_rarity,
                                                 foil='N')
            s_row = s_by_date.get(row.rbprc_date)
            market_foil, _ = resolve_price_with_source(s_row, rarity=card.rbcar_rarity,
                                                      foil='S')
            points.append({
                'date': _iso_day(row.rbprc_date),
                'market': market,
                'low': _float(row.rbprc_low),
                'avg7': _float(row.rbprc_avg7),
                'avg30': _float(row.rbprc_avg30),
                'market_foil': market_foil,
            })

    return {
        'range': range_,
        'currency': 'EUR',
        'foilable': foilable,
        'product_id': product_n,
        'points': points,
    }
