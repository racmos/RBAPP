"""Owner feedback 2026-10-29 S17: `flask riot recheck-pending [--dry-run]` marks the
pending proposals the S12-S16 rules no longer produce as `obsolete`. No network:
the proposed value is compared with the stored card."""
from datetime import date, datetime

import pytest

from app import db
from app.models.audit import RbAdminAudit
from app.models.card import RbCard
from app.models.card_change import RbCardChange
from app.models.set import RbSet

URL_A = 'https://cmsassets.test/img/a.png'


@pytest.fixture
def cli(app):
    runner = app.test_cli_runner(mix_stderr=False)

    def _invoke(*args):
        return runner.invoke(args=['riot', *args])
    return _invoke


def change(set_id, card_id, field, old, new, status='pending', day=1):
    db.session.add(RbCardChange(rbchg_rbset_id=set_id, rbchg_rbcar_id=card_id,
                                rbchg_field=field, rbchg_old_value=old,
                                rbchg_new_value=new, rbchg_status=status,
                                rbchg_detected_at=datetime(2026, 10, day, 12, 0)))


@pytest.fixture
def data(app):
    db.session.add_all([
        RbSet(rbset_id='OGN', rbset_name='Origins', rbset_outdat=date(2025, 1, 1)),
        RbSet(rbset_id='OGS', rbset_name='Proving', rbset_outdat=date(2025, 1, 1)),
        RbSet(rbset_id='VEN', rbset_name='Vendetta', rbset_ncard=166,
              rbset_outdat=date(2025, 1, 1)),
    ])
    db.session.add_all([
        RbCard(rbcar_rbset_id='OGN', rbcar_id='66', rbcar_name='Ahri, Alluring',
               rbcar_type='Champion Unit', rbcar_energy=9, image_url=URL_A),
        RbCard(rbcar_rbset_id='OGN', rbcar_id='67', rbcar_name='Riven, Shattered',
               rbcar_type='Champion Unit'),
        RbCard(rbcar_rbset_id='OGS', rbcar_id='17', rbcar_name='Dark Child',
               rbcar_type='Legend'),
        RbCard(rbcar_rbset_id='VEN', rbcar_id='69a', rbcar_name='X', rbcar_rarity='Epic'),
        RbCard(rbcar_rbset_id='VEN', rbcar_id='189s', rbcar_name='Y', rbcar_rarity='Epic'),
    ])
    db.session.commit()
    change('OGN', '66', 'rbcar_name', 'Ahri, Alluring', 'Ahri')           # S12: obsolete
    change('OGN', '67', 'rbcar_name', 'Riven, Shattered', 'Riven')        # S12: obsolete
    change('OGN', '66', 'image_url', URL_A, URL_A + '?accountingTag=RB')  # S16: obsolete
    change('OGN', '66', 'rbcar_energy', '9', '2')                         # real: stays
    change('OGS', '17', 'rbcar_type', 'Legend', 'Champion Legend')        # S13: obsolete
    change('VEN', '69a', 'rbcar_rarity', 'Epic', 'Showcase')              # S15: obsolete
    change('VEN', '189s', 'rbcar_rarity', 'Epic', 'Showcase')             # S15: stays
    change('OGN', '67', 'rbcar_type', 'Champion Unit', 'Unit', status='rejected')
    change('OGN', '66', 'rbcar_name', 'Ahri, Alluring', 'Ahri', status='approved')
    db.session.commit()
    return app


def statuses():
    return {(r.rbchg_rbset_id, r.rbchg_rbcar_id, r.rbchg_field, r.rbchg_status):
            (r.rbchg_decided_at, r.rbchg_decided_by)
            for r in RbCardChange.query.order_by(RbCardChange.rbchg_id)}


REPORT = ['Checked 7 pending proposals: 5 obsolete, 2 still pending.',
          '  OGN image_url: 1',
          '  OGN rbcar_name: 2',
          '  OGS rbcar_type: 1',
          '  VEN rbcar_rarity: 1']


class TestRecheck:
    def test_marks_obsolete_and_reports(self, cli, data, frozen_clock):
        result = cli('recheck-pending')
        assert result.exit_code == 0, result.output
        assert result.stdout.splitlines() == REPORT
        assert result.stderr == ''
        rows = RbCardChange.query.order_by(RbCardChange.rbchg_id).all()
        assert [r.rbchg_status for r in rows] == [
            'obsolete', 'obsolete', 'obsolete', 'pending', 'obsolete', 'obsolete',
            'pending', 'rejected', 'approved']
        for row in rows:
            if row.rbchg_status == 'obsolete':
                assert (row.rbchg_decided_at, row.rbchg_decided_by) == (
                    datetime(2030, 1, 1, 12, 0), None)
            if row.rbchg_status == 'pending':
                assert row.rbchg_decided_at is None
        cards = {(c.rbcar_rbset_id, c.rbcar_id): c for c in RbCard.query.all()}
        assert cards[('OGN', '66')].rbcar_name == 'Ahri, Alluring'
        assert cards[('VEN', '69a')].rbcar_rarity == 'Epic'
        audit = RbAdminAudit.query.filter_by(rbaud_action='riot.recheck').one()
        assert audit.rbaud_actor_username == 'system'
        assert audit.rbaud_details == {'checked': 7, 'obsolete': 5, 'pending': 2,
                                       'by_set_field': {'OGN image_url': 1,
                                                        'OGN rbcar_name': 2,
                                                        'OGS rbcar_type': 1,
                                                        'VEN rbcar_rarity': 1}}

    def test_dry_run_changes_nothing(self, cli, data, frozen_clock):
        before = statuses()
        result = cli('recheck-pending', '--dry-run')
        assert result.exit_code == 0, result.output
        assert result.stdout.splitlines() == REPORT + ['Dry run: nothing was changed.']
        db.session.expire_all()
        assert statuses() == before
        assert RbAdminAudit.query.count() == 0

    def test_a_second_run_finds_nothing(self, cli, data, frozen_clock):
        cli('recheck-pending')
        result = cli('recheck-pending')
        assert result.exit_code == 0
        assert result.stdout.splitlines() == [
            'Checked 2 pending proposals: 0 obsolete, 2 still pending.']
        assert RbAdminAudit.query.filter_by(rbaud_action='riot.recheck').count() == 1

    def test_no_pending_proposals(self, cli, app):
        result = cli('recheck-pending')
        assert result.exit_code == 0
        assert result.stdout.splitlines() == [
            'Checked 0 pending proposals: 0 obsolete, 0 still pending.']
        assert RbAdminAudit.query.count() == 0

    def test_a_card_now_holding_the_proposed_value_is_obsolete(self, cli, data):
        card = RbCard.query.filter_by(rbcar_rbset_id='OGN', rbcar_id='66').one()
        card.rbcar_energy = 2
        db.session.commit()
        cli('recheck-pending')
        row = RbCardChange.query.filter_by(rbchg_field='rbcar_energy').one()
        assert row.rbchg_status == 'obsolete'

    def test_the_group_is_listed_in_the_help(self, app):
        runner = app.test_cli_runner(mix_stderr=False)
        result = runner.invoke(args=['riot', '--help'])
        assert result.exit_code == 0
        assert 'recheck-pending' in result.stdout
