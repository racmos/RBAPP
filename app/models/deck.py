from app import db
from datetime import datetime


class RbDeck(db.Model):
    __tablename__ = 'rbdecks'
    __table_args__ = (
        db.UniqueConstraint('rbdck_user', 'rbdck_name', 'rbdck_seq', name='uq_deck_user_name_seq'),
        {"schema": "riftbound"}
    )
    
    # Primary key autoincremental
    id = db.Column(db.Integer, primary_key=True)
    
    # Identificación del deck
    rbdck_user = db.Column(db.Text, nullable=False, index=True)
    rbdck_name = db.Column(db.Text, nullable=False, index=True)
    
    # Secuencial: permite múltiples decks con el mismo nombre por usuario
    rbdck_seq = db.Column(db.SmallInteger, default=1)
    
    # Snapshot con fecha/hora completa
    rbdck_snapshot = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Metadatos del deck
    rbdck_decription = db.Column(db.Text)
    rbdck_mode = db.Column(db.Text, nullable=False, default='1v1')
    rbdck_format = db.Column(db.Text, nullable=False, default='Standard')
    rbdck_max_set = db.Column(db.Text)
    rbdck_ncards = db.Column(db.Integer, default=0)
    rbdck_orden = db.Column(db.Numeric)
    
    # Cartas en formato JSON
    rbdck_cards = db.Column(db.JSON)
    
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
        """Alias para rbdck_decription (compatibilidad)."""
        return self.rbdck_decription
    
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