"""
Collection quantity (unit b, specs QTY-2..QTY-4).

`rbcol_quantity` is an integer NOT NULL column since revision 0003. These
tests pin how the collection routes store, read, sort and import it.
"""
import re
from contextlib import contextmanager
from pathlib import Path

import pytest
import sqlalchemy as sa
from flask import template_rendered

from app import db
from app.models import RbCard, RbCollection, RbSet
from app.routes.domains import collection as collection_routes

SET_ID = 'QTY1'
USER = 'testuser'            # the user created by the authenticated_client fixture
COLLECTION_ROUTES = Path(collection_routes.__file__)


def _seed_cards(app, *card_ids, rarity='Common'):
    with app.app_context():
        db.session.add(RbSet(rbset_id=SET_ID, rbset_name='Quantity Set', rbset_ncard=100))
        for card_id in card_ids:
            db.session.add(RbCard(rbcar_rbset_id=SET_ID, rbcar_id=card_id,
                                  rbcar_name=f'Card {card_id}', rbcar_rarity=rarity))
        db.session.commit()


def _seed_lines(app, **quantities):
    """One collection line per `card_id=quantity` for the authenticated user."""
    with app.app_context():
        for card_id, quantity in quantities.items():
            db.session.add(RbCollection(
                rbcol_rbset_id=SET_ID, rbcol_rbcar_id=card_id, rbcol_foil='N',
                rbcol_user=USER, rbcol_quantity=quantity))
        db.session.commit()


def _lines(app, user=USER):
    with app.app_context():
        return [(r.rbcol_rbcar_id, r.rbcol_foil, r.rbcol_quantity)
                for r in RbCollection.query.filter_by(rbcol_user=user)
                .order_by(RbCollection.rbcol_id)]


@contextmanager
def _captured_templates(app):
    recorded = []

    def record(sender, template, context, **extra):
        recorded.append((template, context))

    template_rendered.connect(record, app)
    try:
        yield recorded
    finally:
        template_rendered.disconnect(record, app)


def _listed_quantities(app, client, order):
    with _captured_templates(app) as rendered:
        resp = client.get(f'/riftbound/collection?sort_by=quantity&sort_order={order}&per_page=100')
    assert resp.status_code == 200
    (_, context), = [r for r in rendered if r[0].name == 'collection.html']
    return [d['collection'].rbcol_quantity for d in context['collections_data']]


# --- QTY-2: numeric ordering -------------------------------------------------

class TestNumericSort:
    @pytest.mark.parametrize('order,expected', [('asc', [2, 3, 10]), ('desc', [10, 3, 2])])
    def test_sorts_by_number_not_by_text(self, app, authenticated_client, order, expected):
        _seed_cards(app, 'a', 'b', 'c')
        _seed_lines(app, a=2, b=10, c=3)
        assert _listed_quantities(app, authenticated_client, order) == expected

    def test_ten_vs_nine_boundary(self, app, authenticated_client):
        # as text '10' < '9'; as numbers 9 < 10
        _seed_cards(app, 'a', 'b')
        _seed_lines(app, a=10, b=9)
        assert _listed_quantities(app, authenticated_client, 'asc') == [9, 10]


# --- QTY-3: atomic merge, integers everywhere --------------------------------

def _add(client, quantity, card_id='a'):
    return client.post('/riftbound/collection/add', json={
        'rbcol_rbset_id': SET_ID, 'rbcol_rbcar_id': card_id, 'rbcol_foil': 'N',
        'rbcol_quantity': quantity, 'rbcol_selling': 'N'})


