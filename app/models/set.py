from app import db

class RbSet(db.Model):
    __tablename__ = 'rbset'
    __table_args__ = {"schema": "riftbound", "comment": 'Tabla de expansiones'}
    
    rbset_id = db.Column(db.Text, primary_key=True, comment='ID de la expansión')
    rbset_name = db.Column(db.Text, nullable=False, comment='Nombre expansión')
    rbset_ncard = db.Column(db.SmallInteger, comment='Número de cartas que contiene la expansión')
    rbset_outdat = db.Column(db.Date, comment='Fecha de lanzamiento de la expansión')
