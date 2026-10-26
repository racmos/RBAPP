"""F2-b S6 (AC3): `price_summaries` — one batched read for many cards."""
import pytest
from sqlalchemy import event

from app import db
from app.models.card import RbCard
from app.models.cardmarket import RbcmPrice, RbcmProductCardMap
from app.models.set import RbSet
from app.services import pricing


def _seeded(app, n):
    """N mapped common cards, each with an N and an S product and 3 price rows."""
    db.session.add(RbSet(rbset_id='OGN', rbset_name='Origins'))
    for i in range(n):
        db.session.add(RbCard(rbcar_rbset_id='OGN', rbcar_id=str(i),
                              rbcar_name=f'Card {i}', rbcar_rarity='Common'))
        db.session.add(RbcmProductCardMap(rbpcm_id_product=1000 + i,
                                         rbpcm_rbset_id='OGN', rbpcm_rbcar_id=str(i),
                                         rbpcm_foil='N', rbpcm_match_type='manual'))
        db.session.add(RbcmProductCardMap(rbpcm_id_product=2000 + i,
                                         rbpcm_rbset_id='OGN', rbpcm_rbcar_id=str(i),
                                         rbpcm_foil='S', rbpcm_match_type='manual'))
        for day, avg in (('20261001', 1.00), ('20261014', 1.10), ('20261021', 1.21)):
            db.session.add(RbcmPrice(rbprc_date=day, rbprc_id_product=1000 + i,
                                     rbprc_avg7=avg))
            db.session.add(RbcmPrice(rbprc_date=day, rbprc_id_product=2000 + i,
                                     rbprc_avg7_foil=avg))
    db.session.commit()
    return [('OGN', str(i), 'Common', True) for i in range(n)]


def _counted(fn):
    statements = []

    def before(conn, cursor, statement, params, context, executemany):
        if statement.lstrip().upper().startswith('SELECT'):
            statements.append(statement)

    event.listen(db.engine, 'before_cursor_execute', before)
    try:
        return fn(), statements
    finally:
        event.remove(db.engine, 'before_cursor_execute', before)


def test_spec_example(app):
    items = _seeded(app, 1)
    result, statements = _counted(lambda: pricing.price_summaries(items))
    assert result[('OGN', '0')] == {
        'market': 1.21, 'market_source': 'avg7',
        'market_foil': 1.21, 'market_foil_source': 'avg7_foil',
        'trend_7d_pct': 10.0, 'trend_30d_pct': None,
        'as_of': '2026-10-21',
    }
    assert len(statements) <= 6, statements


def test_non_foilable_card_has_no_foil_price(app):
    db.session.add(RbSet(rbset_id='OGN', rbset_name='Origins'))
    db.session.add(RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='Dragon',
                          rbcar_rarity='Rare'))
    db.session.add(RbcmProductCardMap(rbpcm_id_product=7, rbpcm_rbset_id='OGN',
                                      rbpcm_rbcar_id='1', rbpcm_foil=None,
                                      rbpcm_match_type='manual'))
    db.session.add(RbcmPrice(rbprc_date='20261021', rbprc_id_product=7, rbprc_low=3.0))
    db.session.commit()
    result = pricing.price_summaries([('OGN', '1', 'Rare', False)])
    assert result[('OGN', '1')]['market'] == 3.0
    assert result[('OGN', '1')]['market_source'] == 'low'
    assert result[('OGN', '1')]['market_foil'] is None
    assert result[('OGN', '1')]['market_foil_source'] is None
    assert result[('OGN', '1')]['as_of'] == '2026-10-21'


def test_unmapped_card_is_none(app):
    db.session.add(RbSet(rbset_id='OGN', rbset_name='Origins'))
    db.session.add(RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='Lonely'))
    db.session.commit()
    assert pricing.price_summaries([('OGN', '1', 'Common', True)]) == {('OGN', '1'): None}


def test_trend_needs_both_ends_and_a_nonzero_base(app):
    db.session.add(RbSet(rbset_id='OGN', rbset_name='Origins'))
    db.session.add(RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='New'))
    db.session.add(RbcmProductCardMap(rbpcm_id_product=9, rbpcm_rbset_id='OGN',
                                      rbpcm_rbcar_id='1', rbpcm_foil='N',
                                      rbpcm_match_type='manual'))
    db.session.add(RbcmPrice(rbprc_date='20261021', rbprc_id_product=9, rbprc_avg7=2.0))
    db.session.commit()
    result = pricing.price_summaries([('OGN', '1', 'Common', True)])
    assert result[('OGN', '1')]['trend_7d_pct'] is None
    assert result[('OGN', '1')]['trend_30d_pct'] is None


def test_zero_base_gives_no_trend(app):
    db.session.add(RbSet(rbset_id='OGN', rbset_name='Origins'))
    db.session.add(RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='Zero'))
    db.session.add(RbcmProductCardMap(rbpcm_id_product=9, rbpcm_rbset_id='OGN',
                                      rbpcm_rbcar_id='1', rbpcm_foil='N',
                                      rbpcm_match_type='manual'))
    db.session.add(RbcmPrice(rbprc_date='20261014', rbprc_id_product=9, rbprc_avg7=0))
    db.session.add(RbcmPrice(rbprc_date='20261021', rbprc_id_product=9, rbprc_avg7=2.0))
    db.session.commit()
    result = pricing.price_summaries([('OGN', '1', 'Common', True)])
    assert result[('OGN', '1')]['trend_7d_pct'] is None


def test_statement_count_is_bounded_at_fifty_cards(app):
    items = _seeded(app, 50)
    _, statements = _counted(lambda: pricing.price_summaries(items))
    assert len(statements) <= 6, len(statements)


def test_mapped_card_without_rows_is_all_none(app):
    db.session.add(RbSet(rbset_id='OGN', rbset_name='Origins'))
    db.session.add(RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='Ghost'))
    db.session.add(RbcmProductCardMap(rbpcm_id_product=42, rbpcm_rbset_id='OGN',
                                      rbpcm_rbcar_id='1', rbpcm_foil='N',
                                      rbpcm_match_type='manual'))
    db.session.commit()
    assert pricing.price_summaries([('OGN', '1', 'Common', True)]) == {
        ('OGN', '1'): {'market': None, 'market_source': None, 'market_foil': None,
                       'market_foil_source': None, 'trend_7d_pct': None,
                       'trend_30d_pct': None, 'as_of': None}}
