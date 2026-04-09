"""
Validation utilities using Pydantic.
"""
from functools import wraps
from flask import request, jsonify
from pydantic import BaseModel, ValidationError


def validate_json(schema: type[BaseModel]):
    """
    Decorator to validate JSON request body against a Pydantic schema.
    
    Usage:
        @validate_json(SetCreate)
        def add_set():
            data = request.validated_data  # Validated and parsed data
            ...
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not request.is_json:
                return jsonify({
                    'success': False,
                    'error': 'Bad Request',
                    'message': 'Content-Type must be application/json'
                }), 400
            
            try:
                data = request.get_json()
                validated = schema(**data)
                request.validated_data = validated
            except ValidationError as e:
                errors = e.errors()
                return jsonify({
                    'success': False,
                    'error': 'Validation Error',
                    'message': 'Invalid request data',
                    'details': [
                        {
                            'field': '.'.join(str(loc) for loc in err['loc']),
                            'message': err['msg'],
                            'type': err['type']
                        }
                        for err in errors
                    ]
                }), 400
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': 'Bad Request',
                    'message': str(e)
                }), 400
            
            return f(*args, **kwargs)
        return wrapper
    return decorator


def validate_query(schema: type[BaseModel]):
    """
    Decorator to validate query parameters against a Pydantic schema.
    
    Usage:
        @validate_query(CardQueryParams)
        def cards():
            params = request.validated_query
            ...
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                # Convert query params to dict
                data = {k: v for k, v in request.args.items()}
                
                # Convert integer params
                for key in ['page', 'per_page', 'energy_min', 'energy_max', 
                           'power_min', 'power_max', 'might_min', 'might_max']:
                    if key in data and data[key]:
                        try:
                            data[key] = int(data[key])
                        except ValueError:
                            pass
                
                validated = schema(**data)
                request.validated_query = validated
            except ValidationError as e:
                errors = e.errors()
                return jsonify({
                    'success': False,
                    'error': 'Validation Error',
                    'message': 'Invalid query parameters',
                    'details': [
                        {
                            'field': '.'.join(str(loc) for loc in err['loc']),
                            'message': err['msg']
                        }
                        for err in errors
                    ]
                }), 400
            
            return f(*args, **kwargs)
        return wrapper
    return decorator
