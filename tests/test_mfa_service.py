"""F9-d S4-S6 (AC2): `app.services.mfa`: the secret encrypted at rest, the TOTP check (window of
one step each side, replay protection through `last_step`) and the recovery codes (format,
normalisation, hashed storage, single use, regeneration)."""
import hashlib
import logging
import re
from datetime import datetime, timedelta

import pyotp
import pytest
import sqlalchemy as sa
from cryptography.fernet import Fernet

from app import db
from app.models import RbRecoveryCode, RbUserMfa
from app.services import mfa
from tests.conftest import TEST_TOTP_KEY

EPOCH = datetime(1970, 1, 1)
RECOVERY = re.compile(r'^[abcdefghjkmnpqrstuvwxyz23456789]{5}-[abcdefghjkmnpqrstuvwxyz23456789]{5}$')


def at_step(frozen_clock, step, seconds=0):
    """Move the frozen clock to `seconds` into TOTP step `step`."""
    frozen_clock.now = EPOCH + timedelta(seconds=step * 30 + seconds)


def code(secret, step):
    """The authenticator app's code of `step` (pyotp defaults: SHA-1, 6 digits, 30 s)."""
    return pyotp.TOTP(secret).generate_otp(step)


def row_of(user):
    db.session.expire_all()
    return db.session.get(RbUserMfa, user.id)


def codes_of(user):
    db.session.expire_all()
    return db.session.execute(sa.select(RbRecoveryCode).where(
        RbRecoveryCode.rbrco_user_id == user.id).order_by(RbRecoveryCode.rbrco_id)).scalars().all()


@pytest.fixture
def ana(app, make_user, frozen_clock):
    return make_user('ana')


@pytest.fixture
def secret(ana):
    """`ana` with a pending setup; returns the clear secret."""
    return mfa.setup(ana)['secret'].replace(' ', '')


def enable(user, secret_, frozen_clock, step=1000):
    """Turn 2FA on for `user` at `step` with the code of that step; returns the recovery codes."""
    at_step(frozen_clock, step)
    status, codes, _ = mfa.enable(user, code(secret_, step), keep_session_id=None)
    assert status is mfa.MfaStatus.OK
    return codes


# --- Availability and the secret at rest (S2, S4) --------------------------------------------

class TestSecret:
    def test_available_only_with_a_valid_key(self, app):
        assert mfa.available() is True
        app.config['TOTP_ENCRYPTION_KEY'] = None
        assert mfa.available() is False
        app.config['TOTP_ENCRYPTION_KEY'] = 'not-a-fernet-key'
        assert mfa.available() is False

    def test_the_secret_is_32_base32_characters(self, secret):
        assert re.fullmatch(r'[A-Z2-7]{32}', secret)

    def test_the_column_holds_only_ciphertext(self, ana, secret):
        stored = row_of(ana).rbmfa_secret_enc
        assert secret not in stored
        assert secret.lower() not in stored.lower()
        assert Fernet(TEST_TOTP_KEY.encode()).decrypt(stored.encode()).decode() == secret

    def test_two_encryptions_differ(self, app):
        assert mfa.encrypt_secret('A' * 32) != mfa.encrypt_secret('A' * 32)
        assert mfa.decrypt_secret(mfa.encrypt_secret('A' * 32), user_id=1) == 'A' * 32

    def test_another_key_fails_cleanly_without_logging_the_secret(self, app, ana, secret,
                                                                  caplog):
        app.config['TOTP_ENCRYPTION_KEY'] = Fernet.generate_key().decode()
        with caplog.at_level(logging.DEBUG):
            with pytest.raises(mfa.MfaUnavailable):
                mfa.decrypt_secret(row_of(ana).rbmfa_secret_enc, user_id=ana.id)
        assert 'cannot be decrypted' in caplog.text
        assert secret not in caplog.text

    def test_setup_logs_nothing_secret(self, ana, caplog):
        with caplog.at_level(logging.DEBUG):
            clear = mfa.setup(ana)['secret'].replace(' ', '')
        assert clear not in caplog.text

    def test_a_new_setup_replaces_the_pending_secret(self, ana, secret):
        again = mfa.setup(ana)['secret'].replace(' ', '')
        assert again != secret
        assert db.session.execute(sa.select(sa.func.count()).select_from(RbUserMfa)).scalar() == 1
        assert mfa.decrypt_secret(row_of(ana).rbmfa_secret_enc, user_id=ana.id) == again


