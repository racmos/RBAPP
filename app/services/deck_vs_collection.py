"""A deck against the user's collection (F5-f, F5-R11): what is missing, what it costs, and
"add the missing cards to a wishlist" (owner decision 5 of
docs/requirements/F3/F3-f-wishlists-design.md).

Copies count per card NAME across printings (product.md DECK-1), over legend, champion, main,
runes, battlefields and sideboard of the current version; the workbench is not part of the deck.
For every name: `need` = the copies the deck uses, `have` = the copies of that name in the
user's collection (every printing, foil or not, every line including the copies for sale),
`missing = max(0, need - have)`. The name stands for the deck's printing of it: the first one
in deck order. Prices are the deck value's (`price_summaries` market, non-foil chain) of that
printing. Cards missing from the catalog are left out (they have no name).

No Flask objects here; `decks.DeckNotFound` and `wishlists.ListNotFound` mean a 404.
"""
import sqlalchemy as sa
from sqlalchemy import tuple_

from app import db
from app.models import RbCard, RbCollection, RbSet
from app.services import catalog, deck_rules, wishlists
from app.services.bans import name_key
from app.services.card_detail import _card_mini
from app.services.decks import VALUE_ZONES, _current, _foilable, _head, _key, _refs, normal_content
from app.services.pricing import price_summaries


def _money(value):
    return round(value + 0.0, 2)


def _compare(user, deck_id):
    """`(names, cards, base_keys, owned)`: one entry per name of the deck, in section order
    then by name, `{key (printing), zone, need, have, missing, price, name}`; the catalog rows
    by key, the base printings and the user's copies per printing of those names.
    Statements: head, version, cards, sets, prices (two), the user's copies."""
    head = _head(user, deck_id)
    version = _current(head)
    content = normal_content(version.rbdkv_content if version else None)
    cards = {(c.rbcar_rbset_id, c.rbcar_id): c for c in db.session.execute(
        sa.select(RbCard)).scalars()}

    names = {}
    for zone, _field, ref, qty in _refs(content):
        key = _key(ref)
        if zone not in VALUE_ZONES or key not in cards:
            continue
        name = name_key(cards[key].rbcar_name)
        entry = names.setdefault(name, {'key': key, 'zone': zone, 'need': 0,
                                        'name': cards[key].rbcar_name})
        entry['need'] += qty
    if not names:
        return [], cards, set(), {}

    printings = [key for key, card in cards.items() if name_key(card.rbcar_name) in names]
    base_keys = catalog.base_printing_keys(
        [cards[key] for key in printings], catalog.set_order(db.session.query(RbSet).all()))
    shown = sorted({entry['key'] for entry in names.values()})
    prices = price_summaries((s, i, cards[(s, i)].rbcar_rarity, _foilable(cards[(s, i)]))
                             for s, i in shown)
    have, owned = {}, {}
    for set_id, card_id, qty in db.session.execute(
            sa.select(RbCollection.rbcol_rbset_id, RbCollection.rbcol_rbcar_id,
                      sa.func.sum(RbCollection.rbcol_quantity))
            .where(RbCollection.rbcol_user == user.username,
                   tuple_(RbCollection.rbcol_rbset_id, RbCollection.rbcol_rbcar_id)
                   .in_(printings))
            .group_by(RbCollection.rbcol_rbset_id, RbCollection.rbcol_rbcar_id)).all():
        name = name_key(cards[(set_id, card_id)].rbcar_name)
        have[name] = have.get(name, 0) + int(qty or 0)
        owned[(set_id, card_id)] = int(qty or 0)

    zone_rank = {zone: n for n, zone in enumerate(VALUE_ZONES)}
    out = []
    for name, entry in names.items():
        entry['have'] = have.get(name, 0)
        entry['missing'] = max(0, entry['need'] - entry['have'])
        entry['price'] = (prices.get(entry['key']) or {}).get('market')
        out.append(entry)
    out.sort(key=lambda e: (zone_rank[e['zone']], deck_rules.name_sort_key(e['name'])))
    return out, cards, base_keys, owned


def _mini(entry, cards, base_keys, owned):
    key = entry['key']
    return _card_mini(cards[key], market=entry['price'], owned_total=owned.get(key, 0),
                      is_base=key in base_keys)


def vs_collection(user, deck_id):
    """`{missing: [{card: CardMini, zone, need, have, missing}], complete, names, cost_eur,
    owned_value, unpriced}` of the deck's current version. `missing` lists the names with
    missing copies; `complete` counts the names fully owned and `names` every name; `cost_eur`
    = missing x price over the missing names (`unpriced` = those without a price, which add 0);
    `owned_value` = min(need, have) x price over every name."""
    entries, cards, base_keys, owned = _compare(user, deck_id)
    missing = [e for e in entries if e['missing'] > 0]
    return {
        'missing': [{'card': _mini(e, cards, base_keys, owned), 'zone': e['zone'],
                     'need': e['need'], 'have': e['have'], 'missing': e['missing']}
                    for e in missing],
        'complete': len(entries) - len(missing),
        'names': len(entries),
        'cost_eur': _money(sum(e['missing'] * e['price'] for e in missing
                               if e['price'] is not None)),
        'owned_value': _money(sum(min(e['need'], e['have']) * e['price'] for e in entries
                                  if e['price'] is not None)),
        'unpriced': sum(1 for e in missing if e['price'] is None),
    }


def missing_to_wishlist(user, deck_id, wishlist_id=None):
    """Put the missing copies of the deck in a wishlist of the user (the default list when
    `wishlist_id` is None, created like `GET /wishlists` does). One by-printing line per
    missing name (the deck's printing, foil `any`, no max price), in `vs_collection` order,
    through `wishlists.raise_lines`: a line already there is raised to the missing count, never
    summed, so a second call changes nothing. Returns `{wishlist: {id, name}, added, merged,
    unchanged, skipped: [{card, missing, reason}], total_missing_names}`."""
    entries, cards, base_keys, owned = _compare(user, deck_id)
    missing = [e for e in entries if e['missing'] > 0]
    result = wishlists.raise_lines(user, wishlist_id, [
        {'name_key': name_key(e['name']), 'name': e['name'], 'set_id': e['key'][0],
         'card_id': e['key'][1], 'qty': e['missing']} for e in missing])
    by_key = {e['key']: e for e in missing}
    skipped = [{'card': _mini(by_key[(s['set_id'], s['card_id'])], cards, base_keys, owned),
                'missing': s['missing'], 'reason': s['reason']} for s in result['skipped']]
    return {'wishlist': result['wishlist'], 'added': result['added'],
            'merged': result['merged'], 'unchanged': result['unchanged'], 'skipped': skipped,
            'total_missing_names': len(missing)}
