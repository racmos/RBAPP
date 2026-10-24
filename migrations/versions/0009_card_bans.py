"""card bans: rbcardbans, seeded with the official ban list

Spec S4 of F2-a (docs/requirements/F2/F2-a-card-bans.md).

`riftbound.rbcardbans` holds one row per banned card name and game mode
(`1v1`, `2v2`); a ban covers every printing of the name. The upgrade creates
the table and inserts the official list (https://riftbound.gg/rules/banned-cards/,
read 2026-10-24) with the catalog spellings: 12 names in both modes and
`Wuju Bladesman` in 2v2 only, 25 rows. The legacy `rbcar_banned` flag is
never read nor modified (D-F2-2: the Riot scraper resets it).

No data loss on upgrade (a new table only). The downgrade drops the table:
downgrade loses every ban, including those added after the upgrade.

`name_key` below is a frozen copy of `app.services.bans.name_key` (migrations
never import app code); a test keeps both equal.

Revision ID: 0009_card_bans
Revises: 0008_jobs_daily_prices
Create Date: 2026-10-24

"""
from datetime import date

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0009_card_bans'
down_revision = '0008_jobs_daily_prices'
branch_labels = None
depends_on = None

SCHEMA = 'riftbound'
REASON = 'Official ban list (riftbound.gg, read 2026-10-24)'
READ_ON = date(2026, 10, 24)
# The site gives a start date only for the latest wave.
SINCE = {'Ekko, Recurrent': date(2026, 9, 18), 'Stacked Deck': date(2026, 9, 18)}
BOTH_MODES = (
    "Aspirant's Climb", 'Obelisk of Power', "Reaver's Row", "The Arena's Greatest",
    'The Dreaming Tree', 'Scrapheap', 'Called Shot', 'Fight or Flight', 'Stacked Deck',
    'Draven, Vanquisher', 'Ekko, Recurrent', 'Stealthy Pursuer',
)
ONLY_2V2 = ('Wuju Bladesman',)


def name_key(name: str) -> str:
    """Frozen copy of `app.services.bans.name_key` (2026-10-24)."""
    return ' '.join(name.replace('’', "'").replace('‘', "'").casefold().split())


def _seed():
    pairs = [(name, mode) for mode in ('1v1', '2v2') for name in BOTH_MODES]
    pairs += [(name, '2v2') for name in ONLY_2V2]
    return [{'rbban_name_key': name_key(name), 'rbban_name': name, 'rbban_mode': mode,
             'rbban_since': SINCE.get(name, READ_ON), 'rbban_reason': REASON}
            for name, mode in pairs]


def upgrade():
    bans = op.create_table(
        'rbcardbans',
        sa.Column('rbban_id', sa.Integer(), autoincrement=True, nullable=False,
                  comment='Ban id'),
        sa.Column('rbban_name_key', sa.String(length=200), nullable=False,
                  comment='Normalized card name (name_key)'),
        sa.Column('rbban_name', sa.String(length=200), nullable=False,
                  comment='Card name as displayed'),
        sa.Column('rbban_mode', sa.String(length=3), nullable=False,
                  comment='Game mode: 1v1 or 2v2'),
        sa.Column('rbban_since', sa.Date(), nullable=False,
                  comment='Date the ban applies from'),
        sa.Column('rbban_reason', sa.String(length=500), nullable=True,
                  comment='Why the card is banned (free text)'),
        sa.Column('rbban_created_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.now(), comment='When the row was created (UTC)'),
        sa.PrimaryKeyConstraint('rbban_id', name='rbcardbans_pkey'),
        sa.UniqueConstraint('rbban_name_key', 'rbban_mode', name='rbcardbans_name_mode_key'),
        sa.CheckConstraint("rbban_mode IN ('1v1', '2v2')", name='rbcardbans_mode_chk'),
        schema=SCHEMA,
        comment='Bans by card name and game mode (F2).',
    )
    op.bulk_insert(bans, _seed())


def downgrade():
    op.drop_table('rbcardbans', schema=SCHEMA)