# --- The TOTP check (S4, S5) -----------------------------------------------------------------

class TestVerifyTotp:
    def test_rfc_6238_sha1_six_digits_thirty_seconds(self, app, make_user, frozen_clock):
        """RFC 6238 appendix B: SHA-1 secret "12345678901234567890" at T=59 s -> 94287082."""
        user = make_user('rfc')
        mfa.setup(user)
        row = row_of(user)
        row.rbmfa_secret_enc = mfa.encrypt_secret('GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ')
        db.session.commit()
        frozen_clock.now = EPOCH + timedelta(seconds=59)
        assert mfa.verify_totp(user, '287082') is True

    @pytest.mark.parametrize('offset', [-1, 0, 1])
    def test_one_step_either_side_is_accepted(self, ana, secret, frozen_clock, offset):
        at_step(frozen_clock, 500, seconds=15)
        assert mfa.verify_totp(ana, code(secret, 500 + offset)) is True
        db.session.commit()
        assert row_of(ana).rbmfa_last_step == 500 + offset

    @pytest.mark.parametrize('offset', [-2, 2])
    def test_two_steps_away_is_refused(self, ana, secret, frozen_clock, offset):
        at_step(frozen_clock, 500)
        assert mfa.verify_totp(ana, code(secret, 500 + offset)) is False
        assert row_of(ana).rbmfa_last_step is None

    def test_the_replay_example(self, ana, secret, frozen_clock):
        """S5: a code accepted at step 100 is refused at step 100 and 101; the next one passes."""
        at_step(frozen_clock, 100)
        assert mfa.verify_totp(ana, code(secret, 100)) is True
        db.session.commit()
        assert mfa.verify_totp(ana, code(secret, 100)) is False
        at_step(frozen_clock, 101)
        assert mfa.verify_totp(ana, code(secret, 100)) is False
        assert mfa.verify_totp(ana, code(secret, 101)) is True
        db.session.commit()
        assert row_of(ana).rbmfa_last_step == 101

    def test_an_earlier_step_after_a_later_one_is_refused(self, ana, secret, frozen_clock):
        at_step(frozen_clock, 100)
        assert mfa.verify_totp(ana, code(secret, 101)) is True
        db.session.commit()
        assert mfa.verify_totp(ana, code(secret, 100)) is False
        assert mfa.verify_totp(ana, code(secret, 99)) is False

    def test_spaces_are_removed(self, ana, secret, frozen_clock):
        at_step(frozen_clock, 100)
        given = code(secret, 100)
        assert mfa.verify_totp(ana, f' {given[:3]} {given[3:]} ') is True

    @pytest.mark.parametrize('given', ['', '12345', '1234567', '12a456', '12-456', '１２３４５６',
                                       '+12345', '123456\n7'])
    def test_anything_but_six_digits_is_refused(self, ana, secret, frozen_clock, given):
        at_step(frozen_clock, 100)
        assert mfa.verify_totp(ana, given) is False
        assert row_of(ana).rbmfa_last_step is None

    def test_a_five_or_seven_digit_prefix_of_the_right_code_is_refused(self, ana, secret,
                                                                       frozen_clock):
        at_step(frozen_clock, 100)
        right = code(secret, 100)
        assert mfa.verify_totp(ana, right[:5]) is False
        assert mfa.verify_totp(ana, right + '0') is False

    def test_a_user_without_2fa_never_passes(self, ana, frozen_clock):
        at_step(frozen_clock, 100)
        assert mfa.verify_totp(ana, '123456') is False

    def test_the_comparison_is_constant_time(self, ana, secret, frozen_clock, monkeypatch):
        seen = []
        real = mfa.hmac.compare_digest

        def spy(a, b):
            seen.append((a, b))
            return real(a, b)

        monkeypatch.setattr(mfa.hmac, 'compare_digest', spy)
        at_step(frozen_clock, 100)
        assert mfa.verify_totp(ana, code(secret, 100)) is True
        assert len(seen) == 3          # every step of the window, no early exit


# --- Recovery codes (S6) ---------------------------------------------------------------------

