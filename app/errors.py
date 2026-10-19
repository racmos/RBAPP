"""
Error handlers for the application.

JSON or HTML (API-8, D18): `wants_json()` decides, and every handler below uses
it, so one request gets one kind of answer whatever went wrong.
"""
import math
import time

from flask import render_template, jsonify, make_response, request
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import HTTPException

from app.api.error_codes import ErrorCode

# Everything under this prefix is the JSON API: always JSON, whatever the headers.
API_PREFIX = '/riftbound/api/'

# Error pages that exist as templates; any other status uses errors/generic.html.
ERROR_TEMPLATES = {400: 'errors/400.html', 401: 'errors/401.html', 403: 'errors/403.html',
                   404: 'errors/404.html', 500: 'errors/500.html'}

# Fixed texts for the statuses where the stock description says too much or too little.
# 400 is not here: abort(400, '...') carries a message meant for the caller.
FRIENDLY_MESSAGES = {
    401: 'Authentication is required',
    403: 'You do not have permission to access this resource',
    404: 'The requested resource was not found',
    500: 'An unexpected error occurred',
}


def wants_json():
    """True when the answer to this request should be JSON (API-8, D18).

    - the path is under /riftbound/api/, or
    - the body is JSON, or
    - Accept prefers application/json over text/html (a bare `*/*`, which is what
      `fetch` sends, counts as JSON).

    A request with NO Accept header is HTML: browsers' navigations and the
    baseline tests rely on it.
    """
    if request.path.startswith(API_PREFIX):
        return True
    if request.is_json:
        return True
    return request.accept_mimetypes.best_match(['application/json', 'text/html']) == 'application/json'


def json_error(error, message, status, details=None, *, code=None, params=None):
    """The error envelope: {success:false, error, message, details?, code?, params?}.

    `code` (an `ErrorCode`) and `params` are added only when given (API-9), so a
    codeless error is byte-identical to the F0 body. `params` only travels with a
    code: it is the code's variables.
    """
    body = {'success': False, 'error': error, 'message': message}
    if details:
        body['details'] = details
    if code is not None:
        body['code'] = str(code)
        if params:
            body['params'] = params
    return make_response(jsonify(body), status)


def http_error_response(error):
    """One response for any HTTPException: JSON envelope or the error page."""
    code = error.code or 500
    if wants_json():
        message = FRIENDLY_MESSAGES.get(code) or error.description or 'Invalid request'
        response = json_error(error.name, message, code)
        allow = dict(error.get_headers()).get('Allow')      # 405 says which methods work
        if allow:
            response.headers['Allow'] = allow
        return response
    return render_template(ERROR_TEMPLATES.get(code, 'errors/generic.html'), error=error), code


def unexpected_error_response(error):
    """A 500 for an exception that is not an HTTPException: logged, never shown."""
    from flask import current_app
    current_app.logger.error(f'Unhandled exception: {error}', exc_info=True)
    if wants_json():
        return json_error('Internal Server Error', FRIENDLY_MESSAGES[500], 500)
    return render_template('errors/500.html', error=error), 500


def register_error_handlers(app):
    """Register all error handlers with the app."""

    app.register_error_handler(HTTPException, http_error_response)
    app.register_error_handler(Exception, unexpected_error_response)

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        """Missing, invalid or cross-origin CSRF token (CSRF-1, CSRF-2).

        A browser navigation gets the HTML 400 page; fetch, JSON and API clients
        get the JSON envelope.
        """
        if wants_json():
            return json_error('CSRF Error', error.description, 400, code=ErrorCode.CSRF_INVALID)
        return render_template('errors/400.html', error=error, csrf_error=True), 400

    @app.errorhandler(429)
    def too_many_requests(error):
        """Rate limit hit (LOGIN-7): always carries an integer Retry-After."""
        retry_after = _retry_after_seconds()
        if wants_json():
            response = json_error('Too Many Requests',
                                  'Too many requests. Please wait before trying again.', 429,
                                  code=ErrorCode.RATE_LIMITED, params={'retry_after': retry_after})
        else:
            response = make_response(render_template('errors/429.html', error=error,
                                                     retry_after=retry_after), 429)
        response.headers['Retry-After'] = str(retry_after)
        return response


def _retry_after_seconds(default=60):
    """Seconds until the limit that was just hit resets (at least 1)."""
    from app import limiter
    current = limiter.current_limit
    if current is None:
        return default
    reset_epoch = current.window[0]            # when the window of the breached limit ends
    return max(1, math.ceil(reset_epoch - time.time()))
