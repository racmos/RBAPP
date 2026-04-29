"""
TDD tests for RbcmIgnored model, ignored CRUD endpoints, mappings browser
exclusion, matcher exclusion, and selective auto-match apply endpoint.

Written FIRST (RED), then implementation (GREEN).
"""
import pytest
from app import db
from app.models import RbSet, RbCard
from app.models.cardmarket import (
    RbcmProduct, RbcmPrice, RbcmExpansion, RbcmProductCardMap,
)


# ---------------------------------------------------------------------------
# Group A — RbcmIgnored model
# ---------------------------------------------------------------------------

class TestRbcmIgnoredModel:

    def test_rbcm_ignored_model_pk(self, app):
        """RbcmIgnored must insert and query back by composite PK (id_product, name)."""
        from app.models.cardmarket import RbcmIgnored
        with app.app_context():
            row = RbcmIgnored(rbig_id_product=12345, rbig_name='Test Card Foil')
            db.session.add(row)
            db.session.commit()

            fetched = RbcmIgnored.query.filter_by(
                rbig_id_product=12345,
                rbig_name='Test Card Foil',
            ).first()
            assert fetched is not None
            assert fetched.rbig_id_product == 12345
            assert fetched.rbig_name == 'Test Card Foil'
            assert fetched.rbig_ignored_at is not None

    def test_rbcm_ignored_pk_is_composite(self, app):
        """Different (id_product, name) pairs must coexist in the table."""
        from app.models.cardmarket import RbcmIgnored
        with app.app_context():
            db.session.add(RbcmIgnored(rbig_id_product=1, rbig_name='Alpha'))
            db.session.add(RbcmIgnored(rbig_id_product=1, rbig_name='Beta'))  # same id, diff name
            db.session.add(RbcmIgnored(rbig_id_product=2, rbig_name='Alpha'))  # same name, diff id
            db.session.commit()

            count = RbcmIgnored.query.count()
            assert count == 3


# ---------------------------------------------------------------------------
# Group B — Ignored CRUD endpoints
# ---------------------------------------------------------------------------

class TestIgnoredAdd:

    def test_post_ignored_add_inserts(self, authenticated_client, app):
        """POST /price/ignored/add must insert a row and return {success: true}."""
        resp = authenticated_client.post(
            '/riftbound/price/ignored/add',
            json={'id_product': 99001, 'name': 'Fire Imp Foil'},
        )
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['success'] is True

        with app.app_context():
            from app.models.cardmarket import RbcmIgnored
            row = RbcmIgnored.query.filter_by(
                rbig_id_product=99001,
                rbig_name='Fire Imp Foil',
            ).first()
            assert row is not None

    def test_post_ignored_add_idempotent(self, authenticated_client):
        """POSTing the same (id_product, name) twice must not error (upsert/ignore)."""
        payload = {'id_product': 99002, 'name': 'Shadow Blade'}
        authenticated_client.post('/riftbound/price/ignored/add', json=payload)
        resp = authenticated_client.post('/riftbound/price/ignored/add', json=payload)
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['success'] is True


class TestIgnoredRestore:

    def test_post_ignored_restore_deletes(self, authenticated_client, app):
        """POST /price/ignored/restore must delete the row and return {success: true}."""
        with app.app_context():
            from app.models.cardmarket import RbcmIgnored
            db.session.add(RbcmIgnored(rbig_id_product=88001, rbig_name='Restore Me'))
            db.session.commit()

        resp = authenticated_client.post(
            '/riftbound/price/ignored/restore',
            json={'id_product': 88001, 'name': 'Restore Me'},
        )
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['success'] is True

        with app.app_context():
            from app.models.cardmarket import RbcmIgnored
            row = RbcmIgnored.query.filter_by(
                rbig_id_product=88001,
                rbig_name='Restore Me',
            ).first()
            assert row is None

    def test_post_ignored_restore_nonexistent_returns_success(self, authenticated_client):
        """Restoring a non-existent entry should still return success (idempotent)."""
        resp = authenticated_client.post(
            '/riftbound/price/ignored/restore',
            json={'id_product': 99999, 'name': 'Does Not Exist'},
        )
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['success'] is True


class TestIgnoredList:

    def test_get_ignored_returns_list(self, authenticated_client, app):
        """GET /price/ignored must return list of {id_product, name, ignored_at}."""
        with app.app_context():
            from app.models.cardmarket import RbcmIgnored
            db.session.add(RbcmIgnored(rbig_id_product=77001, rbig_name='Listed Card'))
            db.session.commit()

        resp = authenticated_client.get('/riftbound/price/ignored')
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['success'] is True
        assert isinstance(data['ignored'], list)
        assert len(data['ignored']) >= 1

        # Verify structure of a returned item
        item = next(
            (i for i in data['ignored'] if i['id_product'] == 77001),
            None
        )
        assert item is not None
        assert item['name'] == 'Listed Card'
        assert 'ignored_at' in item

    def test_get_ignored_empty_when_none(self, authenticated_client):
        """GET /price/ignored with no rows returns empty list."""
        resp = authenticated_client.get('/riftbound/price/ignored')
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['success'] is True
        assert data['ignored'] == []


# ---------------------------------------------------------------------------
# Group C — Mappings browser excludes ignored
# ---------------------------------------------------------------------------

