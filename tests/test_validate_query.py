"""S1: validate_query decorator behaviour."""
from typing import List, Literal, Optional

import pytest
from flask import request
from pydantic import BaseModel, Field

from app.schemas.validation import validate_query
from app.schemas.validators import BanListQuery


QUERY_URL = '/_test/query'
BAN_QUERY_URL = '/_test/ban_query'


class _DemoQuery(BaseModel, extra='ignore'):
    q: Optional[str] = None
    tags: Optional[List[str]] = Field(default_factory=list)
    per_page: Optional[int] = Field(None, ge=1, le=192)
    base_only: Optional[bool] = False
    sort: Optional[Literal['name', 'price']] = 'name'


@pytest.fixture
def query_client(app):
    @app.route(QUERY_URL, methods=['GET'])
    @validate_query(_DemoQuery)
    def _handler():
        return {'success': True, 'data': request.validated_query.model_dump()}

    return app.test_client()


@pytest.fixture
def ban_query_client(app):
    @app.route(BAN_QUERY_URL, methods=['GET'])
    @validate_query(BanListQuery)
    def _handler():
        return {'success': True, 'mode': request.validated_query.mode}

    return app.test_client()


def test_repeated_params_become_list(query_client):
    resp = query_client.get(QUERY_URL, query_string={'tags': ['a', 'b', 'c']})
    assert resp.status_code == 200
    assert resp.get_json()['data']['tags'] == ['a', 'b', 'c']


def test_single_param_for_scalar_field(query_client):
    resp = query_client.get(QUERY_URL, query_string={'q': 'jinx'})
    assert resp.status_code == 200
    assert resp.get_json()['data']['q'] == 'jinx'


def test_empty_string_dropped_for_scalar(query_client):
    resp = query_client.get(QUERY_URL, query_string={'q': ''})
    assert resp.status_code == 200
    assert resp.get_json()['data']['q'] is None


def test_empty_strings_dropped_from_list(query_client):
    resp = query_client.get(QUERY_URL, query_string={'tags': ['a', '', 'b', '']})
    assert resp.status_code == 200
    assert resp.get_json()['data']['tags'] == ['a', 'b']


def test_all_empty_list_becomes_empty_list(query_client):
    resp = query_client.get(QUERY_URL, query_string={'tags': ''})
    assert resp.status_code == 200
    assert resp.get_json()['data']['tags'] == []


def test_unknown_params_ignored(query_client):
    resp = query_client.get(QUERY_URL, query_string={'q': 'jinx', 'unknown': 'value', 'extra': ['x', 'y']})
    assert resp.status_code == 200
    data = resp.get_json()['data']
    assert data['q'] == 'jinx'
    assert 'unknown' not in data
    assert 'extra' not in data


@pytest.mark.parametrize('value, expected', [
    ('true', True),
    ('false', False),
    ('1', True),
    ('0', False),
])
def test_bool_coercion(query_client, value, expected):
    resp = query_client.get(QUERY_URL, query_string={'base_only': value})
    assert resp.status_code == 200
    assert resp.get_json()['data']['base_only'] is expected


def test_int_coercion(query_client):
    resp = query_client.get(QUERY_URL, query_string={'per_page': '24'})
    assert resp.status_code == 200
    assert resp.get_json()['data']['per_page'] == 24


def test_error_body_shape_and_detail_codes(query_client):
    resp = query_client.get(QUERY_URL, query_string={'per_page': '500', 'sort': 'popularity'})
    assert resp.status_code == 400
    body = resp.get_json()
    assert body['success'] is False
    assert body['error'] == 'Validation Error'
    assert body['message'] == 'Invalid query parameters'
    assert body['code'] == 'validation_error'
    details = body['details']
    assert len(details) == 2
    per_page_detail = next(d for d in details if d['field'] == 'per_page')
    assert per_page_detail['type'] == 'less_than_equal'
    assert per_page_detail['code'] == 'out_of_range'
    assert per_page_detail['params'] == {'max': 192}
    sort_detail = next(d for d in details if d['field'] == 'sort')
    assert sort_detail['type'] == 'literal_error'
    assert sort_detail['code'] == 'invalid_value'


def test_ban_mode_valid(ban_query_client):
    resp = ban_query_client.get(BAN_QUERY_URL, query_string={'mode': '1v1'})
    assert resp.status_code == 200
    assert resp.get_json()['mode'] == '1v1'


def test_ban_mode_empty_is_absent(ban_query_client):
    """S1: sent-but-empty counts as absent -> None."""
    resp = ban_query_client.get(BAN_QUERY_URL, query_string={'mode': ''})
    assert resp.status_code == 200
    assert resp.get_json()['mode'] is None


@pytest.mark.parametrize('mode', ['3v3', 'all', '1V1', ' 1v1'])
def test_ban_mode_invalid_is_400(ban_query_client, mode):
    resp = ban_query_client.get(BAN_QUERY_URL, query_string={'mode': mode})
    assert resp.status_code == 400
    body = resp.get_json()
    assert body['message'] == 'Invalid query parameters'
    detail = body['details'][0]
    assert detail['field'] == 'mode'
    assert detail['type'] == 'literal_error'
    assert detail['code'] == 'invalid_value'
