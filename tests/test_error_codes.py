"""Machine-readable error codes (API-1, API-9, R6; unit c of f1-app-shell).

`TestAdditive` and `TestJinjaRegisterText` are characterization tests (CHAR):
they pin what the F0 bodies already say and MUST pass before and after the
codes land, because the codes are additive (new keys only, none removed). The
rest drives the codes themselves.
"""
import pytest

API = '/riftbound/api/v1'
PASSWORD = 'Passw0rd!x'


def api_post(client, path, body=None, **headers):
    return client.post(f'{API}{path}', json=body if body is not None else {}, headers=headers)


def has_old_keys(body, keys):
    """Every key F0 returned is still there (new keys may have been added)."""
    return set(keys) <= set(body)


# ---------------------------------------------------------------------------
# 3.2 CHAR: the F0 bodies stay valid (R6)
# ---------------------------------------------------------------------------

class TestAdditive:
    def test_legacy_json_validation_400_keeps_its_keys(self, admin_client):
        resp = admin_client.post('/riftbound/set/add', json={})
        body = resp.get_json()
        assert resp.status_code == 400
        assert has_old_keys(body, ('success', 'error', 'message', 'details'))
        assert (body['success'], body['error'], body['message']) == (
            False, 'Validation Error', 'Invalid request data')
        assert {d['field'] for d in body['details']} == {'rbset_id', 'rbset_name'}
        for detail in body['details']:
            assert has_old_keys(detail, ('field', 'message', 'type'))
            assert detail['type'] == 'missing'
            assert detail['message'] == 'Field required'

    def test_api_404_keeps_the_f0_shape(self, client):
        resp = client.get(f'{API}/nope')
        assert resp.status_code == 404
        assert resp.get_json() == {'success': False, 'error': 'Not Found',
                                   'message': 'The requested resource was not found'}

    def test_api_401_keeps_its_keys(self, client):
        resp = api_post(client, '/auth/logout')
        body = resp.get_json()
        assert resp.status_code == 401
        assert has_old_keys(body, ('success', 'error', 'message'))
        assert (body['success'], body['error'], body['message']) == (
            False, 'Unauthorized', 'Authentication is required')

    def test_api_csrf_400_keeps_its_keys(self, csrf_app, client):
        resp = api_post(client, '/auth/login', {'username': 'u', 'password': 'p'})
        body = resp.get_json()
        assert resp.status_code == 400
        assert has_old_keys(body, ('success', 'error', 'message'))
        assert (body['success'], body['error']) == (False, 'CSRF Error')
        assert body['message']


# ---------------------------------------------------------------------------
# 3.3 CHAR: the Jinja register text goes through removeprefix('Value error, ')
# ---------------------------------------------------------------------------

VALID_FORM = {'username': 'newbie', 'email': 'newbie@test.com', 'password': 'longenough1'}


def flashes(client):
    with client.session_transaction() as sess:
        return [message for _category, message in sess.get('_flashes', [])]


class TestJinjaRegisterText:
    def test_a_bad_email_reads_as_a_plain_sentence(self, client):
        client.post('/riftbound/register', data={**VALID_FORM, 'email': 'not-an-email'})
        assert flashes(client) == ['email: Invalid email format']

    def test_a_bad_username_reads_as_a_plain_sentence(self, client):
        client.post('/riftbound/register', data={**VALID_FORM, 'username': 'ab'})
        assert flashes(client) == [
            'username: Username must be 3-32 characters: letters, digits, ".", "_" or "-"']

    def test_a_short_password_reads_as_a_plain_sentence(self, client):
        client.post('/riftbound/register', data={**VALID_FORM, 'password': 'short7!'})
        assert flashes(client) == ['password: String should have at least 8 characters']


# ---------------------------------------------------------------------------
# 3.15 Helpers (D9)
# ---------------------------------------------------------------------------

CODES = {
    'invalid_credentials', 'locked', 'rate_limited', 'username_taken', 'email_taken',
    'captcha_failed', 'csrf_invalid', 'unauthenticated', 'validation_error',
}


