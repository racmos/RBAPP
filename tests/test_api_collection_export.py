"""F3-d S1-S4 (AC1, AC2): GET /collection/export in the RBAPP and Cardmarket formats."""
import csv
import io

import pytest

from app import db
from app.models import RbCard, RbcmProduct
from tests.collection_read_helpers import line, seed_all, seed_catalog, seed_lines

URL = '/riftbound/api/v1/collection/export'
BOM = b'\xef\xbb\xbf'


@pytest.fixture
def api(app, authenticated_client, make_user, frozen_clock):
    make_user('otheruser')
    seed_all(app)
    return authenticated_client


def export(api, **params):
    return api.get(URL, query_string=params)


def table(response):
    text = response.get_data()
    assert text.startswith(BOM)
    return list(csv.reader(io.StringIO(text[len(BOM):].decode('utf-8'), newline='')))


class TestRbappFormat:
    def test_header_and_status(self, api):
        response = export(api, format='rbapp')
        assert response.status_code == 200
        assert response.headers['Content-Type'] == 'text/csv; charset=utf-8'
        assert table(response)[0] == ['set_id', 'card_id', 'name', 'foil', 'qty', 'condition',
                                      'language', 'purchase_price', 'selling', 'sell_qty',
                                      'sell_price']

    def test_rbapp_is_the_default_format(self, api):
        assert export(api).get_data() == export(api, format='rbapp').get_data()

    def test_one_row_per_line_in_catalog_order_with_exact_values(self, api):
        rows = table(export(api))[1:]
        assert rows == [
            ['OGN', '1', 'Alpha Fury', 'N', '4', 'NM', 'English', '8.00', 'Y', '1', '12.50'],
            ['OGN', '1', 'Alpha Fury', 'N', '2', 'LP', 'Spanish', '', 'N', '0', ''],
            ['OGN', '1', 'Alpha Fury', 'S', '1', 'NM', 'English', '20.00', 'N', '0', ''],
            ['OGN', '2', 'Beta Calm', 'N', '3', 'EX', 'French', '0.00', 'Y', '3', ''],
            ['OGN', '79', 'Jinx, Loose Cannon', 'N', '1', 'MT', 'English', '25.00', 'N', '0', ''],
            ['SFD', '10', 'Delta Gear', 'N', '2', 'NM', 'German', '', 'N', '0', ''],
            ['SFD', '257', 'Jinx, Loose Cannon', 'N', '1', 'NM', 'English', '', 'N', '0', ''],
        ]

    def test_minimal_quoting_and_plain_newlines(self, api):
        body = export(api).get_data()[len(BOM):].decode('utf-8')
        assert '"Jinx, Loose Cannon"' in body
        assert '"OGN"' not in body and '\r' not in body
        assert body.endswith('\n') and body.count('\n') == 8

    def test_filters_apply(self, api):
        assert [r[:2] for r in table(export(api, set='SFD'))[1:]] == [['SFD', '10'], ['SFD', '257']]
        assert [r[1] for r in table(export(api, condition='EX'))[1:]] == ['2']
        assert len(table(export(api, foil='foil'))) == 2

    def test_only_selling(self, api):
        rows = table(export(api, only_selling='true'))[1:]
        assert [(r[1], r[8]) for r in rows] == [('1', 'Y'), ('2', 'Y')]
        assert len(table(export(api, only_selling='false'))) == 8

    def test_never_exports_another_users_lines(self, api):
        assert sum(int(r[4]) for r in table(export(api))[1:]) == 14     # not 14 + 9


class TestCardmarketFormat:
    def test_only_the_copies_for_sale_with_price_rules(self, api):
        response = export(api, format='cardmarket')
        text = response.get_data()[len(BOM):].decode('utf-8')
        assert text == ('"name","language","quantity","price"\n'
                        '"Alpha Fury","English","1","12.50"\n'
                        '"Beta Calm","French","3","5.00"\n')

    def test_only_selling_is_forced(self, api):
        a = export(api, format='cardmarket', only_selling='false').get_data()
        assert a == export(api, format='cardmarket').get_data()

    def test_unpriced_lines_cost_zero(self, app, api):
        with app.app_context():
            db.session.add(line('10', 2, set_id='SFD', selling='Y', sell_qty=2))
            db.session.commit()
        text = export(api, format='cardmarket').get_data().decode('utf-8-sig')
        assert '"Delta Gear","English","2","0.00"' in text

    def test_the_cardmarket_product_name_wins(self, app, api):
        with app.app_context():
            db.session.add(RbcmProduct(rbprd_date='20261020', rbprd_id_product=2,
                                       rbprd_name='Beta Calm [Origins]', rbprd_type='single'))
            db.session.commit()
        text = export(api, format='cardmarket').get_data().decode('utf-8-sig')
        assert '"Beta Calm [Origins]","French","3","5.00"' in text

    def test_rows_with_nothing_to_sell_are_skipped(self, app, api):
        with app.app_context():
            db.session.add(line('79', 2, selling='Y', sell_qty=0))
            db.session.commit()
        response = export(api, format='cardmarket')
        assert response.headers['X-Rows-Exported'] == '2'
        assert 'Jinx' not in response.get_data(as_text=True)


