from app import db

class RbSet(db.Model):
    __tablename__ = 'rbset'
    __table_args__ = {"schema": "riftbound"}
    
    rbset_id = db.Column(db.Text, primary_key=True)
    rbset_name = db.Column(db.Text, nullable=False)
    rbset_ncard = db.Column(db.SmallInteger)
    rbset_outdat = db.Column(db.Date)
