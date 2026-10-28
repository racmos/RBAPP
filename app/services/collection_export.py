"""CSV export of the collection (F3-d): the RBAPP format and the Cardmarket format.

`build_export` returns the rows and the file name; `stream` turns rows into CSV text one row
at a time. The lines come from `collection_read.export_lines`, so the filters and the prices
are those of `GET /collection`.
"""
import csv
import io
from collections.abc import Iterator
from decimal import Decimal

from app.services import collection_read, pricing
from app.utils import clock

BOM = '\ufeff'
RBAPP_HEADER = ['set_id', 'card_id', 'name', 'foil', 'qty', 'condition', 'language',
                'purchase_price', 'selling', 'sell_qty', 'sell_price']
CARDMARKET_HEADER = ['name', 'language', 'quantity', 'price']
_DANGEROUS = ('=', '+', '-', '@', '\t', '\r')


def defuse(text) -> str:
    """A text cell that a spreadsheet would read as a formula gets a leading `'` (S4)."""
    text = '' if text is None else str(text)
    return f"'{text}" if text.startswith(_DANGEROUS) else text


def _money(value: Decimal | None) -> str:
    return '' if value is None else f'{value:.2f}'


def _rbapp_rows(lines) -> Iterator[list[str]]:
    for line in lines:
        card = line.parsed['card']
        yield [defuse(line.key[0]), defuse(line.key[1]), defuse(card.rbcar_name),
               'S' if line.foil else 'N', str(line.qty), defuse(line.condition),
               defuse(line.language), _money(line.purchase), line.selling, str(line.sell_qty),
               _money(line.sell_price)]


def _cardmarket_rows(lines) -> Iterator[list[str]]:
    for line in lines:
        card = line.parsed['card']
        name = line.product_name or card.rbcar_name
        if line.sell_price is not None:
            price = float(line.sell_price)
        elif line.market is not None:
            price = float(line.market)
        else:
            price = 0.0
        yield [defuse(name), defuse(line.language), str(line.sell_qty), f'{price:.2f}']


def build_export(query, user) -> tuple[list[list[str]], list[str], str, int]:
    """`(rows, header, file_name, quoting)` for the format of `query`."""
    stamp = clock.utcnow().strftime('%Y%m%d%H%M%S')
    lines = collection_read.export_lines(query, user)
    if query.format == 'cardmarket':
        lines = [line for line in lines if line.selling == 'Y' and line.sell_qty > 0]
        names = pricing.product_names(
            {(line.key[0], line.key[1], 'S' if line.foil else 'N') for line in lines})
        for line in lines:
            line.product_name = names.get((line.key[0], line.key[1], 'S' if line.foil else 'N'))
        lines.sort(key=lambda line: (line.parsed['card'].rbcar_name, line.foil, line.id))
        return (list(_cardmarket_rows(lines)), CARDMARKET_HEADER,
                f'{stamp}_cardmarket.csv', csv.QUOTE_ALL)
    if query.only_selling:
        lines = [line for line in lines if line.selling == 'Y']
    return (list(_rbapp_rows(lines)), RBAPP_HEADER,
            f'rbapp_collection_{stamp}.csv', csv.QUOTE_MINIMAL)


def stream(rows, header, quoting) -> Iterator[str]:
    """The CSV text, BOM first, one row per chunk (`\\n` line endings)."""
    yield BOM
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=quoting, lineterminator='\n')
    for row in (header, *rows):
        writer.writerow(row)
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate()
