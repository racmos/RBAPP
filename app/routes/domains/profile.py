"""
Profile routes module with Pydantic validation.
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from app import db
from app.models import User
from app.schemas.validators import ProfileUpdate
from app.schemas.validation import validate_json

profile_bp = Blueprint('profile', __name__, url_prefix='/riftbound/profile')


@profile_bp.route('')
@login_required
def profile():
    """User profile page."""
    return render_template('profile.html', user=current_user)


@profile_bp.route('/update', methods=['POST'])
@login_required
@validate_json(ProfileUpdate)
def update_profile():
    """Update user profile."""
    data = request.validated_data

    # A new password needs the current one (PROF-2); the schema already made
    # sure it was sent.
    if data.password is not None and not current_user.check_password(data.current_password):
        return jsonify({
            'success': False,
            'error': 'Bad Request',
            'message': 'The current password is incorrect',
        }), 400

    if data.email is not None:
        # Case-insensitive, other accounts only (the schema already trimmed it).
        taken = User.query.filter(
            func.lower(User.email) == data.email.lower(),
            User.id != current_user.id,
        ).first()
        if taken:
            return _email_conflict()
        current_user.email = data.email

    if data.password is not None:
        current_user.set_password(data.password)

    try:
        db.session.commit()
    except IntegrityError:
        # Lost a race against another account taking the address (PROF-1).
        db.session.rollback()
        return _email_conflict()
    return jsonify({'success': True})


def _email_conflict():
    """409 for an email address another account already uses."""
    db.session.rollback()
    return jsonify({
        'success': False,
        'error': 'Conflict',
        'message': 'That email address is already in use',
    }), 409
