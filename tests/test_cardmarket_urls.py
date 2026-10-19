"""
Cardmarket URL allow-list (ACL-7).

`price/cardmarket-load` lets an admin override the three download URLs. An
override is only accepted when it is https, on an allow-listed host, without
userinfo and on port 443; anything else is a 400 and nothing is downloaded
(no SSRF to cloud-metadata or internal hosts).
"""
import pytest

from app.services import cardmarket_loader
from app.services.cardmarket_loader import CARDMARKET_URLS, validate_override_url
from config import load_settings

HOST = 'downloads.s3.cardmarket.com'
ALLOWED = (HOST,)


class TestValidateOverrideUrl:
    @pytest.mark.parametrize('url', [
        f'https://{HOST}/productCatalog/priceGuide/price_guide_22.json',
        f'https://{HOST}:443/x.json',
        f'HTTPS://{HOST.upper()}/x.json',
        f'https://{HOST}/x.json?v=2#frag',
        f'https://{HOST}',
    ])
    def test_accepts_https_on_the_allowed_host(self, url):
        assert validate_override_url(url, ALLOWED) == url

    @pytest.mark.parametrize('url', [
        f'http://{HOST}/x.json',                          # not https
        f'ftp://{HOST}/x.json',
        'file:///etc/passwd',
        'https://169.254.169.254/latest/meta-data/',      # cloud metadata
        'https://evil.example/x.json',
        f'https://{HOST}.evil.example/x.json',            # suffix trick
        f'https://evil.example/{HOST}/x.json',            # host only in the path
        f'https://user:secret@{HOST}/x.json',             # userinfo
        f'https://{HOST}@evil.example/x.json',            # userinfo disguising the host
        f'https://{HOST}:8443/x.json',                    # wrong port
        f'https://{HOST}:abc/x.json',                     # unparseable port
        f'https://evil.example\\@{HOST}/x.json',          # backslash parsed differently by clients
        f'https://{HOST}/x.json\nHost: evil.example',     # control characters
        f'https://{HOST}/a b.json',                       # whitespace
        'https:///x.json',                                # no host
        '',
        '   ',
        '//downloads.s3.cardmarket.com/x.json',           # scheme-relative
    ])
    def test_rejects_everything_else(self, url):
        with pytest.raises(ValueError):
            validate_override_url(url, ALLOWED)

    def test_a_non_string_is_rejected(self):
        with pytest.raises(ValueError):
            validate_override_url(None, ALLOWED)
        with pytest.raises(ValueError):
            validate_override_url(123, ALLOWED)

    def test_the_error_names_the_problem_not_a_stack_trace(self):
        with pytest.raises(ValueError, match='https'):
            validate_override_url(f'http://{HOST}/x', ALLOWED)
        with pytest.raises(ValueError, match='host'):
            validate_override_url('https://evil.example/x', ALLOWED)

    def test_the_allow_list_is_a_parameter(self):
        url = 'https://files.example.org/x.json'
        assert validate_override_url(url, ('files.example.org',)) == url
        with pytest.raises(ValueError):
            validate_override_url(url, ALLOWED)

    def test_the_built_in_urls_pass_their_own_rule(self):
        assert len(CARDMARKET_URLS) == 3
        for url in CARDMARKET_URLS.values():
            assert validate_override_url(url, ALLOWED) == url


class TestAllowListConfig:
    def test_default_is_the_host_of_the_built_in_urls(self):
        settings = load_settings('testing', {})
        assert settings['CARDMARKET_ALLOWED_HOSTS'] == (HOST,)

    def test_env_overrides_with_a_comma_separated_list(self):
        settings = load_settings(
            'testing', {'CARDMARKET_ALLOWED_HOSTS': ' Files.Example.org ,mirror.example.net,, '})
        assert settings['CARDMARKET_ALLOWED_HOSTS'] == ('files.example.org', 'mirror.example.net')

    def test_a_blank_env_value_keeps_the_default(self):
        settings = load_settings('testing', {'CARDMARKET_ALLOWED_HOSTS': '  '})
        assert settings['CARDMARKET_ALLOWED_HOSTS'] == (HOST,)

    def test_the_app_carries_it(self, app):
        assert app.config['CARDMARKET_ALLOWED_HOSTS'] == (HOST,)


@pytest.fixture
def downloads(monkeypatch):
    """Record every download the loader attempts; they all fail, so nothing is loaded."""
    calls = []

    def fake_get(url, *args, **kwargs):
        calls.append(url)
        raise ConnectionError('network disabled in tests')

    monkeypatch.setattr(cardmarket_loader.requests, 'get', fake_get)
    return calls


class TestCardmarketLoadRoute:
    @pytest.mark.parametrize('field', ['singles_url', 'nonsingles_url', 'price_guide_url'])
    @pytest.mark.parametrize('bad', [
        'http://169.254.169.254/x',
        'https://evil.example/x',
        f'https://user:pw@{HOST}/x',
        f'http://{HOST}/x',
    ])
    def test_foreign_override_is_a_400_and_nothing_is_downloaded(
            self, admin_client, downloads, field, bad):
        resp = admin_client.post('/riftbound/price/cardmarket-load', json={field: bad})
        assert resp.status_code == 400
        assert resp.json['success'] is False
        assert resp.json['error'] and resp.json['message']
        assert field in resp.json['message']
        assert downloads == []

    def test_one_bad_override_blocks_the_whole_request(self, admin_client, downloads):
        resp = admin_client.post('/riftbound/price/cardmarket-load', json={
            'singles_url': f'https://{HOST}/ok.json',
            'price_guide_url': 'https://evil.example/x'})
        assert resp.status_code == 400
        assert downloads == []

    def test_an_allowed_override_is_the_url_that_gets_downloaded(self, admin_client, downloads):
        override = f'https://{HOST}/productCatalog/priceGuide/other_22.json'
        resp = admin_client.post('/riftbound/price/cardmarket-load',
                                 json={'price_guide_url': override})
        assert resp.status_code != 400                  # accepted; the download itself fails here
        assert downloads[0] == override                 # price_guide is fetched first

    def test_no_override_uses_the_built_in_urls(self, admin_client, downloads):
        admin_client.post('/riftbound/price/cardmarket-load', json={})
        assert downloads[0] == CARDMARKET_URLS['price_guide']

    def test_empty_overrides_mean_no_override(self, admin_client, downloads):
        resp = admin_client.post('/riftbound/price/cardmarket-load', json={'singles_url': ''})
        assert resp.status_code != 400
        assert CARDMARKET_URLS['singles'] in downloads

    def test_a_custom_allow_list_is_honoured(self, app, admin_client, downloads):
        app.config['CARDMARKET_ALLOWED_HOSTS'] = ('files.example.org',)
        url = 'https://files.example.org/x.json'
        assert admin_client.post('/riftbound/price/cardmarket-load',
                                 json={'price_guide_url': url}).status_code != 400
        assert admin_client.post('/riftbound/price/cardmarket-load',
                                 json={'price_guide_url': f'https://{HOST}/x.json'}).status_code == 400
