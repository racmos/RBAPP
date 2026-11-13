"""F9-b S12 (AC6): GET /meta/config lists the profile country codes; the other keys stay."""
from app.schemas.profile_domain import COUNTRY_CODES

URL = '/riftbound/api/v1/meta/config'


def test_countries_are_the_249_assigned_codes_sorted_upper_case(client):
    countries = client.get(URL).get_json()['data']['countries']
    assert len(countries) == 249
    assert countries == sorted(countries)
    assert all(len(code) == 2 and code.isascii() and code.isupper() for code in countries)
    assert countries == list(COUNTRY_CODES)
    assert {'ES', 'GB', 'US', 'AX', 'BQ', 'SS', 'XK'} - set(countries) == {'XK'}


def test_the_other_keys_are_unchanged(client):
    data = client.get(URL).get_json()['data']
    assert sorted(data) == ['captcha', 'countries', 'csrf', 'env', 'registration_open']
    assert data['captcha'] == {'provider': 'none', 'required_for': []}
    assert data['csrf'] == {'header': 'X-CSRFToken'}
    assert data['registration_open'] is True
