from app import db
from datetime import datetime

class RbCollection(db.Model):
    __tablename__ = 'rbcollection'
    __table_args__ = {"schema": "riftbound"}
    
    rbcol_rbset_id = db.Column(db.Text, primary_key=True)
    rbcol_rbcar_id = db.Column(db.Text, primary_key=True)
    rbcol_foil = db.Column(db.Text, primary_key=True, default='N')
    rbcol_quantity = db.Column(db.Text, nullable=False)
    rbcol_chadat = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    rbcol_user = db.Column(db.String(64))
