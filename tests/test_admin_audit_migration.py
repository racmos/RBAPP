"""F13-a S4 (AC3): migration `0010_admin_audit` round trip, drift and FK behaviour."""
from tests.migration_helpers import downgrade, drift, inspector, rows, run, tables, upgrade

AUDIT = ("INSERT INTO riftbound.rbadminaudit (rbaud_actor_id, rbaud_actor_username, "
         "rbaud_action, rbaud_target_type, rbaud_created_at) "
         "VALUES (:actor, 'admin', 'set.create', 'set', '2030-01-01 12:00:00')")


def _admin_user():
    from app import db
    from app.models.user import User
    user = User(username='auditor', email='auditor@test.com')
    user.password_hash = 'x'
    user.is_admin = True
    db.session.add(user)
    db.session.commit()
    return user.id


def test_round_trip_and_no_drift(migration_app):
    upgrade()
    assert 'rbadminaudit' in tables()
    downgrade('0009_card_bans')
    assert 'rbadminaudit' not in tables()
    assert 'rbcardbans' in tables()
    upgrade()
    assert 'rbadminaudit' in tables()
    assert drift() == []


def test_named_constraints_and_indexes(migration_app):
    upgrade()
    indexes = {i['name']: i for i in inspector().get_indexes('rbadminaudit', schema='riftbound')}
    assert indexes['idx_rbadminaudit_created']['column_names'] == ['rbaud_created_at']
    assert indexes['idx_rbadminaudit_target']['column_names'] == [
        'rbaud_target_type', 'rbaud_target_id']
    fks = inspector().get_foreign_keys('rbadminaudit', schema='riftbound')
    assert [(fk['name'], fk['constrained_columns'], fk['referred_table'],
             fk['options'].get('ondelete')) for fk in fks] == [
        ('rbadminaudit_actor_fk', ['rbaud_actor_id'], 'rbusers', 'SET NULL')]


def test_columns(migration_app):
    upgrade()
    columns = {c['name']: c for c in inspector().get_columns('rbadminaudit', schema='riftbound')}
    assert set(columns) == {
        'rbaud_id', 'rbaud_actor_id', 'rbaud_actor_username', 'rbaud_action',
        'rbaud_target_type', 'rbaud_target_id', 'rbaud_details', 'rbaud_created_at'}
    assert columns['rbaud_actor_username']['nullable'] is False
    assert columns['rbaud_target_id']['nullable'] is True
    assert columns['rbaud_details']['nullable'] is True


def test_deleting_the_actor_nulls_the_row(migration_app):
    upgrade()
    run('PRAGMA foreign_keys = ON')
    actor = _admin_user()
    run(AUDIT, actor=actor)
    run('DELETE FROM riftbound.rbusers WHERE id = :id', id=actor)
    assert rows('SELECT rbaud_actor_id, rbaud_actor_username FROM riftbound.rbadminaudit') == [
        (None, 'admin')]
