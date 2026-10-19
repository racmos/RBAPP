from app import db
from app.schemas.prefs_domain import (ACCENTS, BG_INTENSITY_MAX, BG_INTENSITY_MIN,
                                      COLLECTION_VIEWS, DENSITIES, LANGS, sql_in)
from app.utils import clock


class RbUserPrefs(db.Model):
    """Interface preferences of one user (PREF-1, D6): 1:1 with `rbusers`.

    A row is created on the first write (`app.services.prefs`); a user without a
    row simply has every preference on Auto. Every preference is nullable and
    NULL means Auto. The domains are enforced by named CHECKs, built from the same
    tuples as the `PrefsUpdate` schema so both layers agree. The names match
    migration 0006.
    """
    __tablename__ = 'rbuserprefs'
    __table_args__ = (
        db.PrimaryKeyConstraint('rbprf_user_id', name='rbuserprefs_pkey'),
        db.ForeignKeyConstraint(
            ['rbprf_user_id'], ['riftbound.rbusers.id'],
            name='rbuserprefs_user_fk', ondelete='CASCADE'),
        db.CheckConstraint(sql_in('rbprf_lang', LANGS), name='rbuserprefs_lang_chk'),
        db.CheckConstraint(sql_in('rbprf_density', DENSITIES), name='rbuserprefs_density_chk'),
        db.CheckConstraint(sql_in('rbprf_accent', ACCENTS), name='rbuserprefs_accent_chk'),
        db.CheckConstraint(
            f'rbprf_bg_intensity BETWEEN {BG_INTENSITY_MIN} AND {BG_INTENSITY_MAX}',
            name='rbuserprefs_bg_intensity_chk'),
        db.CheckConstraint(sql_in('rbprf_collection_view', COLLECTION_VIEWS),
                           name='rbuserprefs_collection_view_chk'),
        {"schema": "riftbound"},
    )

    rbprf_user_id = db.Column(db.Integer, nullable=False)
    rbprf_lang = db.Column(db.String(2), nullable=True)
    rbprf_density = db.Column(db.String(10), nullable=True)
    rbprf_accent = db.Column(db.String(10), nullable=True)
    rbprf_bg_intensity = db.Column(db.SmallInteger, nullable=True)
    rbprf_collection_view = db.Column(db.String(10), nullable=True)
    rbprf_updated_at = db.Column(db.DateTime, nullable=False, default=lambda: clock.utcnow(),
                                 server_default=db.func.now())
