"""F14-b S1 (AC1): `product_price` chain and `product_price_summaries`."""
from decimal import Decimal
from types import SimpleNamespace

from app import db
from app.models import RbcmPrice
from app.services.product_prices import product_price, product_price_summaries
from tests.product_helpers import add_price, add_product, count_statements


def _row(avg7=None, trend=None, low=None, **foil):
    return SimpleNamespace(rbprc_avg7=avg7, rbprc_trend=trend, rbprc_low=low, **foil)


class TestChain:
    def test_avg7_wins(self):
        assert product_price(_row(avg7=12.5, trend=11, low=9)) == (12.5, 'avg7')

    def test_zero_avg7_falls_to_trend(self):
        assert product_price(_row(avg7=0, trend=11, low=9)) == (11.0, 'trend')

    def test_null_avg7_falls_to_trend(self):
        assert product_price(_row(avg7=None, trend=11, low=9)) == (11.0, 'trend')

    def test_null_avg7_and_zero_trend_fall_to_low(self):
        assert product_price(_row(avg7=None, trend=0, low=9)) == (9.0, 'low')

    def test_nothing_is_none_never_zero(self):
        assert product_price(_row(avg7=0, trend=None, low=0)) == (None, None)

    def test_no_row_is_none(self):
        assert product_price(None) == (None, None)

    def test_foil_fields_are_never_read(self):
        row = _row(rbprc_avg7_foil=50, rbprc_low_foil=40, rbprc_trend_foil=45)
        assert product_price(row) == (None, None)

    def test_stored_decimal_comes_back_as_float(self, app):
        add_price(7, '20261021', trend=Decimal('39.95'))
        db.session.commit()
        value, source = product_price(db.session.get(RbcmPrice, ('20261021', 7)))
        assert (value, source) == (39.95, 'trend')
        assert type(value) is float


class TestSummaries:
    def test_value_changes_and_as_of(self, app):
        add_product(1, 'Origins Booster')
        add_price(1, '20260910', trend=10)       # 30-day reference (newest on or before 09-21)
        add_price(1, '20260925', trend=10.5)     # newer than 09-21: not the 30-day reference
        add_price(1, '20261014', trend=11)       # exactly latest - 7: the 7-day reference
        add_price(1, '20261021', avg7=0, trend=12.1, low=9)
        db.session.commit()
        assert product_price_summaries([1]) == {1: {
            'value': 12.1, 'source': 'trend',
            'change_7d_pct': 10.0, 'change_30d_pct': 21.0,
            'as_of': '2026-10-21',
        }}

    def test_changes_are_rounded_to_one_decimal(self, app):
        add_price(1, '20261014', avg7=3)
        add_price(1, '20261021', avg7=4)
        db.session.commit()
        assert product_price_summaries([1])[1]['change_7d_pct'] == 33.3

    def test_reference_value_comes_from_its_own_chain(self, app):
        add_price(1, '20261014', avg7=None, trend=None, low=8)
        add_price(1, '20261021', avg7=10)
        db.session.commit()
        summary = product_price_summaries([1])[1]
        assert (summary['value'], summary['source']) == (10.0, 'avg7')
        assert summary['change_7d_pct'] == 25.0

    def test_no_reference_row_means_no_change(self, app):
        add_price(1, '20261015', trend=5)
        add_price(1, '20261021', trend=6)
        db.session.commit()
        summary = product_price_summaries([1])[1]
        assert summary['change_7d_pct'] is None
        assert summary['change_30d_pct'] is None

    def test_reference_without_any_value_means_no_change(self, app):
        add_price(1, '20261014', avg7=0, trend=0, low=None)
        add_price(1, '20261021', trend=6)
        db.session.commit()
        assert product_price_summaries([1])[1]['change_7d_pct'] is None

    def test_latest_row_without_value(self, app):
        add_price(1, '20261014', trend=5)
        add_price(1, '20261021', avg7=0, trend=0, low=0, rbprc_avg7_foil=9)
        db.session.commit()
        assert product_price_summaries([1]) == {1: {
            'value': None, 'source': None,
            'change_7d_pct': None, 'change_30d_pct': None,
            'as_of': '2026-10-21',
        }}

    def test_product_without_rows_is_none(self, app):
        add_price(1, '20261021', trend=6)
        db.session.commit()
        result = product_price_summaries([1, 2])
        assert result[2] is None
        assert sorted(result) == [1, 2]

    def test_no_ids_runs_no_statement(self, app):
        result, statements = count_statements(app, lambda: product_price_summaries([]))
        assert result == {}
        assert statements == 0

    def test_statement_count_is_constant(self, app):
        for product_id in range(1, 51):
            for day, trend in (('20260921', 1), ('20261014', 2), ('20261021', 3)):
                add_price(product_id, day, trend=trend)
        db.session.commit()
        one, one_count = count_statements(app, lambda: product_price_summaries([1]))
        many, many_count = count_statements(
            app, lambda: product_price_summaries(range(1, 51)))
        assert one[1]['change_7d_pct'] == 50.0
        assert one[1]['change_30d_pct'] == 200.0
        assert len(many) == 50
        assert one_count <= 4 and many_count <= 4
        assert one_count == many_count
