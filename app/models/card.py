from app import db


def _image_folder(image_filename):
    """Extract the set folder from the image filename.

    Image filenames follow the pattern {set_prefix}_{card_id}.png
    where set_prefix is the actual folder name (e.g. 'ogn' for 'ogn_1.png').
    This handles promo sets like OGNX (image=ogn_257.png -> folder=ogn)
    and PROK (image=ogn_265.png -> folder=ogn) correctly.
    """
    if not image_filename:
        return ''
    parts = image_filename.rsplit('_', 1)
    return parts[0].lower() if len(parts) == 2 else ''


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

    @property
    def image_src(self):
        """Full image URL path derived from the image filename.

        Uses the set_prefix embedded in the filename (e.g. ogn_257.png -> ogn/)
        instead of rbcar_rbset_id (which would give ognx/ or prok/ for promo sets).
        """
        if not self.image:
            return None
        folder = _image_folder(self.image)
        return f"/riftbound/static/images/cards/{folder}/{self.image}"
