from app import db

class RbCard(db.Model):
    __tablename__ = 'rbcards'
    __table_args__ = {"schema": "riftbound"}
    
    rbcar_rbset_id = db.Column(db.Text, primary_key=True)
    rbcar_id = db.Column(db.Text, primary_key=True)
    rbcar_name = db.Column(db.Text, nullable=False)
    rbcar_domain = db.Column(db.Text)
    rbcar_type = db.Column(db.Text)
    rbcar_tags = db.Column(db.Text)
    rbcar_energy = db.Column(db.SmallInteger)
    rbcar_power = db.Column(db.SmallInteger)
    rbcar_might = db.Column(db.SmallInteger)
    rbcar_ability = db.Column(db.Text)
    rbcar_rarity = db.Column(db.Text)
    rbcar_artist = db.Column(db.Text)
    rbcar_banned = db.Column(db.Text, default='N')
    image_url = db.Column(db.Text)
    image = db.Column(db.Text)
