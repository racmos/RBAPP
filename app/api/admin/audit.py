"""Admin audit log (CM-e): the `rbadminaudit` rows, filtered and paged, and the values of
the filter selects. Read-only; logic in `app/services/audit_log.py`."""
from flask import request

from app.api.admin import api_admin
from app.api.responses import ok
from app.schemas.admin import AdminAuditFacetsQuery, AdminAuditQuery
from app.schemas.validation import validate_query
from app.services import audit_log


@api_admin.get('/audit')
@validate_query(AdminAuditQuery)
def list_audit():
    """Audit rows, newest first, with `meta {page, per_page, total, pages}`."""
    params = request.validated_query
    items, total = audit_log.list_audit(params)
    pages = max((total + params.per_page - 1) // params.per_page, 1)
    return ok({'items': items,
               'meta': {'page': params.page, 'per_page': params.per_page,
                        'total': total, 'pages': pages}})


@api_admin.get('/audit/facets')
@validate_query(AdminAuditFacetsQuery)
def audit_facets():
    """`{actions: [{action, count}], target_types: [{target_type, count}]}` by name."""
    return ok(audit_log.facets())
