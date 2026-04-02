from app import db
from datetime import datetime

class RbCardMarket(db.Model):
    __tablename__ = 'rbcardmarket'
    __table_args__ = {"schema": "riftbound"}
    
    rbcmk_snapshot = db.Column(db.DateTime, primary_key=True, default=datetime.utcnow)
    rbcmk_rbset_id = db.Column(db.Text, primary_key=True)
    rbcmk_rbcar_id = db.Column(db.Text, primary_key=True)
    rbcmk_foil = db.Column(db.Text, primary_key=True, default='N')
    rbcmk_name = db.Column(db.Text, nullable=False)
    rbcmk_price = db.Column(db.Numeric, nullable=False)
