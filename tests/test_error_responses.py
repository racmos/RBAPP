"""Unexpected failures of the legacy endpoints never show exception text (M-c S2-S5).

The failing service is mocked to raise an exception that carries a secret-looking
text. Users get a clear message and a `code`; the text travels only under
`detail`, only for a signed-in admin, and always reaches the log.
"""
import io
import logging
from unittest.mock import patch

import pytest
from pydantic import BaseModel, model_validator

from app.schemas.validation import validate_json

SECRET = 'password=hunter2 host=db.internal'
DETAIL = f'RuntimeError: {SECRET}'


def _boom(*_args, **_kwargs):
    raise RuntimeError(SECRET)


def _upload(client):
    return client.post('/riftbound/card/upload_image', content_type='multipart/form-data',
                       data={'image': (io.BytesIO(b'png'), 'card.png'), 'set_id': 'ogn'})


def _refresh(client):
    return client.post('/riftbound/price/refresh-riot-sets', json={})


def _extract(client):
    return client.post('/riftbound/price/extract-riot-cards', json={'sets': []})


def _cardmarket_load(client):
    return client.post('/riftbound/price/cardmarket-load', json={})


def _auto_match(client):
    return client.post('/riftbound/price/cardmarket-auto-match', json={'dry_run': True})


# (call, patched target, clear message, legacy keys the page reads besides `message`)
SITES = {
    'upload_card_image': (_upload, 'app.routes.domains.cards.card_image_path',
                          'The image could not be uploaded', {}),
    'refresh_riot_sets': (_refresh, 'app.services.riot_scraper.refresh_riot_sets',
                          'The Riot sets could not be loaded', {'sets': []}),
    'extract_riot_cards': (_extract, 'app.services.riot_scraper.extract_riot_cards',
                           'The Riot cards could not be extracted',
                           {'steps': [], 'stats': {},
                            'errors': ['The Riot cards could not be extracted']}),
    'cardmarket_load': (_cardmarket_load, 'app.services.cardmarket_loader.CardmarketLoader.run',
                        'The Cardmarket data could not be loaded',
                        {'steps': [], 'errors': ['The Cardmarket data could not be loaded']}),
    'cardmarket_auto_match': (_auto_match, 'app.services.cardmarket_matcher.auto_match',
                              'The auto-match could not be run', {}),
}


def _secret_anywhere(response):
    return SECRET in response.get_data(as_text=True)


@pytest.mark.parametrize('site', sorted(SITES))
class TestUnexpectedFailureOfALegacyEndpoint:
    """S3: the 500s of the image upload and the price tools (all admin-only)."""

    def test_the_admin_gets_a_clear_500_with_the_detail(self, admin_client, site, caplog):
        call, target, message, legacy = SITES[site]
        with patch(target, side_effect=_boom), caplog.at_level(logging.ERROR):
            response = call(admin_client)

        assert response.status_code == 500
        body = response.get_json()
        assert body['success'] is False
        assert body['code'] == 'internal_error'
        assert body['message'] == message
        assert body['detail'] == DETAIL
        for key, value in legacy.items():
            assert body[key] == value
        without_detail = {k: v for k, v in body.items() if k != 'detail'}
        assert SECRET not in str(without_detail)

    def test_the_failure_is_logged_with_its_traceback(self, admin_client, site, caplog):
        call, target, _message, _legacy = SITES[site]
        with patch(target, side_effect=_boom), caplog.at_level(logging.ERROR):
            call(admin_client)

        records = [r for r in caplog.records if r.exc_info and SECRET in str(r.exc_info[1])]
        assert records, 'the exception was not logged with exc_info'
        assert records[0].levelno == logging.ERROR

    def test_a_plain_user_never_reaches_the_service(self, authenticated_client, site):
        call, target, _message, _legacy = SITES[site]
        with patch(target, side_effect=_boom) as service:
            response = call(authenticated_client)

        assert response.status_code == 403
        assert not service.called
        assert not _secret_anywhere(response)


