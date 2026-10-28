"""F3-e S5 (AC2, AC3): POST /collection/import/commit and the export -> import round trip."""

import pytest

from app import db
from app.models import RbCollection, RbImportPreview
from tests.collection_read_helpers import line, seed_catalog, seed_lines
from tests.import_helpers import COMMIT, PREVIEW, make_csv, row

EXPORT = '/riftbound/api/v1/collection/export'


@pytest.fixture
def api(app, authenticated_client, make_user, frozen_clock):
    make_user('otheruser')
    with app.app_context():
        seed_catalog()
    return authenticated_client


def preview(api, rows, **kwargs):
    response = api.post(PREVIEW, json={'text': make_csv(rows, **kwargs)})
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()['data']['preview_id']


def commit(api, preview_id, mode='add'):
    return api.post(COMMIT, json={'preview_id': preview_id, 'mode': mode})


def mine(user='testuser'):
    db.session.expire_all()
    return [(r.rbcol_rbset_id, r.rbcol_rbcar_id, r.rbcol_foil, r.rbcol_quantity,
             r.rbcol_condition, r.rbcol_language, r.rbcol_selling, r.rbcol_sell_qty)
            for r in RbCollection.query.filter_by(rbcol_user=user)
            .order_by(RbCollection.rbcol_id)]


class TestAdd:
    def test_creates_lines_and_counts_them(self, api):
        pid = preview(api, [row(qty='2', condition='NM'), row(card_id='2', name='Beta Calm')])
        response = commit(api, pid)
        assert response.status_code == 200
        assert response.get_json()['data'] == {'created': 2, 'merged': 0, 'replaced': 0,
                                               'skipped': 0}
        assert mine() == [('OGN', '1', 'N', 2, 'NM', None, 'N', 0),
                          ('OGN', '2', 'N', 1, None, None, 'N', 0)]

    def test_merges_into_existing_identical_lines(self, app, api):
        with app.app_context():
            db.session.add(line('1', 3, condition='NM', language='English'))
            db.session.commit()
        pid = preview(api, [row(qty='2', condition='NM', language='English')])
        data = commit(api, pid).get_json()['data']
        assert (data['created'], data['merged']) == (0, 1)
        assert mine()[0][3] == 5

    def test_duplicate_rows_of_the_file_merge_on_commit(self, api):
        pid = preview(api, [row(qty='2'), row(qty='3')])
        data = commit(api, pid).get_json()['data']
        assert (data['created'], data['merged']) == (1, 1)
        assert mine() == [('OGN', '1', 'N', 5, None, None, 'N', 0)]

    def test_selling_rows_keep_their_quantities_and_price_as_in_the_file(self, api):
        pid = preview(api, [row(qty='5', selling='Y', sell_qty='2'),
                            row(card_id='2', qty='3', selling='Y', sell_price='4,5')])
        commit(api, pid)
        db.session.expire_all()
        first, second = RbCollection.query.order_by(RbCollection.rbcol_id).all()
        assert (first.rbcol_selling, first.rbcol_sell_qty, first.rbcol_sell_price) == ('Y', 2, None)
        assert (second.rbcol_sell_qty, float(second.rbcol_sell_price)) == (3, 4.5)

    def test_error_rows_are_skipped_and_counted(self, api):
        pid = preview(api, [row(), row(set_id='ZZZ'), row(qty='0'), row(name='Other')])
        data = commit(api, pid).get_json()['data']
        assert data == {'created': 1, 'merged': 1, 'replaced': 0, 'skipped': 2}
        assert mine() == [('OGN', '1', 'N', 2, None, None, 'N', 0)]

    def test_the_preview_is_deleted_and_cannot_be_used_twice(self, api):
        pid = preview(api, [row()])
        assert commit(api, pid).status_code == 200
        db.session.expire_all()
        assert db.session.get(RbImportPreview, pid) is None
        assert commit(api, pid).status_code == 410

    def test_other_users_lines_are_never_touched(self, app, api):
        with app.app_context():
            db.session.add(line('1', 9, user='otheruser'))
            db.session.commit()
        commit(api, preview(api, [row(qty='2')]))
        assert mine('otheruser')[0][3] == 9


