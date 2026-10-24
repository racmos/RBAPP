from app import db
from app.schemas.game_domain import GAME_MODES
from app.schemas.prefs_domain import sql_in
from app.utils import clock

NAME_MAX_LENGTH = 200
REASON_MAX_LENGTH = 500


class RbCardBan(db.Model):
    """A card name banned in one game mode (F2-a, D-F2-2).

    A ban covers every printing of the name: rows are keyed by
    `app.services.bans.name_key`, not by card id. This table is the only source
    of bans; the legacy `rbcar_banned` flag is not read. The names match
    migration 0009.
    """
    __tablename__ = 'rbcardbans'
    __table_args__ = (
        db.PrimaryKeyConstraint('rbban_id', name='rbcardbans_pkey'),
        db.UniqueConstraint('rbban_name_key', 'rbban_mode', name='rbcardbans_name_mode_key'),
        db.CheckConstraint(sql_in('rbban_mode', GAME_MODES), name='rbcardbans_mode_chk'),
        {"schema": "riftbound", "comment": 'Bans by card name and game mode (F2).'},
    )

    rbban_id = db.Column(db.Integer, autoincrement=True, comment='Ban id')
    rbban_name_key = db.Column(db.String(NAME_MAX_LENGTH), nullable=False,
                               comment='Normalized card name (name_key)')
    rbban_name = db.Column(db.String(NAME_MAX_LENGTH), nullable=False,
                           comment='Card name as displayed')
    rbban_mode = db.Column(db.String(3), nullable=False, comment='Game mode: 1v1 or 2v2')
    rbban_since = db.Column(db.Date, nullable=False, comment='Date the ban applies from')
    rbban_reason = db.Column(db.String(REASON_MAX_LENGTH), nullable=True,
                             comment='Why the card is banned (free text)')
    rbban_created_at = db.Column(db.DateTime, nullable=False, default=lambda: clock.utcnow(),
                                 server_default=db.func.now(),
                                 comment='When the row was created (UTC)')
