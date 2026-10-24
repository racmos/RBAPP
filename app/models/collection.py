from app import db
from app.utils import clock


class RbCollection(db.Model):
    __tablename__ = 'rbcollection'
    # Constraint / index names match the dev database (MIG-6, D6).
    __table_args__ = (
        db.ForeignKeyConstraint(
            ['rbcol_rbset_id', 'rbcol_rbcar_id'],
            ['riftbound.rbcards.rbcar_rbset_id', 'riftbound.rbcards.rbcar_id'],
            name='rbcollection_rbcar_fk_1', onupdate='CASCADE', ondelete='CASCADE'),
        db.ForeignKeyConstraint(
            ['rbcol_user'], ['riftbound.rbusers.username'],
            name='rbcollection_user_fk_1', onupdate='CASCADE', ondelete='RESTRICT'),
        db.CheckConstraint("rbcol_selling IN ('Y', 'N', 'S')", name='rbcollection_selling_chk'),
        db.CheckConstraint('rbcol_playset IS NULL OR rbcol_playset IN (1, 2, 3)',
                           name='rbcollection_playset_chk'),
        db.CheckConstraint('rbcol_quantity >= 1', name='rbcollection_quantity_chk'),
        db.Index('idx_rbcollection_selling', 'rbcol_user', 'rbcol_selling'),
        db.Index('idx_rbcollection_user_card_foil',
                 'rbcol_user', 'rbcol_rbset_id', 'rbcol_rbcar_id', 'rbcol_foil'),
        {"schema": "riftbound", "comment": 'Tabla de cartas en posesión'},
    )

    # PK sintética. Permite múltiples filas para la misma (set, card, foil, user)
    # que difieran en condición / idioma / precio de venta.
    # BIGINT en PostgreSQL (como en la BD); INTEGER en SQLite, donde solo un
    # INTEGER PRIMARY KEY es alias del rowid y se autoincrementa (tests).
    rbcol_id = db.Column(db.BigInteger().with_variant(db.Integer, 'sqlite'),
                         primary_key=True, autoincrement=True,
                         comment='PK sintética. Permite varias filas con la misma (set, card, foil, user) '
                                 'que difieran en condición, idioma o precio de venta.')
    rbcol_rbset_id = db.Column(db.Text, nullable=False, comment='ID de la expansión')
    rbcol_rbcar_id = db.Column(db.Text, nullable=False, comment='ID de la carta')
    rbcol_foil = db.Column(db.Text, nullable=False, default='N', comment='Si es foil, S o N')
    rbcol_user = db.Column(db.String(64), nullable=False, comment='Usuario de la colección')
    # Entero NOT NULL (QTY-1): el rango 1..9999 lo valida la app y el CHECK >= 1.
    rbcol_quantity = db.Column(db.Integer, nullable=False, comment='Cantidad de cartas')
    rbcol_selling = db.Column(db.Text, default='N', comment='Indica si la carta está a la venta (Y/N)')
    rbcol_playset = db.Column(db.Integer, nullable=True, comment='Nº de copias reservadas para playset (1, 2 o 3)')
    rbcol_sell_price = db.Column(db.Numeric, nullable=True, comment='Precio de venta unitario sobre el sobrante (quantity - playset)')
    rbcol_condition = db.Column(db.String(8), nullable=True, comment='Estado de conservación (MT, NM, EX, GD, LP, PL, PO)')
    rbcol_language = db.Column(db.String(40), nullable=True, comment='Idioma de la carta (English, Chinese, Spanish, ...)')
    rbcol_chadat = db.Column(db.DateTime, nullable=False, default=lambda: clock.utcnow(), comment='Fecha del último cambio')
