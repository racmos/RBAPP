"""
Landing page blueprint — serves the root URL (/) and HTMX partials.

Migrated from rb_landing (FastAPI) to Flask.
Routes:
  GET /                    → Full landing page
  GET /api/noticias        → HTMX partial: Riftbound news
  GET /api/discord         → HTMX partial: Discord news
  GET /api/torneos-online  → HTMX partial: online tournaments
  GET /api/torneos-fisicos → HTMX partial: physical tournaments
  GET /api/videos          → HTMX partial: YouTube videos
  GET /api/decks           → HTMX partial: deck listings
  GET /frames/manifest.json → frames manifest (JSON)
  GET /frames/<filename>   → individual frame images
"""

import os
from flask import Blueprint, render_template, send_from_directory, abort

from app.services.scraper import (
    fetch_noticias,
    fetch_discord,
    fetch_torneos_online,
    fetch_torneos_fisicos,
    fetch_videos,
    fetch_decks,
)

# Blueprint — template_folder and static_folder are relative to this file's location.
# This file lives at app/routes/landing.py, so:
#   ../templates/landing  →  app/templates/landing
#   ../static/landing     →  app/static/landing
landing_bp = Blueprint(
    'landing',
    __name__,
    template_folder='../templates/landing',
    static_folder='../static/landing',
    static_url_path='/landing/static',
)

# Absolute path to the frames directory (served at /frames/<filename>)
_FRAMES_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', 'static', 'landing', 'frames',
)


# ─── Main Page ───

@landing_bp.route('/')
def index():
    """Render the full landing page."""
    return render_template('index.html')


# ─── HTMX Partial Endpoints ───

@landing_bp.route('/api/noticias')
def api_noticias():
    """Fetch and render Riftbound news cards."""
    items = fetch_noticias()
    return render_template('components/noticias.html', items=items)


@landing_bp.route('/api/discord')
def api_discord():
    """Fetch and render Discord news cards."""
    items = fetch_discord()
    return render_template('components/discord.html', items=items)


@landing_bp.route('/api/torneos-online')
def api_torneos_online():
    """Fetch and render online tournament cards."""
    items = fetch_torneos_online()
    return render_template('components/torneos_online.html', items=items)


@landing_bp.route('/api/torneos-fisicos')
def api_torneos_fisicos():
    """Fetch and render physical tournament cards."""
    items = fetch_torneos_fisicos()
    return render_template('components/torneos_fisicos.html', items=items)


@landing_bp.route('/api/videos')
def api_videos():
    """Fetch and render video cards."""
    items = fetch_videos()
    return render_template('components/videos.html', items=items)


@landing_bp.route('/api/decks')
def api_decks():
    """Fetch and render deck cards."""
    items = fetch_decks()
    return render_template('components/decks.html', items=items)


# ─── Frame Serving ───
# Serve frames at their original /frames/... paths so camera-scroll.js
# and manifest.json need no changes.

@landing_bp.route('/frames/manifest.json')
def frames_manifest():
    """Serve the frames manifest JSON file."""
    return send_from_directory(_FRAMES_DIR, 'manifest.json')


@landing_bp.route('/frames/<path:filename>')
def frames_file(filename):
    """Serve individual frame images."""
    return send_from_directory(_FRAMES_DIR, filename)
