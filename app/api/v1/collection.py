"""Collection endpoints: GET /collection (F3-b) and the writes (F3-c)."""
from flask import Response, abort, current_app, request
from flask_login import current_user, login_required

from app.api.error_codes import DetailCode, ErrorCode
from app.api.responses import fail, ok
from app.api.v1 import api_v1
from app.schemas.validation import validate_json, validate_query
from app.schemas.validators import (CollectionBulk, CollectionExportQuery, ImportCommitBody,
                                    ImportPreviewBody, CollectionLineCreate, CollectionLinePatch,
                                    CollectionListQuery, CollectionSplit, KeepPlaysetBody)
from app.services import collection_export, collection_import, collection_write
from app.services.collection_read import list_collection
from app.services.collection_write import (FoilNotAllowed, InsufficientQuantity, LineNotFound,
                                           StaleLine, UnknownCard)


@api_v1.get('/collection')
@login_required
@validate_query(CollectionListQuery)
def list_collection_groups():
    """The user's collection as groups (one per printing and foil) with totals and facets."""
    result = list_collection(request.validated_query, current_user)
    body = {'success': True, 'data': {'items': result['items']}, 'meta': result['meta']}
    return current_app.response_class(
        current_app.json.dumps(body, sort_keys=False),
        mimetype='application/json',
    )

@api_v1.get('/collection/export')
@login_required
@validate_query(CollectionExportQuery)
def export_collection():
    """The collection as a CSV download: RBAPP format or Cardmarket stock format (F3-d)."""
    query = request.validated_query
    if query.format == 'cardmarket':
        query = query.model_copy(update={'only_selling': True})
    rows, header, file_name, quoting = collection_export.build_export(query, current_user)
    response = Response(collection_export.stream(rows, header, quoting),
                        mimetype='text/csv', headers={
                            'Content-Disposition': f'attachment; filename="{file_name}"',
                            'X-Rows-Exported': str(len(rows))})
    response.charset = 'utf-8'
    return response


# --- writes (F3-c) ---------------------------------------------------------------------------

def _unknown_card():
    return fail('Validation Error', 'Invalid request data', 400,
                details=[{'field': 'card_id', 'message': 'unknown card', 'type': 'value_error',
                          'code': DetailCode.INVALID_VALUE.value}],
                code=ErrorCode.VALIDATION_ERROR)


def _guarded(action):
    """Run a write and turn its domain errors into the API's error responses."""
    try:
        return action()
    except UnknownCard:
        return _unknown_card()
    except FoilNotAllowed:
        return fail('Bad Request', 'This card has no foil version.', 400,
                    code=ErrorCode.FOIL_NOT_ALLOWED)
    except InsufficientQuantity as exc:
        return fail('Conflict', f'Not enough copies (available: {exc.available}).', 409,
                    code=ErrorCode.INSUFFICIENT_QUANTITY, params={'available': exc.available})
    except StaleLine:
        return fail('Conflict', 'This line changed in another window. Reload and try again.', 409,
                    code=ErrorCode.STALE_LINE)
    except LineNotFound:
        abort(404)


@api_v1.post('/collection')
@login_required
@validate_json(CollectionLineCreate)
def create_collection_line():
    """Add copies of a card; an identical line is merged into (S2)."""
    def action():
        line, merged = collection_write.add_line(current_user, request.validated_data)
        return ok({'line': line, 'merged': merged}, 201)
    return _guarded(action)


@api_v1.patch('/collection/<int:line_id>')
@login_required
@validate_json(CollectionLinePatch)
def update_collection_line(line_id):
    """Change the sent fields of one line (S3)."""
    return _guarded(lambda: ok(collection_write.edit_line(
        current_user, line_id, request.validated_data)))


@api_v1.delete('/collection/<int:line_id>')
@login_required
def delete_collection_line(line_id):
    """Delete one line; the answer can be posted back to undo (S4)."""
    return _guarded(lambda: ok({'deleted': collection_write.delete_line(current_user, line_id)}))


@api_v1.post('/collection/<int:line_id>/split')
@login_required
@validate_json(CollectionSplit)
def split_collection_line(line_id):
    """Move some copies of a line into another line (S5)."""
    def action():
        source, target, merged = collection_write.split_line(
            current_user, line_id, request.validated_data)
        return ok({'source': source, 'target': target, 'merged': merged})
    return _guarded(action)


@api_v1.post('/collection/bulk')
@login_required
@validate_json(CollectionBulk)
def bulk_collection_lines():
    """Change or delete many lines, all or none (S6)."""
    data = request.validated_data
    if data.delete:
        return _guarded(lambda: ok({'deleted': collection_write.bulk_delete(
            current_user, data.ids)}))
    return _guarded(lambda: ok({'updated': collection_write.bulk_set(
        current_user, data.ids, data.set)}))


@api_v1.post('/collection/keep-playset')
@login_required
@validate_json(KeepPlaysetBody)
def keep_collection_playset():
    """Mark or unmark a card name as "keep a playset" (S7)."""
    data = request.validated_data
    return _guarded(lambda: ok(collection_write.keep_playset(
        current_user, data.set_id, data.card_id, data.keep)))


# --- import (F3-e) ---------------------------------------------------------------------------

@api_v1.post('/collection/import/preview')
@login_required
@validate_json(ImportPreviewBody)
def preview_collection_import():
    """Parse an uploaded collection file and say what each row would do (S2-S4)."""
    data = request.validated_data
    try:
        return ok(collection_import.create_preview(current_user, data.text, data.format))
    except collection_import.FormatUnknown:
        return fail('Bad Request', "The file format is not recognised. Use the RBAPP format.",
                    400, code=ErrorCode.IMPORT_FORMAT_UNKNOWN)
    except collection_import.TooBig as exc:
        limit = collection_import.MAX_BYTES if 'MB' in str(exc) else collection_import.MAX_ROWS
        return fail('Validation Error', 'Invalid request data', 400,
                    details=[{'field': 'text', 'message': str(exc), 'type': 'value_error',
                              'code': DetailCode.OUT_OF_RANGE.value, 'params': {'max': limit}}],
                    code=ErrorCode.VALIDATION_ERROR)


@api_v1.post('/collection/import/commit')
@login_required
@validate_json(ImportCommitBody)
def commit_collection_import():
    """Apply a preview to the collection: add to it or replace the printings it holds (S5)."""
    data = request.validated_data
    try:
        return ok(collection_import.commit_preview(current_user, data.preview_id, data.mode))
    except collection_import.PreviewExpired:
        return fail('Gone', 'The preview expired. Upload the file again.', 410,
                    code=ErrorCode.IMPORT_EXPIRED)
