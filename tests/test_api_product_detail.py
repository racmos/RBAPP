"""F14-b S4, S5 (AC3): GET /riftbound/api/v1/products/<id> and .../prices."""
from app import db
from tests.product_helpers import add_price, add_product, add_sets, count_statements

BASE = '/riftbound/api/v1/products'
NOT_FOUND = {'success': False, 'error': 'Not Found',
             'message': 'The requested resource was not found'}


def _seed(app):
    add_sets()
    add_product(2, 'Origins Booster Box', kind='box', set_id='OGN',
                category='Riftbound Booster Boxes', description='24 boosters.')
    add_product(4, 'Origins Sleeves', kind='sleeves', set_id=None, category='Sleeves')
    add_product(5, 'Old Bundle', kind='bundle', listed=False)
    add_product(6, 'Secret Case', kind='case', hidden=True)
    add_product(7, 'A single card', kind='other', type_='single')
    # Rows 415, 142, 81, 30 (the 30d boundary), 20 and 0 days before the latest one.
    add_price(2, '20250901', avg7=60, trend=61, low=55, avg30=58)
    add_price(2, '20260601', avg7=80, trend=81, low=75, avg30=78)
    add_price(2, '20260801', avg7=0, trend=90, low=85, avg30=88)
    add_price(2, '20260921', avg7=None, trend=None, low=92, avg30=90)
    add_price(2, '20261001', avg7=110, trend=111, low=105, avg30=100)
    add_price(2, '20261021', avg7=100, trend=98.5, low=90, avg30=104.25)
    for product_id in (5, 6, 7):
        add_price(product_id, '20261021', trend=10)
    db.session.commit()


class TestDetail:
    def test_detail(self, authenticated_client, app):
        _seed(app)
        resp = authenticated_client.get(f'{BASE}/2')
        assert resp.status_code == 200
        data = resp.get_json()['data']
        assert list(data) == ['id', 'name', 'kind', 'category', 'set_id', 'image_src',
                              'listed', 'price', 'owned_qty', 'description', 'columns',
                              'lines']
        assert data == {
            'id': 2, 'name': 'Origins Booster Box', 'kind': 'box',
            'category': 'Riftbound Booster Boxes', 'set_id': 'OGN', 'image_src': None,
            'listed': True,
            'price': {'value': 100.0, 'source': 'avg7', 'change_7d_pct': -9.1,
                      'change_30d_pct': 8.7, 'as_of': '2026-10-21'},
            'owned_qty': 0,
            'description': '24 boosters.',
            'columns': {'avg7': 100.0, 'trend': 98.5, 'low': 90.0, 'avg30': 104.25},
            'lines': [],
        }
        assert list(data['columns']) == ['avg7', 'trend', 'low', 'avg30']

    def test_product_without_prices(self, authenticated_client, app):
        _seed(app)
        data = authenticated_client.get(f'{BASE}/4').get_json()['data']
        assert (data['price'], data['columns'], data['description'], data['set_id']) == (
            None, None, None, None)
        assert data['lines'] == []

    def test_unlisted_product_is_shown(self, authenticated_client, app):
        _seed(app)
        resp = authenticated_client.get(f'{BASE}/5')
        assert resp.status_code == 200
        assert resp.get_json()['data']['listed'] is False

    def test_missing_single_and_hidden_are_404(self, authenticated_client, app):
        _seed(app)
        for path in ('999', '7', '6', 'abc'):
            resp = authenticated_client.get(f'{BASE}/{path}')
            assert resp.status_code == 404, path
            assert resp.get_json() == NOT_FOUND, path

    def test_statement_count(self, authenticated_client, app):
        _seed(app)
        resp, statements = count_statements(app, lambda: authenticated_client.get(f'{BASE}/2'))
        assert resp.status_code == 200
        assert statements <= 6