class TestGoldenAgainstTheJinjaExport:
    def test_same_bytes_after_the_bom(self, app, api):
        with app.app_context():
            db.session.add_all([
                line('1', 3, foil='S', condition='NM', selling='Y', sell_qty=2, sell_price=40.5),
                line('1', 2, condition='EX', language='Spanish', selling='Y', sell_qty=2),
                line('2', 1, condition='MT', selling='Y', sell_qty=1, language='German',
                     sell_price=0.1),
            ])
            db.session.add(RbcmProduct(rbprd_date='20261020', rbprd_id_product=11,
                                       rbprd_name='Alpha Fury (Foil)', rbprd_type='single'))
            db.session.commit()
        jinja = api.post('/riftbound/collection/export_csv',
                         json={'rbset_id': 'OGN', 'rarity': 'Common'})
        mine = export(api, format='cardmarket', set='OGN', rarity='Common')
        assert jinja.status_code == mine.status_code == 200
        assert jinja.get_data().startswith(BOM) and mine.get_data().startswith(BOM)
        assert mine.get_data() == jinja.get_data()
        assert mine.headers['X-Rows-Exported'] == jinja.headers['X-Rows-Exported'] == '3'


class TestHeadersAndStreaming:
    def test_file_names_use_the_utc_clock(self, api):
        rbapp = export(api, format='rbapp')
        cardmarket = export(api, format='cardmarket')
        assert rbapp.headers['Content-Disposition'] == (
            'attachment; filename="rbapp_collection_20300101120000.csv"')
        assert cardmarket.headers['Content-Disposition'] == (
            'attachment; filename="20300101120000_cardmarket.csv"')

    def test_rows_exported_header(self, api):
        assert export(api).headers['X-Rows-Exported'] == '7'
        assert export(api, set='SFD').headers['X-Rows-Exported'] == '2'
        assert export(api, set='ZZZ').headers['X-Rows-Exported'] == '0'

    def test_an_empty_export_is_just_the_header(self, api):
        assert len(table(export(api, set='ZZZ'))) == 1

    def test_the_answer_is_streamed(self, api):
        assert export(api, format='rbapp').is_streamed
        assert export(api, format='cardmarket').is_streamed

    def test_unknown_format_and_bad_filters_are_a_400(self, api):
        for params in ({'format': 'xml'}, {'format': 'rbapp', 'foil': 'x'},
                       {'only_selling': 'maybe'}):
            response = export(api, **params)
            assert response.status_code == 400, params
            assert response.get_json()['code'] == 'validation_error'

    def test_requires_a_session(self, app):
        assert app.test_client().get(URL).status_code == 401


class TestSpreadsheetInjection:
    @pytest.fixture
    def evil(self, app, api):
        with app.app_context():
            db.session.add_all([
                RbCard(rbcar_rbset_id='OGN', rbcar_id='90', rbcar_name='=HYPERLINK("x")',
                       rbcar_type='Unit', rbcar_rarity='Common'),
                RbCard(rbcar_rbset_id='OGN', rbcar_id='91', rbcar_name='@cmd', rbcar_type='Unit',
                       rbcar_rarity='Common'),
                RbCard(rbcar_rbset_id='OGN', rbcar_id='92', rbcar_name='-1+1', rbcar_type='Unit',
                       rbcar_rarity='Common'),
                RbCard(rbcar_rbset_id='OGN', rbcar_id='93', rbcar_name='+SUM(A1)',
                       rbcar_type='Unit', rbcar_rarity='Common'),
            ])
            db.session.add_all([line(c, 1, language='=1+1', selling='Y', sell_qty=1)
                                for c in ('90', '91', '92', '93')])
            db.session.commit()

    def test_rbapp_text_cells_are_defused(self, api, evil):
        rows = {r[1]: r for r in table(export(api))[1:]}
        assert rows['90'][2] == '\'=HYPERLINK("x")'
        assert rows['91'][2] == "'@cmd"
        assert rows['92'][2] == "'-1+1"
        assert rows['93'][2] == "'+SUM(A1)"
        assert rows['90'][6] == "'=1+1"

    def test_cardmarket_text_cells_are_defused(self, api, evil):
        rows = table(export(api, format='cardmarket'))[1:]
        names = {r[0] for r in rows}
        assert {'\'=HYPERLINK("x")', "'@cmd", "'-1+1", "'+SUM(A1)"} <= names
        assert {r[1] for r in rows if r[0].startswith("'")} == {"'=1+1"}

    def test_numbers_and_safe_text_are_untouched(self, api, evil):
        rows = table(export(api))[1:]
        assert rows[0][2] == 'Alpha Fury' and rows[0][7] == '8.00'