class TestAtomicMerge:
    def test_sequential_adds_leave_one_line_with_the_integer_sum(self, app, authenticated_client):
        _seed_cards(app, 'a')
        _seed_lines(app, a=1)
        r1, r2 = _add(authenticated_client, 2), _add(authenticated_client, 3)
        assert r1.get_json()['merged'] is True and r2.get_json()['merged'] is True
        with app.app_context():
            [line] = RbCollection.query.all()
            assert line.rbcol_quantity == 6 and isinstance(line.rbcol_quantity, int)

    def test_a_concurrent_write_between_read_and_update_is_not_lost(
            self, app, authenticated_client, monkeypatch):
        """No read-modify-write: another writer adds 10 after this request has
        read the line but before it writes. An increment done in SQL keeps both."""
        _seed_cards(app, 'a')
        _seed_lines(app, a=1)
        real_find = collection_routes._find_exact_duplicate

        def find_then_race(**kwargs):
            row = real_find(**kwargs)
            db.session.execute(
                sa.update(RbCollection).where(RbCollection.rbcol_id == row.rbcol_id)
                .values(rbcol_quantity=RbCollection.rbcol_quantity + 10)
                .execution_options(synchronize_session=False))
            return row

        monkeypatch.setattr(collection_routes, '_find_exact_duplicate', find_then_race)
        assert _add(authenticated_client, 2).get_json()['merged'] is True
        with app.app_context():
            assert RbCollection.query.one().rbcol_quantity == 13       # 1 + 10 + 2

    def test_new_line_stores_an_integer(self, app, authenticated_client):
        _seed_cards(app, 'a')
        assert _add(authenticated_client, 4).get_json()['merged'] is False
        with app.app_context():
            line = RbCollection.query.one()
            assert line.rbcol_quantity == 4 and isinstance(line.rbcol_quantity, int)

    def test_update_quantity_stores_an_integer(self, app, authenticated_client):
        _seed_cards(app, 'a')
        _seed_lines(app, a=1)
        with app.app_context():
            line_id = RbCollection.query.one().rbcol_id
        resp = authenticated_client.post('/riftbound/collection/update_quantity',
                                         json={'rbcol_id': line_id, 'quantity': 7})
        assert resp.get_json() == {'success': True}
        with app.app_context():
            assert RbCollection.query.one().rbcol_quantity == 7

    def test_bulk_apply_sets_the_quantity_and_derives_playset_from_integers(
            self, app, authenticated_client):
        _seed_cards(app, 'a')
        with app.app_context():
            db.session.add_all([
                RbCollection(rbcol_rbset_id=SET_ID, rbcol_rbcar_id='a', rbcol_foil='S',
                             rbcol_user=USER, rbcol_quantity=1),
                RbCollection(rbcol_rbset_id=SET_ID, rbcol_rbcar_id='a', rbcol_foil='N',
                             rbcol_user=USER, rbcol_quantity=1)])
            db.session.commit()
            ids = [r.rbcol_id for r in RbCollection.query.order_by(RbCollection.rbcol_id)]
        resp = authenticated_client.post('/riftbound/collection/bulk_apply',
                                         json={'ids': ids, 'quantity': 12, 'playset': 3})
        assert resp.get_json() == {'success': True, 'updated': 2}
        with app.app_context():
            by_foil = {r.rbcol_foil: (r.rbcol_quantity, r.rbcol_playset, r.rbcol_selling)
                       for r in RbCollection.query.all()}
        # foil first takes the whole playset; the surplus of both lines is for sale
        assert by_foil == {'S': (12, 3, 'Y'), 'N': (12, None, 'Y')}

    def test_playset_update_compares_integer_quantity(self, app, authenticated_client):
        _seed_cards(app, 'a', 'b')
        _seed_lines(app, a=12, b=3)
        with app.app_context():
            ids = {r.rbcol_rbcar_id: r.rbcol_id for r in RbCollection.query.all()}
        for card in ('a', 'b'):
            authenticated_client.post('/riftbound/collection/update_playset',
                                      json={'rbcol_id': ids[card], 'rbcol_playset': 3})
        with app.app_context():
            assert {r.rbcol_rbcar_id: r.rbcol_selling for r in RbCollection.query.all()} == {
                'a': 'Y', 'b': 'N'}

    def test_export_subtracts_the_playset_arithmetically(self, app, authenticated_client):
        _seed_cards(app, 'a', 'b')
        with app.app_context():
            db.session.add_all([
                RbCollection(rbcol_rbset_id=SET_ID, rbcol_rbcar_id='a', rbcol_foil='N',
                             rbcol_user=USER, rbcol_quantity=12, rbcol_playset=3,
                             rbcol_selling='Y'),
                RbCollection(rbcol_rbset_id=SET_ID, rbcol_rbcar_id='b', rbcol_foil='N',
                             rbcol_user=USER, rbcol_quantity=2, rbcol_playset=3,
                             rbcol_selling='Y')])
            db.session.commit()
        resp = authenticated_client.post('/riftbound/collection/export_csv',
                                         json={'rbset_id': SET_ID, 'rarity': 'Common'})
        body = resp.get_data(as_text=True).lstrip('﻿').splitlines()
        assert body[0] == '"name","language","quantity","price"'
        # a: 12 - 3 = 9 ; b: 2 - 3 < 0 is not exported
        assert [line.split(',')[2] for line in body[1:]] == ['"9"']
        assert resp.headers['X-Rows-Exported'] == '1'


