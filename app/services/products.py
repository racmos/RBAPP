"""Product catalog (F14-a): `rbproducts` built from the Cardmarket non-singles.

`refresh_products(date)` runs after each daily price load (job `products_refresh`).
Only `nonsingle` rows are products (D-F14-13); rows of any other type are never
touched and no row is ever deleted. `apply_admin_patch` (F14-d S3) is the admin's
hand edit: it sets the locks the refresh respects.
"""
import sqlalchemy as sa

from app import db
from app.models import RbcmExpansion, RbcmProduct, RbProducts
from app.utils import clock

# (kind, words): the first rule with a word in the category wins (S3). `deck box` is
# removed from the category before the `starter` rule looks for `deck`.
_RULES = (
    ('case', ('case',)),
    ('box', ('booster box', 'display')),
    ('booster', ('booster',)),
    ('bundle', ('bundle', 'gift')),
    ('starter', ('starter', 'deck')),
    ('sleeves', ('sleeve',)),
    ('accessory', ('deck box', 'playmat', 'binder', 'accessor', 'dice', 'token')),
)


class NothingToRefresh(Exception):
    """The date has no non-single products: refreshing would unlist the whole catalog."""


def kind_for(category: str | None) -> str:
    """The product kind of a Cardmarket category name, case-insensitive; `other` when no
    rule matches."""
    text = (category or '').lower()
    for kind, words in _RULES:
        haystack = text.replace('deck box', '') if kind == 'starter' else text
        if any(word in haystack for word in words):
            return kind
    return 'other'


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
    `listed = false`. `rbpdt_updated_at` moves only on a change.

    Returns `new` (inserted), `updated` (existing rows of `date` that changed),
    `not_listed` (`nonsingle` products missing from `date`) and `total` (`nonsingle`
    products after the refresh). Raises NothingToRefresh, changing nothing, when `date`
    has no non-single products.
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
    counts = {'new': 0, 'updated': 0, 'not_listed': 0}

    for item in source:
        values = {'rbpdt_name': item.rbprd_name,
                  'rbpdt_category': item.rbprd_category_name,
                  'rbpdt_type': 'nonsingle',
                  'rbpdt_listed': True}
        product = existing.pop(item.rbprd_id_product, None)
        if product is None or not product.rbpdt_kind_locked:
            values['rbpdt_kind'] = kind_for(item.rbprd_category_name)
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

    A kind locks it; `kind: None` unlocks it and recomputes it from the category. A set id
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
        put('kind', 'rbpdt_kind', kind if kind is not None else kind_for(product.rbpdt_category))
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
