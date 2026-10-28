"""Shared helpers of the F3-c tests (collection write API). Prices come from
`tests/collection_read_helpers.seed_catalog`: OGN/1 10 (foil 30), OGN/2 5, OGN/79 20 (rare, no foil),
SFD/10 and SFD/257 unpriced."""
from app import db
from app.models import RbCollection
from tests.collection_read_helpers import line, seed_catalog

BASE = '/riftbound/api/v1/collection'


def card(card_id='1', set_id='OGN', **body):
    return {'set_id': set_id, 'card_id': card_id, 'foil': False, 'qty': 1, **body}


def fetch(line_id):
    db.session.expire_all()
    return db.session.get(RbCollection, line_id)


def all_rows(user='testuser'):
    db.session.expire_all()
    return RbCollection.query.filter_by(rbcol_user=user).order_by(RbCollection.rbcol_id).all()


__all__ = ['BASE', 'card', 'fetch', 'all_rows', 'line', 'seed_catalog']
