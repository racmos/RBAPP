"""F3-e S1-S4 (AC1): POST /collection/import/preview."""
from datetime import timedelta

import pytest

from app import db
from app.models import RbImportPreview, User
from tests.collection_read_helpers import seed_catalog
from tests.import_helpers import HEADER, PREVIEW, make_csv, row


@pytest.fixture
def api(app, authenticated_client, make_user, frozen_clock):
    make_user('otheruser')
    with app.app_context():
        seed_catalog()
    return authenticated_client


def preview(api, text, **extra):
    return api.post(PREVIEW, json={'text': text, **extra})


def rows_of(response):
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()['data']['rows']


def codes(response):
    return [r['reason_codes'] for r in rows_of(response)]


class TestFormatDetection:
    def test_rbapp_is_detected(self, api):
        data = preview(api, make_csv([row()])).get_json()['data']
        assert data['format'] == 'rbapp' and len(data['preview_id']) == 36

    def test_columns_in_any_order_with_extras_and_mixed_case(self, api):
        header = ['QTY', 'Extra', 'set_id', 'Card_Id', 'foil', 'name', 'condition', 'language',
                  'purchase_price', 'selling', 'sell_qty', 'sell_price']
        text = make_csv([['2', 'zzz', 'ogn', '1', 'N', 'Alpha Fury', '', '', '', '', '', '']],
                        header=header)
        found = rows_of(preview(api, text, format='rbapp'))
        assert found[0]['status'] == 'ok' and found[0]['qty'] == 2

    def test_a_bom_is_stripped(self, api):
        assert rows_of(preview(api, make_csv([row()], bom=True)))[0]['status'] == 'ok'

    @pytest.mark.parametrize('text', [
        '', 'a,b,c\n1,2,3\n', ','.join(HEADER[:-1]) + '\n', 'name,language,quantity,price\n'])
    def test_other_headers_are_unknown(self, api, text):
        response = preview(api, text)
        body = response.get_json()
        assert response.status_code == 400 and body['code'] == 'import_format_unknown'
        assert RbImportPreview.query.count() == 0

    def test_a_header_only_file_is_a_valid_empty_preview(self, api):
        data = preview(api, make_csv([])).get_json()['data']
        assert data['summary'] == {'total': 0, 'ok': 0, 'warning': 0, 'error': 0, 'printings': 0}

    def test_format_must_be_auto_or_rbapp(self, api):
        assert preview(api, make_csv([row()]), format='xlsx').status_code == 400


class TestRowShape:
    def test_a_valid_row(self, api):
        found = rows_of(preview(api, make_csv([row(
            qty='3', condition='nm', language='English', purchase_price='8,5', selling='Y',
            sell_qty='2', sell_price='12.50')])))[0]
        assert found['status'] == 'ok' and found['reason_codes'] == []
        assert found['line'] == 2
        assert (found['foil'], found['qty'], found['condition'], found['language']) == (
            False, 3, 'NM', 'English')
        assert (found['purchase_price'], found['selling'], found['sell_qty'],
                found['sell_price']) == (8.5, True, 2, 12.5)
        assert found['card']['name'] == 'Alpha Fury' and found['card']['key'] == 'OGN-1'
        assert found['set_id'] == 'OGN' and found['card_id'] == '1'

    def test_set_is_upper_cased_and_card_lower_cased(self, api):
        text = make_csv([row(set_id='ogn', card_id='1'), row(set_id='Ogn', card_id='79', name='Jinx, Loose Cannon')])
        assert [r['status'] for r in rows_of(preview(api, text))] == ['ok', 'ok']
        db.session.expire_all()
        stored = RbImportPreview.query.one().rbimp_rows
        assert (stored[0]['set_id'], stored[0]['card_id']) == ('OGN', '1')

    def test_line_numbers_count_blank_lines_and_the_header(self, api):
        text = make_csv([row()]) + '\n' + ','.join(row(card_id='2')) + '\n'
        assert [r['line'] for r in rows_of(preview(api, text))] == [2, 4]

    def test_defaults_when_selling_columns_are_empty(self, api):
        found = rows_of(preview(api, make_csv([row(qty='4'), row(qty='4', selling='Y')])))
        assert (found[0]['selling'], found[0]['sell_qty']) == (False, 0)
        assert (found[1]['selling'], found[1]['sell_qty']) == (True, 4)

    def test_boolean_foil_spellings(self, api):
        text = make_csv([row(foil=f) for f in ('S', 's', 'true', 'TRUE', '1', 'n', 'false', '0')])
        assert [r['foil'] for r in rows_of(preview(api, text))] == [True] * 5 + [False] * 3


