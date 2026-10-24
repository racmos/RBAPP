"""F2-a S9: the Jinja catalog (GET /riftbound/card) reads bans from `rbcardbans`:
Banned cell, grid badge and the `search_banned` filter; the admin add/edit modals
lose the banned field. Plus what still holds of the touched page (PRESERVE)."""
from datetime import date

import pytest
from bs4 import BeautifulSoup

from app import db
from app.models import RbCard, RbSet
from app.services import bans

URL = '/riftbound/card'
JINX = 'Jinx, Loose Cannon'


@pytest.fixture
def catalog(app):
    db.session.add_all([RbSet(rbset_id='OGN', rbset_name='Origins'),
                        RbSet(rbset_id='OGNX', rbset_name='Origins promos')])
    db.session.add_all([
        RbCard(rbcar_rbset_id='OGN', rbcar_id='79', rbcar_name=JINX),
        RbCard(rbcar_rbset_id='OGNX', rbcar_id='257', rbcar_name='JINX, LOOSE CANNON'),
        RbCard(rbcar_rbset_id='OGN', rbcar_id='1', rbcar_name='Called Shot'),
        # the legacy flag says banned; the ban table does not
        RbCard(rbcar_rbset_id='OGN', rbcar_id='2', rbcar_name='Legacy Flag', rbcar_banned='S'),
        RbCard(rbcar_rbset_id='OGN', rbcar_id='3', rbcar_name='Plain Card', rbcar_banned='N'),
    ])
    db.session.commit()


@pytest.fixture
def banned(catalog):
    bans.add_ban(JINX, ['1v1', '2v2'], since=date(2026, 9, 1))
    bans.add_ban('Called Shot', ['2v2'], since=date(2026, 9, 18))


def _page(client, **args):
    resp = client.get(URL, query_string=args)
    assert resp.status_code == 200
    return BeautifulSoup(resp.get_data(as_text=True), 'html.parser')


def _table(soup):
    """(set, id, name, banned cell) of every table row, in page order."""
    rows = []
    for tr in soup.select('#listView tbody tr'):
        cells = [td.get_text(strip=True) for td in tr.find_all('td', recursive=False)]
        rows.append((cells[1], cells[2], cells[3], cells[10]))
    return rows


def _badges(soup):
    """(name, badge text, badge classes) of every grid card, in page order."""
    return [(item.h3.get_text(strip=True),
             ' '.join(item.select_one('.banned-badge').get_text().split()),
             sorted(set(item.select_one('.banned-badge')['class']) - {'banned-badge'}))
            for item in soup.select('#imageView .card-item')]


# --- PRESERVE: what the page did before and still does ---------------------------------

def test_catalog_lists_every_card_in_set_and_number_order(authenticated_client, catalog):
    assert [row[:3] for row in _table(_page(authenticated_client))] == [
        ('OGN', '1', 'Called Shot'), ('OGN', '2', 'Legacy Flag'), ('OGN', '3', 'Plain Card'),
        ('OGN', '79', JINX), ('OGNX', '257', 'JINX, LOOSE CANNON')]


def test_other_filters_still_apply(authenticated_client, catalog):
    soup = _page(authenticated_client, search_name='jinx')
    assert [row[:3] for row in _table(soup)] == [
        ('OGN', '79', JINX), ('OGNX', '257', 'JINX, LOOSE CANNON')]
    soup = _page(authenticated_client, search_set='OGNX')
    assert [row[1] for row in _table(soup)] == ['257']


def test_status_filter_select_keeps_its_options(authenticated_client, catalog):
    select = _page(authenticated_client, search_banned='S').select_one('select#search_banned')
    assert [(o['value'], o.get_text(strip=True), o.has_attr('selected'))
            for o in select.find_all('option')] == [
        ('', 'All', False), ('N', 'Allowed', False), ('S', 'Banned', True)]


def test_modals_are_for_admins_only(authenticated_client, admin_client, catalog):
    plain = _page(authenticated_client)
    assert plain.select('#addModal, #editModal') == []
    admin = _page(admin_client)
    assert len(admin.select('#addModal')) == 1 and len(admin.select('#editModal')) == 1
    assert len(admin.select('#listView tbody button')) == 5


