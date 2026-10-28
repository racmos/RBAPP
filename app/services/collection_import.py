"""Collection import from a CSV file (F3-e): a preview that explains every row, then a commit.

`create_preview` parses the RBAPP format (the file `GET /collection/export` writes), checks every
row against the catalog and stores what the commit needs in `rbimportpreviews` for 30 minutes.
`commit_preview` applies it in one transaction: all of it or nothing. The file is untrusted:
size and row limits are checked before anything is parsed row by row, and every cell is
validated.
"""
import csv
import io
import re
import uuid
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import sqlalchemy as sa

from app import db
from app.models import RbCard, RbCollection, RbImportPreview, RbSet
from app.schemas.game_domain import CONDITIONS
from app.services import bans as bans_service
from app.services import catalog, collection_write, pricing
from app.utils import clock

MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 10_000
TTL = timedelta(minutes=30)
COLUMNS = ('set_id', 'card_id', 'name', 'foil', 'qty', 'condition', 'language', 'purchase_price',
           'selling', 'sell_qty', 'sell_price')
FORMAT = 'rbapp'
_DANGEROUS = ('=', '+', '-', '@', '\t', '\r')
_FOIL = {'s': True, 'true': True, '1': True, 'n': False, 'false': False, '0': False}
_ERRORS = {'card_not_found', 'invalid_value', 'foil_not_allowed', 'invalid_qty', 'invalid_price',
           'invalid_sell_qty'}
CENT = Decimal('0.01')
_REPLACE_CHUNK = 400


class FormatUnknown(Exception):
    """The header is not a known format."""


class TooBig(Exception):
    """The text is over the size or row limit; `args[0]` says which."""


class PreviewExpired(Exception):
    """The preview is unknown, expired or not the user's."""


def _undefuse(cell: str) -> str:
    """Undo the leading `'` the export puts before text that looks like a formula."""
    return cell[1:] if len(cell) > 1 and cell[0] == "'" and cell[1] in _DANGEROUS else cell


def _price(cell: str):
    """`(value, ok)`: empty is `(None, True)`; `.` or `,` as the decimal separator."""
    if cell == '':
        return None, True
    try:
        value = Decimal(cell.replace(',', '.'))
    except InvalidOperation:
        return None, False
    if not value.is_finite() or value < 0 or value > Decimal('99999.99'):
        return None, False
    return value.quantize(CENT, ROUND_HALF_UP), True


def _int(cell: str):
    return int(cell) if re.fullmatch(r'[0-9]{1,6}', cell) else None


def _read(text: str) -> tuple[dict[str, int], list[tuple[int, list[str]]]]:
    """The column positions and the `(line, cells)` of the data rows, or raise."""
    if len(text.encode('utf-8')) > MAX_BYTES:
        raise TooBig('text is over 2 MB')
    text = text.lstrip('﻿')
    reader = csv.reader(io.StringIO(text, newline=''))
    try:
        header = next(reader, None)
        if header is None:
            raise FormatUnknown()
        names = [cell.strip().lower() for cell in header]
        columns = {name: index for index, name in enumerate(names) if name in COLUMNS}
        if set(columns) != set(COLUMNS):
            raise FormatUnknown()
        rows = []
        for cells in reader:
            if not any(cell.strip() for cell in cells):
                continue
            rows.append((reader.line_num, cells))
            if len(rows) > MAX_ROWS:
                raise TooBig('text has more than 10 000 rows')
    except csv.Error:
        raise FormatUnknown() from None
    return columns, rows