class TestReasonCodes:
    @pytest.mark.parametrize('cells, status, expected', [
        ({'set_id': 'ZZZ'}, 'error', ['card_not_found']),
        ({'card_id': '999'}, 'error', ['card_not_found']),
        ({'name': 'Something else'}, 'warning', ['name_mismatch']),
        ({'name': 'alpha   FURY'}, 'ok', []),
        ({'foil': 'maybe'}, 'error', ['invalid_value']),
        ({'foil': ''}, 'error', ['invalid_value']),
        ({'foil': 'S', 'set_id': 'OGN', 'card_id': '79', 'name': 'Jinx, Loose Cannon'},
         'error', ['foil_not_allowed']),
        ({'qty': '0'}, 'error', ['invalid_qty']),
        ({'qty': '10000'}, 'error', ['invalid_qty']),
        ({'qty': '1.5'}, 'error', ['invalid_qty']),
        ({'qty': 'x'}, 'error', ['invalid_qty']),
        ({'qty': ''}, 'error', ['invalid_qty']),
        ({'condition': 'mint'}, 'warning', ['unknown_condition']),
        ({'condition': 'ex'}, 'ok', []),
        ({'language': 'x' * 41}, 'error', ['invalid_value']),
        ({'purchase_price': '-1'}, 'error', ['invalid_price']),
        ({'purchase_price': 'abc'}, 'error', ['invalid_price']),
        ({'purchase_price': 'NaN'}, 'error', ['invalid_price']),
        ({'purchase_price': '100000'}, 'error', ['invalid_price']),
        ({'sell_price': '1,25'}, 'ok', []),
        ({'sell_price': 'x'}, 'error', ['invalid_price']),
        ({'selling': 'maybe'}, 'error', ['invalid_value']),
        ({'qty': '2', 'sell_qty': '3'}, 'error', ['invalid_sell_qty']),
        ({'qty': '2', 'sell_qty': '-1'}, 'error', ['invalid_sell_qty']),
        ({'qty': '2', 'sell_qty': 'a'}, 'error', ['invalid_sell_qty']),
        ({'qty': '2', 'sell_qty': '2'}, 'ok', []),
    ])
    def test_each_code(self, api, cells, status, expected):
        found = rows_of(preview(api, make_csv([row(**cells)])))[0]
        assert (found['status'], found['reason_codes']) == (status, expected), cells

    def test_an_unknown_condition_is_stored_as_null(self, api):
        found = rows_of(preview(api, make_csv([row(condition='mint')])))[0]
        assert found['condition'] is None

    def test_several_problems_in_one_row_are_all_listed(self, api):
        found = rows_of(preview(api, make_csv([row(qty='0', purchase_price='x')])))[0]
        assert found['reason_codes'] == ['invalid_qty', 'invalid_price']

    def test_an_unresolved_card_has_no_card_object(self, api):
        assert 'card' not in rows_of(preview(api, make_csv([row(set_id='ZZZ')])))[0]

    def test_the_same_merge_key_again_is_a_duplicate_warning(self, api):
        same = dict(condition='NM', language='English', purchase_price='8', selling='Y',
                    sell_price='12')
        text = make_csv([row(**same), row(**same), row(**{**same, 'condition': 'EX'}),
                         row(foil='S', **same)])
        found = rows_of(preview(api, text))
        assert [r['reason_codes'] for r in found] == [[], ['duplicate_row'], [], []]
        assert [r['status'] for r in found] == ['ok', 'warning', 'ok', 'ok']


class TestSummaryAndStorage:
    def test_summary_counts_rows_and_printings(self, api):
        text = make_csv([row(), row(foil='S'), row(card_id='2', name='Beta Calm'),
                         row(name='Other'), row(set_id='ZZZ'), row(qty='0')])
        summary = preview(api, text).get_json()['data']['summary']
        assert summary == {'total': 6, 'ok': 3, 'warning': 1, 'error': 2, 'printings': 3}

    def test_the_rows_are_stored_for_the_commit(self, api):
        data = preview(api, make_csv([row(qty='2'), row(set_id='ZZZ')])).get_json()['data']
        db.session.expire_all()
        stored = db.session.get(RbImportPreview, data['preview_id'])
        user = User.query.filter_by(username='testuser').one()
        assert (stored.rbimp_user_id, stored.rbimp_format) == (user.id, 'rbapp')
        assert [(r['line'], r['status']) for r in stored.rbimp_rows] == [(2, 'ok'), (3, 'error')]
        assert stored.rbimp_rows[0]['qty'] == 2
        assert stored.rbimp_expires_at - stored.rbimp_created_at == timedelta(minutes=30)

    def test_expired_previews_of_anyone_are_purged(self, api, frozen_clock):
        old = preview(api, make_csv([row()])).get_json()['data']['preview_id']
        frozen_clock.advance(minutes=31)
        new = preview(api, make_csv([row()])).get_json()['data']['preview_id']
        db.session.expire_all()
        assert db.session.get(RbImportPreview, old) is None
        assert db.session.get(RbImportPreview, new) is not None

    def test_a_user_keeps_only_the_latest_preview(self, api):
        first = preview(api, make_csv([row()])).get_json()['data']['preview_id']
        second = preview(api, make_csv([row()])).get_json()['data']['preview_id']
        db.session.expire_all()
        assert db.session.get(RbImportPreview, first) is None
        assert db.session.get(RbImportPreview, second) is not None

    def test_nothing_is_written_to_the_collection(self, api):
        from app.models import RbCollection
        preview(api, make_csv([row(qty='5')]))
        assert RbCollection.query.count() == 0


class TestLimits:
    def test_more_than_10000_rows(self, api):
        text = make_csv([row()] * 10001)
        body = preview(api, text).get_json()
        assert body['code'] == 'validation_error'
        detail = body['details'][0]
        assert (detail['field'], detail['code']) == ('text', 'out_of_range')

    def test_exactly_10000_rows_are_accepted(self, api):
        response = preview(api, make_csv([row()] * 10000))
        assert response.status_code == 200
        assert response.get_json()['data']['summary']['total'] == 10000

    def test_more_than_2_mb(self, api):
        text = make_csv([row(language='x' * 40)] * 100) + ' ' * (2 * 1024 * 1024)
        body = preview(api, text).get_json()
        assert body['code'] == 'validation_error'
        assert body['details'][0]['field'] == 'text'

    def test_bad_bodies(self, api):
        assert api.post(PREVIEW, json={}).status_code == 400
        assert api.post(PREVIEW, json={'text': 5}).status_code == 400

    def test_requires_a_session(self, app):
        assert app.test_client().post(PREVIEW, json={'text': ''}).status_code == 401


class TestFormulaUndoing:
    def test_a_defused_export_cell_comes_back_as_it_was(self, api):
        found = rows_of(preview(api, make_csv([row(language="'=1+1")])))[0]
        assert found['language'] == '=1+1'
