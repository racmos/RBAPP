"""CM-d: the Cardmarket expansions API under /riftbound/api/v1/admin/cardmarket (A).

Every Cardmarket expansion with its product counts on the latest load, mapping one to a
set of ours (creating the set on the way, exactly as `POST /admin/sets` does), changing
and removing the mapping. Ports the legacy `/cardmarket-unmapped-expansions` and
`/cardmarket-map-expansion` of `price_bp` (left untouched). Data from
`tests/cardmarket_matching_data.py`: expansions 10 -> OGN, 11 -> OGNX, 12 unmapped.

Every item also carries the context that tells an expansion apart when Cardmarket gives it no
name (sample products, price range, first seen, the set its linked cards suggest).
"""
from datetime import date

import pytest
import sqlalchemy as sa
from sqlalchemy import event

from app import db
from app.models import RbSet
from app.models.audit import RbAdminAudit
from app.models.cardmarket import RbcmExpansion
from app.schemas.admin import AdminExpansionNewSet, AdminSetCreate
from app.services import audit as audit_service
from app.services import cardmarket_log
from tests import cardmarket_matching_data as cm
from tests.test_authz_matrix import classify

BASE = '/riftbound/api/v1/admin/cardmarket'
EXPANSIONS = f'{BASE}/expansions'
NEW_SET = {'name': 'Spiritforged', 'release_date': '2026-02-13', 'declared_count': 220}


@pytest.fixture
def data(app):
    cm.build()
    # 13: unmapped, no product on the latest load; 14: mapped to a set that does not exist
    db.session.add(RbcmExpansion(rbexp_id=13, rbexp_name='Arcane Box Set'))
    db.session.add(RbcmExpansion(rbexp_id=14, rbexp_name='Ghost', rbexp_rbset_id='GONE'))
    db.session.commit()
    return app


COUNT_KEYS = ('id', 'name', 'products_count', 'singles_count', 'sealed_count',
              'mapped_set_id', 'mapped_set_name')
CONTEXT_KEYS = ('sample_products', 'price_range', 'first_seen', 'suggested_set_id',
                'suggested_set_name', 'suggested_confidence', 'suggested_count', 'linked_count')
NO_CONTEXT = {'sample_products': [], 'price_range': None, 'first_seen': None,
              'suggested_set_id': None, 'suggested_set_name': None,
              'suggested_confidence': None, 'suggested_count': None, 'linked_count': 0}


def counts(item):
    """The CM-d keys of an item, without the context."""
    return {key: item[key] for key in COUNT_KEYS}


def context(item):
    return {key: item[key] for key in CONTEXT_KEYS}


def by_id(items):
    return {item['id']: item for item in items}


def sample(id_product, name, low, type_='single'):
    return {'id_product': id_product, 'name': name, 'type': type_, 'low_price': low}


def mapping():
    db.session.expire_all()
    return {e.rbexp_id: e.rbexp_rbset_id
            for e in db.session.execute(sa.select(RbcmExpansion)).scalars()}


def set_ids():
    db.session.expire_all()
    return sorted(db.session.execute(sa.select(RbSet.rbset_id)).scalars())


def audits():
    db.session.expire_all()
    return [(a.rbaud_action, a.rbaud_target_type, a.rbaud_target_id, a.rbaud_details)
            for a in RbAdminAudit.query.order_by(RbAdminAudit.rbaud_id).all()]


def ok(resp, status=200):
    assert resp.status_code == status, resp.get_json()
    body = resp.get_json()
    assert body['success'] is True
    return body['data']


def err(resp, status, code=None):
    assert resp.status_code == status, resp.get_json()
    body = resp.get_json()
    assert body['success'] is False
    if code:
        assert body.get('code') == code, body
    return body


def statements(client, method, url, **kwargs):
    counted = []

    def before(conn, cursor, statement, params, context, executemany):
        counted.append(statement)

    event.listen(db.engine, 'before_cursor_execute', before)
    try:
        resp = getattr(client, method)(url, **kwargs)
        assert resp.status_code < 300, resp.get_json()
    finally:
        event.remove(db.engine, 'before_cursor_execute', before)
    return counted


ROUTES = [('get', EXPANSIONS), ('put', f'{EXPANSIONS}/12'),
          ('delete', f'{EXPANSIONS}/10/mapping')]


