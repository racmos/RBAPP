"""
TDD tests for REQ-1: Auto-merge exact duplicates in collection.

Tests written FIRST (RED), then implementation.
"""
import json
import pytest
from app import db
from app.models import RbSet, RbCard, RbCollection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _add_payload(**overrides):
    """Base valid payload for POST /riftbound/collection/add."""
    base = {
        'rbcol_rbset_id': 'TEST1',
        'rbcol_rbcar_id': '001',
        'rbcol_foil': 'N',
        'rbcol_quantity': 1,
        'rbcol_selling': 'N',
        'rbcol_sell_price': None,
        'rbcol_condition': None,
        'rbcol_language': None,
    }
    base.update(overrides)
    return base


def _post_add(client, payload):
    return client.post(
        '/riftbound/collection/add',
        data=json.dumps(payload),
        content_type='application/json',
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def setup_card(app):
    """Create TEST1 set + card 001 (Common)."""
    with app.app_context():
        s = RbSet(rbset_id='TEST1', rbset_name='Test Set', rbset_ncard=100)
        db.session.add(s)
        db.session.flush()
        c = RbCard(
            rbcar_rbset_id='TEST1',
            rbcar_id='001',
            rbcar_name='Test Common',
            rbcar_rarity='Common',
        )
        db.session.add(c)
        db.session.commit()


# ---------------------------------------------------------------------------
# A1 - test_add_creates_new_when_no_duplicate
# ---------------------------------------------------------------------------

class TestAutoMergeDuplicates:

    def test_add_creates_new_when_no_duplicate(self, app, authenticated_client, setup_card):
        """Adding a card with no existing row MUST create a new row (merged=False)."""
        with app.app_context():
            resp = _post_add(authenticated_client, _add_payload())
            assert resp.status_code == 200
            data = resp.get_json()
            assert data['success'] is True
            assert data['merged'] is False
            # Verify exactly 1 row in DB
            rows = RbCollection.query.filter_by(
                rbcol_rbset_id='TEST1', rbcol_rbcar_id='001'
            ).all()
            assert len(rows) == 1
            assert int(rows[0].rbcol_quantity) == 1

    def test_add_merges_when_exact_duplicate(self, app, authenticated_client, setup_card):
        """Adding the SAME card twice with identical fields MUST merge (qty summed, merged=True)."""
        with app.app_context():
            # First add: qty=2
            r1 = _post_add(authenticated_client, _add_payload(rbcol_quantity=2))
            assert r1.status_code == 200
            d1 = r1.get_json()
            assert d1['merged'] is False

            # Second add: same fields, qty=3
            r2 = _post_add(authenticated_client, _add_payload(rbcol_quantity=3))
            assert r2.status_code == 200
            d2 = r2.get_json()
            assert d2['success'] is True
            assert d2['merged'] is True
            # Same rbcol_id (the original row)
            assert d2['rbcol_id'] == d1['rbcol_id']

            # DB: still exactly 1 row, quantity is 2+3=5
            rows = RbCollection.query.filter_by(
                rbcol_rbset_id='TEST1', rbcol_rbcar_id='001'
            ).all()
            assert len(rows) == 1
            assert int(rows[0].rbcol_quantity) == 5

    def test_add_inserts_new_when_field_differs(self, app, authenticated_client, setup_card):
        """Adding same card but with a DIFFERENT condition MUST create a new row (merged=False)."""
        with app.app_context():
            r1 = _post_add(authenticated_client, _add_payload(rbcol_condition='NM'))
            r2 = _post_add(authenticated_client, _add_payload(rbcol_condition='EX'))
            assert r1.status_code == 200
            assert r2.status_code == 200
            assert r1.get_json()['merged'] is False
            assert r2.get_json()['merged'] is False

            rows = RbCollection.query.filter_by(
                rbcol_rbset_id='TEST1', rbcol_rbcar_id='001'
            ).all()
            assert len(rows) == 2

    def test_add_handles_null_fields_as_equal(self, app, authenticated_client, setup_card):
        """NULL == NULL: two adds with all nullable fields=None MUST merge into 1 row."""
        with app.app_context():
            r1 = _post_add(authenticated_client, _add_payload(
                rbcol_sell_price=None,
                rbcol_condition=None,
                rbcol_language=None,
                rbcol_quantity=1,
            ))
            r2 = _post_add(authenticated_client, _add_payload(
                rbcol_sell_price=None,
                rbcol_condition=None,
                rbcol_language=None,
                rbcol_quantity=1,
            ))
            assert r1.get_json()['merged'] is False
            assert r2.get_json()['merged'] is True

            rows = RbCollection.query.filter_by(
                rbcol_rbset_id='TEST1', rbcol_rbcar_id='001'
            ).all()
            assert len(rows) == 1
            assert int(rows[0].rbcol_quantity) == 2