class TestPriceHistory:
    def _dates(self, client, range_=None):
        query = {'range': range_} if range_ else {}
        resp = client.get(f'{BASE}/2/prices', query_string=query)
        assert resp.status_code == 200, resp.get_json()
        data = resp.get_json()['data']
        return data['range'], [point['date'] for point in data['points']]

    def test_default_is_90d(self, authenticated_client, app):
        _seed(app)
        assert self._dates(authenticated_client) == (
            '90d', ['2026-08-01', '2026-09-21', '2026-10-01', '2026-10-21'])

    def test_ranges_are_inclusive_windows_from_the_latest_row(self, authenticated_client, app):
        _seed(app)
        assert self._dates(authenticated_client, '30d') == (
            '30d', ['2026-09-21', '2026-10-01', '2026-10-21'])
        assert self._dates(authenticated_client, '1y') == (
            '1y', ['2026-06-01', '2026-08-01', '2026-09-21', '2026-10-01', '2026-10-21'])
        assert self._dates(authenticated_client, 'all') == (
            'all', ['2025-09-01', '2026-06-01', '2026-08-01', '2026-09-21', '2026-10-01',
                    '2026-10-21'])

    def test_points(self, authenticated_client, app):
        _seed(app)
        data = authenticated_client.get(f'{BASE}/2/prices',
                                        query_string={'range': '30d'}).get_json()['data']
        assert list(data) == ['range', 'points']
        assert data['points'] == [
            {'date': '2026-09-21', 'value': 92.0, 'avg7': None, 'trend': None, 'low': 92.0},
            {'date': '2026-10-01', 'value': 110.0, 'avg7': 110.0, 'trend': 111.0,
             'low': 105.0},
            {'date': '2026-10-21', 'value': 100.0, 'avg7': 100.0, 'trend': 98.5, 'low': 90.0},
        ]
        assert list(data['points'][0]) == ['date', 'value', 'avg7', 'trend', 'low']

    def test_value_skips_a_zero_avg7(self, authenticated_client, app):
        _seed(app)
        points = authenticated_client.get(f'{BASE}/2/prices').get_json()['data']['points']
        assert points[0] == {'date': '2026-08-01', 'value': 90.0, 'avg7': 0.0,
                             'trend': 90.0, 'low': 85.0}

    def test_product_without_rows(self, authenticated_client, app):
        _seed(app)
        resp = authenticated_client.get(f'{BASE}/4/prices', query_string={'range': 'all'})
        assert resp.get_json()['data'] == {'range': 'all', 'points': []}

    def test_invalid_range(self, authenticated_client, app):
        _seed(app)
        resp = authenticated_client.get(f'{BASE}/2/prices', query_string={'range': '7d'})
        body = resp.get_json()
        assert resp.status_code == 400
        assert body['code'] == 'validation_error'
        assert body['message'] == 'Invalid query parameters'
        assert [(d['field'], d['code']) for d in body['details']] == [('range',
                                                                       'invalid_value')]

    def test_missing_single_and_hidden_are_404(self, authenticated_client, app):
        _seed(app)
        for product_id in (999, 7, 6):
            resp = authenticated_client.get(f'{BASE}/{product_id}/prices')
            assert resp.status_code == 404, product_id
            assert resp.get_json() == NOT_FOUND

    def test_statement_count(self, authenticated_client, app):
        _seed(app)
        resp, statements = count_statements(
            app, lambda: authenticated_client.get(f'{BASE}/2/prices'))
        assert resp.status_code == 200
        assert statements <= 4


class TestAuthz:
    def test_anonymous_gets_a_json_401(self, client, app):
        _seed(app)
        for url in (f'{BASE}/2', f'{BASE}/2/prices'):
            resp = client.get(url)
            assert resp.status_code == 401, url
            assert resp.get_json()['code'] == 'unauthenticated'

    def test_other_user_sees_the_same_product(self, authenticated_client, other_user_client,
                                              app):
        _seed(app)
        for url in (f'{BASE}/2', f'{BASE}/2/prices'):
            assert authenticated_client.get(url).get_json() == \
                other_user_client.get(url).get_json()

    def test_endpoint_names(self, app):
        found = sorted((r.rule, r.endpoint) for r in app.url_map.iter_rules()
                       if r.rule.startswith(f'{BASE}/'))
        assert found == [(f'{BASE}/<int:product_id>', 'api_v1.get_product'),
                         (f'{BASE}/<int:product_id>/prices', 'api_v1.get_product_prices')]
