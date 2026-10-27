"""
Validation utilities using Pydantic.
"""
import types
from functools import wraps
from typing import Union, get_args, get_origin

from flask import request, jsonify
from pydantic import BaseModel, ValidationError

from app.api.error_codes import DetailCode, ErrorCode
from app.errors import unexpected_failure

# Pydantic error types -> the stable `details[].code` set (API-9, design 5.3).
_TOO_SHORT = {'string_too_short', 'too_short'}
_TOO_LONG = {'string_too_long', 'too_long'}
_LOWER_BOUND = {'greater_than_equal': 'ge', 'greater_than': 'gt'}
_UPPER_BOUND = {'less_than_equal': 'le', 'less_than': 'lt'}


def detail_code(error: dict) -> tuple[str, dict | None]:
    """`(code, params)` for one item of `ValidationError.errors()`.

    Pure. Only JSON scalars taken from the error context are returned as
    params: `min` / `max` for lengths and numeric bounds (Pydantic reports just
    the bound that was broken). Everything unknown is `invalid_value`.
    """
    kind = error.get('type', '')
    ctx = error.get('ctx') or {}
    if kind == 'missing':
        return DetailCode.REQUIRED.value, None
    if kind in _TOO_SHORT:
        return DetailCode.TOO_SHORT.value, {'min': ctx['min_length']}
    if kind in _TOO_LONG:
        return DetailCode.TOO_LONG.value, {'max': ctx['max_length']}
    if kind in _LOWER_BOUND:
        return DetailCode.OUT_OF_RANGE.value, {'min': ctx[_LOWER_BOUND[kind]]}
    if kind in _UPPER_BOUND:
        return DetailCode.OUT_OF_RANGE.value, {'max': ctx[_UPPER_BOUND[kind]]}
    if kind == DetailCode.INVALID_FORMAT.value:
        return DetailCode.INVALID_FORMAT.value, None
    return DetailCode.INVALID_VALUE.value, None


def _detail(error: dict) -> dict:
    """One `details[]` item: the F0 keys plus `code` and, when it has any, `params`."""
    code, params = detail_code(error)
    detail = {
        'field': '.'.join(str(loc) for loc in error['loc']),
        'message': error['msg'],
        'type': error['type'],
        'code': code,
    }
    if params:
        detail['params'] = params
    return detail


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
                return jsonify({
                    'success': False,
                    'error': 'Validation Error',
                    'message': 'Invalid request data',
                    'details': [_detail(err) for err in e.errors()],
                    'code': ErrorCode.VALIDATION_ERROR.value,
                }), 400
            except Exception as e:
                return unexpected_failure(e, 'Invalid request body', 400, error='Bad Request',
                                          code=ErrorCode.BAD_REQUEST)
            
            return f(*args, **kwargs)
        return wrapper
    return decorator


def _is_list_annotation(annotation) -> bool:
    """True when a Pydantic field annotation accepts a list of values."""
    origin = get_origin(annotation)
    if origin is list:
        return True
    # `Optional[List[...]]`, `List[...] | None`, and other unions.
    if origin is Union or origin is types.UnionType:
        return any(_is_list_annotation(arg) for arg in get_args(annotation))
    return False


def validate_query(schema: type[BaseModel]):
    """
    Decorator to validate query parameters against a Pydantic schema.

    - Fields annotated with a list type consume `request.args.getlist(name)`;
      all other fields consume `request.args.get(name)`.
    - Empty strings are dropped, so `?price_min=` is treated as absent.
    - Unknown parameters are passed through to Pydantic, so schemas with
      `extra='forbid'` reject them and `extra='ignore'` schemas discard them.
    - Pydantic coerces scalars (`int`, `float`, `bool`, `Literal`).

    On error the response body matches `validate_json` exactly, except for
    `message: "Invalid query parameters"`. The validated model is attached
    to `request.validated_query`.

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
                data = {}
                known_names = set(schema.model_fields.keys())

                # Known fields: list annotations consume getlist, scalars consume get.
                for name in known_names:
                    field_info = schema.model_fields[name]
                    if _is_list_annotation(field_info.annotation):
                        data[name] = [v for v in request.args.getlist(name) if v != '']
                    else:
                        value = request.args.get(name)
                        if value == '':
                            value = None
                        if value is not None:
                            data[name] = value

                # Unknown params are passed through so schemas with extra='forbid'
                # can reject them; extra='ignore' schemas discard them as before.
                for key in request.args.keys():
                    if key not in known_names:
                        values = [v for v in request.args.getlist(key) if v != '']
                        if values:
                            data[key] = values[0] if len(values) == 1 else values

                validated = schema(**data)
                request.validated_query = validated
            except ValidationError as e:
                return jsonify({
                    'success': False,
                    'error': 'Validation Error',
                    'message': 'Invalid query parameters',
                    'details': [_detail(err) for err in e.errors()],
                    'code': ErrorCode.VALIDATION_ERROR.value,
                }), 400

            return f(*args, **kwargs)
        return wrapper
    return decorator
