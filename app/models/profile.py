from app import db
from app.utils import clock


class RbUserProfile(db.Model):
    """Private profile of one user (F9-b): 1:1 with `rbusers`.

    A row is created by the first successful `PATCH /me` (`app.services.profile`); reading
    never creates one, and a user without a row has every field empty. Field limits and the
    country codes live in `app/schemas/profile_domain.py`. The avatar columns are filled by
    F9-c. Names match migration 0030.
    """
    __tablename__ = 'rbuserprofile'
    __table_args__ = (
        db.PrimaryKeyConstraint('rbupf_user_id', name='rbuserprofile_pkey'),
        db.ForeignKeyConstraint(
            ['rbupf_user_id'], ['riftbound.rbusers.id'],
            name='rbuserprofile_user_fk', ondelete='CASCADE'),
        {"schema": "riftbound", "comment": 'Private profile of a user (F9).'},
    )

    rbupf_user_id = db.Column(db.Integer, nullable=False, comment='User id')
    rbupf_display_name = db.Column(db.String(40), nullable=True, comment='Display name')
    rbupf_bio = db.Column(db.String(240), nullable=True, comment='Short bio; line breaks allowed')
    rbupf_country = db.Column(db.CHAR(2), nullable=True,
                              comment='ISO 3166-1 alpha-2 country code, upper case')
    rbupf_city = db.Column(db.String(80), nullable=True, comment='City')
    rbupf_avatar_file = db.Column(db.String(64), nullable=True,
                                  comment='Avatar file name (F9-c); NULL = no avatar')
    rbupf_avatar_version = db.Column(db.Integer, nullable=False, default=0, server_default='0',
                                     comment='Bumped on every avatar change (F9-c)')
    rbupf_updated_at = db.Column(db.DateTime, nullable=False, default=lambda: clock.utcnow(),
                                 comment='Last profile change (UTC)')
