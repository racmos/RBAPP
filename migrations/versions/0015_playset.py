"""playset: per-user playset size and "keep a playset" marks per card name

Spec S3 of F3-a (docs/requirements/F3/F3-a-collection-data.md).

`rbuserprefs.rbprf_playset_size` (SMALLINT, NULL = 3, between 1 and 9) and the
table `rbkeepplayset`, one row per user and normalized card name. The table is
seeded (D-F3-12) from the collection rows that have `rbcol_playset` set: one
row per user and `name_key(card name)`, duplicates collapsed. `rbcol_playset`
itself is not touched (deprecated, dropped in F11).

Data loss on downgrade: the column and the table are dropped, so every playset
size and every "keep a playset" mark is lost.

`name_key` below is a frozen copy of `app.services.bans.name_key` (migrations
never import app code); a test keeps both equal.

Revision ID: 0015_playset
Revises: 0014_collection_selling
Create Date: 2026-10-28

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0015_playset'
down_revision = '0014_collection_selling'
branch_labels = None
depends_on = None

SCHEMA = 'riftbound'


def name_key(name: str) -> str:
    """Frozen copy of `app.services.bans.name_key` (2026-10-28)."""
    return ' '.join(name.replace('’', "'").replace('‘', "'").casefold().split())


def upgrade():
    with op.batch_alter_table('rbuserprefs', schema=SCHEMA) as batch:
        batch.add_column(sa.Column(
            'rbprf_playset_size', sa.SmallInteger(), nullable=True,
            comment='Copies that make a playset; NULL = 3'))
        batch.create_check_constraint(
            'rbuserprefs_playset_size_chk', 'rbprf_playset_size BETWEEN 1 AND 9')

    keep = op.create_table(
        'rbkeepplayset',
        sa.Column('rbkps_user_id', sa.Integer(), nullable=False, comment='User id'),
        sa.Column('rbkps_name_key', sa.String(length=200), nullable=False,
                  comment='Normalized card name (name_key)'),
        sa.Column('rbkps_created_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.now(), comment='When the mark was created (UTC)'),
        sa.PrimaryKeyConstraint('rbkps_user_id', 'rbkps_name_key', name='rbkeepplayset_pkey'),
        sa.ForeignKeyConstraint(['rbkps_user_id'], [f'{SCHEMA}.rbusers.id'],
                                name='rbkeepplayset_user_fk', ondelete='CASCADE'),
        schema=SCHEMA,
        comment='Card names a user keeps a playset of (F3).',
    )
    found = op.get_bind().execute(sa.text(
        f'SELECT DISTINCT u.id, c.rbcar_name FROM {SCHEMA}.rbcollection col '
        f'JOIN {SCHEMA}.rbusers u ON u.username = col.rbcol_user '
        f'JOIN {SCHEMA}.rbcards c ON c.rbcar_rbset_id = col.rbcol_rbset_id '
        'AND c.rbcar_id = col.rbcol_rbcar_id WHERE col.rbcol_playset IS NOT NULL')).fetchall()
    pairs = sorted({(user_id, name_key(name)) for user_id, name in found})
    if pairs:
        op.bulk_insert(keep, [{'rbkps_user_id': user_id, 'rbkps_name_key': key}
                              for user_id, key in pairs])


def downgrade():
    op.drop_table('rbkeepplayset', schema=SCHEMA)
    with op.batch_alter_table('rbuserprefs', schema=SCHEMA) as batch:
        batch.drop_constraint('rbuserprefs_playset_size_chk', type_='check')
        batch.drop_column('rbprf_playset_size')