class TestNoTextQuantityLeftovers:
    """QTY-3 code review (task 2.28) as a test: nothing converts quantities
    to or from text any more, and no read-modify-write is left."""

    def test_no_text_helper_or_string_write(self):
        source = COLLECTION_ROUTES.read_text(encoding='utf-8')
        assert '_qty_int' not in source
        assert not re.search(r'rbcol_quantity\s*=\s*str\(', source)
        assert not re.search(r'rbcol_quantity\s*=\s*rbcol_quantity\b', source)

    def test_merge_is_a_sql_expression(self):
        source = COLLECTION_ROUTES.read_text(encoding='utf-8')
        assert re.search(r'existing\.rbcol_quantity\s*=\s*RbCollection\.rbcol_quantity\s*\+', source)


# --- QTY-4: validated CSV import ---------------------------------------------

IMPORT_URL = '/riftbound/collection/import_csv'
MIXED_INPUT = ('OGN;1;N;3\nOGN;999;N;1\nOGN;1;X;1\nOGN;1;N;abc\n'
               'OGN;1;N;0\nOGN;1;S;10000\nbad')


def _seed_ogn(app):
    with app.app_context():
        db.session.add(RbSet(rbset_id='OGN', rbset_name='Origins', rbset_ncard=10))
        db.session.add(RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='Ahri',
                              rbcar_rarity='Common'))
        db.session.add(RbCard(rbcar_rbset_id='OGN', rbcar_id='2', rbcar_name='Annie',
                              rbcar_rarity='Common'))
        db.session.commit()


def _import(client, csv_data):
    return client.post(IMPORT_URL, json={'csv_data': csv_data})


