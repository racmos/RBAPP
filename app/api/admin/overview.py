"""GET /admin/overview: the first counters of the admin area (F13-R25, S3, F13-e S7).

Four catalog COUNTs, at most four statements, plus one `rbcardchanges` COUNT,
the sets list and the latest `riot_sync` job. Clients ignore unknown keys.
"""
from sqlalchemy import func, or_

from app import db
from app.api.admin import api_admin
from app.api.responses import ok
from app.models.card import RbCard
from app.models.card_change import RbCardChange
from app.models.job import RbJob
from app.models.set import RbSet
from app.services import riot_sync
from app.utils import clock


@api_admin.get('/overview')
def overview():
    sets = db.session.scalar(db.select(func.count()).select_from(RbSet))
    sets_without_date = db.session.scalar(
        db.select(func.count()).select_from(RbSet).where(RbSet.rbset_outdat.is_(None)))
    cards = db.session.scalar(db.select(func.count()).select_from(RbCard))
    cards_without_image = db.session.scalar(
        db.select(func.count()).select_from(RbCard)
        .where(or_(RbCard.image.is_(None), RbCard.image == '')))
    pending = db.session.scalar(
        db.select(func.count()).select_from(RbCardChange)
        .where(RbCardChange.rbchg_status == 'pending'))
    rows = db.session.query(RbSet.rbset_id, RbSet.rbset_name,
                            RbSet.rbset_outdat).all()
    today = riot_sync.today_madrid(clock.utcnow())
    now_local = riot_sync.now_madrid(clock.utcnow())
    active, placeholders = [], []
    for set_id, name, release_date in rows:
        window = riot_sync.window_for(release_date, today)
        if window in riot_sync.ACTIVE_WINDOWS:
            nxt = riot_sync.next_run(release_date, now_local)
            active.append({'id': set_id, 'name': name, 'window': window,
                           'next_run_at': nxt.isoformat() if nxt else None})
        if name == set_id and release_date is None:
            placeholders.append(set_id)
    last = (db.session.query(RbJob)
            .filter_by(rbjob_kind='riot_sync').order_by(RbJob.rbjob_id.desc()).first())
    if last is None:
        last_sync = None
    else:
        params = dict(last.rbjob_params or {})
        last_sync = {'job_id': last.rbjob_id, 'status': last.rbjob_status,
                     'finished_at': last.rbjob_finished_at.isoformat()
                     if last.rbjob_finished_at else None,
                     'trigger': params.get('trigger', 'manual')}
    return ok({'catalog': {
        'sets': sets,
        'sets_without_release_date': sets_without_date,
        'cards': cards,
        'cards_without_image': cards_without_image,
    }, 'riot': {
        'pending_changes': pending,
        'active_sets': active,
        'last_sync': last_sync,
        'placeholder_sets': sorted(placeholders),
    }})
