"""The daily Cardmarket load (F4-b): what the `daily_prices` job checks after
`CardmarketLoader().run()`. No Flask request objects.

The loader and the matcher are used as the admin endpoints use them; this
module only reads what they wrote (`rbcm_load_history`, `rbcm_products`,
`rbcm_price`).
"""
import sqlalchemy as sa
from sqlalchemy.orm import aliased

from app import db
from app.models.cardmarket import RbcmLoadHistory, RbcmPrice, RbcmProduct

# The three files of a load, in the order the loader downloads them.
FILE_TYPES = ('price_guide', 'singles', 'nonsingles')


class ValidationFailed(Exception):
    """The load ran but what it left does not pass the S3 checks."""


def _count(query) -> int:
    return db.session.execute(query).scalar_one()


def _latest_history(date: str) -> dict[str, RbcmLoadHistory]:
    """The last history row of each file type on `date` (a re-run adds rows)."""
    latest = {}
    for row in db.session.execute(
            sa.select(RbcmLoadHistory).where(RbcmLoadHistory.rblh_date == date)
            .order_by(RbcmLoadHistory.rblh_id)).scalars():
        latest[row.rblh_file_type] = row
    return latest


def validate_load(date: str) -> dict:
    """The validation record of the load of `date` (YYYYMMDD); raises
    ValidationFailed when a file has no history row or no price row exists."""
    history = _latest_history(date)
    for file_type in FILE_TYPES:
        if file_type not in history:
            raise ValidationFailed(f'Validation failed: {file_type} missing for {date}')

    price_rows = _count(sa.select(sa.func.count()).select_from(RbcmPrice)
                        .where(RbcmPrice.rbprc_date == date))
    if price_rows == 0:
        raise ValidationFailed(f'Validation failed: no price rows for {date}')

    earlier = aliased(RbcmProduct)
    today = sa.select(sa.func.count()).select_from(RbcmProduct).where(
        RbcmProduct.rbprd_date == date)
    new = today.where(~sa.exists().where(
        earlier.rbprd_id_product == RbcmProduct.rbprd_id_product,
        earlier.rbprd_date < date))
    return {
        'date': date,
        'files': {file_type: {'status': history[file_type].rblh_status,
                              'rows': history[file_type].rblh_rows}
                  for file_type in FILE_TYPES},
        'price_rows': price_rows,
        'products_today': _count(today),
        'new_products': _count(new),
    }
