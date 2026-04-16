"""
Riot Card Gallery scraper.
Fetches card data + images from https://riftbound.leagueoflegends.com/en-us/card-gallery/
Inserts into rbcards table and saves images to app/static/images/cards/<set_id>/
"""

from __future__ import annotations

import json
import logging
import os
import re
from html import unescape
from pathlib import Path
from typing import Optional

import requests
from flask import current_app
from app import db
from app.models import RbCard, RbSet

logger = logging.getLogger(__name__)

BASE_URL = "https://riftbound.leagueoflegends.com"
GALLERY_URL = f"{BASE_URL}/en-us/card-gallery/"

# Reusable session headers
_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
}


def _get_session() -> requests.Session:
    """Create session with browser-like headers."""
    session = requests.Session()
    session.headers.update(_HEADERS)
    return session


def _fetch_gallery_json(session: requests.Session) -> list[dict]:
    """Fetch gallery page and extract card JSON from __NEXT_DATA__."""
    response = session.get(GALLERY_URL, timeout=30)
    response.raise_for_status()

    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>',
        response.text,
    )
    if not match:
        raise ValueError("Could not find __NEXT_DATA__ JSON in gallery page")

    json_data = json.loads(match.group(1))
    blades = (
        json_data.get('props', {})
        .get('pageProps', {})
        .get('page', {})
        .get('blades', [])
    )

    for blade in blades:
        if 'cards' in blade and 'items' in blade['cards']:
            return blade['cards']['items']

    raise ValueError("No cards found in gallery JSON data")


def _extract_sets_from_filters(json_data: dict) -> list[dict]:
    """Extract available sets from the gallery page filter options."""
    blades = (
        json_data.get('props', {})
        .get('pageProps', {})
        .get('page', {})
        .get('blades', [])
    )

    for blade in blades:
        # Look for filter config in cards blade
        filters = blade.get('cards', {}).get('filters', [])
        for f in filters:
            filter_id = f.get('id', '') or f.get('label', '')
            # Set filter usually has id "set" or label "Set"
            if filter_id.lower() in ('set', 'sets', 'expansion'):
                options = f.get('options', []) or f.get('values', [])
                return [
                    {
                        'id': opt.get('value', opt.get('id', '')),
                        'label': opt.get('label', opt.get('name', '')),
                    }
                    for opt in options
                    if opt.get('value', opt.get('id', ''))
                ]

    # Fallback: extract unique sets from cards themselves
    cards_items = []
    for blade in blades:
        if 'cards' in blade and 'items' in blade['cards']:
            cards_items = blade['cards']['items']
            break

    seen = {}
    for card in cards_items:
        card_id = card.get('id', '')
        match = re.match(r'([a-zA-Z]+)-', card_id)
        if match:
            set_id = match.group(1).upper()
            if set_id not in seen:
                # Try to get set name from card data
                set_name = card.get('set', {}).get('value', {}).get('label', set_id)
                seen[set_id] = {'id': set_id, 'label': set_name}

    return list(seen.values())


def _clean_html(html_text: str) -> str:
    """Strip HTML tags and decode entities."""
    if not html_text:
        return ''
    text = re.sub(r'<[^>]+>', ' ', html_text)
    text = unescape(text)
    return ' '.join(text.split())


def _strip_leading_zeros(card_id: str) -> str:
    """Strip leading zeros from numeric portion of card ID.
    '001' -> '1', '050a' -> '50a', '227s' -> '227s', 't03' -> 't03'
    """
    m = re.match(r'^(\d+)(.*)', card_id)
    if m:
        return str(int(m.group(1))) + m.group(2)
    return card_id


