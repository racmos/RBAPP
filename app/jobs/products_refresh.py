"""`products_refresh`: the product catalog refresh (F14-a).

Queued by `daily_prices` when it succeeds, after `value_snapshot` (and by hand with
`flask jobs enqueue products_refresh [--param date=YYYYMMDD]`). It brings
`rbproducts` in step with the non-single Cardmarket products of `date` (default: the
latest `rbcm_products` date).
"""
from datetime import datetime

import sqlalchemy as sa

from app import db
from app.jobs.registry import JobFailed, JobKind, register
from app.models import RbcmProduct
from app.services import products

NAME = 'products_refresh'


def _date(params: dict) -> str:
    unknown = sorted(set(params) - {'date'})
    if unknown:
        raise JobFailed(f"{NAME}: unknown params: {', '.join(unknown)}")
    if 'date' not in params:
        latest = db.session.execute(sa.select(sa.func.max(RbcmProduct.rbprd_date))).scalar()
        if latest is None:
            raise JobFailed(f'{NAME}: no Cardmarket products loaded')
        return latest
    value = params['date']
    try:
        if not (isinstance(value, str) and len(value) == 8 and value.isdigit()):
            raise ValueError(value)
        datetime.strptime(value, '%Y%m%d')
    except ValueError:
        raise JobFailed(f'{NAME}: date must be YYYYMMDD') from None
    return value


def run(params: dict) -> dict:
    date = _date(params)
    try:
        return products.refresh_products(date)
    except products.NothingToRefresh as exc:
        raise JobFailed(f'{NAME}: {exc}') from None


register(JobKind(NAME, run, timeout_seconds=600))