class TestHelpers:
    def test_error_code_has_the_nine_values_of_the_design(self):
        from app.api.error_codes import ErrorCode
        assert {member.value for member in ErrorCode} == CODES
        assert len(ErrorCode) == 9

    def test_error_code_members_are_lowercase_snake_case_strings(self):
        import re
        from app.api.error_codes import ErrorCode
        for member in ErrorCode:
            assert isinstance(member, str)
            assert re.fullmatch(r'[a-z]+(_[a-z]+)*', member.value), member
            assert member.name.lower() == member.value

    def test_detail_codes_are_the_stable_set_of_api_9(self):
        from app.api.error_codes import DetailCode
        assert {member.value for member in DetailCode} == {
            'required', 'too_short', 'too_long', 'invalid_format', 'invalid_value',
            'out_of_range'}

    def test_json_error_without_code_is_byte_identical_to_f0(self, app):
        from app.errors import json_error
        with app.test_request_context():
            plain = json_error('Not Found', 'nope', 404)
            with_details = json_error('Validation Error', 'bad', 400, details=[{'field': 'x'}])
        assert plain.get_data() == (
            b'{"error":"Not Found","message":"nope","success":false}\n')
        assert with_details.get_json() == {
            'success': False, 'error': 'Validation Error', 'message': 'bad',
            'details': [{'field': 'x'}]}

    def test_json_error_adds_code_and_params_only_when_given(self, app):
        from app.errors import json_error
        with app.test_request_context():
            coded = json_error('Conflict', 'taken', 409, code='username_taken')
            with_params = json_error('Too Many Requests', 'wait', 429, code='locked',
                                     params={'retry_after': 30})
            params_only = json_error('X', 'y', 400, params={'a': 1})
        assert coded.get_json() == {'success': False, 'error': 'Conflict', 'message': 'taken',
                                    'code': 'username_taken'}
        assert with_params.get_json()['code'] == 'locked'
        assert with_params.get_json()['params'] == {'retry_after': 30}
        assert 'code' not in params_only.get_json()          # params without a code: not added
        assert 'params' not in coded.get_json()

    def test_code_and_params_are_keyword_only(self, app):
        from app.api.responses import fail
        from app.errors import json_error
        with app.test_request_context():
            with pytest.raises(TypeError):
                json_error('E', 'm', 400, None, 'code_as_positional')
            with pytest.raises(TypeError):
                fail('E', 'm', 400, None, None, 'code_as_positional')

    def test_fail_passes_code_params_and_headers(self, app):
        from app.api.error_codes import ErrorCode
        from app.api.responses import fail
        with app.test_request_context():
            resp = fail('Too Many Requests', 'wait', 429, code=ErrorCode.LOCKED,
                        params={'retry_after': 7}, headers={'Retry-After': '7'})
        assert resp.status_code == 429
        assert resp.headers['Retry-After'] == '7'
        assert resp.get_json()['code'] == 'locked'
        assert resp.get_json()['params'] == {'retry_after': 7}


# ---------------------------------------------------------------------------
# 3.17 Validation mapping (D9, design 5.3), pure
# ---------------------------------------------------------------------------

