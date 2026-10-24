from app import db
from app.utils import clock
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

class User(UserMixin, db.Model):
    __tablename__ = 'rbusers'
    # Names match the dev database (MIG-6, D6): the UNIQUE constraints already
    # create their indexes, so the columns carry no extra `index=True`.
    __table_args__ = (
        db.UniqueConstraint('username', name='rbusers_username_key'),
        db.UniqueConstraint('email', name='rbusers_email_key'),
        {"schema": "riftbound"},
    )
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: clock.utcnow())
    # Roles / access (ACL-1, D10). Only the CLI (`flask users promote|block`)
    # changes them; no request input ever does.
    is_admin = db.Column(db.Boolean, nullable=False, default=False,
                         server_default=db.false())
    is_blocked = db.Column(db.Boolean, nullable=False, default=False,
                           server_default=db.false())
    # Login protection (LOGIN-1, R3). `failed_login_count` is also the lockout
    # level: services.auth derives the lock length from it. The temporary lock
    # (`locked_until`) is checked only when logging in, never on a live session.
    failed_login_count = db.Column(db.Integer, nullable=False, default=0,
                                   server_default='0')
    locked_until = db.Column(db.DateTime, nullable=True)
    last_login_at = db.Column(db.DateTime, nullable=True)

    @property
    def is_active(self):
        """Flask-Login reads this: a blocked user can't log in and loses the
        session on the next request (UserMixin.is_authenticated follows it)."""
        return not self.is_blocked

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
