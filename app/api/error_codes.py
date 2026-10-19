"""Machine-readable error codes (API-1, API-9, D9).

An error body may carry `code` (one of these, lowercase snake_case) and
`params` (JSON scalars, for example `{"retry_after": 30}`) next to the F0 keys
`success`, `error`, `message`, `details`. Clients translate by code and fall back
to `message`. Adding a code means adding it here, to both frontend catalogs
(`frontend/src/i18n/locales/{es,en}/errors.json`, key `code.<value>`) and to the
contract test that checks them (`tests/test_frontend_contracts.py`, unit d).

Codes and params never carry secrets, stack traces or internals.
"""
from enum import StrEnum


class ErrorCode(StrEnum):
    """Top-level `code` of an error response."""
    INVALID_CREDENTIALS = 'invalid_credentials'   # login 401 (also a blocked account, R4)
    LOCKED = 'locked'                             # login 429, account lock; params.retry_after
    RATE_LIMITED = 'rate_limited'                 # limiter 429; params.retry_after
    USERNAME_TAKEN = 'username_taken'             # register 409
    EMAIL_TAKEN = 'email_taken'                   # register 409
    CAPTCHA_FAILED = 'captcha_failed'             # register 400
    CSRF_INVALID = 'csrf_invalid'                 # any unsafe request without a valid token, 400
    UNAUTHENTICATED = 'unauthenticated'           # JSON access without a session, 401
    VALIDATION_ERROR = 'validation_error'         # request body failed validation, 400


class DetailCode(StrEnum):
    """`code` of one item of `details[]` in a validation error (stable set)."""
    REQUIRED = 'required'
    TOO_SHORT = 'too_short'                       # params.min
    TOO_LONG = 'too_long'                         # params.max
    INVALID_FORMAT = 'invalid_format'
    INVALID_VALUE = 'invalid_value'
    OUT_OF_RANGE = 'out_of_range'                 # params.min and/or params.max