class TestImportCsv:
    def test_mixed_input_applies_one_line_and_reports_the_other_six(
            self, app, authenticated_client):
        _seed_ogn(app)
        resp = _import(authenticated_client, MIXED_INPUT)
        body = resp.get_json()
        assert resp.status_code == 200
        assert body['success'] is True
        assert body['imported'] == 1
        assert [s['line'] for s in body['skipped']] == [2, 3, 4, 5, 6, 7]
        reasons = [s['reason'] for s in body['skipped']]
        assert 'exist' in reasons[0]                       # OGN/999
        assert 'foil' in reasons[1]                        # X
        assert 'quantity' in reasons[2]                    # abc
        assert 'quantity' in reasons[3]                    # 0
        assert 'quantity' in reasons[4]                    # 10000
        assert 'fields' in reasons[5]                      # bad
        assert _lines(app) == [('1', 'N', 3)]

    def test_overwrite_keeps_one_row_with_the_new_integer_quantity(
            self, app, authenticated_client):
        _seed_ogn(app)
        with app.app_context():
            db.session.add(RbCollection(rbcol_rbset_id='OGN', rbcol_rbcar_id='1', rbcol_foil='N',
                                        rbcol_user=USER, rbcol_quantity=5))
            db.session.commit()
        body = _import(authenticated_client, 'OGN;1;N;2').get_json()
        assert (body['imported'], body['skipped']) == (1, [])
        assert _lines(app) == [('1', 'N', 2)]

    def test_same_card_twice_in_one_import_last_line_wins(self, app, authenticated_client):
        _seed_ogn(app)
        body = _import(authenticated_client, 'OGN;1;N;3\nOGN;1;N;4').get_json()
        assert body['imported'] == 2
        assert _lines(app) == [('1', 'N', 4)]

    def test_foil_and_non_foil_are_separate_lines(self, app, authenticated_client):
        _seed_ogn(app)
        _import(authenticated_client, 'OGN;1;N;1\nOGN;1;S;2')
        assert _lines(app) == [('1', 'N', 1), ('1', 'S', 2)]

    @pytest.mark.parametrize('text,expected_lines,imported', [
        ('OGN;1;N;3\r\nOGN;2;S;4\r\n', [('1', 'N', 3), ('2', 'S', 4)], 2),
        ('\n\nOGN;1;N;3\n\n   \nOGN;2;N;9999\n', [('1', 'N', 3), ('2', 'N', 9999)], 2),
        ('  OGN ; 1 ; N ;  7  ', [('1', 'N', 7)], 1),
    ], ids=['crlf', 'blank-lines', 'padding'])
    def test_carriage_returns_blank_lines_and_padding_are_tolerated(
            self, app, authenticated_client, text, expected_lines, imported):
        _seed_ogn(app)
        body = _import(authenticated_client, text).get_json()
        assert (body['imported'], body['skipped']) == (imported, [])
        assert _lines(app) == expected_lines

    def test_line_numbers_count_blank_lines(self, app, authenticated_client):
        _seed_ogn(app)
        body = _import(authenticated_client, 'OGN;1;N;3\n\nOGN;1;N;0\n').get_json()
        assert [s['line'] for s in body['skipped']] == [3]

    @pytest.mark.parametrize('quantity,ok', [('1', True), ('9999', True), ('0', False),
                                             ('10000', False), ('-3', False), ('1.5', False)])
    def test_quantity_range_boundaries(self, app, authenticated_client, quantity, ok):
        _seed_ogn(app)
        body = _import(authenticated_client, f'OGN;1;N;{quantity}').get_json()
        assert body['imported'] == (1 if ok else 0)
        assert len(body['skipped']) == (0 if ok else 1)

    def test_scoped_to_the_caller(self, app, authenticated_client):
        _seed_ogn(app)
        with app.app_context():
            db.session.add(RbCollection(rbcol_rbset_id='OGN', rbcol_rbcar_id='1', rbcol_foil='N',
                                        rbcol_user='bob', rbcol_quantity=9))
            db.session.commit()
        body = _import(authenticated_client, 'OGN;1;N;4').get_json()
        assert body['imported'] == 1
        assert _lines(app, user='bob') == [('1', 'N', 9)]
        assert _lines(app, user=USER) == [('1', 'N', 4)]

    def test_nothing_valid_still_succeeds_with_everything_skipped(self, app, authenticated_client):
        _seed_ogn(app)
        resp = _import(authenticated_client, 'OGN;9;N;1')
        assert resp.status_code == 200
        assert resp.get_json()['imported'] == 0
        assert _lines(app) == []


class TestImportCsvBadBody:
    def _assert_envelope(self, resp):
        body = resp.get_json()
        assert resp.status_code == 400
        assert body['success'] is False
        assert body['error'] and body['message']

    def test_non_json_body(self, app, authenticated_client):
        resp = authenticated_client.post(IMPORT_URL, data='OGN;1;N;3',
                                         content_type='text/plain')
        self._assert_envelope(resp)

    def test_json_without_csv_data(self, app, authenticated_client):
        self._assert_envelope(authenticated_client.post(IMPORT_URL, json={'other': 1}))

    @pytest.mark.parametrize('body', [[1, 2], 'text', 5, {'csv_data': 7}, {'csv_data': None}])
    def test_json_of_the_wrong_shape(self, app, authenticated_client, body):
        self._assert_envelope(authenticated_client.post(IMPORT_URL, json=body))

    def test_malformed_json(self, app, authenticated_client):
        resp = authenticated_client.post(IMPORT_URL, data='{not json',
                                         content_type='application/json')
        self._assert_envelope(resp)

    def test_requires_login(self, client):
        resp = client.post(IMPORT_URL, json={'csv_data': 'OGN;1;N;3'})
        assert resp.status_code in (302, 401)
