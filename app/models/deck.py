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
    
    # Métodos de clase para consultas comunes
    @classmethod
    def get_by_user_and_name(cls, user, name, seq=None):
        """Obtener deck por usuario, nombre y opcionalmente seq."""
        query = cls.query.filter_by(rbdck_user=user, rbdck_name=name)
        if seq:
            return query.filter_by(rbdck_seq=seq).first()
        return query.order_by(cls.rbdck_seq.desc()).first()
    
    @classmethod
    def get_versions(cls, user, name):
        """Obtener todas las versiones de un deck."""
        return cls.query.filter_by(
            rbdck_user=user, 
            rbdck_name=name
        ).order_by(cls.rbdck_seq.desc()).all()
    
    @classmethod
    def get_next_seq(cls, user, name):
        """Calcular el siguiente secuencial para un deck."""
        last_deck = cls.query.filter_by(
            rbdck_user=user, 
            rbdck_name=name
        ).order_by(cls.rbdck_seq.desc()).first()
        
        return (last_deck.rbdck_seq + 1) if last_deck and last_deck.rbdck_seq else 1
    
    # Propiedades para acceder a las cartas
    @property
    def cards_main(self):
        """Cartas del main deck."""
        if self.rbdck_cards:
            return self.rbdck_cards.get('main', [])
        return []
    
    @property
    def cards_sideboard(self):
        """Cartas del sideboard."""
        if self.rbdck_cards:
            return self.rbdck_cards.get('sideboard', [])
        return []
    
    @property
    def cards(self):
        """Todas las cartas (para compatibilidad con templates)."""
        main = self.cards_main
        sideboard = self.cards_sideboard
        return main + sideboard
    
    @property
    def name(self):
        """Alias para rbdck_name (compatibilidad)."""
        return self.rbdck_name
    
    @property
    def description(self):
        """Alias para rbdck_description (compatibilidad)."""
        return self.rbdck_description
    
    @property
    def mode(self):
        """Alias para rbdck_mode (compatibilidad)."""
        return self.rbdck_mode
    
    @property
    def format(self):
        """Alias para rbdck_format (compatibilidad)."""
        return self.rbdck_format
    
    @property
    def user(self):
        """Alias para rbdck_user (compatibilidad)."""
        return self.rbdck_user
    
    @property
    def snapshot(self):
        """Alias para rbdck_snapshot (compatibilidad)."""
        return self.rbdck_snapshot
    
    @property
    def max_set(self):
        """Alias para rbdck_max_set (compatibilidad)."""
        return self.rbdck_max_set