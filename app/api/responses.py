"""Envelopes of the JSON API (API-1).

Success: {"success": true, "data": {...}, "meta": {...}?}
Error:   {"success": false, "error": "<name>", "message": "...", "details": [...]?,
          "code": "<snake_case>"?, "params": {...}?}

The error envelope is the one `app.errors` uses for every other JSON error, so
the whole API (including 404, 405 and CSRF errors) answers in one format.
"""
from flask import jsonify, make_response

from app.errors import json_error


def ok(data=None, status=200, meta=None):
    """A success response; `data` defaults to an empty object."""
    body = {'success': True, 'data': {} if data is None else data}
    if meta is not None:
        body['meta'] = meta
    return make_response(jsonify(body), status)


def fail(error, message, status, details=None, headers=None, *, code=None, params=None):
    """An error response; `headers` (for example Retry-After) are added as given.

    `code` (an `ErrorCode`) and `params` are optional and keyword-only (API-9).
    """
    response = json_error(error, message, status, details=details, code=code, params=params)
    for name, value in (headers or {}).items():
        response.headers[name] = value
    return response