class TestRecoveryCodes:
    def test_ten_codes_in_the_shown_format(self, ana, secret, frozen_clock):
        codes = enable(ana, secret, frozen_clock)
        assert len(codes) == 10 and len(set(codes)) == 10
        assert all(RECOVERY.match(c) for c in codes), codes

    def test_only_hashes_are_stored(self, ana, secret, frozen_clock):
        codes = enable(ana, secret, frozen_clock)
        stored = {r.rbrco_code_hash for r in codes_of(ana)}
        assert stored == {hashlib.sha256(c.replace('-', '').encode()).hexdigest() for c in codes}
        for given in codes:
            assert all(given.replace('-', '') not in h for h in stored)

    @pytest.mark.parametrize('given', ['ABCDE FGHJK', 'abcde-fghjk', 'abcdefghjk',
                                       ' AbCdE-FgHjK ', 'abcde - fghjk'])
    def test_normalisation(self, ana, secret, frozen_clock, given):
        enable(ana, secret, frozen_clock)
        db.session.add(RbRecoveryCode(rbrco_user_id=ana.id,
                                      rbrco_code_hash=hashlib.sha256(b'abcdefghjk').hexdigest()))
        db.session.commit()
        assert mfa.use_recovery_code(ana, given) is True

    def test_single_use(self, ana, secret, frozen_clock):
        first = enable(ana, secret, frozen_clock)[0]
        assert mfa.use_recovery_code(ana, first) is True
        db.session.commit()
        assert mfa.use_recovery_code(ana, first) is False
        used = [r for r in codes_of(ana) if r.rbrco_used_at is not None]
        assert [r.rbrco_used_at for r in used] == [frozen_clock.now]
        assert mfa.status(ana.id)['recovery_codes_left'] == 9

    def test_a_wrong_code_or_another_users_code_is_refused(self, ana, secret, frozen_clock,
                                                           make_user):
        enable(ana, secret, frozen_clock)
        bo = make_user('bo')
        bo_codes = enable(bo, mfa.setup(bo)['secret'].replace(' ', ''), frozen_clock, step=1001)
        assert mfa.use_recovery_code(ana, bo_codes[0]) is False
        assert mfa.use_recovery_code(ana, 'zzzzz-zzzzz') is False
        assert mfa.use_recovery_code(ana, '') is False

    def test_regeneration_replaces_every_previous_code(self, ana, secret, frozen_clock):
        old = enable(ana, secret, frozen_clock)
        assert mfa.use_recovery_code(ana, old[0]) is True
        db.session.commit()
        status, new, _ = mfa.regenerate_codes(ana, keep_session_id=None)
        assert status is mfa.MfaStatus.OK
        assert len(codes_of(ana)) == 10
        assert not set(old) & set(new)
        assert all(mfa.use_recovery_code(ana, c) is False for c in old)
        assert mfa.use_recovery_code(ana, new[0]) is True

    def test_the_comparison_is_constant_time(self, ana, secret, frozen_clock, monkeypatch):
        codes = enable(ana, secret, frozen_clock)
        seen = []
        real = mfa.hmac.compare_digest
        monkeypatch.setattr(mfa.hmac, 'compare_digest',
                            lambda a, b: seen.append(1) or real(a, b))
        assert mfa.use_recovery_code(ana, codes[3]) is True
        assert len(seen) == 10         # every unused code, no early exit


# --- Status and reset (S14, S15) -------------------------------------------------------------

class TestStatusAndReset:
    def test_status_through_the_lifecycle(self, ana, frozen_clock):
        off = {'available': True, 'enabled': False, 'pending': False, 'recovery_codes_left': 0}
        assert mfa.status(ana.id) == off
        secret_ = mfa.setup(ana)['secret'].replace(' ', '')
        assert mfa.status(ana.id) == {**off, 'pending': True}
        enable(ana, secret_, frozen_clock)
        assert mfa.status(ana.id) == {**off, 'enabled': True, 'recovery_codes_left': 10}

    def test_reset_deletes_everything(self, ana, secret, frozen_clock):
        enable(ana, secret, frozen_clock)
        assert mfa.reset(ana) == 0
        assert row_of(ana) is None and codes_of(ana) == []

    def test_reset_without_2fa_is_none_and_changes_nothing(self, ana, secret):
        assert mfa.reset(ana) is None
        assert row_of(ana) is not None       # a pending setup is not 2FA
