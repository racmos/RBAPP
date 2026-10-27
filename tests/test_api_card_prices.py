"""F2-d S8: GET /riftbound/api/v1/cards/<set_id>/<card_id>/prices."""
from datetime import date

import pytest
from sqlalchemy import event

from app import db
from app.models import RbCard, RbSet, RbcmPrice, RbcmProductCardMap

URL = '/riftbound/api/v1/cards/OGN/1/prices'


def _seed_prices(app):
    with app.app_context():
        db.session.add_all([
            RbSet(rbset_id='OGN', rbset_name='Origins', rbset_outdat=date(2025, 10, 31)),
        ])
        db.session.add_all([
            RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='Alpha Fury',
                   rbcar_domain='Fury', rbcar_type='Unit', rbcar_rarity='Common',
                   rbcar_energy=1, rbcar_tags='Noxus', rbcar_ability='Charge.'),
            RbCard(rbcar_rbset_id='OGN', rbcar_id='2', rbcar_name='Beta Calm',
                   rbcar_domain='Calm', rbcar_type='Spell', rbcar_rarity='Uncommon',
                   rbcar_energy=2, rbcar_tags='Ionia', rbcar_ability='Heal.'),
            RbCard(rbcar_rbset_id='OGN', rbcar_id='3', rbcar_name='Gamma Gear',
                   rbcar_domain='Order', rbcar_type='Gear', rbcar_rarity='Rare',
                   rbcar_tags='', rbcar_ability='Equip.'),
        ])
        db.session.add_all([
            RbcmProductCardMap(rbpcm_rbset_id='OGN', rbpcm_rbcar_id='1',
                               rbpcm_id_product=1, rbpcm_foil='N'),
            # 111 days before the latest row: inside `all`, outside `90d`.
            RbcmPrice(rbprc_date='20260701', rbprc_id_product=1,
                      rbprc_avg7=6, rbprc_low=5, rbprc_avg30=5.5),
            RbcmPrice(rbprc_date='20261020', rbprc_id_product=1,
                      rbprc_avg7=10, rbprc_low=9, rbprc_avg30=9.5),
            # Foilable common: the foil product has a row only on the latest date.
            RbcmProductCardMap(rbpcm_rbset_id='OGN', rbpcm_rbcar_id='2',
                               rbpcm_id_product=2, rbpcm_foil='N'),
            RbcmProductCardMap(rbpcm_rbset_id='OGN', rbpcm_rbcar_id='2',
                               rbpcm_id_product=22, rbpcm_foil='S'),
            RbcmPrice(rbprc_date='20261010', rbprc_id_product=2,
                      rbprc_avg7=4, rbprc_low=3),
            RbcmPrice(rbprc_date='20261020', rbprc_id_product=2,
                      rbprc_avg7=5, rbprc_low=4),
            RbcmPrice(rbprc_date='20261020', rbprc_id_product=22,
                      rbprc_avg7_foil=7, rbprc_low_foil=6),
        ])
        # OGN/3 is unmapped on purpose.
        db.session.commit()


class TestRanges:
    def test_default_range_is_90d(self, authenticated_client, app):
        _seed_prices(app)
        body = authenticated_client.get(URL).get_json()
        assert body['success'] is True
        assert body['data']['range'] == '90d'
        assert body['data']['currency'] == 'EUR'
        assert body['data']['foilable'] is True
        assert body['data']['product_id'] == 1
        assert [p['date'] for p in body['data']['points']] == ['2026-10-20']

    def test_90d_excludes_a_row_111_days_old(self, authenticated_client, app):
        _seed_prices(app)
        body = authenticated_client.get(URL, query_string={'range': '90d'}).get_json()
        assert [p['date'] for p in body['data']['points']] == ['2026-10-20']

    def test_all_returns_every_row_ascending(self, authenticated_client, app):
        _seed_prices(app)
        body = authenticated_client.get(URL, query_string={'range': 'all'}).get_json()
        points = body['data']['points']
        assert [p['date'] for p in points] == ['2026-07-01', '2026-10-20']
        assert points[0]['market'] == 6
        assert points[1] == {'date': '2026-10-20', 'market': 10, 'low': 9,
                             'avg7': 10, 'avg30': 9.5, 'market_foil': None}

    def test_30d_and_1y_windows(self, authenticated_client, app):
        _seed_prices(app)
        short = authenticated_client.get(URL, query_string={'range': '30d'}).get_json()
        assert [p['date'] for p in short['data']['points']] == ['2026-10-20']
        year = authenticated_client.get(URL, query_string={'range': '1y'}).get_json()
        assert [p['date'] for p in year['data']['points']] == ['2026-07-01', '2026-10-20']


class TestFoilAndUnmapped:
    def test_market_foil_follows_same_date_rows(self, authenticated_client, app):
        _seed_prices(app)
        body = authenticated_client.get(
            '/riftbound/api/v1/cards/OGN/2/prices',
            query_string={'range': 'all'}).get_json()
        assert body['data']['foilable'] is True
        assert body['data']['product_id'] == 2
        points = body['data']['points']
        assert points[0]['market_foil'] is None  # no S row that day
        assert points[1]['market_foil'] == 7

    def test_unmapped_card_returns_empty_points(self, authenticated_client, app):
        _seed_prices(app)
        body = authenticated_client.get(
            '/riftbound/api/v1/cards/OGN/3/prices').get_json()
        assert body['data'] == {'range': '90d', 'currency': 'EUR',
                                'foilable': False, 'product_id': None,
                                'points': []}


class TestErrorsAndAuthz:
    def test_invalid_range_is_a_400(self, authenticated_client, app):
        _seed_prices(app)
        resp = authenticated_client.get(URL, query_string={'range': 'week'})
        body = resp.get_json()
        assert resp.status_code == 400
        assert body['code'] == 'validation_error'
        assert body['details'][0]['field'] == 'range'
        assert body['details'][0]['code'] == 'invalid_value'

    def test_missing_card_is_a_404(self, authenticated_client, app):
        _seed_prices(app)
        resp = authenticated_client.get('/riftbound/api/v1/cards/NOPE/1/prices')
        assert resp.status_code == 404
        assert resp.get_json()['success'] is False

    def test_anonymous_gets_a_json_401(self, client, app):
        _seed_prices(app)
        resp = client.get(URL)
        assert resp.status_code == 401
        assert resp.get_json()['code'] == 'unauthenticated'

    def test_endpoint_name(self, app):
        rules = [r for r in app.url_map.iter_rules()
                 if r.rule == '/riftbound/api/v1/cards/<set_id>/<card_id>/prices']
        assert [(r.endpoint, sorted(r.methods - {'HEAD', 'OPTIONS'})) for r in rules] == [
            ('api_v1.get_card_prices', ['GET'])]


class TestStatementBound:
    def test_prices_under_4_statements(self, authenticated_client, app):
        _seed_prices(app)
        counts = []

        def listener(conn, cursor, statement, parameters, context, executemany):
            counts.append(statement)

        with app.app_context():
            event.listen(db.engine, 'before_cursor_execute', listener)
            try:
                resp = authenticated_client.get(URL)
                assert resp.status_code == 200
            finally:
                event.remove(db.engine, 'before_cursor_execute', listener)
        assert len(counts) <= 4
