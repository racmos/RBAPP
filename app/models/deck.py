from app import db
from app.utils import clock
from sqlalchemy.dialects.postgresql import JSONB


class RbDeck(db.Model):
    __tablename__ = 'rbdecks'
    # Constraint names match the dev database (MIG-6, D6). The owner FK targets
    # rbusers.username (0002 repointed it away from the legacy old1_rbusers).
    __table_args__ = (
        db.UniqueConstraint('rbdck_user', 'rbdck_name', 'rbdck_seq',
                            name='rbdecks_rbdck_user_rbdck_name_rbdck_seq_key'),
        db.ForeignKeyConstraint(
            ['rbdck_user'], ['riftbound.rbusers.username'],
            name='fk_deck_user', onupdate='CASCADE', ondelete='RESTRICT'),
        {"schema": "riftbound"}
    )
    
    # Primary key autoincremental
    id = db.Column(db.Integer, primary_key=True)
    
    # Identificación del deck
    rbdck_user = db.Column(db.String(80), nullable=False)
    rbdck_name = db.Column(db.String(200), nullable=False)
    
    # Secuencial: permite múltiples decks con el mismo nombre por usuario
    rbdck_seq = db.Column(db.Integer, default=1)
    
    # Snapshot con fecha/hora completa
    rbdck_snapshot = db.Column(db.DateTime, nullable=False, default=lambda: clock.utcnow())
    
    # Metadatos del deck
    rbdck_description = db.Column(db.Text)
    rbdck_mode = db.Column(db.String(50), default='1v1', server_default='1v1')
    rbdck_format = db.Column(db.String(50), default='Standard', server_default='Standard')
    rbdck_max_set = db.Column(db.String(100))
    rbdck_ncards = db.Column(db.Integer, default=0)
    rbdck_orden = db.Column(db.Numeric)
    
    # Cartas en formato JSON
    # JSONB en PostgreSQL (como en la BD); JSON en SQLite (tests).
    rbdck_cards = db.Column(db.JSON().with_variant(JSONB(), 'postgresql'))
