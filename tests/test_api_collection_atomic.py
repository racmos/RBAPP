"""F3-c AC6: merging and splitting add the quantity in SQL, never read-modify-write."""
import re

import pytest
from sqlalchemy import event

from app import db
from tests.collection_write_helpers import BASE, card, line, seed_catalog

INCREMENT = re.compile(r'rbcol_quantity\s*=\s*\(?\s*(riftbound\.)?(rbcollection\.)?rbcol_quantity\s*\+',
                       re.I)


@pytest.fixture
def api(app, authenticated_client):
    with app.app_context():
        seed_catalog()
    return authenticated_client


def statements(app, action):
    seen = []

    def listener(conn, cursor, statement, parameters, context, executemany):
        seen.append(statement)

    event.listen(db.engine, 'before_cursor_execute', listener)
    try:
        action()
    finally:
        event.remove(db.engine, 'before_cursor_execute', listener)
    return seen


def updates_of_quantity(seen):
    return [s for s in seen if s.lstrip().upper().startswith('UPDATE') and 'rbcol_quantity' in s]


def test_a_merge_increments_in_one_update(app, api):
    api.post(BASE, json=card(qty=2, condition='NM'))
    seen = statements(app, lambda: api.post(BASE, json=card(qty=3, condition='NM')))
    updates = updates_of_quantity(seen)
    assert len(updates) == 1 and INCREMENT.search(updates[0]), updates


def test_a_split_into_an_existing_line_increments_it_in_one_update(app, api):
    first = api.post(BASE, json=card(qty=5, condition='NM')).get_json()['data']['line']['id']
    api.post(BASE, json=card(qty=1, condition='EX'))
    seen = statements(app, lambda: api.post(f'{BASE}/{first}/split',
                                             json={'qty': 2, 'condition': 'EX'}))
    increments = [s for s in updates_of_quantity(seen) if INCREMENT.search(s)]
    assert len(increments) == 1, updates_of_quantity(seen)


def test_the_source_of_a_split_decrements_in_sql_too(app, api):
    first = api.post(BASE, json=card(qty=5)).get_json()['data']['line']['id']
    seen = statements(app, lambda: api.post(f'{BASE}/{first}/split',
                                             json={'qty': 2, 'condition': 'EX'}))
    assert any(re.search(r'rbcol_quantity\s*=\s*\(?\s*(riftbound\.)?(rbcollection\.)?rbcol_quantity\s*-',
                         s, re.I) for s in updates_of_quantity(seen))