def _safe_int(value: str) -> Optional[int]:
    """Convert string to int, return None if empty or non-numeric."""
    if not value:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _parse_card(card_json: dict) -> Optional[dict]:
    """Parse single card JSON into dict matching RbCard columns."""
    card_id_raw = card_json.get('id', '')

    # Pattern: sfd-227-star-221 -> set=SFD, id=227s (showcase)
    m = re.match(r'([a-zA-Z]+)-(\d+)-star-(\d+)', card_id_raw)
    if m:
        rbset_id = m.group(1).upper()
        rbcar_id = _strip_leading_zeros(f"{m.group(2)}s")
    else:
        # Pattern: sfd-138-221 -> set=SFD, id=138
        m = re.match(r'([a-zA-Z]+)-(\d+[a-zA-Z]*)-(\d+)', card_id_raw)
        if m:
            rbset_id = m.group(1).upper()
            rbcar_id = _strip_leading_zeros(m.group(2))
        else:
            # Pattern: sfd-t03 -> set=SFD, id=t03
            m = re.match(r'([a-zA-Z]+)-([tT]\d+)', card_id_raw)
            if m:
                rbset_id = m.group(1).upper()
                rbcar_id = m.group(2)
            else:
                logger.warning(f"Cannot parse card ID: {card_id_raw}")
                return None

    # Domain
    domain_vals = card_json.get('domain', {}).get('values', [])
    domain = ' '.join(d.get('label', '') for d in domain_vals) if domain_vals else ''

    # Card type
    ct = card_json.get('cardType', {})
    types = [t.get('label', '') for t in ct.get('superType', [])]
    types += [t.get('label', '') for t in ct.get('type', [])]
    card_type = ' '.join(types)

    # Tags
    tags = ', '.join(card_json.get('tags', {}).get('tags', []))

    # Stats
    energy = card_json.get('energy', {}).get('value', {}).get('label', '')
    power = card_json.get('power', {}).get('value', {}).get('label', '')
    might = card_json.get('might', {}).get('value', {}).get('label', '')

    # Ability
    ability_html = card_json.get('text', {}).get('richText', {}).get('body', '')

    # Rarity
    rarity = card_json.get('rarity', {}).get('value', {}).get('label', '')

    # Artist
    artist_vals = card_json.get('illustrator', {}).get('values', [])
    artist = ', '.join(a.get('label', '') for a in artist_vals) if artist_vals else ''

    # Image
    image_url = card_json.get('cardImage', {}).get('url', '')
    image_filename = f"{rbset_id.lower()}_{rbcar_id}.png"

    return {
        'rbcar_rbset_id': rbset_id,
        'rbcar_id': rbcar_id,
        'rbcar_name': card_json.get('name', ''),
        'rbcar_domain': domain,
        'rbcar_type': card_type,
        'rbcar_tags': tags,
        'rbcar_energy': _safe_int(energy),
        'rbcar_power': _safe_int(power),
        'rbcar_might': _safe_int(might),
        'rbcar_ability': _clean_html(ability_html),
        'rbcar_rarity': rarity,
        'rbcar_artist': artist,
        'rbcar_banned': 'N',
        'image_url': image_url,
        'image': image_filename,
    }


def _download_image(session: requests.Session, url: str, dest_path: str) -> bool:
    """Download image to dest_path. Skip if exists."""
    if not url:
        return False
    if os.path.exists(dest_path):
        return True
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        with open(dest_path, 'wb') as f:
            f.write(resp.content)
        return True
    except Exception as e:
        logger.warning(f"Image download failed {url}: {e}")
        return False


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────

def refresh_riot_sets() -> dict:
    """
    Fetch gallery page, extract available set filters.
    Returns: { success, sets: [{id, label}, ...] }
    """
    session = _get_session()
    try:
        response = session.get(GALLERY_URL, timeout=30)
        response.raise_for_status()

        match = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>',
            response.text,
        )
        if not match:
            return {'success': False, 'message': 'Cannot find JSON data in gallery page', 'sets': []}

        json_data = json.loads(match.group(1))
        sets = _extract_sets_from_filters(json_data)

        return {
            'success': True,
            'sets': sets,
            'count': len(sets),
        }
    except Exception as e:
        logger.error(f"refresh_riot_sets failed: {e}")
        return {'success': False, 'message': str(e), 'sets': []}