class TestAuthorization:
    @pytest.mark.parametrize('method,url', ROUTES)
    def test_anonymous_401_user_403(self, app, authenticated_client, data, method, url):
        before = mapping()
        assert getattr(app.test_client(), method)(url, json={'set_id': 'OGN'}).status_code == 401
        assert getattr(authenticated_client, method)(
            url, json={'set_id': 'OGN'}).status_code == 403
        assert mapping() == before and audits() == []

    def test_the_rules_are_admin_in_the_matrix(self, app):
        rules = [rule for rule in app.url_map.iter_rules()
                 if rule.rule.startswith(EXPANSIONS)]
        assert {classify(rule) for rule in rules} == {'A'}
        found = {(rule.rule, method) for rule in rules for method in rule.methods
                 if method not in ('HEAD', 'OPTIONS')}
        assert found == {(EXPANSIONS, 'GET'),
                         (f'{EXPANSIONS}/<int:expansion_id>', 'PUT'),
                         (f'{EXPANSIONS}/<int:expansion_id>/mapping', 'DELETE')}


# ---------------------------------------------------------------------------
# GET /expansions
# ---------------------------------------------------------------------------

class TestList:
    def test_every_expansion_unmapped_first_with_counts(self, admin_client, data):
        got = ok(admin_client.get(EXPANSIONS))
        assert set(got['items'][0]) == {*COUNT_KEYS, *CONTEXT_KEYS}
        assert [counts(item) for item in got['items']] == [
            {'id': 12, 'name': 'Accessories', 'products_count': 1, 'singles_count': 0,
             'sealed_count': 1, 'mapped_set_id': None, 'mapped_set_name': None},
            {'id': 13, 'name': 'Arcane Box Set', 'products_count': 0, 'singles_count': 0,
             'sealed_count': 0, 'mapped_set_id': None, 'mapped_set_name': None},
            {'id': 10, 'name': 'Origins', 'products_count': 8, 'singles_count': 7,
             'sealed_count': 1, 'mapped_set_id': 'OGN', 'mapped_set_name': 'Origins'},
            {'id': 11, 'name': 'Origins Promos', 'products_count': 1, 'singles_count': 1,
             'sealed_count': 0, 'mapped_set_id': 'OGNX',
             'mapped_set_name': 'Origins Promos'},
            # a soft FK to a set that does not exist keeps its id, without a name
            {'id': 14, 'name': 'Ghost', 'products_count': 0, 'singles_count': 0,
             'sealed_count': 0, 'mapped_set_id': 'GONE', 'mapped_set_name': None},
        ]
        assert got['meta'] == {'unmapped': 2, 'total': 5, 'date': '2030-10-02'}

    def test_the_sets_to_map_to(self, admin_client, data):
        db.session.add(RbSet(rbset_id='SFD', rbset_name='Spiritforged',
                             rbset_outdat=date(2026, 2, 13)))
        db.session.commit()
        # newest release first, sets without a release date last, then by id (S19)
        assert ok(admin_client.get(EXPANSIONS))['sets'] == [
            {'id': 'SFD', 'name': 'Spiritforged', 'release_date': '2026-02-13'},
            {'id': 'OGN', 'name': 'Origins', 'release_date': None},
            {'id': 'OGNX', 'name': 'Origins Promos', 'release_date': None},
        ]

    def test_unmapped_only(self, admin_client, data):
        got = ok(admin_client.get(f'{EXPANSIONS}?unmapped=true'))
        assert [item['id'] for item in got['items']] == [12, 13]
        assert got['meta'] == {'unmapped': 2, 'total': 2, 'date': '2030-10-02'}
        assert [item['id'] for item in
                ok(admin_client.get(f'{EXPANSIONS}?unmapped=false'))['items']] == [
            12, 13, 10, 11, 14]

    @pytest.mark.parametrize('query', ['unmapped=maybe', 'page=2'])
    def test_a_bad_query_is_400(self, admin_client, data, query):
        err(admin_client.get(f'{EXPANSIONS}?{query}'), 400, 'validation_error')

    def test_no_load_yet(self, admin_client, app):
        db.session.add(RbcmExpansion(rbexp_id=1, rbexp_name='Origins'))
        db.session.commit()
        got = ok(admin_client.get(EXPANSIONS))
        assert [counts(item) for item in got['items']] == [
            {'id': 1, 'name': 'Origins', 'products_count': 0, 'singles_count': 0,
             'sealed_count': 0, 'mapped_set_id': None, 'mapped_set_name': None}]
        assert context(got['items'][0]) == NO_CONTEXT
        assert got['sets'] == [] and got['meta'] == {'unmapped': 1, 'total': 1, 'date': None}

    def test_the_unmapped_count_is_the_status_counter(self, admin_client, data):
        status = ok(admin_client.get(f'{BASE}/status'))
        assert ok(admin_client.get(EXPANSIONS))['meta']['unmapped'] == \
            status['unmapped_expansions'] == cardmarket_log.unmapped_expansions_count() == 2

    def test_bounded_statements(self, admin_client, data):
        small = len(statements(admin_client, 'get', EXPANSIONS))
        for n in range(20, 60):
            db.session.add(RbcmExpansion(rbexp_id=n, rbexp_name=f'Exp {n}'))
            db.session.add(RbSet(rbset_id=f'S{n}', rbset_name=f'Set {n}'))
            for k in range(3):
                pid = 1000 + n * 10 + k
                cm.product(pid, f'Card {n}.{k}', expansion=n, date_added='2026-01-01')
                cm.price(pid, k + 1)
                cm.link(pid, 'OGN' if k else f'S{n}', f'{n}{k}')
            cm.product(2000 + n, f'Box {n}', expansion=n, type_='nonsingle')
        db.session.commit()
        big = statements(admin_client, 'get', EXPANSIONS)
        assert len(big) == small
        # the signed-in user, the expansions with their counts, price range and first seen,
        # their sample products, their linked sets, the sets, the latest date and the
        # unmapped counter
        assert small == 7, small