class TestReplace:
    def test_replaces_only_the_printings_in_the_file(self, app, api):
        with app.app_context():
            db.session.add_all([
                line('1', 5, condition='NM'), line('1', 2, condition='EX'),   # OGN-1 N
                line('1', 1, foil='S'),                                       # OGN-1 S: not in file
                line('2', 4)])                                                # OGN-2: not in file
            db.session.commit()
        pid = preview(api, [row(qty='7', condition='GD')])
        data = commit(api, pid, 'replace').get_json()['data']
        assert data == {'created': 1, 'merged': 0, 'replaced': 1, 'skipped': 0}
        assert mine() == [('OGN', '1', 'S', 1, 'NM', 'English', 'N', 0),
                          ('OGN', '2', 'N', 4, 'NM', 'English', 'N', 0),
                          ('OGN', '1', 'N', 7, 'GD', None, 'N', 0)]

    def test_error_rows_do_not_replace_anything(self, app, api):
        with app.app_context():
            db.session.add(line('2', 4))
            db.session.commit()
        pid = preview(api, [row(card_id='2', name='Beta Calm', qty='0')])
        data = commit(api, pid, 'replace').get_json()['data']
        assert (data['replaced'], data['skipped']) == (0, 1)
        assert mine()[0][3] == 4

    def test_replace_never_touches_another_user(self, app, api):
        with app.app_context():
            db.session.add(line('1', 9, user='otheruser'))
            db.session.commit()
        commit(api, preview(api, [row(qty='2')]), 'replace')
        assert mine('otheruser')[0][3] == 9


class TestOwnershipAndErrors:
    def test_unknown_preview_is_410(self, api):
        response = commit(api, '00000000-0000-0000-0000-000000000000')
        body = response.get_json()
        assert response.status_code == 410 and body['code'] == 'import_expired'

    def test_expired_preview_is_410_and_writes_nothing(self, api, frozen_clock):
        pid = preview(api, [row()])
        frozen_clock.advance(minutes=31)
        assert commit(api, pid).status_code == 410
        assert mine() == []

    def test_another_users_preview_is_410(self, app, api, make_user):
        pid = preview(api, [row()])
        from tests.conftest import login_as
        other = login_as(app.test_client(), 'otheruser')
        assert commit(other, pid).status_code == 410
        assert commit(api, pid).status_code == 200            # still the owner's

    @pytest.mark.parametrize('body', [{}, {'preview_id': 'x'}, {'preview_id': 'x', 'mode': 'merge'},
                                      {'mode': 'add'}])
    def test_bad_bodies_are_a_400(self, api, body):
        response = api.post(COMMIT, json=body)
        assert response.status_code == 400 and response.get_json()['code'] == 'validation_error'

    def test_requires_a_session(self, app):
        assert app.test_client().post(COMMIT, json={}).status_code == 401

    def test_a_failure_in_the_middle_leaves_nothing(self, api, monkeypatch):
        from app.services import collection_write
        real = collection_write.add_row
        calls = []

        def flaky(*args, **kwargs):
            calls.append(1)
            if len(calls) == 2:
                raise RuntimeError('boom')
            return real(*args, **kwargs)

        pid = preview(api, [row(), row(card_id='2', name='Beta Calm')])
        monkeypatch.setattr(collection_write, 'add_row', flaky)
        response = commit(api, pid)
        assert response.status_code == 500
        assert mine() == []
        db.session.expire_all()
        assert db.session.get(RbImportPreview, pid) is not None      # the user may retry


def full_snapshot(user='testuser'):
    """Every stored field of the user's lines, ids left out."""
    db.session.expire_all()
    money = lambda v: None if v is None else float(v)
    return sorted((r.rbcol_rbset_id, r.rbcol_rbcar_id, r.rbcol_foil, r.rbcol_quantity,
                   r.rbcol_condition or '', r.rbcol_language or '', money(r.rbcol_purchase_price),
                   r.rbcol_selling, r.rbcol_sell_qty, money(r.rbcol_sell_price))
                  for r in RbCollection.query.filter_by(rbcol_user=user))


class TestRoundTrip:
    def test_export_then_import_with_replace_changes_nothing(self, app, api):
        with app.app_context():
            seed_lines()
        before = full_snapshot()
        assert len(before) == 7
        exported = api.get(EXPORT, query_string={'format': 'rbapp'}).get_data(as_text=True)
        response = api.post(PREVIEW, json={'text': exported})
        assert response.status_code == 200
        data = response.get_json()['data']
        assert (data['summary']['error'], data['summary']['total']) == (0, 7)
        result = commit(api, data['preview_id'], 'replace').get_json()['data']
        assert (result['created'], result['replaced'], result['skipped']) == (7, 6, 0)
        assert full_snapshot() == before

    def test_exporting_then_importing_with_add_doubles_the_quantities(self, app, api):
        with app.app_context():
            seed_lines()
        exported = api.get(EXPORT).get_data(as_text=True)
        data = api.post(PREVIEW, json={'text': exported}).get_json()['data']
        result = commit(api, data['preview_id'], 'add').get_json()['data']
        assert (result['created'], result['merged']) == (0, 7)
        assert sum(r[3] for r in full_snapshot()) == 28