def test_card_endpoints_still_accept_rbcar_banned_and_keep_the_column(admin_client, catalog):
    resp = admin_client.post('/riftbound/card/update/OGN/2', json={'rbcar_name': 'Legacy Flag'})
    assert resp.get_json() == {'success': True}
    assert db.session.get(RbCard, ('OGN', '2')).rbcar_banned == 'S'
    resp = admin_client.post('/riftbound/card/update/OGN/3', json={'rbcar_banned': 'S'})
    assert resp.get_json() == {'success': True}
    assert db.session.get(RbCard, ('OGN', '3')).rbcar_banned == 'S'
    resp = admin_client.post('/riftbound/card/add', json={
        'rbcar_rbset_id': 'OGN', 'rbcar_id': '4', 'rbcar_name': 'New Card'})
    assert resp.get_json() == {'success': True}
    assert db.session.get(RbCard, ('OGN', '4')).rbcar_banned == 'N'


# --- S9: bans come from the ban table -----------------------------------------------

def test_banned_cell_shows_the_modes(authenticated_client, banned):
    assert [(row[1], row[3]) for row in _table(_page(authenticated_client))] == [
        ('1', '2v2'), ('2', '—'), ('3', '—'), ('79', '1v1, 2v2'), ('257', '1v1, 2v2')]


def test_grid_badge_shows_the_modes(authenticated_client, banned):
    assert _badges(_page(authenticated_client)) == [
        ('Called Shot', 'BANNED 2v2', ['banned-yes']),
        ('Legacy Flag', 'ALLOWED', ['banned-no']),
        ('Plain Card', 'ALLOWED', ['banned-no']),
        (JINX, 'BANNED 1v1, 2v2', ['banned-yes']),
        ('JINX, LOOSE CANNON', 'BANNED 1v1, 2v2', ['banned-yes']),
    ]


def test_without_bans_everything_is_allowed(authenticated_client, catalog):
    soup = _page(authenticated_client)
    assert {row[3] for row in _table(soup)} == {'—'}
    assert {badge[1] for badge in _badges(soup)} == {'ALLOWED'}


def test_search_banned_s_keeps_cards_banned_in_some_mode(authenticated_client, banned):
    assert [row[1] for row in _table(_page(authenticated_client, search_banned='S'))] == [
        '1', '79', '257']


def test_search_banned_n_keeps_cards_banned_in_no_mode(authenticated_client, banned):
    assert [row[1] for row in _table(_page(authenticated_client, search_banned='N'))] == [
        '2', '3']


def test_search_banned_with_no_bans(authenticated_client, catalog):
    assert _table(_page(authenticated_client, search_banned='S')) == []
    assert len(_table(_page(authenticated_client, search_banned='N'))) == 5


def test_search_banned_combines_with_other_filters(authenticated_client, banned):
    soup = _page(authenticated_client, search_banned='S', search_set='OGN')
    assert [row[1] for row in _table(soup)] == ['1', '79']


def test_modals_have_no_banned_control_and_the_js_does_not_send_it(admin_client, banned):
    resp = admin_client.get(URL)
    html = resp.get_data(as_text=True)
    soup = BeautifulSoup(html, 'html.parser')
    assert soup.select('#add_rbcar_banned, #edit_rbcar_banned') == []
    for modal in soup.select('#addModal, #editModal'):
        assert 'Banned' not in modal.get_text()
    script = '\n'.join(s.get_text() for s in soup.find_all('script'))
    assert 'rbcar_banned:' not in script
    assert 'rbcar_banned' not in script.replace('"rbcar_banned"', '')


@pytest.mark.parametrize('value', ['X', 'Y', 's'])
def test_search_banned_other_values_still_match_nothing(authenticated_client, banned, value):
    assert _table(_page(authenticated_client, search_banned=value)) == []


def test_search_banned_empty_is_all(authenticated_client, banned):
    assert len(_table(_page(authenticated_client, search_banned=''))) == 5