# ---------------------------------------------------------------------------
# GET /expansions: the context of each expansion
# ---------------------------------------------------------------------------

class TestContext:
    def test_samples_and_price_range_of_the_latest_load(self, admin_client, data):
        items = by_id(ok(admin_client.get(EXPANSIONS))['items'])
        # the three dearest singles, then the dearest sealed product
        assert items[10]['sample_products'] == [
            sample(250, 'Ahri, Nine-Tailed Fox', 9.0), sample(200, 'Vi', 2.0),
            sample(101, 'Jinx (Foil)', 1.0),
            sample(300, 'Origins Booster Box', 100.0, 'nonsingle')]
        assert items[10]['price_range'] == {'min': 0.1, 'max': 9.0}
        assert items[11]['sample_products'] == [sample(201, 'Vi (Promo)', 5.0)]
        assert items[11]['price_range'] == {'min': 5.0, 'max': 5.0}
        # sealed only, without a price: no price range
        assert items[12]['sample_products'] == [
            sample(301, 'Origins Playmat', None, 'nonsingle')]
        assert items[12]['price_range'] is None
        # nothing on the latest load
        assert items[13]['sample_products'] == [] and items[13]['price_range'] is None

    def test_sample_rules(self, admin_client, data):
        db.session.add(RbcmExpansion(rbexp_id=20, rbexp_name=None))
        for pid, name, low in ((2001, 'Dear A', 3.0), (2002, 'No Price', None),
                               (2000, 'Dear B', 3.0), (2003, 'Mid', 1.0),
                               (2004, 'Cheap', 0.5)):
            cm.product(pid, name, expansion=20)
            if low is not None:
                cm.price(pid, low)
        for pid, name, low in ((2101, 'Box No Price', None), (2102, 'Case', 20.0),
                               (2103, 'Booster', 10.0)):
            cm.product(pid, name, expansion=20, type_='nonsingle')
            if low is not None:
                cm.price(pid, low)
        # an older snapshot never counts, nor a price of another day
        cm.product(2009, 'Old Chase', expansion=20, date=cm.D1)
        cm.price(2009, 500.0, date=cm.D1)
        cm.price(2002, 99.0, date=cm.D1)
        db.session.commit()
        item = by_id(ok(admin_client.get(EXPANSIONS))['items'])[20]
        assert item['name'] is None
        # dearest first, the lower id first on a tie, unpriced last
        assert item['sample_products'] == [
            sample(2000, 'Dear B', 3.0), sample(2001, 'Dear A', 3.0), sample(2003, 'Mid', 1.0),
            sample(2102, 'Case', 20.0, 'nonsingle'),
            sample(2103, 'Booster', 10.0, 'nonsingle')]
        assert item['price_range'] == {'min': 0.5, 'max': 3.0}

    def test_unpriced_products_fill_the_samples(self, admin_client, data):
        db.session.add(RbcmExpansion(rbexp_id=20, rbexp_name=None))
        cm.product(2001, 'Second', expansion=20)
        cm.product(2000, 'First', expansion=20)
        db.session.commit()
        item = by_id(ok(admin_client.get(EXPANSIONS))['items'])[20]
        assert item['sample_products'] == [sample(2000, 'First', None),
                                           sample(2001, 'Second', None)]
        assert item['price_range'] is None

    def test_first_seen_is_the_earliest_date_added_on_the_latest_load(self, admin_client,
                                                                     data):
        db.session.add(RbcmExpansion(rbexp_id=20, rbexp_name=None))
        db.session.add(RbcmExpansion(rbexp_id=21, rbexp_name=None))
        cm.product(2000, 'A', expansion=20, date_added='2025-07-14 16:11:32')
        cm.product(2001, 'B', expansion=20, date_added='2025-06-01 10:00:00')
        cm.product(2002, 'C', expansion=20)
        cm.product(2003, 'Old', expansion=20, date=cm.D1, date_added='2020-01-01 00:00:00')
        cm.product(2100, 'D', expansion=21, date_added='soon')
        db.session.commit()
        items = by_id(ok(admin_client.get(EXPANSIONS))['items'])
        assert items[20]['first_seen'] == '2025-06-01'
        assert items[21]['first_seen'] is None          # not a date
        assert items[10]['first_seen'] is None          # no date_added at all

    def test_the_set_most_linked_products_point_to(self, admin_client, data):
        cm.link(100, 'OGN', '001')
        cm.link(200, 'OGN', '002')
        cm.link(250, 'OGNX', '002')
        cm.link(201, 'OGNX', '002', foil='S')
        # product 900 is on the older snapshot only: its link does not count
        cm.link(900, 'OGNX', '009')
        db.session.commit()
        items = by_id(ok(admin_client.get(EXPANSIONS))['items'])
        assert {key: items[10][key] for key in CONTEXT_KEYS[3:]} == {
            'suggested_set_id': 'OGN', 'suggested_set_name': 'Origins',
            'suggested_confidence': 0.667, 'suggested_count': 2, 'linked_count': 3}
        assert (items[11]['suggested_set_id'], items[11]['suggested_confidence'],
                items[11]['suggested_count'], items[11]['linked_count']) == ('OGNX', 1.0, 1, 1)
        for one in (12, 13, 14):
            assert (items[one]['suggested_set_id'], items[one]['suggested_set_name'],
                    items[one]['suggested_confidence'], items[one]['suggested_count'],
                    items[one]['linked_count']) == (None, None, None, None, 0)

    def test_a_tie_goes_to_the_lower_set_id_and_only_our_sets_are_suggested(
            self, admin_client, data):
        cm.link(100, 'OGNX', '001')
        cm.link(200, 'OGN', '002')
        cm.link(101, 'GONE', '001')
        cm.link(250, 'GONE', '003')
        db.session.commit()
        item = by_id(ok(admin_client.get(EXPANSIONS))['items'])[10]
        # GONE holds the most links but is not a set of ours; OGN and OGNX tie
        assert (item['suggested_set_id'], item['suggested_set_name'],
                item['suggested_confidence'], item['suggested_count'],
                item['linked_count']) == ('OGN', 'Origins', 0.25, 1, 4)

    def test_links_to_a_missing_set_only_suggest_nothing(self, admin_client, data):
        cm.link(201, 'GONE', '002')
        db.session.commit()
        item = by_id(ok(admin_client.get(EXPANSIONS))['items'])[11]
        assert (item['suggested_set_id'], item['suggested_confidence'],
                item['suggested_count'], item['linked_count']) == (None, None, None, 1)

    def test_the_written_item_carries_the_context_too(self, admin_client, data):
        cm.link(100, 'OGN', '001')
        db.session.commit()
        mapped = ok(admin_client.put(f'{EXPANSIONS}/12', json={'set_id': 'OGN'}))['expansion']
        assert mapped['sample_products'] == [sample(301, 'Origins Playmat', None, 'nonsingle')]
        unmapped = ok(admin_client.delete(f'{EXPANSIONS}/10/mapping'))['expansion']
        assert context(unmapped) == context(
            by_id(ok(admin_client.get(EXPANSIONS))['items'])[10])
        assert unmapped['suggested_set_id'] == 'OGN' and unmapped['linked_count'] == 1


