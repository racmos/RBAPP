"""Gallery items as the Riot card gallery sends them (`__NEXT_DATA__` cards), built as dicts.

No network: the tests feed these to `riot_scraper._parse_card` or, through a patched
`riot_sync._fetch_gallery_json`, to the whole sync.
"""


def gallery_item(card_id, name, *, set_id=None, subtitle=None, card_type='Unit',
                 supertypes=(), rarity='Common', domain='Fury', energy='', power='',
                 might='', text='', artist='An Artist', with_image=True):
    """One raw gallery card. `set_id=None` leaves out the `set` key (the id prefix decides)."""
    item = {
        'id': card_id,
        'name': name,
        'cardType': {'type': [{'label': card_type}],
                     'superType': [{'label': label} for label in supertypes]},
        'rarity': {'value': {'label': rarity}},
        'domain': {'values': [{'label': domain}]},
        'energy': {'value': {'label': energy}},
        'power': {'value': {'label': power}},
        'might': {'value': {'label': might}},
        'text': {'richText': {'body': text}},
        'illustrator': {'values': [{'label': artist}] if artist else []},
        'tags': {'tags': []},
    }
    if subtitle is not None:
        item['subtitle'] = subtitle
    if set_id is not None:
        item['set'] = {'label': 'Card Set', 'value': {'id': set_id, 'label': set_id.title()}}
    if with_image:
        item['cardImage'] = {'url': f'https://img.test/{card_id}.png?accountingTag=RB'}
    return item


_RUNE_DOMAINS = {1: 'Fury', 2: 'Calm', 3: 'Mind', 4: 'Body', 5: 'Chaos', 6: 'Order'}


def _rune(set_id, number, variant=''):
    domain = _RUNE_DOMAINS[number]
    return gallery_item(f'{set_id.lower()}-r0{number}{variant}', f'{domain} Rune',
                        set_id=set_id, card_type='Rune', supertypes=('Basic',),
                        rarity='Showcase' if variant else 'Common', domain=domain,
                        text='<p>[NO TEXT]</p>', artist=None)


def _special(set_id, number, total, name, subtitle):
    return gallery_item(f'{set_id.lower()}-sp{number}-{total}', name, set_id=set_id,
                        subtitle=subtitle, supertypes=('Champion',), rarity='Showcase')


# The 29 cards of the live gallery (measured 2026-11-18) the three old id patterns dropped.
REAL_NEW_ITEMS = (
    [_rune('RAD', n) for n in range(1, 7)]
    + [_rune('RAD', n, 'a') for n in range(1, 7)]
    + [_rune('VEN', n) for n in range(1, 7)]
    + [_special('RAD', 1, '005', 'Ahri', 'Confident'),
       _special('RAD', 2, '005', 'Akali', 'Brash'),
       _special('RAD', 3, '005', 'Evelynn', 'In Control'),
       _special('RAD', 4, '005', "Kai'Sa", 'Rebel'),
       _special('RAD', 5, '005', 'Seraphine', 'Not Alone'),
       _special('VEN', 1, '006', "Kai'Sa", 'Survivor'),
       _special('VEN', 2, '006', 'Sona', 'Harmonious'),
       _special('VEN', 3, '006', 'Ahri', 'Inquisitive'),
       _special('VEN', 4, '006', 'Sett', 'Brawler'),
       _special('VEN', 5, '006', 'Ezreal', 'Prodigy'),
       _special('VEN', 6, '006', 'Lux', 'Crownguard')]
)

# raw id -> (set, stored id, image name) for every item of REAL_NEW_ITEMS.
REAL_NEW_IDS = {
    **{f'rad-r0{n}': ('RAD', f'r0{n}', f'rad_r0{n}.png') for n in range(1, 7)},
    **{f'rad-r0{n}a': ('RAD', f'r0{n}a', f'rad_r0{n}a.png') for n in range(1, 7)},
    **{f'ven-r0{n}': ('VEN', f'r0{n}', f'ven_r0{n}.png') for n in range(1, 7)},
    **{f'rad-sp{n}-005': ('RAD', f'sp{n}', f'rad_sp{n}.png') for n in range(1, 6)},
    **{f'ven-sp{n}-006': ('VEN', f'sp{n}', f'ven_sp{n}.png') for n in range(1, 7)},
}
