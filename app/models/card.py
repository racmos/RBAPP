import re

from app import db

_SAFE_FOLDER = re.compile(r'[a-z0-9]+')


def card_image_folder(image_filename, set_id=None):
    """The folder under images/cards/ where a card image lives (IMG-1, D13).

    Image filenames follow the pattern {set_prefix}_{card_id}.png
    where set_prefix is the actual folder name (e.g. 'ogn' for 'ogn_1.png').
    This handles promo sets like OGNX (image=ogn_257.png -> folder=ogn)
    and PROK (image=ogn_265.png -> folder=ogn) correctly.

    A name without a prefix falls back to `set_id.lower()`. The result must be
    letters and digits only (no separators, no dots), otherwise it is '': that
    is what keeps both reads and writes inside the cards folder.
    """
    folder = ''
    if image_filename:
        prefix, separator, _card = image_filename.rpartition('_')
        if separator:
            folder = prefix.lower()
    if not folder:
        folder = (set_id or '').lower()
    return folder if is_safe_folder(folder) else ''


def is_safe_folder(folder) -> bool:
    """True when `folder` is a card images folder name: lowercase letters and digits only."""
    return isinstance(folder, str) and _SAFE_FOLDER.fullmatch(folder) is not None


# Name used by the IMG-1 characterization tests; same rule, set id optional.
_image_folder = card_image_folder


class RbCard(db.Model):
    __tablename__ = 'rbcards'
    __table_args__ = (
        db.ForeignKeyConstraint(
            ['rbcar_rbset_id'], ['riftbound.rbset.rbset_id'],
            name='rbcards_rbset_fk_1', onupdate='CASCADE', ondelete='CASCADE'),
        {"schema": "riftbound", "comment": 'Tabla de cartas'},
    )
    
    rbcar_rbset_id = db.Column(db.Text, primary_key=True, comment='ID de la expansión')
    rbcar_id = db.Column(db.Text, primary_key=True, comment='ID de la carta')
    rbcar_name = db.Column(db.Text, nullable=False, comment='Nombre de la carta')
    rbcar_domain = db.Column(db.Text, comment='Dominio o color: fury, calm, mind, body, chaos, order, colorless')
    rbcar_type = db.Column(db.Text, comment='Tipo de carta: Spell, Unit,...')
    rbcar_tags = db.Column(db.Text, comment='Región, nombre de único o temática (ej. Dragón)')
    rbcar_energy = db.Column(db.SmallInteger, comment='Coste de energía')
    rbcar_power = db.Column(db.SmallInteger, comment='Coste de poder')
    rbcar_might = db.Column(db.SmallInteger, comment='Fuerza / Defensa')
    rbcar_ability = db.Column(db.Text, comment='Habilidad en el cuadro de la carta')
    rbcar_rarity = db.Column(db.Text, comment='Rareza: Común, infrecuente,...')
    rbcar_artist = db.Column(db.Text, comment='Autor del dibujo de la carta')
    # Deprecated (F2): bans live in rbcardbans; removed in F11.
    rbcar_banned = db.Column(db.Text, default='N', comment='Si ha sido baneada para jugarse en competitivo, S o N')
    image_url = db.Column(db.Text, comment='Enlace a la imagen')
    image = db.Column(db.Text, comment='Nombre del archivo de la imagen')

    @property
    def image_src(self):
        """Image URL, /riftbound/media/cards/<folder>/<image> (IMG-1, M-d).

        Uses the set_prefix embedded in the filename (e.g. ogn_257.png -> ogn/)
        instead of rbcar_rbset_id (which would give ognx/ or prok/ for promo sets);
        a name without prefix falls back to the set id. None when there is no
        image or no safe folder.
        """
        from app.services.card_images import card_image_url
        return card_image_url(self.image, self.rbcar_rbset_id)