# ---------------------------------------------------------------------------
# PUT /expansions/<id>
# ---------------------------------------------------------------------------

class TestMap:
    def test_maps_an_unmapped_expansion_and_audits(self, admin_client, data):
        got = ok(admin_client.put(f'{EXPANSIONS}/12', json={'set_id': 'OGN'}))
        assert set(got) == {'expansion', 'previous', 'created_set'}
        assert counts(got['expansion']) == {
            'id': 12, 'name': 'Accessories', 'products_count': 1, 'singles_count': 0,
            'sealed_count': 1, 'mapped_set_id': 'OGN', 'mapped_set_name': 'Origins'}
        assert (got['previous'], got['created_set']) == (None, None)
        assert mapping()[12] == 'OGN'
        assert audits() == [('cardmarket.expansion.map', 'cardmarket_expansion', '12',
                             {'name': 'Accessories', 'set_id': 'OGN', 'previous': None})]
        assert ok(admin_client.get(f'{BASE}/status'))['unmapped_expansions'] == 1

    def test_remaps_a_mapped_expansion_and_returns_the_previous_set(self, admin_client, data):
        got = ok(admin_client.put(f'{EXPANSIONS}/11', json={'set_id': 'OGN'}))
        assert got['previous'] == 'OGNX'
        assert got['expansion']['mapped_set_id'] == 'OGN'
        assert mapping()[11] == 'OGN'
        assert audits() == [('cardmarket.expansion.map', 'cardmarket_expansion', '11',
                             {'name': 'Origins Promos', 'set_id': 'OGN',
                              'previous': 'OGNX'})]

    def test_the_same_set_again_changes_nothing(self, admin_client, data):
        got = ok(admin_client.put(f'{EXPANSIONS}/10', json={'set_id': 'OGN'}))
        assert got['previous'] == 'OGN' and got['expansion']['mapped_set_id'] == 'OGN'
        assert audits() == []

    def test_unknown_expansion_is_404(self, admin_client, data):
        before = mapping()
        err(admin_client.put(f'{EXPANSIONS}/999', json={'set_id': 'OGN'}), 404)
        assert mapping() == before and audits() == []

    def test_unknown_set_is_400(self, admin_client, data):
        body = err(admin_client.put(f'{EXPANSIONS}/12', json={'set_id': 'NOPE'}), 400,
                   'validation_error')
        assert body['details'] == [{'field': 'set_id', 'message': 'unknown set',
                                    'type': 'value_error', 'code': 'invalid_value'}]
        assert mapping()[12] is None and audits() == []

    @pytest.mark.parametrize('body', [{}, {'set_id': ''}, {'set_id': 'OGN', 'extra': 1},
                                      {'set_id': 'OGN', 'create_set': {'name': 'X'}}])
    def test_a_bad_body_is_400(self, admin_client, data, body):
        err(admin_client.put(f'{EXPANSIONS}/12', json=body), 400, 'validation_error')
        assert mapping()[12] is None and audits() == [] and set_ids() == ['OGN', 'OGNX']


