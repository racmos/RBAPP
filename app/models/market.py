from app import db
from app.utils import clock

class RbCardMarket(db.Model):
    __tablename__ = 'rbcardmarket'
    __table_args__ = (
        db.ForeignKeyConstraint(
            ['rbcmk_rbset_id', 'rbcmk_rbcar_id'],
            ['riftbound.rbcards.rbcar_rbset_id', 'riftbound.rbcards.rbcar_id'],
            name='rbcmk_rbcar_fk_1', onupdate='CASCADE', ondelete='CASCADE'),
        {"schema": "riftbound", "comment": 'Tabla de precios de Cardmarket'},
    )
    
    rbcmk_snapshot = db.Column(db.DateTime, primary_key=True, default=lambda: clock.utcnow(), comment='Fecha de la foto de los precios extraídos')
    rbcmk_rbset_id = db.Column(db.Text, primary_key=True, comment='ID de la expansión')
    rbcmk_rbcar_id = db.Column(db.Text, primary_key=True, comment='ID de la carta')
    rbcmk_foil = db.Column(db.Text, primary_key=True, default='N', comment='Si es foil, S o N')
    rbcmk_name = db.Column(db.Text, nullable=False, comment='Nombre de la carta')
    rbcmk_price = db.Column(db.Numeric, nullable=False, comment='Precio de la carta')