class TestValidationMapping:
    @pytest.mark.parametrize('error, expected', [
        ({'type': 'missing'}, ('required', None)),
        ({'type': 'string_too_short', 'ctx': {'min_length': 8}}, ('too_short', {'min': 8})),
        ({'type': 'too_short', 'ctx': {'min_length': 1}}, ('too_short', {'min': 1})),
        ({'type': 'string_too_long', 'ctx': {'max_length': 128}}, ('too_long', {'max': 128})),
        ({'type': 'too_long', 'ctx': {'max_length': 5}}, ('too_long', {'max': 5})),
        ({'type': 'greater_than_equal', 'ctx': {'ge': 0}}, ('out_of_range', {'min': 0})),
        ({'type': 'greater_than', 'ctx': {'gt': 0}}, ('out_of_range', {'min': 0})),
        ({'type': 'less_than_equal', 'ctx': {'le': 100}}, ('out_of_range', {'max': 100})),
        ({'type': 'less_than', 'ctx': {'lt': 10}}, ('out_of_range', {'max': 10})),
        ({'type': 'invalid_format'}, ('invalid_format', None)),
        ({'type': 'literal_error', 'ctx': {'expected': "'a' or 'b'"}}, ('invalid_value', None)),
        ({'type': 'bool_type'}, ('invalid_value', None)),
        ({'type': 'int_from_float'}, ('invalid_value', None)),
        ({'type': 'int_type'}, ('invalid_value', None)),
        ({'type': 'string_type'}, ('invalid_value', None)),
        ({'type': 'value_error', 'ctx': {'error': ValueError('x')}}, ('invalid_value', None)),
        ({'type': 'something_new'}, ('invalid_value', None)),
    ])
    def test_the_table(self, error, expected):
        from app.schemas.validation import detail_code
        assert detail_code(error) == expected

    def test_params_never_carry_non_json_context(self):
        import json
        from app.schemas.validation import detail_code
        code, params = detail_code({'type': 'value_error', 'ctx': {'error': ValueError('x')}})
        json.dumps({'code': code, 'params': params})

    def test_a_real_pydantic_error_maps_end_to_end(self):
        from pydantic import ValidationError
        from app.schemas.validation import detail_code
        from app.schemas.validators import PrefsUpdate, RegisterRequest
        with pytest.raises(ValidationError) as err:
            RegisterRequest(username='ab', email='nope', password='123')
        mapped = {e['loc'][0]: detail_code(e) for e in err.value.errors()}
        assert mapped == {'username': ('invalid_format', None),
                          'email': ('invalid_format', None),
                          'password': ('too_short', {'min': 8})}
        with pytest.raises(ValidationError) as err:
            PrefsUpdate(bg_intensity=101, accent='purple')
        mapped = {e['loc'][0]: detail_code(e) for e in err.value.errors()}
        assert mapped == {'bg_intensity': ('out_of_range', {'max': 100}),
                          'accent': ('invalid_value', None)}


# ---------------------------------------------------------------------------
# 3.18 validate_json (API-9, R6)
# ---------------------------------------------------------------------------

