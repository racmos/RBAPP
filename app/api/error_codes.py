"""Machine-readable error codes (API-1, API-9, D9).

An error body may carry `code` (one of these, lowercase snake_case) and
`params` (JSON scalars, for example `{"retry_after": 30}`) next to the F0 keys
`success`, `error`, `message`, `details`. Clients translate by code and fall back
to `message`. Adding a code means adding it here, to both frontend catalogs
(`frontend/src/i18n/locales/{es,en}/errors.json`, key `code.<value>`) and to the
catalog test that checks them (`tests/test_error_catalogs.py`).

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
    BAD_REQUEST = 'bad_request'                   # unreadable request body (@validate_json), 400
    INTERNAL_ERROR = 'internal_error'             # unexpected failure of a legacy endpoint, 500
    ALREADY_EXISTS = 'already_exists'             # duplicate id/key on an admin write, 409
    SET_IN_USE = 'set_in_use'                     # set has cards: no id change, no delete, 409
    CARD_IN_USE = 'card_in_use'                   # card in collections/decks: no delete, 409
    JOB_RUNNING = 'job_running'                   # a sync is already queued or running, 409
    CHANGE_STALE = 'change_stale'                 # the card changed after the proposal, 409
    CHANGE_DECIDED = 'change_decided'             # the change was already approved or rejected, 409
    FOIL_NOT_ALLOWED = 'foil_not_allowed'         # foil line of a card without foil version, 400
    INSUFFICIENT_QUANTITY = 'insufficient_quantity'  # not enough copies; params.available, 409
    STALE_LINE = 'stale_line'                     # the collection line changed meanwhile, 409
    IMPORT_EXPIRED = 'import_expired'             # the import preview is gone or not the user's, 410
    IMPORT_FORMAT_UNKNOWN = 'import_format_unknown'  # the file header is not a known format, 400


class DetailCode(StrEnum):
    """`code` of one item of `details[]` in a validation error (stable set)."""
    REQUIRED = 'required'
    TOO_SHORT = 'too_short'                       # params.min
    TOO_LONG = 'too_long'                         # params.max
    INVALID_FORMAT = 'invalid_format'
    INVALID_VALUE = 'invalid_value'
    OUT_OF_RANGE = 'out_of_range'                 # params.min and/or params.max
