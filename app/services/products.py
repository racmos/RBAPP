"""Product catalog (F14-a): `rbproducts` built from the Cardmarket non-singles.

`refresh_products(date)` runs after each daily price load (job `products_refresh`).
Only `nonsingle` rows are products (D-F14-13); rows of any other type are never
touched and no row is ever deleted. `apply_admin_patch` (F14-d S3) is the admin's
hand edit: it sets the locks the refresh respects.
"""
import sqlalchemy as sa

from app import db
from app.models import RbcmExpansion, RbcmProduct, RbProducts
from app.models.cardmarket import NOT_USED_KIND
from app.utils import clock

# The owner's taxonomy (2026-11-20): Cardmarket category -> our kind.
#   Singles -> `card` (virtual, never stored); Booster -> `booster`; Booster Boxes (`Display`; a
#   case is a booster box too) -> `booster_box`; Champion Decks -> `champion_deck`; Box Sets ->
#   `sealed_box_set`; Accessories, every subcategory -> `accessory` (the Cardmarket category name
#   stays in `rbpdt_category` as the subcategory); Sets (`RB Set`) and Sealed Products -> not
#   used (`NOT_USED_KIND`: `refresh_products` skips them); anything else -> `other`.
# NAME RULE (owner, CM-g 2026-11-20; remove the `champion_deck` + `box set` rule to drop it): in
#   Box Sets a product whose name has `deck` (the Trial Decks) is a champion deck.
# (kind, category words, name words): the first rule with a word in the category (and, when the
# rule has name words, one of them in the product name) wins; then the Sets rule (a category
# ending in `set` / `sets`); else `other`. Case-insensitive.
_ACCESSORY_WORDS = ('accessor', 'sleeve', 'playmat', 'play mat', 'binder', 'album', 'portfolio',
                    'deck box', 'storage', 'dice', 'token', 'life counter', 'protector')
_RULES = (
    (NOT_USED_KIND, ('sealed product',), None),
    ('accessory', _ACCESSORY_WORDS, None),
    ('booster_box', ('case', 'booster box', 'display'), None),
    ('booster', ('booster',), None),
    ('champion_deck', ('box set',), ('deck',)),
    ('sealed_box_set', ('box set', 'bundle', 'gift'), None),
    ('champion_deck', ('starter', 'deck'), None),
)
# Cardmarket's Sets category (`RB Set`): the category is `set` / `sets` or ends with that word
_SETS = ('set', 'sets')


class NothingToRefresh(Exception):
    """The date has no non-single products: refreshing would unlist the whole catalog."""


def kind_for(category: str | None, name: str | None = None) -> str:
    """Our kind of a Cardmarket category name and product name, case-insensitive: one of
    `PRODUCT_KINDS`, or `NOT_USED_KIND` for a category we do not use (never stored); `other`
    when no rule matches. The name counts only for the Box Sets rule."""
    text = (category or '').lower()
    title = (name or '').lower()
    for kind, words, name_words in _RULES:
        if any(word in text for word in words) and (
                name_words is None or any(word in title for word in name_words)):
            return kind
    if any(text == word or text.endswith(f' {word}') for word in _SETS):
        return NOT_USED_KIND
    return 'other'


def stored_kind(category: str | None, name: str | None = None) -> str:
    """`kind_for` as a value `rbproducts` accepts: a not used category gives `other` (only a row
    stored before the taxonomy can have one; the refresh never adds them)."""
    kind = kind_for(category, name)
    return 'other' if kind == NOT_USED_KIND else kind


def kind_sql(category, name=None):
    """`kind_for` as SQL over the category expression `category` and the product name
    expression `name` (the same rules, in the same order, case-insensitive; `other` when none
    matches), so a query can filter and count by kind."""
    text = sa.func.lower(sa.func.coalesce(category, ''))
    title = sa.func.lower(sa.func.coalesce(name, '')) if name is not None else None
    whens = []
    for kind, words, name_words in _RULES:
        condition = sa.or_(*(text.like(f'%{word}%') for word in words))
        if name_words is not None:
            if title is None:
                continue        # no name: the rule never matches, as in `kind_for`
            condition = sa.and_(condition,
                                sa.or_(*(title.like(f'%{word}%') for word in name_words)))
        whens.append((condition, kind))
    whens.append((sa.or_(*(sa.or_(text == word, text.like(f'% {word}')) for word in _SETS)),
                  NOT_USED_KIND))
    return sa.case(*whens, else_='other')


def expansion_set(product_id: int) -> str | None:
    """The set `refresh_products` would give the product: the mapped set of the expansion
    of its latest non-single Cardmarket row, or None (no row, no expansion, or an
    expansion not mapped yet). One statement."""
    row = db.session.execute(
        sa.select(RbcmExpansion.rbexp_rbset_id)
        .select_from(RbcmProduct)
        .outerjoin(RbcmExpansion, RbcmExpansion.rbexp_id == RbcmProduct.rbprd_id_expansion)
        .where(RbcmProduct.rbprd_id_product == product_id,
               RbcmProduct.rbprd_type == 'nonsingle')
        .order_by(RbcmProduct.rbprd_date.desc()).limit(1)).first()
    return row[0] if row else None