class TestValidateJson:
    def test_register_details_carry_code_and_params_and_keep_the_f0_keys(self, client):
        resp = api_post(client, '/auth/register', {
            'username': 'newbie', 'email': 'not-an-email', 'password': '123'})
        body = resp.get_json()
        assert resp.status_code == 400
        assert (body['success'], body['error'], body['code']) == (
            False, 'Validation Error', 'validation_error')
        details = {d['field']: d for d in body['details']}
        assert set(details) == {'email', 'password'}
        assert (details['password']['code'], details['password']['params']) == (
            'too_short', {'min': 8})
        assert details['email']['code'] == 'invalid_format'
        assert 'params' not in details['email']
        for detail in details.values():
            assert {'field', 'message', 'type'} <= set(detail)
        assert details['email']['message'] == 'Invalid email format'
        assert details['password']['message'] == 'String should have at least 8 characters'

    def test_missing_fields_are_required(self, client):
        body = api_post(client, '/auth/login', {'username': 'u'}).get_json()
        assert body['code'] == 'validation_error'
        [detail] = body['details']
        assert (detail['field'], detail['code'], detail['type']) == (
            'password', 'required', 'missing')

    def test_remember_not_boolean_is_invalid_value(self, client):
        body = api_post(client, '/auth/login', {
            'username': 'u', 'password': 'p', 'remember': 'yes'}).get_json()
        [detail] = body['details']
        assert (detail['field'], detail['code']) == ('remember', 'invalid_value')

    def test_too_long_username_in_register(self, client):
        body = api_post(client, '/auth/register', {
            'username': 'x' * 40, 'email': 'a@b.io', 'password': 'longenough1'}).get_json()
        [detail] = body['details']
        assert (detail['field'], detail['code']) == ('username', 'invalid_format')

    def test_too_long_password_in_register(self, client):
        body = api_post(client, '/auth/register', {
            'username': 'newbie', 'email': 'a@b.io', 'password': 'p' * 129}).get_json()
        [detail] = body['details']
        assert (detail['field'], detail['code'], detail['params']) == (
            'password', 'too_long', {'max': 128})

    def test_too_long_email_in_register(self, client):
        body = api_post(client, '/auth/register', {
            'username': 'newbie', 'email': 'a' * 120 + '@x.io', 'password': 'longenough1'}
        ).get_json()
        [detail] = body['details']
        assert (detail['field'], detail['code'], detail['params']) == ('email', 'too_long', {'max': 120})
        assert detail['message'] == 'Email must have at most 120 characters'

    def test_legacy_json_endpoints_get_the_additive_code_too(self, admin_client):
        body = admin_client.post('/riftbound/set/add', json={}).get_json()
        assert body['code'] == 'validation_error'
        assert {d['code'] for d in body['details']} == {'required'}
        assert {'success', 'error', 'message', 'details'} <= set(body)

    def test_a_non_json_content_type_stays_codeless(self, client):
        resp = client.post(f'{API}/auth/login', data='x=1',
                           content_type='application/x-www-form-urlencoded')
        body = resp.get_json()
        assert resp.status_code == 400
        assert body['error'] == 'Bad Request'
        assert 'code' not in body


# ---------------------------------------------------------------------------
# 3.20 Endpoint codes (API-9)
# ---------------------------------------------------------------------------

def token_of(client):
    return client.get(f'{API}/auth/session').get_json()['data']['csrf_token']


