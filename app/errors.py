"""
Error handlers for the application.
"""
import math
import time

from flask import render_template, jsonify, make_response, request
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import HTTPException


def register_error_handlers(app):
    """Register all error handlers with the app."""
    
    @app.errorhandler(404)
    def not_found_error(error):
        """Handle 404 Not Found errors."""
        # Check if request expects JSON (API call)
        if request_wants_json():
            return jsonify({
                'success': False,
                'error': 'Not Found',
                'message': 'The requested resource was not found'
            }), 404
        return render_template('errors/404.html', error=error), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 Internal Server errors."""
        # Check if request expects JSON (API call)
        if request_wants_json():
            return jsonify({
                'success': False,
                'error': 'Internal Server Error',
                'message': 'An unexpected error occurred'
            }), 500
        return render_template('errors/500.html', error=error), 500
    
    @app.errorhandler(403)
    def forbidden_error(error):
        """Handle 403 Forbidden errors."""
        if request_wants_json():
            return jsonify({
                'success': False,
                'error': 'Forbidden',
                'message': 'You do not have permission to access this resource'
            }), 403
        return render_template('errors/403.html', error=error), 403
    
    @app.errorhandler(401)
    def unauthorized_error(error):
        """Handle 401 Unauthorized errors."""
        if request_wants_json():
            return jsonify({
                'success': False,
                'error': 'Unauthorized',
                'message': 'Authentication is required'
            }), 401
        return render_template('errors/401.html', error=error), 401
    
    @app.errorhandler(400)
    def bad_request_error(error):
        """Handle 400 Bad Request errors."""
        if request_wants_json():
            return jsonify({
                'success': False,
                'error': 'Bad Request',
                'message': str(error.description) if hasattr(error, 'description') else 'Invalid request'
            }), 400
        return render_template('errors/400.html', error=error), 400
    
    @app.errorhandler(CSRFError)
    def csrf_error(error):
        """Missing, invalid or cross-origin CSRF token (CSRF-1, CSRF-2).

        A browser navigation gets the HTML 400 page; everything else (fetch,
        JSON, no Accept header) gets the JSON envelope.
        """
        if _browser_navigation():
            return render_template('errors/400.html', error=error, csrf_error=True), 400
        return jsonify({
            'success': False,
            'error': 'CSRF Error',
            'message': error.description
        }), 400

    @app.errorhandler(429)
    def too_many_requests(error):
        """Rate limit hit (LOGIN-7): always carries an integer Retry-After."""
        retry_after = _retry_after_seconds()
        if _browser_navigation():
            response = make_response(render_template('errors/429.html', error=error,
                                                     retry_after=retry_after), 429)
        else:
            response = make_response(jsonify({
                'success': False,
                'error': 'Too Many Requests',
                'message': 'Too many requests. Please wait before trying again.'
            }), 429)
        response.headers['Retry-After'] = str(retry_after)
        return response

    @app.errorhandler(Exception)
    def handle_exception(error):
        """Handle all other exceptions."""
        # Handle HTTP exceptions
        if isinstance(error, HTTPException):
            if request_wants_json():
                return jsonify({
                    'success': False,
                    'error': error.name,
                    'message': error.description
                }), error.code
            return render_template('errors/generic.html', error=error), error.code
        
        # Log unexpected errors
        app.logger.error(f'Unhandled exception: {error}', exc_info=True)
        
        if request_wants_json():
            return jsonify({
                'success': False,
                'error': 'Internal Server Error',
                'message': 'An unexpected error occurred'
            }), 500
        
        return render_template('errors/500.html', error=error), 500


def _retry_after_seconds(default=60):
    """Seconds until the limit that was just hit resets (at least 1)."""
    from app import limiter
    current = limiter.current_limit
    if current is None:
        return default
    reset_epoch = current.window[0]            # when the window of the breached limit ends
    return max(1, math.ceil(reset_epoch - time.time()))


def _browser_navigation():
    """True when the client asked for a page: it prefers text/html over JSON.

    Interim predicate for the CSRF handler; unit e replaces it with
    `wants_json()` (D18). `fetch` sends `Accept: */*`, which resolves to JSON
    here (first in the server list), and a request without Accept gets JSON too.
    """
    if request.is_json:
        return False
    return request.accept_mimetypes.best_match(['application/json', 'text/html']) == 'text/html'


def request_wants_json():
    """Check if the request prefers JSON response."""
    from flask import request
    return (
        request.is_json or
        request.accept_mimetypes.accept_json or
        request.headers.get('Accept') == 'application/json'
    )
