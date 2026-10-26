"""Riot sync control and change review (F13-e S1, S3-S6): all admin-only."""
from flask import request

from app import db
from app.api.admin import api_admin
from app.api.error_codes import DetailCode, ErrorCode
from app.api.responses import fail, ok
from app.models.card_change import RbCardChange
from app.models.set import RbSet
from app.schemas.admin import AdminBulkBody, AdminChangesQuery, AdminRiotSyncBody
from app.schemas.validation import validate_json, validate_query
from app.services import audit as audit_service
from app.services import change_review
from app.services import jobs as jobs_service
from app.services.jobs import JobAlreadyActive


@api_admin.post('/riot/sync')
@validate_json(AdminRiotSyncBody)
def queue_sync():
    """Queue a manual `riot_sync` job (S1)."""
    data = request.validated_data
    known = {row[0] for row in db.session.query(RbSet.rbset_id).all()}
    unknown = sorted(set(data.sets) - known)
    if unknown:
        return fail('Validation Error', 'Invalid request data', 400,
                    details=[{'field': 'sets', 'message': 'unknown set codes',
                              'type': 'value_error', 'code': DetailCode.INVALID_VALUE,
                              'params': {'values': unknown}}],
                    code=ErrorCode.VALIDATION_ERROR)
    params = {'trigger': 'manual'}
    if data.sets:
        params['sets'] = ','.join(data.sets)
    try:
        job = jobs_service.enqueue('riot_sync', params,
                                   requested_by=_actor_id())
    except JobAlreadyActive:
        return fail('Conflict', 'A sync is already running.', 409,
                    code=ErrorCode.JOB_RUNNING)
    audit_service.record('riot.sync_requested', 'job', str(job.rbjob_id),
                         {'sets': data.sets}, actor=_actor())
    db.session.commit()
    return ok({'job_id': job.rbjob_id}, 202)


@api_admin.get('/riot/changes')
@validate_query(AdminChangesQuery)
def list_changes():
    """Proposed and decided changes (S3)."""
    params = request.validated_query
    status = None if params.status == 'all' else params.status
    items, total = change_review.list_changes(
        status=status, set_id=params.set, field=params.field, q=params.q,
        page=params.page, per_page=params.per_page)
    pages = max((total + params.per_page - 1) // params.per_page, 1)
    return ok({'items': items,
               'meta': {'page': params.page, 'per_page': params.per_page,
                        'total': total, 'pages': pages,
                        'counts': change_review.pending_counts()}})


@api_admin.post('/riot/changes/<int:change_id>/approve')
def approve_change(change_id):
    """Apply one pending change (S4)."""
    change = RbCardChange.query.get(change_id)
    if change is None:
        return fail('Not Found', f'Change {change_id} not found.', 404)
    actor = _actor()
    try:
        warnings = change_review.apply_change(change, actor)
    except change_review.DecidedChange:
        return fail('Conflict', 'This change was already approved or rejected.', 409,
                    code=ErrorCode.CHANGE_DECIDED)
    except change_review.StaleChange:
        db.session.rollback()
        return fail('Conflict', 'The card changed after this change was detected.', 409,
                    code=ErrorCode.CHANGE_STALE)
    db.session.commit()
    from flask import jsonify
    body = {'success': True, 'data': change_review.change_item(change)}
    if warnings:
        body['warnings'] = warnings
    return jsonify(body)


@api_admin.post('/riot/changes/<int:change_id>/reject')
def reject_change(change_id):
    """Reject one pending change (S5)."""
    change = RbCardChange.query.get(change_id)
    if change is None:
        return fail('Not Found', f'Change {change_id} not found.', 404)
    try:
        change_review.reject_change(change, _actor())
    except change_review.DecidedChange:
        return fail('Conflict', 'This change was already approved or rejected.', 409,
                    code=ErrorCode.CHANGE_DECIDED)
    db.session.commit()
    return ok(change_review.change_item(change))


@api_admin.post('/riot/changes/bulk')
@validate_json(AdminBulkBody)
def bulk_decide():
    """Approve or reject many changes, each in its own transaction (S6)."""
    from app.services.change_review import DecidedChange, StaleChange
    data = request.validated_data
    results = []
    counts = {'approved': 0, 'rejected': 0, 'stale': 0, 'decided': 0, 'not_found': 0}
    actor = _actor()
    for change_id in sorted(data.ids):
        change = RbCardChange.query.get(change_id)
        if change is None:
            outcome = 'not_found'
        else:
            try:
                if data.action == 'approve':
                    change_review.apply_change(change, actor)
                    outcome = 'approved'
                else:
                    change_review.reject_change(change, actor)
                    outcome = 'rejected'
                db.session.commit()
            except DecidedChange:
                db.session.rollback()
                outcome = 'decided'
            except StaleChange:
                db.session.rollback()
                outcome = 'stale'
        results.append({'id': change_id, 'outcome': outcome})
        counts[outcome] += 1
    return ok({'results': results, 'counts': counts})


def _actor():
    from flask_login import current_user
    return current_user._get_current_object()


def _actor_id():
    actor = _actor()
    return actor.id if actor is not None else None
