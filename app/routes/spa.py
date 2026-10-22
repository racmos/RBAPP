"""Single-page app hosting (F1 unit b, specs HOST-1..HOST-7).

Serves the Vite build found in `FRONTEND_DIST` under /riftbound/app/:

  /riftbound/app            -> 308 to /riftbound/app/ (strict slashes)
  /riftbound/app/           -> dist/index.html
  /riftbound/app/<path>     -> the file when it exists in dist; a missing file
                               that LOOKS like a file (`.js`, `.css`, `.map`...)
                               is a real 404; anything else is a client-side
                               route and gets index.html (D2)

The routes are public (the SPA hosts its own login screen) and never touch
`session` or `current_user`, so no response carries a `Set-Cookie` (HOST-6).
The directory is read per request, so a rebuild needs no restart and tests can
point the app at a temporary dist. No dist, or a dist without index.html, is a
503 (HOST-5): the app still starts and every other route works.

Errors never go through the Jinja error pages: `base.html` calls `csrf_token()`
and `current_user`, which would write the session and set a cookie (R11, D5).
"""
import os
import re
from html import escape
from pathlib import Path

from flask import Blueprint, current_app, make_response, send_from_directory
from werkzeug.security import safe_join

from app.errors import json_error, wants_json

spa_bp = Blueprint('spa', __name__, url_prefix='/riftbound/app')

# Files under this prefix carry a content hash in their name (Vite `assets/`).
HASHED_PREFIX = 'assets/'

# A last path segment with an extension is a file request, not a client route.
FILE_LIKE = re.compile(r'\.[A-Za-z0-9]{1,8}$')

# Explicit mimetypes (D4): `mimetypes.add_type` is process-global and depends on
# the host's /etc/mime.types.
SPA_MIMETYPES = {
    '.webmanifest': 'application/manifest+json',
    '.woff2': 'font/woff2',
    '.webp': 'image/webp',
    '.js': 'text/javascript',
    '.svg': 'image/svg+xml',
}

# Report-only policy of the app document (F1 unit g). It blocks nothing: the
# browser console lists what an enforcing policy would break (F12).
CSP_HEADER = 'Content-Security-Policy-Report-Only'
CSP_REPORT_ONLY = ("default-src 'self'; script-src 'self'; "
                   "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
                   "font-src 'self'; worker-src 'self' blob: data:; connect-src 'self'; "
                   "frame-ancestors 'self'; base-uri 'self'")

CACHE_IMMUTABLE = 'public, max-age=31536000, immutable'
CACHE_REVALIDATE = 'no-cache'

BUILD_MISSING_MESSAGE = ('The new app is not built on this server. '
                         'Run: cd frontend && npm ci && npm run build')

_ERROR_NAMES = {404: 'Not Found', 503: 'Service Unavailable'}

# Minimal page: no stylesheet, no script, no template inheritance.
_ERROR_PAGE = ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
               '<meta name="viewport" content="width=device-width, initial-scale=1">'
               '<title>Rift Manager</title></head>'
               '<body style="font-family:sans-serif;background:#06222c;color:#e8eef0;padding:2rem">'
               '<h1>{status} {name}</h1><p>{message}</p></body></html>\n')


def _is_file_like(path: str) -> bool:
    """True when the last segment of `path` has a file extension (D2)."""
    return FILE_LIKE.search(path.rsplit('/', 1)[-1]) is not None


def _cache_control(path: str) -> str:
    """Cache-Control for `path` (relative to dist, D3): hashed assets are
    immutable; everything else revalidates (ETag gives the 304)."""
    return CACHE_IMMUTABLE if path.startswith(HASHED_PREFIX) else CACHE_REVALIDATE


def _spa_error(status: int, message: str):
    """JSON envelope for JSON clients, a minimal inline page otherwise (R11, D5).
    Never cached."""
    name = _ERROR_NAMES.get(status, 'Error')
    if wants_json():
        response = json_error(name, message, status)
    else:
        body = _ERROR_PAGE.format(status=status, name=name, message=escape(message))
        response = make_response(body, status)
        response.content_type = 'text/html; charset=utf-8'
    response.headers['Cache-Control'] = 'no-store'
    return response


def _send(dist: Path, path: str):
    """Send `path` from `dist` with the mimetype map and the D3 cache header."""
    mimetype = SPA_MIMETYPES.get(os.path.splitext(path)[1].lower())
    response = send_from_directory(dist, path, mimetype=mimetype, conditional=True)
    response.headers['Cache-Control'] = _cache_control(path)
    return response


def _serve(path: str):
    """The one place that decides what a request under /riftbound/app/ gets."""
    dist = Path(current_app.config['FRONTEND_DIST'])
    if not (dist / 'index.html').is_file():
        return _spa_error(503, BUILD_MISSING_MESSAGE)
    if path:
        target = safe_join(str(dist), path)         # None when it escapes dist
        if target is not None and os.path.isfile(target):
            return _send_document(dist) if path == 'index.html' else _send(dist, path)
        if _is_file_like(path):
            return _spa_error(404, 'File not found')
    return _send_document(dist)


def _send_document(dist: Path):
    """index.html, the only response that gets the CSP (SPA_CSP=off drops it)."""
    response = _send(dist, 'index.html')
    if current_app.config.get('SPA_CSP', 'report-only') == 'report-only':
        response.headers[CSP_HEADER] = CSP_REPORT_ONLY
    return response


@spa_bp.after_request
def _security_headers(response):
    """Every SPA response (D3). The referrer policy is the one the CSRF Referer
    check needs; do not weaken it."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response


@spa_bp.get('/')
def index():
    return _serve('')


@spa_bp.get('/<path:path>')
def asset(path):
    return _serve(path)
