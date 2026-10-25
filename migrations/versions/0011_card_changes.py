"""Riot sync change proposals: rbcardchanges

Spec S8 of F13-c (docs/requirements/F13/F13-c-riot-sync-engine.md).

`riftbound.rbcardchanges` holds one row per differing synced field found in a
`monthly` (or `none`) window run: the stored value, the gallery value and the
status. The admin approves or rejects it (F13-g); auto-applied changes never
land here. The FK to the card cascades on update and delete; the unique index
allows a single `pending` row per card and field (a decided row may exist next
to a new pending one).

No data loss on upgrade (a new table only). The downgrade drops the table:
downgrade loses every proposal, including decided ones.

Revision ID: 0011_card_changes
Revises: 0010_admin_audit
Create Date: 2026-10-26

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0011_card_changes'
down_revision = '0010_admin_audit'
branch_labels = None
depends_on = None

SCHEMA = 'riftbound'
FIELDS = ('rbcar_name', 'rbcar_domain', 'rbcar_type', 'rbcar_tags',
          'rbcar_energy', 'rbcar_power', 'rbcar_might', 'rbcar_ability',
          'rbcar_rarity', 'rbcar_artist', 'image_url', 'image')
STATUSES = ('pending', 'approved', 'rejected')
PENDING = "rbchg_status = 'pending'"


def _check(column, values):
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade():
    op.create_table(
        'rbcardchanges',
        sa.Column('rbchg_id', sa.BigInteger().with_variant(sa.Integer(), 'sqlite'),
                  autoincrement=True, nullable=False, comment='Change row id'),
        sa.Column('rbchg_rbset_id', sa.Text(), nullable=False,
                  comment='Set id of the card'),
        sa.Column('rbchg_rbcar_id', sa.Text(), nullable=False,
                  comment='Card id within the set'),
        sa.Column('rbchg_field', sa.String(length=32), nullable=False,
                  comment='Synced field that differs (S5 list)'),
        sa.Column('rbchg_old_value', sa.Text(), nullable=True,
                  comment='Stored value as text, NULL as NULL'),
        sa.Column('rbchg_new_value', sa.Text(), nullable=True,
                  comment='Gallery value as text, NULL as NULL'),
        sa.Column('rbchg_status', sa.String(length=10), nullable=False,
                  server_default='pending',
                  comment='pending, approved or rejected'),
        sa.Column('rbchg_job_id', sa.BigInteger(), nullable=True,
                  comment='Sync job that proposed it; NULL when cleared'),
        sa.Column('rbchg_detected_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.now(),
                  comment='When the difference was seen (UTC)'),
        sa.Column('rbchg_decided_at', sa.DateTime(), nullable=True,
                  comment='When it was approved or rejected (UTC)'),
        sa.Column('rbchg_decided_by', sa.Integer(), nullable=True,
                  comment='Admin who decided; NULL when undecided'),
        sa.PrimaryKeyConstraint('rbchg_id', name='rbcardchanges_pkey'),
        sa.ForeignKeyConstraint(['rbchg_rbset_id', 'rbchg_rbcar_id'],
                                [f'{SCHEMA}.rbcards.rbcar_rbset_id',
                                 f'{SCHEMA}.rbcards.rbcar_id'],
                                name='rbcardchanges_card_fk',
                                onupdate='CASCADE', ondelete='CASCADE'),
        sa.CheckConstraint(_check('rbchg_field', FIELDS),
                           name='rbcardchanges_field_chk'),
        sa.CheckConstraint(_check('rbchg_status', STATUSES),
                           name='rbcardchanges_status_chk'),
        sa.ForeignKeyConstraint(['rbchg_job_id'], [f'{SCHEMA}.rbjobs.rbjob_id'],
                                name='rbcardchanges_job_fk', ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['rbchg_decided_by'], [f'{SCHEMA}.rbusers.id'],
                                name='rbcardchanges_decided_by_fk',
                                ondelete='SET NULL'),
        schema=SCHEMA,
        comment='Proposed card changes from the Riot sync (F13)',
    )
    op.create_index('uq_rbcardchanges_pending', 'rbcardchanges',
                    ['rbchg_rbset_id', 'rbchg_rbcar_id', 'rbchg_field'],
                    unique=True, schema=SCHEMA,
                    postgresql_where=sa.text(PENDING), sqlite_where=sa.text(PENDING))
    op.create_index('idx_rbcardchanges_target', 'rbcardchanges',
                    ['rbchg_rbset_id', 'rbchg_rbcar_id'], schema=SCHEMA)


def downgrade():
    op.drop_index('idx_rbcardchanges_target', table_name='rbcardchanges', schema=SCHEMA)
    op.drop_index('uq_rbcardchanges_pending', table_name='rbcardchanges', schema=SCHEMA)
    op.drop_table('rbcardchanges', schema=SCHEMA)
