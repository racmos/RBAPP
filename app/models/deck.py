from app import db
from datetime import datetime

class RbDeck(db.Model):
    __tablename__ = 'rbdecks'
    __table_args__ = {"schema": "riftbound"}
    
    rbdck_snapshot = db.Column(db.DateTime, primary_key=True, default=datetime.utcnow)
    rbdck_rbset_id = db.Column(db.Text, primary_key=True)
    rbdck_rbcar_id = db.Column(db.Text, primary_key=True)
    rbdck_sideboard = db.Column(db.Text, primary_key=True, default='N')
    rbdck_user = db.Column(db.Text, primary_key=True, nullable=False)
    rbdck_name = db.Column(db.Text, nullable=False)
    rbdck_decription = db.Column(db.Text)
    rbdck_mode = db.Column(db.Text, nullable=False, default='1v1')
    rbdck_format = db.Column(db.Text, nullable=False, default='Standard')
    rbdck_max_set = db.Column(db.Text, nullable=False)
    rbdck_ncards = db.Column(db.Numeric, nullable=False, default=1)
    rbdck_orden = db.Column(db.Numeric)
