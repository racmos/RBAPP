"""
Riot Card Gallery scraper (fetch + parse only since F13-c).
Fetches card data from https://riftbound.leagueoflegends.com/en-us/card-gallery/
and parses it (`fetch_gallery` in `app/services/riot_sync.py` drives it).
Writes go through the sync engine.
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


_SET_CODE = re.compile(r'[A-Za-z0-9]+')
_PREFIXED_ID = re.compile(r'([A-Za-z0-9]+)-(.*)', re.DOTALL)
_SHOWCASE_ID = re.compile(r'(\d+)-star-(\d+)')
_NUMBERED_ID = re.compile(r'(\d+[a-zA-Z]*)-(\d+)')
_TOKEN_ID = re.compile(r'([tT]\d+)')
_RUNE_ID = re.compile(r'[rR]\d+[a-zA-Z]?')
_SPECIAL_ID = re.compile(r'([sS][pP]\d+)-\d+')
_NOT_ID_CHARS = re.compile(r'[^a-z0-9]')


def card_key(card_json: dict) -> Optional[tuple[str, str]]:
    """`(set id, card id)` of a gallery card, or None when it has no recognisable set.

    The set is the gallery filter's `set.value.id` ("RAD"), trimmed and upper-cased;
    only when it is missing or not letters and digits does the id prefix decide
    (`rad-...` -> RAD). The card id is the rest of the gallery id after that prefix
    (the whole id when it has none), read by the first rule that matches:

    - `227-star-221` -> `227s` (showcase), `050a-221` -> `50a`, `t03` -> `t03`: the
      historical patterns, unchanged (prefix match, the leading zeros stripped);
    - `r01`, `r01a` -> `r01`, `r01a` (runes and their variants, lower case);
    - `sp1-005` -> `sp1` (special prints; `005` is the printed total of the set);
    - anything else: the rest lower-cased, one `-` between segments, each segment
      reduced to letters and digits and its leading zeros stripped (`promo-007`
      -> `promo-7`); nothing left means no card id.

    The ids stay lower case like tokens, admin-created ids and the CSV import lookup.
    """
    raw_id = card_json.get('id')
    raw_id = raw_id if isinstance(raw_id, str) else ''
    prefixed = _PREFIXED_ID.fullmatch(raw_id)
    rest = prefixed.group(2) if prefixed else raw_id
    set_id = _gallery_set(card_json) or (prefixed.group(1).upper() if prefixed else None)
    if not set_id:
        return None
    card_id = _card_part(rest)
    return (set_id, card_id) if card_id else None


def _gallery_set(card_json: dict) -> Optional[str]:
    """The set code of the gallery filter (`set.value.id`), or None when unusable."""
    set_field = card_json.get('set')
    value = set_field.get('value') if isinstance(set_field, dict) else None
    code = value.get('id') if isinstance(value, dict) else None
    if not isinstance(code, str):
        return None
    code = code.strip().upper()
    return code if _SET_CODE.fullmatch(code) else None


def _card_part(rest: str) -> str:
    """The stored card id of the part of a gallery id after its set prefix."""
    m = _SHOWCASE_ID.match(rest)
    if m:
        return _strip_leading_zeros(f"{m.group(1)}s")
    m = _NUMBERED_ID.match(rest)
    if m:
        return _strip_leading_zeros(m.group(1))
    m = _TOKEN_ID.match(rest)
    if m:
        return m.group(1)
    if _RUNE_ID.fullmatch(rest):
        return rest.lower()
    m = _SPECIAL_ID.fullmatch(rest)
    if m:
        return m.group(1).lower()
    segments = (_NOT_ID_CHARS.sub('', segment) for segment in rest.lower().split('-'))
    return '-'.join(_strip_leading_zeros(segment) for segment in segments if segment)


def _parse_card(card_json: dict) -> Optional[dict]:
    """Parse single card JSON into dict matching RbCard columns (`card_key` for the ids)."""
    key = card_key(card_json)
    if key is None:
        logger.warning("Cannot parse card ID: %r", card_json.get('id'))
        return None
    rbset_id, rbcar_id = key

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
