"""The log of the daily Cardmarket load (CM-a), computed on read. No Flask request objects.

A load day is a date of `rbcm_load_history` (YYYYMMDD, the loader's UTC date). Everything
else is derived from what the loader and the `daily_prices` job left: the products of
the day (`rbcm_products`), its new products (present on the day and absent on the
previous date with products), the singles still unmatched (only meaningful for the
latest day) and the `daily_prices` job that ran it. No table of its own.
"""
from collections import defaultdict
from datetime import datetime, time, timedelta

import sqlalchemy as sa
from sqlalchemy.orm import aliased

from app import db
from app.models.cardmarket import (RbcmExpansion, RbcmIgnored, RbcmLoadHistory, RbcmPrice,
                                   RbcmProduct, RbcmProductCardMap)
from app.models.job import RbJob
from app.services import pricing
from app.services.daily_prices import FILE_TYPES
from app.utils import clock

JOB_KIND = 'daily_prices'
# New products shown per day in the list, and at most in the detail of one day.
SAMPLE_SIZE = 20
DETAIL_CAP = 500


def iso(day: str) -> str:
    """`YYYYMMDD` → `YYYY-MM-DD`."""
    return f'{day[:4]}-{day[4:6]}-{day[6:]}'


def compact(value: str) -> str | None:
    """`YYYY-MM-DD` → `YYYYMMDD`, or None when it is not a real date in that form."""
    try:
        parsed = datetime.strptime(value, '%Y-%m-%d')
    except (TypeError, ValueError):
        return None
    if parsed.strftime('%Y-%m-%d') != value:
        return None
    return parsed.strftime('%Y%m%d')


def _stamp(value):
    return value.isoformat() if value else None


def _day_start(day: str) -> datetime:
    return datetime.combine(datetime.strptime(day, '%Y%m%d').date(), time.min)


def derive_status(latest: dict) -> str:
    """Status of a day from the latest status of each file type: every file skipped →
    `skipped`; a file in error (or missing) → `partial` when another succeeded, else
    `error`; otherwise `success` (a skipped file only means it had not changed)."""
    values = [latest.get(file_type) for file_type in FILE_TYPES]
    values += [status for file_type, status in latest.items() if file_type not in FILE_TYPES]
    if all(value == 'skipped' for value in values):
        return 'skipped'
    if any(value not in ('success', 'skipped') for value in values):
        return 'partial' if 'success' in values else 'error'
    return 'success'


def _file(row) -> dict:
    return {'type': row.rblh_file_type, 'rows': row.rblh_rows, 'status': row.rblh_status,
            'message': row.rblh_message, 'loaded_at': _stamp(row.rblh_loaded_at)}


def _latest_files(rows) -> list:
    """The latest row of each file type (a re-run adds rows), in the loader's order."""
    latest = {}
    for row in sorted(rows, key=lambda r: r.rblh_id):
        latest[row.rblh_file_type] = row
    order = {file_type: n for n, file_type in enumerate(FILE_TYPES)}
    return sorted(latest.values(), key=lambda r: (order.get(r.rblh_file_type, len(order)),
                                                  r.rblh_file_type))


def _status_of(files: list) -> str:
    return derive_status({row.rblh_file_type: row.rblh_status for row in files})


def job_brief(job) -> dict:
    """`{id, status, queued_at, started_at, finished_at, message}` of a job."""
    return {'id': job.rbjob_id, 'status': job.rbjob_status,
            'queued_at': _stamp(job.rbjob_requested_at),
            'started_at': _stamp(job.rbjob_started_at),
            'finished_at': _stamp(job.rbjob_finished_at), 'message': job.rbjob_message}


def _duration(job):
    if job is None or job.rbjob_started_at is None or job.rbjob_finished_at is None:
        return None
    return round((job.rbjob_finished_at - job.rbjob_started_at).total_seconds())


# --- queries -----------------------------------------------------------------

def _history(days) -> dict:
    rows = defaultdict(list)
    for row in db.session.execute(
            sa.select(RbcmLoadHistory).where(RbcmLoadHistory.rblh_date.in_(days))
            .order_by(RbcmLoadHistory.rblh_id)).scalars():
        rows[row.rblh_date].append(row)
    return rows


def _product_counts(oldest: str, newest: str) -> dict:
    """`{date: products}` for every date with products from the one before `oldest`
    up to `newest`: one statement."""
    floor = sa.func.coalesce(
        sa.select(sa.func.max(RbcmProduct.rbprd_date))
        .where(RbcmProduct.rbprd_date < oldest).scalar_subquery(), oldest)
    return dict(db.session.execute(
        sa.select(RbcmProduct.rbprd_date, sa.func.count())
        .where(RbcmProduct.rbprd_date >= floor, RbcmProduct.rbprd_date <= newest)
        .group_by(RbcmProduct.rbprd_date)).all())