def extract_riot_cards(filter_sets: list[str] | None = None) -> dict:
    """
    Scrape Riot gallery, extract cards, download images, insert/update DB.

    Args:
        filter_sets: list of set IDs to extract (e.g. ['SFD', 'OGN']).
                     Empty/None = all sets.

    Returns:
        { success, steps: [{step, status, message}], stats: {...} }
    """
    steps = []
    stats = {
        'total_scraped': 0,
        'filtered': 0,
        'inserted': 0,
        'updated': 0,
        'skipped': 0,
        'images_downloaded': 0,
        'images_failed': 0,
        'images_existed': 0,
        'sets_created': 0,
        'errors': [],
    }

    session = _get_session()

    # Step 1: Fetch gallery
    steps.append({'step': '1. Fetch gallery', 'status': 'RUNNING', 'message': 'Downloading gallery page...'})
    try:
        cards_json = _fetch_gallery_json(session)
        steps[-1]['status'] = 'SUCCESS'
        steps[-1]['message'] = f'Found {len(cards_json)} cards in gallery'
    except Exception as e:
        steps[-1]['status'] = 'ERROR'
        steps[-1]['message'] = str(e)
        return {'success': False, 'steps': steps, 'stats': stats}

    # Step 2: Parse cards
    steps.append({'step': '2. Parse cards', 'status': 'RUNNING', 'message': 'Parsing card data...'})
    parsed_cards = []
    for card_raw in cards_json:
        card_data = _parse_card(card_raw)
        if card_data is None:
            continue

        # Apply set filter
        if filter_sets and card_data['rbcar_rbset_id'] not in filter_sets:
            stats['filtered'] += 1
            continue

        parsed_cards.append(card_data)

    stats['total_scraped'] = len(parsed_cards)
    steps[-1]['status'] = 'SUCCESS'
    steps[-1]['message'] = (
        f'Parsed {stats["total_scraped"]} cards'
        + (f' (filtered out {stats["filtered"]})' if stats['filtered'] else '')
    )

    # Step 3: Ensure sets exist in rbset table
    steps.append({'step': '3. Ensure sets exist', 'status': 'RUNNING', 'message': 'Checking/creating sets in database...'})
    try:
        # Collect unique set IDs from parsed cards
        unique_sets = {c['rbcar_rbset_id'] for c in parsed_cards}
        sets_created = 0
        for set_id in unique_sets:
            existing_set = RbSet.query.filter_by(rbset_id=set_id).first()
            if not existing_set:
                new_set = RbSet(
                    rbset_id=set_id,
                    rbset_name=set_id,  # Use ID as name; user can rename later
                    rbset_ncard=sum(1 for c in parsed_cards if c['rbcar_rbset_id'] == set_id),
                )
                db.session.add(new_set)
                sets_created += 1
            else:
                # Update card count
                count = sum(1 for c in parsed_cards if c['rbcar_rbset_id'] == set_id)
                if existing_set.rbset_ncard != count:
                    existing_set.rbset_ncard = count
        db.session.commit()
        steps[-1]['status'] = 'SUCCESS'
        steps[-1]['message'] = (
            f'{len(unique_sets)} sets checked, {sets_created} new sets created'
        )
        stats['sets_created'] = sets_created
    except Exception as e:
        db.session.rollback()
        steps[-1]['status'] = 'ERROR'
        steps[-1]['message'] = f'Set creation error: {e}'
        stats['errors'].append(str(e))
        return {'success': False, 'steps': steps, 'stats': stats}

    # Step 4: Download images
    steps.append({'step': '4. Download images', 'status': 'RUNNING', 'message': 'Downloading card images...'})
    try:
        # Resolve images base dir
        static_dir = current_app.static_folder or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static'
        )
        cards_img_base = os.path.join(static_dir, 'images', 'cards')

        for card_data in parsed_cards:
            set_folder = os.path.join(cards_img_base, card_data['rbcar_rbset_id'].lower())
            Path(set_folder).mkdir(parents=True, exist_ok=True)

            dest = os.path.join(set_folder, card_data['image'])
            if os.path.exists(dest):
                stats['images_existed'] += 1
            else:
                if _download_image(session, card_data['image_url'], dest):
                    stats['images_downloaded'] += 1
                else:
                    stats['images_failed'] += 1

        steps[-1]['status'] = 'SUCCESS'
        steps[-1]['message'] = (
            f"Downloaded {stats['images_downloaded']} new, "
            f"{stats['images_existed']} existed, "
            f"{stats['images_failed']} failed"
        )
    except Exception as e:
        steps[-1]['status'] = 'ERROR'
        steps[-1]['message'] = f'Image download error: {e}'
        stats['errors'].append(str(e))

    # Step 5: Insert/update DB
    steps.append({'step': '5. Database insert', 'status': 'RUNNING', 'message': 'Inserting cards into database...'})
    try:
        for card_data in parsed_cards:
            existing = RbCard.query.filter_by(
                rbcar_rbset_id=card_data['rbcar_rbset_id'],
                rbcar_id=card_data['rbcar_id'],
            ).first()

            if existing:
                # Update all fields
                changed = False
                for key, val in card_data.items():
                    if getattr(existing, key, None) != val:
                        setattr(existing, key, val)
                        changed = True
                if changed:
                    stats['updated'] += 1
                else:
                    stats['skipped'] += 1
            else:
                new_card = RbCard(
                    rbcar_rbset_id=card_data['rbcar_rbset_id'],
                    rbcar_id=card_data['rbcar_id'],
                    rbcar_name=card_data['rbcar_name'],
                    rbcar_domain=card_data['rbcar_domain'],
                    rbcar_type=card_data['rbcar_type'],
                    rbcar_tags=card_data['rbcar_tags'],
                    rbcar_energy=card_data['rbcar_energy'],
                    rbcar_power=card_data['rbcar_power'],
                    rbcar_might=card_data['rbcar_might'],
                    rbcar_ability=card_data['rbcar_ability'],
                    rbcar_rarity=card_data['rbcar_rarity'],
                    rbcar_artist=card_data['rbcar_artist'],
                    rbcar_banned=card_data['rbcar_banned'],
                    image_url=card_data['image_url'],
                    image=card_data['image'],
                )
                db.session.add(new_card)
                stats['inserted'] += 1

        db.session.commit()
        steps[-1]['status'] = 'SUCCESS'
        steps[-1]['message'] = (
            f"Inserted {stats['inserted']}, "
            f"updated {stats['updated']}, "
            f"unchanged {stats['skipped']}"
        )
    except Exception as e:
        db.session.rollback()
        steps[-1]['status'] = 'ERROR'
        steps[-1]['message'] = f'DB error: {e}'
        stats['errors'].append(str(e))
        return {'success': False, 'steps': steps, 'stats': stats}

    return {
        'success': True,
        'steps': steps,
        'stats': stats,
    }
