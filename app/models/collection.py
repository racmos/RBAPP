from app import db
from datetime import datetime


class RbCollection(db.Model):
    __tablename__ = 'rbcollection'
    __table_args__ = {"schema": "riftbound"}

    # PK sintética. Permite múltiples filas para la misma (set, card, foil, user)
    # que difieran en condición / idioma / precio de venta.
    # Nota: usamos Integer (no BigInteger) para compatibilidad con SQLite en tests.
    # En PostgreSQL el tipo INTEGER es suficiente para los IDs típicos.
    rbcol_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    rbcol_rbset_id = db.Column(db.Text, nullable=False)
    rbcol_rbcar_id = db.Column(db.Text, nullable=False)
    rbcol_foil = db.Column(db.Text, nullable=False, default='N')
    rbcol_user = db.Column(db.String(64), nullable=False)
    rbcol_quantity = db.Column(db.Text, nullable=False)
    rbcol_selling = db.Column(db.Text, default='N')
    rbcol_playset = db.Column(db.Integer, nullable=True)
    rbcol_sell_price = db.Column(db.Numeric, nullable=True)
    rbcol_condition = db.Column(db.String(8), nullable=True)
    rbcol_language = db.Column(db.String(40), nullable=True)
    rbcol_chadat = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