class TestMapWithANewSet:
    def test_creates_the_set_and_maps_it_in_one_go(self, admin_client, data, frozen_clock):
        got = ok(admin_client.put(f'{EXPANSIONS}/12',
                                  json={'set_id': 'sfd', 'create_set': NEW_SET}))
        assert got['previous'] is None
        assert got['expansion']['mapped_set_id'] == 'SFD'
        assert got['expansion']['mapped_set_name'] == 'Spiritforged'
        assert got['created_set']['id'] == 'SFD'
        assert mapping()[12] == 'SFD'
        assert audits() == [
            ('set.create', 'set', 'SFD', {'name': 'Spiritforged',
                                          'release_date': '2026-02-13'}),
            ('cardmarket.expansion.map', 'cardmarket_expansion', '12',
             {'name': 'Accessories', 'set_id': 'SFD', 'previous': None})]

    def test_the_set_equals_one_made_by_the_sets_admin(self, admin_client, data,
                                                       frozen_clock):
        created = ok(admin_client.put(f'{EXPANSIONS}/12',
                                      json={'set_id': 'sfd', 'create_set': NEW_SET}))
        made = ok(admin_client.post('/riftbound/api/v1/admin/sets',
                                    json={'id': 'sfx', **NEW_SET}), 201)
        assert {**created['created_set'], 'id': 'SFX'} == made
        db.session.expire_all()
        one, two = RbSet.query.get('SFD'), RbSet.query.get('SFX')
        assert (one.rbset_name, one.rbset_ncard, one.rbset_outdat) == \
            (two.rbset_name, two.rbset_ncard, two.rbset_outdat)
        set_audits = [row for row in audits() if row[0] == 'set.create']
        assert [row[3] for row in set_audits] == [{'name': 'Spiritforged',
                                                   'release_date': '2026-02-13'}] * 2

    def test_the_new_set_fields_are_the_sets_admin_fields(self):
        expected = {name: repr(field) for name, field in AdminSetCreate.model_fields.items()
                    if name != 'id'}
        assert {name: repr(field)
                for name, field in AdminExpansionNewSet.model_fields.items()} == expected

    @pytest.mark.parametrize('set_id,create_set,field', [
        ('S', NEW_SET, 'set_id'),                       # the sets admin id rule
        ('SF-D', NEW_SET, 'set_id'),
        ('SFD', {'name': 'X'}, 'create_set.release_date'),
        ('SFD', {**NEW_SET, 'name': ''}, 'create_set.name'),
        ('SFD', {**NEW_SET, 'declared_count': 1000}, 'create_set.declared_count'),
        ('SFD', {**NEW_SET, 'colour': 'red'}, 'create_set.colour'),
    ])
    def test_the_sets_admin_validation(self, admin_client, data, set_id, create_set, field):
        body = err(admin_client.put(f'{EXPANSIONS}/12',
                                    json={'set_id': set_id, 'create_set': create_set}),
                   400, 'validation_error')
        assert field in [detail['field'] for detail in body['details']]
        assert set_ids() == ['OGN', 'OGNX'] and mapping()[12] is None and audits() == []

    def test_an_existing_set_is_409_like_the_sets_admin(self, admin_client, data):
        body = err(admin_client.put(f'{EXPANSIONS}/12',
                                    json={'set_id': 'ogn', 'create_set': NEW_SET}),
                   409, 'already_exists')
        assert body['params'] == {'field': 'set_id'}
        db.session.expire_all()
        assert RbSet.query.get('OGN').rbset_name == 'Origins'
        assert mapping()[12] is None and audits() == []

    def test_an_unknown_expansion_creates_no_set(self, admin_client, data):
        err(admin_client.put(f'{EXPANSIONS}/999',
                             json={'set_id': 'SFD', 'create_set': NEW_SET}), 404)
        assert set_ids() == ['OGN', 'OGNX'] and audits() == []

    def test_all_or_nothing(self, admin_client, data, monkeypatch):
        real = audit_service.record

        def failing(action, *args, **kwargs):
            if action == 'cardmarket.expansion.map':
                raise RuntimeError('boom')
            return real(action, *args, **kwargs)

        monkeypatch.setattr(audit_service, 'record', failing)
        resp = admin_client.put(f'{EXPANSIONS}/12',
                                json={'set_id': 'SFD', 'create_set': NEW_SET})
        assert resp.status_code == 500
        assert set_ids() == ['OGN', 'OGNX'] and mapping()[12] is None and audits() == []


