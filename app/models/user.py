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
    # Optional (F9-b, D-F9-1): NULL = no e-mail. Unique when present; the services compare
    # it ignoring case.
    email = db.Column(db.String(120), nullable=True)
    # NULL = no password (an OAuth-only account, F9-f): password login is refused (F9-b S2).
    password_hash = db.Column(db.String(256), nullable=True)
    # Last password change (F9-b S3); NULL = unknown (accounts older than 0030, no backfill).
    password_changed_at = db.Column(db.DateTime, nullable=True)
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

    # The session this object was loaded or signed in through (F9-a), set by
    # app.services.sessions; plain attributes, never stored on rbusers.
    session_token = None
    session_id = None

    def get_id(self):
        """What Flask-Login keeps in the session and remember cookies: `s:<token>` of the
        server-side session (F9-a S2). None without a session: never logged in by id."""
        return f's:{self.session_token}' if self.session_token else None

    @property
    def is_active(self):
        """Flask-Login reads this: a blocked user can't log in and loses the
        session on the next request (UserMixin.is_authenticated follows it)."""
        return not self.is_blocked

    @property
    def has_password(self) -> bool:
        """False for an account without a password (OAuth-only, F9-b S2)."""
        return self.password_hash is not None

    def set_password(self, password):
        """Store a new password hash and stamp `password_changed_at` (F9-b S3)."""
        self.password_hash = generate_password_hash(password)
        self.password_changed_at = clock.utcnow()

    def check_password(self, password):
        """False when the account has no password (never raises on a NULL hash)."""
        if self.password_hash is None:
            return False
        return check_password_hash(self.password_hash, password)
