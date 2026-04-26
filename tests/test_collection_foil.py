"""
TDD tests for REQ-2: Foil restriction for Rare/Epic/Showcase cards.

Tests written FIRST (RED), then implementation.
"""
import json
import pytest
from app import db
from app.models import RbSet, RbCard


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _add_payload(**overrides):
    base = {
        'rbcol_rbset_id': 'TEST1',
        'rbcol_rbcar_id': '001',
        'rbcol_foil': 'S',
        'rbcol_quantity': 1,
    }
    base.update(overrides)
    return base


def _post_add(client, payload):
    return client.post(
        '/riftbound/collection/add',
        data=json.dumps(payload),
        content_type='application/json',
    )


def _make_card(app, rarity, card_id='001'):
    """Create TEST1 set + a card with given rarity."""
    with app.app_context():
        existing_set = RbSet.query.filter_by(rbset_id='TEST1').first()
        if not existing_set:
            s = RbSet(rbset_id='TEST1', rbset_name='Test Set', rbset_ncard=100)
            db.session.add(s)
            db.session.flush()
        existing_card = RbCard.query.filter_by(rbcar_rbset_id='TEST1', rbcar_id=card_id).first()
        if not existing_card:
            c = RbCard(
                rbcar_rbset_id='TEST1',
                rbcar_id=card_id,
                rbcar_name=f'Test {rarity}',
                rbcar_rarity=rarity,
            )
            db.session.add(c)
        db.session.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFoilRestriction:

    def test_collection_add_rejects_foil_for_rare(self, app, authenticated_client):
        """POST with foil='S' on a Rare card MUST return HTTP 400."""
        _make_card(app, 'Rare')
        resp = _post_add(authenticated_client, _add_payload(rbcol_foil='S'))
        assert resp.status_code == 400
        data = resp.get_json()
        assert data['success'] is False
        assert 'Foil not allowed' in data['message']
        assert 'Rare' in data['message']

    def test_collection_add_rejects_foil_for_epic(self, app, authenticated_client):
        """POST with foil='S' on an Epic card MUST return HTTP 400."""
        _make_card(app, 'Epic')
        resp = _post_add(authenticated_client, _add_payload(rbcol_foil='S'))
        assert resp.status_code == 400
        data = resp.get_json()
        assert data['success'] is False
        assert 'Foil not allowed' in data['message']
        assert 'Epic' in data['message']

    def test_collection_add_rejects_foil_for_showcase(self, app, authenticated_client):
        """POST with foil='S' on a Showcase card MUST return HTTP 400."""
        _make_card(app, 'Showcase')
        resp = _post_add(authenticated_client, _add_payload(rbcol_foil='S'))
        assert resp.status_code == 400
        data = resp.get_json()
        assert data['success'] is False
        assert 'Foil not allowed' in data['message']
        assert 'Showcase' in data['message']

    def test_collection_add_accepts_foil_for_common(self, app, authenticated_client):
        """POST with foil='S' on a Common card MUST be accepted (HTTP 200)."""
        _make_card(app, 'Common')
        resp = _post_add(authenticated_client, _add_payload(rbcol_foil='S'))
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
