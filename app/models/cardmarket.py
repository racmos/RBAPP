from app import db
from datetime import datetime


class RbcmProduct(db.Model):
    """Raw Cardmarket product data per date."""
    __tablename__ = 'rbcm_products'
    __table_args__ = {"schema": "riftbound"}

    rbprd_date = db.Column(db.Text, primary_key=True)           # YYYYMMDD
    rbprd_id_product = db.Column(db.Integer, primary_key=True)  # idProduct from Cardmarket
    rbprd_name = db.Column(db.Text, nullable=False)
    rbprd_id_category = db.Column(db.Integer)
    rbprd_category_name = db.Column(db.Text)
    rbprd_id_expansion = db.Column(db.Integer)
    rbprd_id_metacard = db.Column(db.Integer)
    rbprd_date_added = db.Column(db.Text)                        # from JSON
    rbprd_type = db.Column(db.Text, nullable=False)              # 'single' | 'nonsingle'


class RbcmPrice(db.Model):
    """Daily price snapshots from Cardmarket."""
    __tablename__ = 'rbcm_price'
    __table_args__ = {"schema": "riftbound"}

    rbprc_date = db.Column(db.Text, primary_key=True)            # YYYYMMDD
    rbprc_id_product = db.Column(db.Integer, primary_key=True)
    rbprc_id_category = db.Column(db.Integer)
    rbprc_avg = db.Column(db.Numeric)
    rbprc_low = db.Column(db.Numeric)
    rbprc_trend = db.Column(db.Numeric)
    rbprc_avg1 = db.Column(db.Numeric)
    rbprc_avg7 = db.Column(db.Numeric)
    rbprc_avg30 = db.Column(db.Numeric)
    rbprc_avg_foil = db.Column(db.Numeric)
    rbprc_low_foil = db.Column(db.Numeric)
    rbprc_trend_foil = db.Column(db.Numeric)
    rbprc_avg1_foil = db.Column(db.Numeric)
    rbprc_avg7_foil = db.Column(db.Numeric)
    rbprc_avg30_foil = db.Column(db.Numeric)
    rbprc_low_ex = db.Column(db.Numeric)                         # low ex+ price tier


class RbcmCategory(db.Model):
    """Category lookup table."""
    __tablename__ = 'rbcm_categories'
    __table_args__ = {"schema": "riftbound"}

    rbcat_id = db.Column(db.Integer, primary_key=True)
    rbcat_name = db.Column(db.Text, nullable=False)


class RbcmExpansion(db.Model):
    """Expansion lookup table."""
    __tablename__ = 'rbcm_expansions'
    __table_args__ = {"schema": "riftbound"}

    rbexp_id = db.Column(db.Integer, primary_key=True)
    rbexp_name = db.Column(db.Text)


class RbcmLoadHistory(db.Model):
    """Tracks each load operation for date validation and change detection."""
    __tablename__ = 'rbcm_load_history'
    __table_args__ = {"schema": "riftbound"}

    rblh_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    rblh_date = db.Column(db.Text, nullable=False)               # YYYYMMDD
    rblh_file_type = db.Column(db.Text, nullable=False)          # 'singles' | 'nonsingles' | 'price_guide'
    rblh_hash = db.Column(db.Text, nullable=False)               # SHA-256
    rblh_rows = db.Column(db.Integer)
    rblh_status = db.Column(db.Text, default='success')          # success | error | skipped
    rblh_message = db.Column(db.Text)
    rblh_loaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class RbcmProductCardMap(db.Model):
    """Maps Cardmarket idProduct to internal rbcards."""
    __tablename__ = 'rbcm_product_card_map'
    __table_args__ = {"schema": "riftbound"}

    rbpcm_id_product = db.Column(db.Integer, primary_key=True)
    rbpcm_rbset_id = db.Column(db.Text, nullable=False)
    rbpcm_rbcar_id = db.Column(db.Text, nullable=False)
    rbpcm_match_type = db.Column(db.Text, default='manual')      # auto | manual
    rbpcm_confidence = db.Column(db.Numeric)


class RbProducts(db.Model):
    """Curated product master table (future use)."""
    __tablename__ = 'rbproducts'
    __table_args__ = {"schema": "riftbound"}

    rbpdt_id_set = db.Column(db.Text, primary_key=True)
    rbpdt_id_product = db.Column(db.Integer, primary_key=True)
    rbpdt_name = db.Column(db.Text, nullable=False)
    rbpdt_description = db.Column(db.Text)
    rbpdt_type = db.Column(db.Text)                               # single | nonsingle
    rbpdt_image_url = db.Column(db.Text)
    rbpdt_image = db.Column(db.Text)
