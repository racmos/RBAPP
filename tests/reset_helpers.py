"""Shared world for the production data reset tests (RESET-b AC2).

`seed_world()` writes at least one row in EVERY table of `db.metadata` and asserts it did, so a
new table also needs a seed here (the reset must be proven on it). It works on SQLite (the `app`
fixture) and on PostgreSQL (the `-m postgres` tests): rows go through the ORM, so the database
assigns the serial ids and the sequences move as they would in real use.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

import sqlalchemy as sa

from app import db
from app import models as m

KEPT = ('rbadmin', 'racmos', 'rbqa')
DELETED = ('olduser1', 'olduser2')
SET_CODES = ('OGN', 'SFD')
NOW = datetime(2026, 11, 14, 9, 30)
BACKUP_NAME = 'riftbound_pre_reset_20261115_0900.dump'


def fake_toc(dbname=':memory:', price=True):
    """What `pg_restore -l` prints for a dump of `dbname` (header format checked against
    pg_restore 18: `;     dbname: <name>`, entries `<id>; <oid> <oid> TABLE DATA <schema> <table>
    <owner>`)."""
    lines = [
        ';',
        '; Archive created at 2026-11-15 09:00:00 CET',
        f';     dbname: {dbname}',
        ';     TOC Entries: 3',
        ';     Compression: gzip',
        ';     Dump Version: 1.16-0',
        ';     Format: CUSTOM',
        ';',
        '; Selected TOC Entries:',
        ';',
        '3366; 0 16388 TABLE DATA riftbound rbusers rb',
    ]
    if price:
        lines.append('3367; 0 16390 TABLE DATA riftbound rbcm_price rb')
    return '\n'.join(lines) + '\n'


def metadata_tables():
    """Every table of the app metadata in schema `riftbound`, in `sorted_tables` order."""
    return [t for t in db.metadata.sorted_tables if t.schema == 'riftbound']


def count(table_name):
    table = db.metadata.tables[f'riftbound.{table_name}']
    return db.session.execute(sa.select(sa.func.count()).select_from(table)).scalar_one()


def counts():
    return {t.name: count(t.name) for t in metadata_tables()}


def table_rows(table_name):
    """Every row of a table as full tuples, in primary key order (row-by-row comparisons)."""
    table = db.metadata.tables[f'riftbound.{table_name}']
    order = list(table.primary_key.columns) or list(table.columns)
    return [tuple(r) for r in db.session.execute(sa.select(table).order_by(*order)).all()]


def snapshot():
    """Full tuples of every metadata table (what an unchanged database looks like)."""
    db.session.expire_all()
    return {t.name: table_rows(t.name) for t in metadata_tables()}


def expansion_mappings():
    rows = db.session.execute(sa.text(
        'SELECT rbexp_id, rbexp_rbset_id FROM riftbound.rbcm_expansions ORDER BY rbexp_id')).all()
    return [tuple(r) for r in rows]


def _add(obj):
    db.session.add(obj)
    db.session.flush()
    return obj


def _user(username, **extra):
    return _add(m.User(username=username, email=f'{username}@mail.example',
                       password_hash=f'hash-of-{username}', **extra))


def seed_world():
    """The AC2 world. Returns a dict with the ids the tests need."""
    users = {
        'rbadmin': _user('rbadmin', is_admin=True, failed_login_count=3,
                         locked_until=NOW + timedelta(minutes=15)),
        'racmos': _user('racmos', is_admin=True),
        'rbqa': _user('rbqa', is_blocked=True),
        'olduser1': _user('olduser1'),
        'olduser2': _user('olduser2'),
    }
    old, kept = users['olduser1'], users['rbadmin']

    # Catalog: two sets, cards, legacy prices, Riot changes.
    for code in SET_CODES:
        _add(m.RbSet(rbset_id=code, rbset_name=f'Set {code}', rbset_ncard=10,
                     rbset_outdat=date(2026, 1, 1)))
    _add(m.RbCard(rbcar_rbset_id='OGN', rbcar_id='001', rbcar_name='Ahri'))
    _add(m.RbCard(rbcar_rbset_id='SFD', rbcar_id='002', rbcar_name='Annie'))
    _add(m.RbCardMarket(rbcmk_snapshot=NOW, rbcmk_rbset_id='OGN', rbcmk_rbcar_id='001',
                        rbcmk_foil='N', rbcmk_name='Ahri', rbcmk_price=Decimal('1.50')))
    _add(m.RbCardBan(rbban_name_key='ahri', rbban_name='Ahri', rbban_mode='1v1',
                     rbban_since=date(2026, 1, 1)))

    # Jobs: finished daily_prices rows stay (one asked by a deleted user, one by a kept one);
    # every other row goes.
    jobs = {
        'daily_ok': _add(m.RbJob(rbjob_kind='daily_prices', rbjob_status='success',
                                 rbjob_requested_by=old.id, rbjob_finished_at=NOW)),
        'daily_error': _add(m.RbJob(rbjob_kind='daily_prices', rbjob_status='error',
                                    rbjob_requested_by=kept.id, rbjob_message='boom')),
        'riot': _add(m.RbJob(rbjob_kind='riot_sync', rbjob_status='success')),
        'heartbeat': _add(m.RbJob(rbjob_kind='heartbeat', rbjob_status='error',
                                  rbjob_requested_by=kept.id)),
    }
    _add(m.RbCardChange(rbchg_rbset_id='OGN', rbchg_rbcar_id='001', rbchg_field='rbcar_name',
                        rbchg_old_value='Ahri', rbchg_new_value='Ahri, Nine-Tailed',
                        rbchg_status='pending', rbchg_job_id=jobs['riot'].rbjob_id,
                        rbchg_decided_by=kept.id))

    # Cardmarket load history (kept), expansions (two mapped, one unmapped), links and the
    # ignored list (wiped).
    _add(m.RbcmCategory(rbcat_id=1, rbcat_name='Riftbound Single'))
    for exp_id, set_id in ((101, 'OGN'), (102, 'SFD'), (103, None)):
        _add(m.RbcmExpansion(rbexp_id=exp_id, rbexp_name=f'Expansion {exp_id}',
                             rbexp_rbset_id=set_id))
    _add(m.RbcmProduct(rbprd_date='2026-11-14', rbprd_id_product=5001, rbprd_name='Ahri',
                       rbprd_id_category=1, rbprd_id_expansion=101, rbprd_type='single'))
    _add(m.RbcmPrice(rbprc_date='2026-11-14', rbprc_id_product=5001,
                     rbprc_avg=Decimal('1.25'), rbprc_trend=Decimal('1.30')))
    _add(m.RbcmLoadHistory(rblh_date='2026-11-14', rblh_file_type='price_guide',
                           rblh_hash='a' * 64, rblh_rows=1, rblh_status='success'))
    _add(m.RbcmIgnored(rbig_id_product=5002, rbig_name='Token'))
    _add(m.RbcmProductCardMap(rbpcm_id_product=5001, rbpcm_rbset_id='OGN', rbpcm_rbcar_id='001',
                              rbpcm_match_type='auto', rbpcm_confidence=1.0))
    # Products (wiped, owner 2026-11-15) carrying the set codes, one of them set-locked; owned
    # by users below (rbuserproducts -> rbproducts RESTRICT).
    _add(m.RbProducts(rbpdt_id_product=7001, rbpdt_name='Origins Booster', rbpdt_id_set='OGN',
                      rbpdt_kind='booster', rbpdt_set_locked=True))
    _add(m.RbProducts(rbpdt_id_product=7002, rbpdt_name='Spiritforged Box', rbpdt_id_set='SFD',
                      rbpdt_kind='booster_box'))

    # User data, on a deleted user (incl. the username foreign keys) and on a kept one.
    for user in (old, kept):
        uid, name = user.id, user.username
        line = _add(m.RbCollection(rbcol_rbset_id='OGN', rbcol_rbcar_id='001', rbcol_user=name,
                                   rbcol_quantity=2, rbcol_foil='N', rbcol_selling='N',
                                   rbcol_sell_qty=0))
        location = _add(m.RbLocation(rbloc_user=name, rbloc_code='BOX-1', rbloc_position=1))
        _add(m.RbCollectionLocation(rbcll_line_id=line.rbcol_id,
                                    rbcll_location_id=location.rbloc_id, rbcll_qty=2))
        deck = _add(m.RbDeckHead(rbdkh_user_id=uid, rbdkh_name='Deck', rbdkh_mode='1v1',
                                 rbdkh_visibility='public', rbdkh_share_slug=f'slug{uid:018d}'))
        version = _add(m.RbDeckVersion(rbdkv_deck_id=deck.rbdkh_id, rbdkv_seq=1,
                                       rbdkv_content={'v': 2}))
        deck.rbdkh_current_version_id = version.rbdkv_id
        wishlist = _add(m.RbWishlist(rbwls_user_id=uid, rbwls_name='Wishlist',
                                     rbwls_is_default=True, rbwls_position=1))
        _add(m.RbWishlistLine(rbwsl_list_id=wishlist.rbwls_id, rbwsl_name_key='ahri',
                              rbwsl_name='Ahri', rbwsl_foil='any', rbwsl_qty=1))
        _add(m.RbWishlistAlert(rbwal_user_id=uid, rbwal_name_key='ahri', rbwal_name='Ahri',
                               rbwal_price=Decimal('1.00'), rbwal_max_price=Decimal('2.00'),
                               rbwal_price_date=date(2026, 11, 14)))
        _add(m.RbUserProduct(rbupr_user_id=uid, rbupr_id_product=7001, rbupr_quantity=1))
        _add(m.RbValueSnapshot(rbvsn_user_id=uid, rbvsn_date=date(2026, 11, 14),
                               rbvsn_value=Decimal('3.00'), rbvsn_qty=2, rbvsn_unique=1,
                               rbvsn_unpriced=0))
        _add(m.RbImportPreview(rbimp_id=f'00000000-0000-0000-0000-{uid:012d}', rbimp_user_id=uid,
                               rbimp_format='rbapp', rbimp_rows=[],
                               rbimp_expires_at=NOW + timedelta(minutes=30)))
        _add(m.RbUserPrefs(rbprf_user_id=uid, rbprf_density='compact'))
        _add(m.RbKeepPlayset(rbkps_user_id=uid, rbkps_name_key='ahri'))
        # F9 tables.
        _add(m.RbSession(rbses_user_id=uid, rbses_token_hash=f'{uid:064d}'))
        _add(m.RbUserProfile(rbupf_user_id=uid, rbupf_display_name=name.title()))
        _add(m.RbUserMfa(rbmfa_user_id=uid, rbmfa_secret_enc='ciphertext',
                         rbmfa_enabled_at=NOW))
        _add(m.RbRecoveryCode(rbrco_user_id=uid, rbrco_code_hash=f'{uid:064d}'))
        _add(m.RbApiKey(rbapk_user_id=uid, rbapk_prefix=f'rb_live_{uid:06d}',
                        rbapk_key_hash=f'{uid:064d}'))
    _add(m.RbCaptchaUsed(rbcap_hash='c' * 64, rbcap_expires_at=NOW))
    _add(m.RbAdminAudit(rbaud_actor_id=kept.id, rbaud_actor_username='rbadmin',
                        rbaud_action='set.create', rbaud_target_type='set', rbaud_target_id='OGN'))
    _add(m.RbAdminAudit(rbaud_actor_id=old.id, rbaud_actor_username='olduser1',
                        rbaud_action='card.update', rbaud_target_type='card',
                        rbaud_target_id='OGN/001'))
    db.session.commit()

    empty = [name for name, rows in counts().items() if rows == 0]
    assert not empty, f'seed_world() wrote no row in: {", ".join(empty)} (add a seed for them)'
    return {
        'user_ids': {name: user.id for name, user in users.items()},
        'job_ids': {name: job.rbjob_id for name, job in jobs.items()},
    }
