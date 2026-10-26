"""Job history (F13-e S2): read-only list and detail for admins."""
from flask import request

from app import db
from app.api.admin import api_admin
from app.api.responses import fail, ok
from app.models.job import RbJob
from app.models.user import User
from app.schemas.admin import AdminJobsQuery
from app.schemas.validation import validate_query


def _actor_name(user_id):
    if user_id is None:
        return None
    user = db.session.get(User, user_id)
    return user.username if user else None


def _item(job):
    return {'id': job.rbjob_id, 'kind': job.rbjob_kind, 'status': job.rbjob_status,
            'requested_by': _actor_name(job.rbjob_requested_by),
            'requested_at': job.rbjob_requested_at.isoformat()
            if job.rbjob_requested_at else None,
            'started_at': job.rbjob_started_at.isoformat() if job.rbjob_started_at else None,
            'finished_at': job.rbjob_finished_at.isoformat() if job.rbjob_finished_at else None,
            'message': job.rbjob_message}


@api_admin.get('/jobs')
@validate_query(AdminJobsQuery)
def list_jobs():
    """Newest jobs first, with kind/status filters (S2)."""
    params = request.validated_query
    query = RbJob.query.order_by(RbJob.rbjob_id.desc())
    if params.kind:
        query = query.filter_by(rbjob_kind=params.kind)
    if params.status:
        query = query.filter_by(rbjob_status=params.status)
    jobs = query.limit(params.limit).all()
    return ok({'items': [_item(job) for job in jobs]})


@api_admin.get('/jobs/<int:job_id>')
def job_detail(job_id):
    """One job with params and result (S2)."""
    job = db.session.get(RbJob, job_id)
    if job is None:
        return fail('Not Found', f'Job {job_id} not found.', 404)
    item = _item(job)
    item['params'] = dict(job.rbjob_params or {})
    item['result'] = job.rbjob_result
    return ok(item)
