"""F3-b S4: "keep a playset" flag and the short warning (D-F3-10)."""
import pytest

from app import db
from app.models import RbKeepPlayset, RbUserPrefs
from app.services.bans import name_key
from tests.collection_read_helpers import URL, line, seed_catalog


@pytest.fixture
def api(app, authenticated_client):
    with app.app_context():
        seed_catalog()
    return authenticated_client


def groups(api, **params):
    response = api.get(URL, query_string=params)
    assert response.status_code == 200
    return {g['key']: g for g in response.get_json()['data']['items']}


def keep(app, name, username='testuser'):
    from app.models import User
    with app.app_context():
        user = User.query.filter_by(username=username).one()
        db.session.add(RbKeepPlayset(rbkps_user_id=user.id, rbkps_name_key=name_key(name)))
        db.session.commit()


def test_without_a_mark_nothing_is_kept_or_short(app, api):
    with app.app_context():
        db.session.add(line('79', 1))
        db.session.commit()
    group = groups(api)['OGN-79:N']
    assert (group['keep_playset'], group['playset_short']) == (False, False)


def test_the_mark_covers_every_printing_and_foil_of_the_name(app, api):
    with app.app_context():
        db.session.add_all([line('79', 1), line('257', 1, set_id='SFD')])
        db.session.commit()
    keep(app, 'jinx, loose cannon')
    found = groups(api)
    assert found['OGN-79:N']['keep_playset'] is True
    assert found['SFD-257:N']['keep_playset'] is True


def test_short_when_the_kept_copies_across_printings_are_below_the_size(app, api):
    with app.app_context():
        db.session.add_all([line('79', 1), line('257', 1, set_id='SFD')])
        db.session.commit()
    keep(app, 'Jinx, Loose Cannon')
    found = groups(api)
    assert found['OGN-79:N']['playset_short'] is True      # 2 kept < 3
    assert found['SFD-257:N']['playset_short'] is True     # the same for every group of the name


def test_not_short_when_the_playset_is_complete(app, api):
    with app.app_context():
        db.session.add_all([line('79', 2), line('257', 1, set_id='SFD', foil='N',
                                                 condition='EX')])
        db.session.commit()
    keep(app, 'Jinx, Loose Cannon')
    found = groups(api)
    assert found['OGN-79:N']['playset_short'] is False     # 3 kept
    assert found['SFD-257:N']['playset_short'] is False


def test_copies_for_sale_are_not_kept(app, api):
    with app.app_context():
        db.session.add_all([line('79', 3, selling='Y', sell_qty=1)])
        db.session.commit()
    keep(app, 'Jinx, Loose Cannon')
    assert groups(api)['OGN-79:N']['playset_short'] is True   # 2 kept of 3


def test_kept_copies_ignore_the_filters(app, api):
    with app.app_context():
        db.session.add_all([line('79', 2), line('257', 1, set_id='SFD', condition='EX')])
        db.session.commit()
    keep(app, 'Jinx, Loose Cannon')
    # only the SFD line matches, yet the 3 copies of the name are counted
    found = groups(api, condition='EX')
    assert list(found) == ['SFD-257:N']
    assert found['SFD-257:N']['keep_playset'] is True
    assert found['SFD-257:N']['playset_short'] is False


def test_a_custom_playset_size(app, api):
    with app.app_context():
        from app.models import User
        user = User.query.filter_by(username='testuser').one()
        db.session.add(RbUserPrefs(rbprf_user_id=user.id, rbprf_playset_size=4))
        db.session.add(line('79', 3))
        db.session.commit()
    keep(app, 'Jinx, Loose Cannon')
    response = api.get(URL)
    assert response.get_json()['meta']['playset_size'] == 4
    assert groups(api)['OGN-79:N']['playset_short'] is True      # 3 < 4


def test_another_users_mark_does_not_count(app, api, make_user):
    make_user('otheruser')
    with app.app_context():
        db.session.add(line('79', 1))
        db.session.commit()
    keep(app, 'Jinx, Loose Cannon', username='otheruser')
    assert groups(api)['OGN-79:N']['keep_playset'] is False


def test_every_group_of_a_name_reports_the_kept_copies_of_the_name(app, api):
    with app.app_context():
        db.session.add_all([line('79', 2, selling='Y', sell_qty=1),
                            line('257', 1, set_id='SFD', condition='EX')])
        db.session.commit()
    found = groups(api)
    assert found['OGN-79:N']['kept'] == found['SFD-257:N']['kept'] == 2     # (2 - 1) + 1
    keep(app, 'Jinx, Loose Cannon')
    assert groups(api, condition='EX')['SFD-257:N']['kept'] == 2            # filters do not change it