def _check_row(line: int, cells: list[str], columns: dict, cards: dict, seen: set) -> dict:
    def cell(name):
        index = columns[name]
        return _undefuse(cells[index].strip()) if index < len(cells) else ''

    codes = []
    set_id, card_id = cell('set_id').upper(), cell('card_id').lower()
    card = cards.get((set_id, card_id))
    if card is None:
        codes.append('card_not_found')
    elif catalog.name_key(cell('name')) != catalog.name_key(card.rbcar_name):
        codes.append('name_mismatch')

    foil = _FOIL.get(cell('foil').lower())
    if foil is None:
        codes.append('invalid_value')
    elif foil and card is not None:
        card_type, _ = catalog.parse_type(card.rbcar_type)
        if not catalog.is_foilable(card_type, card.rbcar_rarity):
            codes.append('foil_not_allowed')

    qty = _int(cell('qty'))
    if qty is None or not 1 <= qty <= 9999:
        qty = None
        codes.append('invalid_qty')

    condition = None
    if cell('condition'):
        condition = next((c for c in CONDITIONS if c.lower() == cell('condition').lower()), None)
        if condition is None:
            codes.append('unknown_condition')

    language = cell('language') or None
    if language is not None and len(language) > 40:
        language = None
        codes.append('invalid_value')

    purchase, purchase_ok = _price(cell('purchase_price'))
    sell_price, sell_price_ok = _price(cell('sell_price'))
    if not purchase_ok or not sell_price_ok:
        codes.append('invalid_price')

    selling_cell = cell('selling').upper()
    if selling_cell not in ('', 'Y', 'N'):
        codes.append('invalid_value')
    selling = selling_cell == 'Y'

    sell_qty = None
    if cell('sell_qty') == '':
        sell_qty = (qty or 0) if selling else 0
    else:
        sell_qty = _int(cell('sell_qty'))
        if sell_qty is None or (qty is not None and sell_qty > qty):
            sell_qty = None
            codes.append('invalid_sell_qty')

    row = {'line': line, 'set_id': set_id, 'card_id': card_id, 'foil': foil, 'qty': qty,
           'condition': condition, 'language': language,
           'purchase_price': None if purchase is None else str(purchase), 'selling': selling,
           'sell_qty': sell_qty, 'sell_price': None if sell_price is None else str(sell_price)}
    if any(code in _ERRORS for code in codes):
        row['status'] = 'error'
    else:
        key = (set_id, card_id, foil, condition, language, row['purchase_price'], selling,
               row['sell_price'])
        if key in seen:
            codes.append('duplicate_row')
        seen.add(key)
        row['status'] = 'warning' if codes else 'ok'
    row['reason_codes'] = codes
    return row


def _summary_cards(rows: list[dict], cards: dict) -> dict:
    """`CardSummary` of every resolved printing of `rows`, priced in one batch."""
    keys = {(r['set_id'], r['card_id']) for r in rows if (r['set_id'], r['card_id']) in cards}
    if not keys:
        return {}
    set_rank = catalog.set_order(db.session.query(RbSet).all())
    base_keys = catalog.base_printing_keys(list(cards.values()), set_rank)
    bans = bans_service.ban_map()
    printings = []
    for key in keys:
        card = cards[key]
        card_type, _ = catalog.parse_type(card.rbcar_type)
        printings.append((key[0], key[1], card.rbcar_rarity,
                          catalog.is_foilable(card_type, card.rbcar_rarity)))
    prices = pricing.price_summaries(printings)
    return {key: catalog.card_summary(cards[key], set_rank=set_rank, base_keys=base_keys,
                                      price=prices.get(key), bans=bans)
            for key in keys}


def _public(row: dict, summaries: dict) -> dict:
    out = {k: row[k] for k in ('line', 'status', 'reason_codes')}
    summary = summaries.get((row['set_id'], row['card_id']))
    if summary is not None:
        out['card'] = summary
    out.update(set_id=row['set_id'], card_id=row['card_id'], foil=row['foil'], qty=row['qty'],
               condition=row['condition'], language=row['language'],
               purchase_price=None if row['purchase_price'] is None else float(row['purchase_price']),
               selling=row['selling'], sell_qty=row['sell_qty'],
               sell_price=None if row['sell_price'] is None else float(row['sell_price']))
    return out


