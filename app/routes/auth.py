from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response
from flask_login import login_user, logout_user, login_required, current_user
from pydantic import ValidationError

from app import limiter
from app.schemas.validators import LoginRequest, RegisterRequest
from app.services import auth as auth_service
from app.services.captcha import FORM_FIELD as CAPTCHA_FIELD, get_captcha_provider
from app.services.auth import AuthStatus, DuplicateUserError

auth_bp = Blueprint('auth', __name__, url_prefix='/riftbound')

# One text for a wrong password, an unknown user and a blocked account (ACL-2, R4).
INVALID_MESSAGE = 'Invalid username or password'
# Registration refused because the captcha payload is missing, wrong, expired or reused.
CAPTCHA_MESSAGE = 'Captcha verification failed. Please try again.'
# Shown with the 429 of a running lock (LOGIN-2); does not say which it is.
LOCKED_MESSAGE = 'Invalid credentials or account temporarily locked'


def _not_post():
    """Only form submissions use up the budget; opening the page is free."""
    return request.method != 'POST'


def _form_errors(error: ValidationError) -> list[str]:
    """One readable line per invalid field, from a Pydantic error."""
    lines = []
    for item in error.errors():
        field = '.'.join(str(part) for part in item['loc'])
        message = item['msg'].removeprefix('Value error, ')
        lines.append(f'{field}: {message}' if field else message)
    return lines


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.shared_limit('10/minute;50/hour', scope='login', exempt_when=_not_post)
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        try:
            credentials = LoginRequest(**request.form.to_dict())
        except ValidationError:
            flash(INVALID_MESSAGE, 'error')
            return redirect(url_for('auth.login'))

        result = auth_service.authenticate(credentials.username, credentials.password)

        if result.status is AuthStatus.OK:
            login_user(result.user)
            return redirect(url_for('main.dashboard'))

        if result.status is AuthStatus.LOCKED:
            flash(LOCKED_MESSAGE, 'error')
            response = make_response(render_template('login.html'), 429)
            response.headers['Retry-After'] = str(result.retry_after)
            return response

        # INVALID, and BLOCKED if it ever appears: indistinguishable (R4).
        flash(INVALID_MESSAGE, 'error')
        return redirect(url_for('auth.login'))

    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit('5/hour', exempt_when=_not_post)
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        try:
            data = RegisterRequest(**request.form.to_dict())
        except ValidationError as error:
            for line in _form_errors(error):
                flash(line, 'error')
            return redirect(url_for('auth.register'))

        # After the fields (so a typo does not burn the payload) and BEFORE the
        # duplicate check (so a bot cannot probe usernames without solving it).
        if not get_captcha_provider().verify(request.form.get(CAPTCHA_FIELD)):
            flash(CAPTCHA_MESSAGE, 'error')
            return redirect(url_for('auth.register'))

        try:
            auth_service.register_user(data)
        except DuplicateUserError as error:
            flash(error.message, 'error')
            return redirect(url_for('auth.register'))

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html', captcha_challenge=get_captcha_provider().challenge())


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