def refresh_products(date: str) -> dict:
    """Bring `rbproducts` in step with the non-single products of `date` (YYYYMMDD).

    New ids are inserted; existing ones get the name, category and `listed = true`, and
    the kind and set unless locked; `nonsingle` products missing from `date` get
    `listed = false`. Products of a category we do not use (Cardmarket Sets and Sealed
    Products, `NOT_USED_KIND`) are skipped: never inserted, and a row stored before the
    taxonomy counts as missing (unlisted, never deleted). `rbpdt_updated_at` moves only on a
    change.

    Returns `new` (inserted), `updated` (existing rows of `date` that changed),
    `not_listed` (`nonsingle` products missing from `date`), `skipped` (products of `date`
    in a category we do not use) and `total` (`nonsingle` products after the refresh).
    Raises NothingToRefresh, changing nothing, when `date` has no non-single products.
    """
    source = db.session.execute(sa.select(RbcmProduct).where(
        RbcmProduct.rbprd_date == date, RbcmProduct.rbprd_type == 'nonsingle')).scalars().all()
    if not source:
        raise NothingToRefresh(f'no non-single products for {date}')

    sets = dict(db.session.execute(sa.select(RbcmExpansion.rbexp_id,
                                             RbcmExpansion.rbexp_rbset_id)).all())
    existing = {p.rbpdt_id_product: p for p in db.session.execute(
        sa.select(RbProducts)).scalars()}
    now = clock.utcnow()
    counts = {'new': 0, 'updated': 0, 'not_listed': 0, 'skipped': 0}

    for item in source:
        kind = kind_for(item.rbprd_category_name, item.rbprd_name)
        if kind == NOT_USED_KIND:
            counts['skipped'] += 1
            continue
        values = {'rbpdt_name': item.rbprd_name,
                  'rbpdt_category': item.rbprd_category_name,
                  'rbpdt_type': 'nonsingle',
                  'rbpdt_listed': True}
        product = existing.pop(item.rbprd_id_product, None)
        if product is None or not product.rbpdt_kind_locked:
            values['rbpdt_kind'] = kind
        if product is None or not product.rbpdt_set_locked:
            values['rbpdt_id_set'] = sets.get(item.rbprd_id_expansion)
        if product is None:
            db.session.add(RbProducts(rbpdt_id_product=item.rbprd_id_product,
                                      rbpdt_updated_at=now, **values))
            counts['new'] += 1
        elif _apply(product, values, now):
            counts['updated'] += 1

    for product in existing.values():
        if product.rbpdt_type != 'nonsingle':
            continue
        _apply(product, {'rbpdt_listed': False}, now)
        counts['not_listed'] += 1

    db.session.commit()
    total = db.session.execute(sa.select(sa.func.count()).select_from(RbProducts).where(
        RbProducts.rbpdt_type == 'nonsingle')).scalar_one()
    return {'date': date, **counts, 'total': total}


def apply_admin_patch(product: RbProducts, fields: dict) -> dict:
    """Apply the admin edit `fields` (any of `hidden`, `kind`, `set_id`; `set_id` is an
    existing set id, None or `"auto"`) and return `{field: [old, new]}` of what changed.

    A kind locks it; `kind: None` unlocks it and recomputes it from the category and the
    name (`stored_kind`: a not used category gives `other`). A set id
    or None locks the set; `"auto"` unlocks it and recomputes it from the expansion.
    `rbpdt_updated_at` moves only on a change. Does not commit.
    """
    changes = {}

    def put(name, attr, value):
        old = getattr(product, attr)
        if old != value:
            changes[name] = [old, value]
            setattr(product, attr, value)

    if 'hidden' in fields:
        put('hidden', 'rbpdt_hidden', fields['hidden'])
    if 'kind' in fields:
        kind = fields['kind']
        put('kind', 'rbpdt_kind', kind if kind is not None
            else stored_kind(product.rbpdt_category, product.rbpdt_name))
        put('kind_locked', 'rbpdt_kind_locked', kind is not None)
    if 'set_id' in fields:
        set_id = fields['set_id']
        auto = set_id == 'auto'
        put('set_id', 'rbpdt_id_set',
            expansion_set(product.rbpdt_id_product) if auto else set_id)
        put('set_locked', 'rbpdt_set_locked', not auto)
    if changes:
        product.rbpdt_updated_at = clock.utcnow()
    return changes


def _apply(product: RbProducts, values: dict, now) -> bool:
    """Set `values` on `product`; True (and `rbpdt_updated_at = now`) when one changed."""
    changed = False
    for name, value in values.items():
        if getattr(product, name) != value:
            setattr(product, name, value)
            changed = True
    if changed:
        product.rbpdt_updated_at = now
    return changed