def _previous_dates(days, counts: dict) -> dict:
    """`{day: previous date with products}` for the days that have products."""
    product_days = sorted(counts)
    previous = {}
    for day in days:
        if counts.get(day):
            earlier = [d for d in product_days if d < day]
            if earlier:
                previous[day] = earlier[-1]
    return previous


def _new_products(previous: dict, cap: int) -> tuple[dict, dict]:
    """The products of each day absent on its previous date: `({day: count},
    {day: [first `cap` items by name]})`, in one statement."""
    if not previous:
        return {}, {}
    pairs = [sa.select(sa.cast(sa.literal(day), sa.Text).label('day'),
                       sa.cast(sa.literal(prev), sa.Text).label('prev'))
             for day, prev in sorted(previous.items())]
    pairs = (sa.union_all(*pairs) if len(pairs) > 1 else pairs[0]).cte('pairs')
    today, before = aliased(RbcmProduct), aliased(RbcmProduct)
    ranked = (
        sa.select(today.rbprd_date.label('day'), today.rbprd_id_product.label('id_product'),
                  today.rbprd_name.label('name'),
                  today.rbprd_category_name.label('category'),
                  today.rbprd_type.label('type'), RbcmPrice.rbprc_low.label('low'),
                  sa.func.row_number().over(
                      partition_by=today.rbprd_date,
                      order_by=(today.rbprd_name, today.rbprd_id_product)).label('rn'),
                  sa.func.count().over(partition_by=today.rbprd_date).label('total'))
        .join(pairs, pairs.c.day == today.rbprd_date)
        .outerjoin(before, sa.and_(before.rbprd_date == pairs.c.prev,
                                   before.rbprd_id_product == today.rbprd_id_product))
        .outerjoin(RbcmPrice, sa.and_(RbcmPrice.rbprc_date == today.rbprd_date,
                                      RbcmPrice.rbprc_id_product == today.rbprd_id_product))
        .where(before.rbprd_id_product.is_(None))
        .subquery())
    counts, lists = {}, defaultdict(list)
    for row in db.session.execute(
            sa.select(ranked).where(ranked.c.rn <= cap)
            .order_by(ranked.c.day, ranked.c.rn)).all():
        counts[row.day] = row.total
        lists[row.day].append({
            'id_product': row.id_product, 'name': row.name, 'category': row.category,
            'type': row.type, 'low_price': float(row.low) if row.low is not None else None})
    return counts, lists


def unmatched_clauses() -> tuple:
    """The one definition of an unmatched Cardmarket product (any type): a row of the
    latest product date that is neither mapped nor ignored (the ignore list is keyed by
    id and name). `unmatched_count` and the CM-b unmatched list both use it."""
    latest = sa.select(sa.func.max(RbcmProduct.rbprd_date)).scalar_subquery()
    return (
        RbcmProduct.rbprd_date == latest,
        ~sa.exists().where(
            RbcmProductCardMap.rbpcm_id_product == RbcmProduct.rbprd_id_product),
        ~sa.exists().where(RbcmIgnored.rbig_id_product == RbcmProduct.rbprd_id_product,
                           RbcmIgnored.rbig_name == RbcmProduct.rbprd_name))


def unmatched_count() -> int:
    """Unmatched singles (`unmatched_clauses`): the current unmatched count."""
    return db.session.execute(
        sa.select(sa.func.count()).select_from(RbcmProduct).where(
            *unmatched_clauses(), RbcmProduct.rbprd_type == 'single')
    ).scalar_one()


def unmapped_expansions_count() -> int:
    """Cardmarket expansions not mapped to a set of ours (`rbexp_rbset_id` NULL): the
    status counter and the CM-d expansions list both use it."""
    return db.session.execute(
        sa.select(sa.func.count()).select_from(RbcmExpansion)
        .where(RbcmExpansion.rbexp_rbset_id.is_(None))).scalar_one()


def _jobs_near(oldest: str, newest: str) -> list:
    """The `daily_prices` jobs queued between the day before `oldest` and the day after
    `newest`, oldest first."""
    return db.session.execute(
        sa.select(RbJob).where(
            RbJob.rbjob_kind == JOB_KIND,
            RbJob.rbjob_requested_at >= _day_start(oldest) - timedelta(days=1),
            RbJob.rbjob_requested_at < _day_start(newest) + timedelta(days=2))
        .order_by(RbJob.rbjob_id)).scalars().all()


