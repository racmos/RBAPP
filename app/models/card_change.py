"""Proposed card changes from the Riot sync (F13-R4, F13-c).

A `monthly` (or `none` window) difference between the gallery and a stored
card becomes one `pending` row per field; the admin approves or rejects it
(F13-g). Auto-applied changes never land here. Values are stored as text
(numbers as decimal strings, NULL as NULL). `obsolete` (owner feedback
2026-10-29, S17) marks a pending row the sync rules no longer produce
(`flask riot recheck-pending`); it is never re-opened.
"""
from sqlalchemy.dialects.postgresql import JSONB  # noqa: F401

from app import db
from app.schemas.prefs_domain import sql_in
from app.utils import clock

# Fields the sync compares and may propose (S5). `rbcar_banned` is never one.
SYNCED_FIELDS = ('rbcar_name', 'rbcar_domain', 'rbcar_type', 'rbcar_tags',
                 'rbcar_energy', 'rbcar_power', 'rbcar_might', 'rbcar_ability',
                 'rbcar_rarity', 'rbcar_artist', 'image_url', 'image')
STATUSES = ('pending', 'approved', 'rejected', 'obsolete')

_PENDING = "rbchg_status = 'pending'"


class RbCardChange(db.Model):
    """One proposed (or decided) field change for one card. Names match 0011."""
    __tablename__ = 'rbcardchanges'
    __table_args__ = (
        db.PrimaryKeyConstraint('rbchg_id', name='rbcardchanges_pkey'),
        db.ForeignKeyConstraint(
            ['rbchg_rbset_id', 'rbchg_rbcar_id'],
            ['riftbound.rbcards.rbcar_rbset_id', 'riftbound.rbcards.rbcar_id'],
            name='rbcardchanges_card_fk', onupdate='CASCADE', ondelete='CASCADE'),
        db.CheckConstraint(sql_in('rbchg_field', SYNCED_FIELDS),
                           name='rbcardchanges_field_chk'),
        db.CheckConstraint(sql_in('rbchg_status', STATUSES),
                           name='rbcardchanges_status_chk'),
        db.ForeignKeyConstraint(
            ['rbchg_job_id'], ['riftbound.rbjobs.rbjob_id'],
            name='rbcardchanges_job_fk', ondelete='SET NULL'),
        db.ForeignKeyConstraint(
            ['rbchg_decided_by'], ['riftbound.rbusers.id'],
            name='rbcardchanges_decided_by_fk', ondelete='SET NULL'),
        db.Index('uq_rbcardchanges_pending',
                 'rbchg_rbset_id', 'rbchg_rbcar_id', 'rbchg_field', unique=True,
                 postgresql_where=db.text(_PENDING), sqlite_where=db.text(_PENDING)),
        db.Index('idx_rbcardchanges_target',
                 'rbchg_rbset_id', 'rbchg_rbcar_id'),
        {"schema": "riftbound", "comment": 'Proposed card changes from the Riot sync (F13)'},
    )

    rbchg_id = db.Column(db.BigInteger().with_variant(db.Integer, 'sqlite'),
                         primary_key=True, autoincrement=True, comment='Change row id')
    rbchg_rbset_id = db.Column(db.Text, nullable=False, comment='Set id of the card')
    rbchg_rbcar_id = db.Column(db.Text, nullable=False, comment='Card id within the set')
    rbchg_field = db.Column(db.String(32), nullable=False,
                            comment='Synced field that differs (S5 list)')
    rbchg_old_value = db.Column(db.Text, nullable=True,
                                comment='Stored value as text, NULL as NULL')
    rbchg_new_value = db.Column(db.Text, nullable=True,
                                comment='Gallery value as text, NULL as NULL')
    rbchg_status = db.Column(db.String(10), nullable=False, default='pending',
                             comment="pending, approved or rejected")
    rbchg_job_id = db.Column(db.BigInteger, nullable=True,
                             comment='Sync job that proposed it; NULL when cleared')
    rbchg_detected_at = db.Column(db.DateTime, nullable=False,
                                  default=lambda: clock.utcnow(),
                                  server_default=db.func.now(),
                                  comment='When the difference was seen (UTC)')
    rbchg_decided_at = db.Column(db.DateTime, nullable=True,
                                 comment='When it was approved or rejected (UTC)')
    rbchg_decided_by = db.Column(db.Integer, nullable=True,
                                 comment='Admin who decided; NULL when undecided')

    def __repr__(self):
        return (f'<RbCardChange {self.rbchg_rbset_id}-{self.rbchg_rbcar_id} '
                f'{self.rbchg_field} {self.rbchg_status}>')
