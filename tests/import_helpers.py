"""Helpers of the F3-e tests (collection import)."""
import csv
import io

HEADER = ['set_id', 'card_id', 'name', 'foil', 'qty', 'condition', 'language', 'purchase_price',
          'selling', 'sell_qty', 'sell_price']
PREVIEW = '/riftbound/api/v1/collection/import/preview'
COMMIT = '/riftbound/api/v1/collection/import/commit'


def row(set_id='OGN', card_id='1', name='Alpha Fury', foil='N', qty='1', condition='',
        language='', purchase_price='', selling='', sell_qty='', sell_price=''):
    return [set_id, card_id, name, foil, qty, condition, language, purchase_price, selling,
            sell_qty, sell_price]


def make_csv(rows, header=None, bom=False):
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator='\n')
    writer.writerow(header if header is not None else HEADER)
    writer.writerows(rows)
    return ('\ufeff' if bom else '') + buffer.getvalue()
