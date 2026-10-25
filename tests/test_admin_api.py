"""F13-a S1/S3 (AC1): the admin API blueprint guard and GET /admin/overview."""
from datetime import date

import pytest
from sqlalchemy import event

from app import db
from app.models.card import RbCard
from app.models.set import RbSet

URL = '/riftbound/api/v1/admin/overview'
JSON = {'Accept': 'application/json'}


@pytest.fixture
def catalog(app):
    """3 sets (2 without a release date) and 4 cards (2 without image)."""
    db.session.add_all([
        RbSet(rbset_id='OGN', rbset_name='Origen', rbset_ncard=2, rbset_outdat=date(2026, 1, 1)),
        RbSet(rbset_id='SFD', rbset_name='Segundo', rbset_ncard=2),
        RbSet(rbset_id='UNL', rbset_name='Tercero', rbset_ncard=0),
    ])
    db.session.add_all([
        RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='A', image='ogn_1.png'),
        RbCard(rbcar_rbset_id='OGN', rbcar_id='2', rbcar_name='B', image=None),
        RbCard(rbcar_rbset_id='SFD', rbcar_id='1', rbcar_name='C', image=''),
        RbCard(rbcar_rbset_id='SFD', rbcar_id='2', rbcar_name='D', image='sfd_2.png'),
    ])
    db.session.commit()
    return app


class TestGuard:
    def test_anonymous_gets_a_json_401(self, client):
        resp = client.get(URL, headers=JSON)
        assert resp.status_code == 401
        body = resp.get_json()
        assert body['success'] is False
        assert body['code'] == 'unauthenticated'

    def test_a_plain_user_gets_a_json_403(self, authenticated_client):
        resp = authenticated_client.get(URL, headers=JSON)
        assert resp.status_code == 403
        body = resp.get_json()
        assert body['success'] is False
        assert body['error'] == 'Forbidden'

    def test_the_rule_is_classified_admin(self):
        from tests.test_authz_matrix import MATRIX
        assert MATRIX['api_admin.*'] == 'A'


class TestOverview:
    def test_the_catalog_counts(self, admin_client, catalog):
        resp = admin_client.get(URL)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert body['data'] == {'catalog': {
            'sets': 3, 'sets_without_release_date': 2,
            'cards': 4, 'cards_without_image': 2}}

    def test_an_empty_catalog_counts_zeros(self, admin_client):
        body = admin_client.get(URL).get_json()
        assert body['data']['catalog'] == {
            'sets': 0, 'sets_without_release_date': 0, 'cards': 0, 'cards_without_image': 0}

    def test_at_most_four_statements_beyond_the_session(self, admin_client, catalog):
        """The handler issues 4 COUNTs; the Flask-Login user load is excluded."""
        counted = []

        def before(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith('SELECT') and 'rbusers' not in statement:
                counted.append(statement)

        event.listen(db.engine, 'before_cursor_execute', before)
        try:
            assert admin_client.get(URL).status_code == 200
        finally:
            event.remove(db.engine, 'before_cursor_execute', before)
        assert len(counted) <= 4, counted
