"""
Error handlers for the application.
"""
from flask import render_template, jsonify
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


def request_wants_json():
    """Check if the request prefers JSON response."""
    from flask import request
    return (
        request.is_json or
        request.accept_mimetypes.accept_json or
        request.headers.get('Accept') == 'application/json'
    )
