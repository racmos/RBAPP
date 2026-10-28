"""F3-b S3: market price by foil, value, profit and loss of a collection line."""
import pytest

from tests.collection_read_helpers import URL, line, seed_catalog
from app import db
from app.models import RbcmPrice, RbcmProductCardMap


@pytest.fixture
def api(app, authenticated_client):
    with app.app_context():
        seed_catalog()
        db.session.add_all([
            line('1', 4, purchase=8),                    # market 10: +2 each
            line('1', 3, foil='S', purchase=20),         # foil market 30
            line('2', 2, purchase=0),                    # purchase 0: no pl
            line('2', 1, condition='EX'),                # no purchase: no pl
            line('79', 1, purchase=25),                  # loss
            line('10', 5, set_id='SFD', purchase=3),     # unpriced card
        ])
        db.session.commit()
    return authenticated_client


def lines_of(api, key):
    groups = {g['key']: g for g in api.get(URL).get_json()['data']['items']}
    return groups[key]['lines']


def test_market_follows_the_foil_of_the_line(api):
    assert lines_of(api, 'OGN-1:N')[0]['market'] == 10.0
    assert lines_of(api, 'OGN-1:S')[0]['market'] == 30.0


def test_value_is_market_times_quantity(api):
    assert lines_of(api, 'OGN-1:N')[0]['value'] == 40.0
    assert lines_of(api, 'OGN-1:S')[0]['value'] == 90.0


def test_profit_and_loss_with_a_purchase_price(api):
    first = lines_of(api, 'OGN-1:N')[0]
    assert (first['purchase_price'], first['pl_abs'], first['pl_pct']) == (8.0, 8.0, 25.0)
    foil = lines_of(api, 'OGN-1:S')[0]
    assert (foil['pl_abs'], foil['pl_pct']) == (30.0, 50.0)
    loss = lines_of(api, 'OGN-79:N')[0]
    assert (loss['pl_abs'], loss['pl_pct']) == (-5.0, -20.0)


def test_no_pl_without_a_positive_purchase_price(api):
    free, unknown = lines_of(api, 'OGN-2:N')
    for entry in (free, unknown):
        assert entry['market'] == 5.0 and entry['value'] in (10.0, 5.0)
        assert entry['pl_abs'] is None and entry['pl_pct'] is None
    assert free['purchase_price'] == 0.0 and unknown['purchase_price'] is None


def test_unpriced_card_has_null_money_but_keeps_the_purchase_price(api):
    entry = lines_of(api, 'SFD-10:N')[0]
    assert (entry['market'], entry['value'], entry['pl_abs'], entry['pl_pct']) == (
        None, None, None, None)
    assert entry['purchase_price'] == 3.0


def test_group_value_is_the_sum_of_its_priced_lines(api):
    groups = {g['key']: g for g in api.get(URL).get_json()['data']['items']}
    assert groups['OGN-2:N']['value'] == 15.0
    assert groups['SFD-10:N']['value'] is None


def test_pl_pct_rounds_half_up_to_one_decimal(app, authenticated_client):
    with app.app_context():
        seed_catalog()
        db.session.add_all([line('1', 1, purchase=9.6), line('1', 1, condition='EX',
                                                                purchase=7.95)])
        db.session.commit()
    first, second = lines_of(authenticated_client, 'OGN-1:N')
    assert first['pl_pct'] == 4.2          # 4.1666...
    assert second['pl_pct'] == 25.8        # (10 - 7.95) / 7.95 = 25.786 -> 25.8
    assert first['pl_abs'] == 0.4 and second['pl_abs'] == 2.05


def test_money_is_rounded_half_up_to_cents(app, authenticated_client):
    with app.app_context():
        seed_catalog()
        db.session.add(RbcmPrice(rbprc_date='20261021', rbprc_id_product=1, rbprc_avg7=0.125))
        db.session.add(line('1', 3, purchase=0.1))
        db.session.commit()
    entry = lines_of(authenticated_client, 'OGN-1:N')[0]
    assert entry['market'] == 0.13          # 0.125 -> 0.13, not banker's 0.12
    assert entry['value'] == 0.38           # 0.125 * 3 = 0.375 -> 0.38
    assert entry['pl_abs'] == 0.08          # (0.125 - 0.1) * 3 = 0.075 -> 0.08
