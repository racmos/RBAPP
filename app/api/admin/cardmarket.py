"""Cardmarket load log (CM-a): the load days, one day in full, the screen header and
"Load now" (queues the `daily_prices` job). Logic in `app/services/cardmarket_log.py`."""
from flask import request
from flask_login import current_user

from app import db
from app.api.admin import api_admin
from app.api.error_codes import ErrorCode
from app.api.responses import fail, ok
from app.schemas.admin import AdminCardmarketLoadsQuery
from app.schemas.validation import validate_query
from app.services import audit as audit_service
from app.services import cardmarket_log
from app.services import jobs as jobs_service
from app.services.jobs import JobAlreadyActive


@api_admin.get('/cardmarket/loads')
@validate_query(AdminCardmarketLoadsQuery)
def list_cardmarket_loads():
    """The latest load days, newest first."""
    return ok({'items': cardmarket_log.list_loads(request.validated_query.limit)})


@api_admin.get('/cardmarket/loads/<date>')
def cardmarket_load_day(date):
    """One load day (`YYYY-MM-DD`) in full; any other value or a day without a load is a 404."""
    day = cardmarket_log.load_day(date)
    if day is None:
        return fail('Not Found', f'No Cardmarket load on {date}.', 404)
    return ok(day)


@api_admin.get('/cardmarket/status')
def cardmarket_status():
    """Header of the Cardmarket admin screen."""
    return ok(cardmarket_log.status())


@api_admin.post('/cardmarket/load')
def queue_cardmarket_load():
    """Queue the `daily_prices` job now (it takes no params)."""
    try:
        job = jobs_service.enqueue(cardmarket_log.JOB_KIND, requested_by=current_user.id)
    except JobAlreadyActive:
        return fail('Conflict', 'A Cardmarket load is already queued or running.', 409,
                    code=ErrorCode.JOB_RUNNING)
    audit_service.record('cardmarket.load', 'job', str(job.rbjob_id))
    db.session.commit()
    return ok({'job_id': job.rbjob_id, 'job': cardmarket_log.job_brief(job)}, 202)