def _link_jobs(days, history: dict, jobs: list) -> dict:
    """`{day: job}`: the newest job whose result names the day (`validation.date`),
    else the newest job that was running when one of the day's files was loaded."""
    by_result, linked = {}, {}
    for job in jobs:
        result = job.rbjob_result if isinstance(job.rbjob_result, dict) else {}
        validation = result.get('validation')
        if isinstance(validation, dict) and validation.get('date'):
            by_result[validation['date']] = job
    for day in days:
        if day in by_result:
            linked[day] = by_result[day]
            continue
        stamps = [row.rblh_loaded_at for row in history.get(day, []) if row.rblh_loaded_at]
        for job in jobs:
            if job.rbjob_started_at is None:
                continue
            end = job.rbjob_finished_at
            if any(job.rbjob_started_at <= stamp and (end is None or stamp <= end)
                   for stamp in stamps):
                linked[day] = job
    return linked


# --- public ------------------------------------------------------------------

def list_loads(limit: int) -> list[dict]:
    """The latest `limit` load days, newest first. Six statements whatever `limit`."""
    days = db.session.execute(
        sa.select(RbcmLoadHistory.rblh_date).distinct()
        .order_by(RbcmLoadHistory.rblh_date.desc()).limit(limit)).scalars().all()
    if not days:
        return []
    oldest, newest = days[-1], days[0]
    history = _history(days)
    counts = _product_counts(oldest, newest)
    previous = _previous_dates(days, counts)
    new_counts, samples = _new_products(previous, SAMPLE_SIZE)
    unmatched = unmatched_count()
    linked = _link_jobs(days, history, _jobs_near(oldest, newest))
    items = []
    for day in days:
        files = _latest_files(history[day])
        job = linked.get(day)
        items.append({
            'date': iso(day),
            'files': [_file(row) for row in files],
            'status': _status_of(files),
            'products_total': counts.get(day, 0),
            'new_products': new_counts.get(day, 0) if day in previous else None,
            'new_products_sample': samples.get(day, []),
            'unmatched_singles': unmatched if day == newest else None,
            'duration_seconds': _duration(job),
            'job_id': job.rbjob_id if job else None,
        })
    return items


def load_day(value: str) -> dict | None:
    """One load day (`YYYY-MM-DD`) in full, or None when it is not a load day: every
    history row in order, the new products (at most `DETAIL_CAP`, `truncated` says
    whether there are more) and the linked job with its result untouched."""
    day = compact(value)
    if day is None:
        return None
    rows = _history([day]).get(day)
    if not rows:
        return None
    counts = _product_counts(day, day)
    previous = _previous_dates([day], counts)
    new_counts, lists = _new_products(previous, DETAIL_CAP)
    newest = db.session.execute(sa.select(sa.func.max(RbcmLoadHistory.rblh_date))).scalar()
    job = _link_jobs([day], {day: rows}, _jobs_near(day, day)).get(day)
    total_new = new_counts.get(day, 0) if day in previous else None
    job_item = None
    if job is not None:
        job_item = job_brief(job)
        job_item['result'] = job.rbjob_result
    return {
        'date': iso(day),
        'files': [_file(row) for row in rows],
        'status': _status_of(_latest_files(rows)),
        'products_total': counts.get(day, 0),
        'new_products': total_new,
        'new_products_list': lists.get(day, []),
        'truncated': bool(total_new and total_new > DETAIL_CAP),
        'unmatched_singles': unmatched_count() if day == newest else None,
        'duration_seconds': _duration(job),
        'job_id': job.rbjob_id if job else None,
        'job': job_item,
    }


def status() -> dict:
    """Header of the Cardmarket admin screen: the last load day, whether it is today
    (UTC, the loader's date), the latest `daily_prices` job and the open counters."""
    newest = db.session.execute(sa.select(sa.func.max(RbcmLoadHistory.rblh_date))).scalar()
    last_load = None
    if newest:
        rows = _history([newest])[newest]
        last_load = {'date': iso(newest), 'status': _status_of(_latest_files(rows)),
                     'loaded_at': _stamp(max((r.rblh_loaded_at for r in rows
                                              if r.rblh_loaded_at), default=None))}
    job = db.session.execute(
        sa.select(RbJob).where(RbJob.rbjob_kind == JOB_KIND)
        .order_by(RbJob.rbjob_id.desc()).limit(1)).scalar()
    return {
        'last_load': last_load,
        'loaded_today': newest == clock.utcnow().strftime('%Y%m%d'),
        'job': job_brief(job) if job else None,
        'unmatched': unmatched_count(),
        'unmapped_expansions': unmapped_expansions_count(),
        'prices_as_of': pricing.price_as_of(),
    }