def create_preview(user, text: str, fmt: str = 'auto') -> dict:
    """Parse `text`, store the preview and return `{preview_id, format, rows, summary}`."""
    now = clock.utcnow()
    db.session.execute(sa.delete(RbImportPreview).where(
        sa.or_(RbImportPreview.rbimp_expires_at < now, RbImportPreview.rbimp_user_id == user.id)))
    columns, raw_rows = _read(text)

    cards = {(c.rbcar_rbset_id, c.rbcar_id): c for c in db.session.query(RbCard).all()}
    seen: set = set()
    rows = [_check_row(line, cells, columns, cards, seen) for line, cells in raw_rows]

    preview = RbImportPreview(rbimp_id=str(uuid.uuid4()), rbimp_user_id=user.id,
                              rbimp_format=FORMAT, rbimp_rows=rows, rbimp_created_at=now,
                              rbimp_expires_at=now + TTL)
    db.session.add(preview)
    db.session.commit()

    summaries = _summary_cards(rows, cards)
    counts = {'ok': 0, 'warning': 0, 'error': 0}
    for row in rows:
        counts[row['status']] += 1
    printings = {(r['set_id'], r['card_id'], r['foil']) for r in rows if r['status'] != 'error'}
    return {'preview_id': preview.rbimp_id, 'format': FORMAT,
            'rows': [_public(row, summaries) for row in rows],
            'summary': {'total': len(rows), **counts, 'printings': len(printings)}}


def commit_preview(user, preview_id: str, mode: str) -> dict:
    """Apply a preview in one transaction (`add` or `replace`); returns the counts."""
    preview = db.session.get(RbImportPreview, preview_id)
    if preview is None or preview.rbimp_user_id != user.id \
            or preview.rbimp_expires_at <= clock.utcnow():
        raise PreviewExpired(preview_id)
    rows = preview.rbimp_rows
    valid = [r for r in rows if r['status'] in ('ok', 'warning')]
    skipped = len(rows) - len(valid)
    cards = {(c.rbcar_rbset_id, c.rbcar_id): c for c in db.session.query(RbCard).all()}
    now = clock.utcnow()

    try:
        replaced = 0
        if mode == 'replace':
            printings = sorted({(r['set_id'], r['card_id'], 'S' if r['foil'] else 'N')
                                for r in valid})
            for start in range(0, len(printings), _REPLACE_CHUNK):
                db.session.execute(sa.delete(RbCollection).where(
                    RbCollection.rbcol_user == user.username,
                    sa.tuple_(RbCollection.rbcol_rbset_id, RbCollection.rbcol_rbcar_id,
                              RbCollection.rbcol_foil).in_(printings[start:start + _REPLACE_CHUNK]))
                    .execution_options(synchronize_session=False))
            replaced = len(printings)

        # Rows with the same merge key add up first: one statement per distinct line.
        merged_keys: dict[tuple, dict] = {}
        for r in valid:
            key = (r['set_id'], r['card_id'], r['foil'], r['condition'], r['language'],
                   r['purchase_price'], r['selling'], r['sell_price'])
            if key in merged_keys:
                merged_keys[key]['qty'] += r['qty']
                merged_keys[key]['sell_qty'] += r['sell_qty']
                merged_keys[key]['rows'] += 1
            else:
                merged_keys[key] = {**r, 'rows': 1}

        created = merged = 0
        for r in merged_keys.values():
            money = lambda v: None if v is None else Decimal(v)
            _, was_merged = collection_write.add_row(
                user, cards[(r['set_id'], r['card_id'])], r['foil'], r['qty'], r['condition'],
                r['language'], money(r['purchase_price']), r['selling'], r['sell_qty'],
                money(r['sell_price']), now)
            created += 0 if was_merged else 1
            merged += r['rows'] - (0 if was_merged else 1)
        db.session.delete(preview)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return {'created': created, 'merged': merged, 'replaced': replaced, 'skipped': skipped}
