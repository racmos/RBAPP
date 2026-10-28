"""import previews: rbimportpreviews

Spec S1 of F3-e (docs/requirements/F3/F3-e-collection-import-api.md).

`riftbound.rbimportpreviews` holds the parsed rows of an uploaded collection file for 30
minutes, between the preview and the commit. A new table only: no data loss on upgrade. The
downgrade drops the table and the previews waiting in it (they are short-lived).

Revision ID: 0018_import_previews
Revises: 0017_jobs_value_snapshot
Create Date: 2026-10-28

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = '0018_import_previews'
down_revision = '0017_jobs_value_snapshot'
branch_labels = None
depends_on = None

SCHEMA = 'riftbound'


def upgrade():
    op.create_table(
        'rbimportpreviews',
        sa.Column('rbimp_id', sa.String(length=36), nullable=False, comment='Preview id (UUID4)'),
        sa.Column('rbimp_user_id', sa.Integer(), nullable=False, comment='User id'),
        sa.Column('rbimp_format', sa.String(length=16), nullable=False,
                  comment='File format (rbapp)'),
        sa.Column('rbimp_rows', sa.JSON().with_variant(JSONB(), 'postgresql'), nullable=False,
                  comment='Parsed rows, as the commit needs them'),
        sa.Column('rbimp_created_at', sa.DateTime(), nullable=False,
                  comment='When the preview was made (UTC)'),
        sa.Column('rbimp_expires_at', sa.DateTime(), nullable=False,
                  comment='When the preview stops being valid (UTC)'),
        sa.PrimaryKeyConstraint('rbimp_id', name='rbimportpreviews_pkey'),
        sa.ForeignKeyConstraint(['rbimp_user_id'], [f'{SCHEMA}.rbusers.id'],
                                name='rbimportpreviews_user_fk', ondelete='CASCADE'),
        schema=SCHEMA,
        comment='Import previews waiting for a commit (F3).',
    )
    op.create_index('ix_rbimportpreviews_expires', 'rbimportpreviews', ['rbimp_expires_at'],
                    schema=SCHEMA)


def downgrade():
    op.drop_index('ix_rbimportpreviews_expires', table_name='rbimportpreviews', schema=SCHEMA)
    op.drop_table('rbimportpreviews', schema=SCHEMA)