class TestMappingsBrowserExcludesIgnored:

    def test_mappings_browser_excludes_ignored(self, authenticated_client, app):
        """cardmarket-unmatched must NOT include products that are in rbcm_ignored."""
        with app.app_context():
            # Seed: one RbcmProduct that should be ignored
            db.session.add(RbcmProduct(
                rbprd_date='20260101',
                rbprd_id_product=55001,
                rbprd_name='Ignored Product',
                rbprd_id_metacard=5001,
                rbprd_type='single',
            ))
            # Another product that should NOT be ignored
            db.session.add(RbcmProduct(
                rbprd_date='20260101',
                rbprd_id_product=55002,
                rbprd_name='Normal Product',
                rbprd_id_metacard=5002,
                rbprd_type='single',
            ))
            from app.models.cardmarket import RbcmIgnored
            db.session.add(RbcmIgnored(rbig_id_product=55001, rbig_name='Ignored Product'))
            db.session.commit()

        resp = authenticated_client.get('/riftbound/price/cardmarket-unmatched')
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['success'] is True

        ids = [item['id_product'] for item in data['unmatched']]
        assert 55001 not in ids, "Ignored product 55001 should not appear in unmatched"
        assert 55002 in ids, "Normal product 55002 should appear in unmatched"


# ---------------------------------------------------------------------------
# Group D — Matcher excludes ignored
# ---------------------------------------------------------------------------

class TestAutoMatchSkipsIgnored:

    def test_auto_match_skips_ignored(self, app):
        """auto_match must skip products in rbcm_ignored and count them in ignored_count."""
        with app.app_context():
            rb_set = RbSet(rbset_id='TST', rbset_name='Test Set', rbset_ncard=10)
            db.session.add(rb_set)

            card = RbCard(
                rbcar_rbset_id='TST',
                rbcar_id='01',
                rbcar_name='Test Card',
                rbcar_type='Unit',
                rbcar_rarity='Rare',
            )
            db.session.add(card)

            exp = RbcmExpansion(rbexp_id=9900, rbexp_name='Test Exp', rbexp_rbset_id='TST')
            db.session.add(exp)

            # Two products: one ignored, one normal
            db.session.add(RbcmProduct(
                rbprd_date='20260101',
                rbprd_id_product=61001,
                rbprd_name='Test Card',
                rbprd_id_metacard=6100,
                rbprd_id_expansion=9900,
                rbprd_type='single',
            ))
            db.session.add(RbcmProduct(
                rbprd_date='20260101',
                rbprd_id_product=61002,
                rbprd_name='Test Card',
                rbprd_id_metacard=6100,
                rbprd_id_expansion=9900,
                rbprd_type='single',
            ))
            from app.models.cardmarket import RbcmIgnored
            db.session.add(RbcmIgnored(rbig_id_product=61001, rbig_name='Test Card'))
            db.session.commit()

        from app.services.cardmarket_matcher import auto_match
        with app.app_context():
            result = auto_match(dry_run=True)

        assert result['success'] is True
        assert 'ignored_count' in result, "Result must include 'ignored_count'"
        assert result['ignored_count'] >= 1

        # Product 61001 was ignored, so only 61002 should be in samples
        sample_ids = [s['id_product'] for s in result.get('samples', [])]
        assert 61001 not in sample_ids, "Ignored product 61001 must not appear in samples"


# ---------------------------------------------------------------------------
# Group E — Selective apply endpoint
# ---------------------------------------------------------------------------

class TestAutoMatchApply:

    def _seed_set_card(self, app):
        """Seed a set + card for testing the apply endpoint."""
        with app.app_context():
            s = RbSet(rbset_id='APL', rbset_name='Apply Set', rbset_ncard=5)
            db.session.add(s)
            c = RbCard(
                rbcar_rbset_id='APL',
                rbcar_id='01',
                rbcar_name='Apply Card',
                rbcar_type='Unit',
                rbcar_rarity='Common',
            )
            db.session.add(c)
            db.session.commit()

    def test_auto_match_apply_inserts_only_selected(self, authenticated_client, app):
        """POST /price/auto-match/apply must insert only the selected pairings."""
        self._seed_set_card(app)

        pairings = [
            {'id_product': 71001, 'rbset_id': 'APL', 'rbcar_id': '01', 'foil': 'N'},
        ]
        resp = authenticated_client.post(
            '/riftbound/price/auto-match/apply',
            json={'pairings': pairings},
        )
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['success'] is True
        assert data['inserted'] == 1
        assert data['review'] == 0

        with app.app_context():
            mapping = RbcmProductCardMap.query.filter_by(rbpcm_id_product=71001).first()
            assert mapping is not None
            assert mapping.rbpcm_rbset_id == 'APL'
            assert mapping.rbpcm_rbcar_id == '01'
            assert mapping.rbpcm_foil == 'N'

    def test_auto_match_apply_skips_duplicate(self, authenticated_client, app):
        """Pairings for already-mapped products must be counted as review, not inserted again."""
        self._seed_set_card(app)

        # Pre-existing mapping for product 72001
        with app.app_context():
            db.session.add(RbcmProductCardMap(
                rbpcm_id_product=72001,
                rbpcm_rbset_id='APL',
                rbpcm_rbcar_id='01',
                rbpcm_foil=None,
                rbpcm_match_type='manual',
            ))
            db.session.commit()

        pairings = [
            {'id_product': 72001, 'rbset_id': 'APL', 'rbcar_id': '01', 'foil': None},
            {'id_product': 72002, 'rbset_id': 'APL', 'rbcar_id': '01', 'foil': 'S'},
        ]
        resp = authenticated_client.post(
            '/riftbound/price/auto-match/apply',
            json={'pairings': pairings},
        )
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['success'] is True
        # 72001 is already mapped → review (skip), 72002 is new → inserted
        assert data['inserted'] == 1
        assert data['review'] == 1