class TestTheLegacyPagesStillWork:
    """PRESERVE: a working service still answers exactly what it returned."""

    @pytest.mark.parametrize('site', ['refresh_riot_sets', 'extract_riot_cards',
                                      'cardmarket_auto_match'])
    def test_the_service_result_is_passed_through(self, admin_client, site):
        call, target, _message, _legacy = SITES[site]
        result = {'success': True, 'sets': [{'id': 'ogn'}], 'steps': [], 'stats': {}}
        with patch(target, return_value=result):
            response = call(admin_client)
        assert response.status_code == 200
        assert response.get_json() == result

    def test_the_cardmarket_loader_result_is_passed_through(self, admin_client):
        result = {'success': True, 'steps': [], 'errors': [], 'date': '2030-01-01'}
        with patch('app.services.cardmarket_loader.CardmarketLoader.run', return_value=result):
            response = _cardmarket_load(admin_client)
        assert response.status_code == 200
        assert response.get_json() == result

    def test_the_image_upload_still_saves_the_file(self, admin_client, tmp_path):
        destination = tmp_path / 'ogn' / 'card.png'
        with patch('app.routes.domains.cards.card_image_path', return_value=str(destination)):
            response = _upload(admin_client)
        assert response.status_code == 200
        assert response.get_json() == {'success': True, 'filename': 'card.png'}
        assert destination.read_bytes() == b'png'


# --- @validate_json: the generic `except Exception` branch -----------------------

class _Exploding(BaseModel):
    """A schema whose validator fails with something Pydantic does not wrap."""

    @model_validator(mode='before')
    @classmethod
    def explode(cls, data):
        raise RuntimeError(SECRET)


@pytest.fixture
def probe_app(app):
    """`app` with a test-only route behind `@validate_json(_Exploding)`.

    Request it BEFORE any logged-in client: routes cannot be added after the
    first request."""
    @app.route('/riftbound/test-probe', methods=['POST'])
    @validate_json(_Exploding)
    def _probe():
        return {'success': True}
    return app


def _probe(client):
    return client.post('/riftbound/test-probe', json={'any': 'thing'})


class TestValidateJsonGenericFailure:
    """S3/S5: 400 "Bad Request", "Invalid request body", `bad_request`; detail for admins."""

    def _assert_clear_400(self, response):
        assert response.status_code == 400
        body = response.get_json()
        assert body['success'] is False
        assert body['error'] == 'Bad Request'
        assert body['message'] == 'Invalid request body'
        assert body['code'] == 'bad_request'
        return body

    def test_a_plain_user_gets_no_detail(self, probe_app, authenticated_client):
        response = _probe(authenticated_client)
        body = self._assert_clear_400(response)
        assert 'detail' not in body
        assert not _secret_anywhere(response)

    def test_an_anonymous_caller_gets_no_detail(self, probe_app, client):
        response = _probe(client)
        assert 'detail' not in self._assert_clear_400(response)
        assert not _secret_anywhere(response)

    def test_the_admin_gets_the_detail(self, probe_app, admin_client):
        body = self._assert_clear_400(_probe(admin_client))
        assert body['detail'] == DETAIL

    def test_the_failure_is_logged(self, probe_app, client, caplog):
        with caplog.at_level(logging.ERROR):
            _probe(client)
        assert any(r.exc_info and SECRET in str(r.exc_info[1]) for r in caplog.records)

    def test_a_body_that_is_not_an_object_on_a_real_endpoint(self, authenticated_client):
        response = authenticated_client.post('/riftbound/profile/update', json=['x'])
        body = self._assert_clear_400(response)
        assert 'detail' not in body
        assert 'mapping' not in response.get_data(as_text=True)

    def test_malformed_json_on_a_real_endpoint(self, authenticated_client):
        response = authenticated_client.post('/riftbound/profile/update', data='{"email": ',
                                             content_type='application/json')
        body = self._assert_clear_400(response)
        assert 'detail' not in body
        assert 'decode' not in response.get_data(as_text=True).lower()


class TestValidateJsonUnchangedBranches:
    """PRESERVE: the Pydantic and Content-Type branches keep their F0 bodies."""

    def test_a_pydantic_error_is_still_a_validation_error(self, authenticated_client):
        response = authenticated_client.post('/riftbound/profile/update',
                                             json={'email': 'no-at-sign'})
        assert response.status_code == 400
        body = response.get_json()
        assert body['error'] == 'Validation Error'
        assert body['message'] == 'Invalid request data'
        assert body['code'] == 'validation_error'
        assert body['details'][0]['field'] == 'email'
        assert 'detail' not in body

    def test_a_non_json_body_still_asks_for_json(self, authenticated_client):
        response = authenticated_client.post('/riftbound/profile/update', data='x',
                                             content_type='text/plain')
        assert response.status_code == 400
        assert response.get_json() == {'success': False, 'error': 'Bad Request',
                                       'message': 'Content-Type must be application/json'}
