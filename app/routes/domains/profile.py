"""
Profile routes module with Pydantic validation.
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app import db
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
    
    if data.email is not None:
        current_user.email = data.email
    
    if data.password is not None:
        current_user.set_password(data.password)
    
    db.session.commit()
    return jsonify({'success': True})