# ---------------------------------------------------------------------------
# DELETE /expansions/<id>/mapping
# ---------------------------------------------------------------------------

class TestUnmap:
    def test_unmaps_and_returns_the_previous_set(self, admin_client, data):
        got = ok(admin_client.delete(f'{EXPANSIONS}/10/mapping'))
        assert got['previous'] == 'OGN'
        assert got['expansion']['mapped_set_id'] is None
        assert got['expansion']['mapped_set_name'] is None
        assert got['expansion']['products_count'] == 8
        assert mapping()[10] is None
        # the set itself stays
        assert set_ids() == ['OGN', 'OGNX']
        assert audits() == [('cardmarket.expansion.unmap', 'cardmarket_expansion', '10',
                             {'name': 'Origins', 'previous': 'OGN'})]
        assert ok(admin_client.get(f'{BASE}/status'))['unmapped_expansions'] == 3

    def test_undo_maps_it_back(self, admin_client, data):
        previous = ok(admin_client.delete(f'{EXPANSIONS}/10/mapping'))['previous']
        ok(admin_client.put(f'{EXPANSIONS}/10', json={'set_id': previous}))
        assert mapping()[10] == 'OGN'

    def test_unknown_expansion_is_404(self, admin_client, data):
        err(admin_client.delete(f'{EXPANSIONS}/999/mapping'), 404)
        assert audits() == []

    def test_an_unmapped_expansion_is_404(self, admin_client, data):
        body = err(admin_client.delete(f'{EXPANSIONS}/12/mapping'), 404)
        assert body['message'] == 'Cardmarket expansion 12 is not mapped.'
        assert audits() == []


class TestLegacyUntouched:
    def test_the_legacy_endpoints_still_answer(self, admin_client, data):
        resp = admin_client.get('/riftbound/price/cardmarket-unmapped-expansions')
        assert resp.status_code == 200
        assert [e['rbexp_id'] for e in resp.get_json()['expansions']] == [12, 13]
