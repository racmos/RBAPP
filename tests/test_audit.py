"""F13-a S5 (AC2): app.services.audit.record."""
import pytest
from flask_login import login_user

from app import db
from app.models.audit import RbAdminAudit
from app.services.audit import SYSTEM, record


@pytest.fixture
def signed_in(app, make_user):
    """An authenticated admin inside a request context; yields the user."""
    user = make_user('auditor', is_admin=True)
    ctx = app.test_request_context('/')
    ctx.push()
    login_user(user)
    yield user
    ctx.pop()


class TestActor:
    def test_the_signed_in_user_is_the_default_actor(self, signed_in):
        row = record('set.create', 'set', 'OGN')
        db.session.commit()
        assert row.rbaud_actor_id == signed_in.id
        assert row.rbaud_actor_username == 'auditor'

    def test_system_has_no_actor_id(self, app):
        with app.test_request_context('/'):
            row = record('riot.apply', 'card', 'OGN/1', actor=SYSTEM)
            db.session.commit()
        assert row.rbaud_actor_id is None
        assert row.rbaud_actor_username == 'system'

    def test_an_explicit_actor_wins(self, signed_in, make_user):
        other = make_user('other')
        row = record('card.delete', 'card', 'OGN/2', actor=other)
        db.session.commit()
        assert (row.rbaud_actor_id, row.rbaud_actor_username) == (other.id, 'other')

    def test_without_a_signed_in_user_actor_none_is_an_error(self, app):
        with app.test_request_context('/'):
            with pytest.raises(RuntimeError):
                record('set.create', 'set')


class TestRow:
    def test_the_row_is_added_but_not_committed(self, signed_in):
        row = record('set.create', 'set', 'OGN', {'name': 'Origen'})
        assert row in db.session.new
        # A fresh connection does not see it yet.
        with db.engine.connect() as conn:
            from sqlalchemy import text
            assert conn.execute(
                text('SELECT COUNT(*) FROM riftbound.rbadminaudit')).scalar() == 0
        db.session.commit()
        stored = db.session.get(RbAdminAudit, row.rbaud_id)
        assert stored.rbaud_action == 'set.create'
        assert stored.rbaud_target_type == 'set'
        assert stored.rbaud_target_id == 'OGN'
        assert stored.rbaud_details == {'name': 'Origen'}
        assert stored.rbaud_created_at is not None

    def test_optional_fields_default_to_none(self, signed_in):
        row = record('set.update', 'set')
        db.session.commit()
        assert row.rbaud_target_id is None
        assert row.rbaud_details is None


class TestValidation:
    @pytest.mark.parametrize('action', [
        'SetCreate', 'set', 'set.create.', '.set.create', 'set..create',
        'SET.CREATE', 'set.create1', 'set-create', '', None,
    ])
    def test_the_action_must_be_dotted_lowercase(self, signed_in, action):
        with pytest.raises(ValueError):
            record(action, 'set')
        assert RbAdminAudit.query.count() == 0

    @pytest.mark.parametrize('action', ['set.create', 'riot.apply_changes', 'a.b', 'x_y.z_w'])
    def test_valid_actions(self, signed_in, action):
        assert record(action, 'set').rbaud_action == action

    def test_details_must_be_serialisable(self, signed_in):
        with pytest.raises(ValueError):
            record('set.create', 'set', details={'x': object()})
        assert RbAdminAudit.query.count() == 0

    def test_details_over_4096_bytes_are_refused(self, signed_in):
        big = {'text': 'á' * 3000}            # > 4096 bytes once serialised as UTF-8
        with pytest.raises(ValueError):
            record('set.create', 'set', details=big)
        assert RbAdminAudit.query.count() == 0

    def test_details_of_exactly_4096_bytes_are_accepted(self, signed_in):
        import json
        text = 'a' * (4096 - len(json.dumps({'t': ''})))
        details = {'t': text}
        assert len(json.dumps(details, ensure_ascii=False).encode('utf-8')) == 4096
        assert record('set.create', 'set', details=details) is not None