class TestEndpointCodes:
    def test_login_401_is_invalid_credentials(self, client, make_user):
        make_user('u', password=PASSWORD)
        body = api_post(client, '/auth/login', {'username': 'u', 'password': 'wrong-pass'}
                        ).get_json()
        assert (body['error'], body['code']) == ('Unauthorized', 'invalid_credentials')
        assert 'params' not in body
        ghost = api_post(client, '/auth/login', {'username': 'ghost', 'password': 'wrong-pass'}
                         ).get_json()
        assert ghost == body                       # unknown user: indistinguishable

    def test_the_sixth_login_is_a_locked_429_with_retry_after_params(
            self, client, make_user, frozen_clock):
        make_user('u', password=PASSWORD)
        for _ in range(5):
            assert api_post(client, '/auth/login', {
                'username': 'u', 'password': 'wrong-pass'}).status_code == 401
        resp = api_post(client, '/auth/login', {'username': 'u', 'password': PASSWORD})
        body = resp.get_json()
        assert resp.status_code == 429
        assert body['code'] == 'locked'
        assert body['params']['retry_after'] == int(resp.headers['Retry-After'])
        assert body['params']['retry_after'] > 0
        assert body['message'] == 'Invalid credentials or account temporarily locked'

    def test_the_limiter_429_is_rate_limited_with_retry_after(self, limited_app, client,
                                                              monkeypatch):
        from werkzeug.security import generate_password_hash
        from app.services import auth
        cheap = generate_password_hash('dummy', method='pbkdf2:sha256:1000')
        monkeypatch.setattr(auth, '_dummy_hash', lambda: cheap)
        for i in range(10):
            api_post(client, '/auth/login', {'username': f'ghost{i}', 'password': 'wrong-pass'})
        resp = api_post(client, '/auth/login', {'username': 'ghost', 'password': 'wrong-pass'})
        body = resp.get_json()
        assert resp.status_code == 429
        assert (body['error'], body['code']) == ('Too Many Requests', 'rate_limited')
        assert body['params']['retry_after'] == int(resp.headers['Retry-After'])
        assert body['params']['retry_after'] >= 1

    def test_a_limited_html_form_still_gets_the_html_page(self, limited_app, client,
                                                          monkeypatch):
        from werkzeug.security import generate_password_hash
        from app.services import auth
        cheap = generate_password_hash('dummy', method='pbkdf2:sha256:1000')
        monkeypatch.setattr(auth, '_dummy_hash', lambda: cheap)
        for i in range(10):
            client.post('/riftbound/login', data={'username': f'g{i}', 'password': 'wrong-pass'})
        resp = client.post('/riftbound/login', data={'username': 'g', 'password': 'wrong-pass'})
        assert resp.status_code == 429
        assert resp.mimetype == 'text/html'

    def test_register_409_names_what_is_taken(self, client, make_user):
        make_user('dup', email='dup@example.com')
        new = {'email': 'fresh@example.com', 'password': 'longenough1'}
        first = api_post(client, '/auth/register', {**new, 'username': 'dup'})
        second = api_post(client, '/auth/register', {
            'username': 'fresh', 'email': 'dup@example.com', 'password': 'longenough1'})
        assert (first.status_code, first.get_json()['code']) == (409, 'username_taken')
        assert (second.status_code, second.get_json()['code']) == (409, 'email_taken')
        assert first.get_json()['error'] == 'Conflict'

    def test_register_without_a_captcha_payload_is_captcha_failed(self, altcha_app, client):
        resp = api_post(client, '/auth/register', {
            'username': 'newbie', 'email': 'newbie@test.com', 'password': 'longenough1'})
        body = resp.get_json()
        assert resp.status_code == 400
        assert (body['error'], body['code']) == ('Captcha Error', 'captcha_failed')

    def test_csrf_failure_on_the_api_is_csrf_invalid(self, csrf_app, client):
        body = api_post(client, '/auth/login', {'username': 'u', 'password': 'p'}).get_json()
        assert (body['error'], body['code']) == ('CSRF Error', 'csrf_invalid')
        # the token from /auth/session works, with no code on success
        ok = api_post(client, '/auth/login', {'username': 'u', 'password': 'p'},
                      **{'X-CSRFToken': token_of(client)})
        assert ok.status_code == 401 and ok.get_json()['code'] == 'invalid_credentials'

    def test_csrf_failure_on_a_legacy_json_endpoint_is_csrf_invalid_too(
            self, authenticated_client, csrf_app):
        resp = authenticated_client.post('/riftbound/set/add', json={'rbset_id': 'X'})
        body = resp.get_json()
        assert resp.status_code == 400
        assert (body['error'], body['code']) == ('CSRF Error', 'csrf_invalid')

    def test_a_csrf_html_failure_stays_an_html_page(self, client, csrf_app):
        resp = client.post('/riftbound/login', data={'username': 'u', 'password': 'p'})
        assert resp.status_code == 400
        assert resp.mimetype == 'text/html'

    def test_anonymous_logout_is_unauthenticated(self, client):
        body = api_post(client, '/auth/logout').get_json()
        assert (body['error'], body['code']) == ('Unauthorized', 'unauthenticated')

    def test_anonymous_json_access_to_a_legacy_endpoint_is_unauthenticated_too(self, client):
        resp = client.post('/riftbound/collection/add', json={},
                           headers={'Accept': 'application/json'})
        assert resp.status_code == 401
        assert resp.get_json()['code'] == 'unauthenticated'

    def test_anonymous_html_access_is_still_a_redirect(self, client):
        resp = client.get('/riftbound/')
        assert resp.status_code == 302
        assert '/riftbound/login' in resp.headers['Location']

    def test_the_unknown_path_404_stays_codeless(self, client):
        body = client.get(f'{API}/nope').get_json()
        assert 'code' not in body and 'params' not in body
        assert set(body) == {'success', 'error', 'message'}

    def test_wrong_method_and_server_errors_stay_codeless(self, client):
        assert 'code' not in client.post(f'{API}/health').get_json()
