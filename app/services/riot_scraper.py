"""
Riot Card Gallery scraper (fetch + parse only since F13-c).
Fetches card data from https://riftbound.leagueoflegends.com/en-us/card-gallery/
and parses it (`fetch_gallery` in `app/services/riot_sync.py` drives it).
Writes go through the sync engine; `refresh_riot_sets` lists the gallery's set filter.
"""

from __future__ import annotations

import json
import logging
import os
import re
from html import unescape
from typing import Optional

import requests

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


def normalise_type(card_type: Optional[str]) -> Optional[str]:
    """The stored type of a gallery type (owner feedback S13).

    Legends have no supertype in the catalog: the gallery's "Champion Legend" is
    "Legend". Every other supertype + type pair ("Champion Unit", "Signature
    Spell", "Token Unit", "Basic Rune") is stored as the gallery builds it.
    """
    if card_type and card_type.split()[-1] == 'Legend':
        return 'Legend'
    return card_type


def full_name(name: str, subtitle: Optional[str], supertypes: list[str],
              card_type: Optional[str]) -> str:
    """The stored card name (owner feedback S12).

    The gallery sends the printed name in two keys: `name` ("Ahri") and
    `subtitle` ("Alluring"). Only Legends store the bare name ("Dark Child", the
    champion is in the tags); every other card stores "Name, Subtitle". Signature
    cards are the exception the data shows: their subtitle is the champion
    ("Bullet Time" / "Miss Fortune") and their printed name is the bare name.
    """
    if not subtitle or normalise_type(card_type) == 'Legend' or 'Signature' in supertypes:
        return name
    return f'{name}, {subtitle}'


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
    supertypes = [t.get('label', '') for t in ct.get('superType', [])]
    types = supertypes + [t.get('label', '') for t in ct.get('type', [])]
    card_type = normalise_type(' '.join(types))

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
        'rbcar_name': full_name(card_json.get('name', ''), card_json.get('subtitle'),
                                supertypes, card_type),
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
