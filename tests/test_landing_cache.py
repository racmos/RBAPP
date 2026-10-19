"""Cached landing feeds (LAND-1, D22, R12).

The six public partials cache the items of their feed function per feed for
`LANDING_CACHE_TTL` seconds. The cache wraps a RAW fetcher (`scraper._raw_<feed>`);
tests patch that raw name, never the cached public one, so the cache stays in
the path. Time is the injectable clock.
"""
import threading
import time

import pytest

from app.services import scraper

FEEDS = {
    # path: (public name, raw name)
    '/api/noticias': ('fetch_noticias', '_raw_noticias'),
    '/api/discord': ('fetch_discord', '_raw_discord'),
    '/api/torneos-online': ('fetch_torneos_online', '_raw_torneos_online'),
    '/api/torneos-fisicos': ('fetch_torneos_fisicos', '_raw_torneos_fisicos'),
    '/api/videos': ('fetch_videos', '_raw_videos'),
    '/api/decks': ('fetch_decks', '_raw_decks'),
}
PLACEHOLDERS = {
    '_raw_noticias': scraper._placeholder_noticias,
    '_raw_discord': scraper._placeholder_discord,
    '_raw_torneos_online': scraper._placeholder_torneos_online,
    '_raw_torneos_fisicos': scraper._placeholder_torneos_fisicos,
    '_raw_videos': scraper._placeholder_videos,
    '_raw_decks': scraper._placeholder_decks,
}


class Calls:
    """A raw fetcher that counts its calls and returns a fixed item list."""

    def __init__(self, raw_name):
        self.count = 0
        self.items = PLACEHOLDERS[raw_name]()

    def __call__(self):
        self.count += 1
        return list(self.items)


@pytest.fixture(autouse=True)
def empty_cache():
    scraper.clear_cache()
    yield
    scraper.clear_cache()


@pytest.fixture
def raw(monkeypatch):
    """Patch every raw fetcher with a counter; returns {raw name: Calls}."""
    counters = {}
    for _public, raw_name in FEEDS.values():
        counters[raw_name] = Calls(raw_name)
        monkeypatch.setattr(scraper, raw_name, counters[raw_name])
    return counters


class TestHit:
    @pytest.mark.parametrize('path', FEEDS)
    def test_five_requests_within_the_ttl_call_the_feed_once(self, client, raw, frozen_clock, path):
        raw_name = FEEDS[path][1]
        bodies = []
        for _ in range(5):
            resp = client.get(path)
            assert resp.status_code == 200
            bodies.append(resp.get_data())
            frozen_clock.advance(seconds=10)
        assert raw[raw_name].count == 1
        assert len(set(bodies)) == 1

    def test_the_output_equals_the_uncached_output(self, app, client, raw, frozen_clock):
        app.config['LANDING_CACHE_TTL'] = 0
        uncached = {p: client.get(p).get_data() for p in FEEDS}
        app.config['LANDING_CACHE_TTL'] = 300
        scraper.clear_cache()
        cached_first = {p: client.get(p).get_data() for p in FEEDS}
        cached_second = {p: client.get(p).get_data() for p in FEEDS}
        assert uncached == cached_first == cached_second

    def test_the_default_ttl_is_five_minutes(self, app):
        assert app.config['LANDING_CACHE_TTL'] == 300


class TestExpiry:
    def test_past_the_ttl_exactly_one_more_call(self, client, raw, frozen_clock):
        client.get('/api/noticias')
        frozen_clock.advance(seconds=301)
        client.get('/api/noticias')
        client.get('/api/noticias')
        assert raw['_raw_noticias'].count == 2

    def test_just_inside_the_ttl_still_hits(self, client, raw, frozen_clock):
        client.get('/api/noticias')
        frozen_clock.advance(seconds=299)
        client.get('/api/noticias')
        assert raw['_raw_noticias'].count == 1

    def test_the_ttl_is_read_from_the_config_per_call(self, app, client, raw, frozen_clock):
        app.config['LANDING_CACHE_TTL'] = 60
        client.get('/api/videos')
        frozen_clock.advance(seconds=59)
        client.get('/api/videos')
        assert raw['_raw_videos'].count == 1
        frozen_clock.advance(seconds=2)
        client.get('/api/videos')
        assert raw['_raw_videos'].count == 2

    def test_a_ttl_of_zero_calls_the_feed_every_time(self, app, client, raw):
        app.config['LANDING_CACHE_TTL'] = 0
        client.get('/api/noticias')
        client.get('/api/noticias')
        assert raw['_raw_noticias'].count == 2

    def test_clear_cache_forgets_everything(self, client, raw):
        client.get('/api/noticias')
        client.get('/api/decks')
        scraper.clear_cache()
        client.get('/api/noticias')
        client.get('/api/decks')
        assert (raw['_raw_noticias'].count, raw['_raw_decks'].count) == (2, 2)


class TestIndependence:
    def test_a_hit_on_one_feed_does_not_serve_another(self, client, raw):
        client.get('/api/decks')
        client.get('/api/decks')
        assert raw['_raw_noticias'].count == 0
        client.get('/api/noticias')
        assert raw['_raw_noticias'].count == 1
        assert raw['_raw_decks'].count == 1

    def test_every_feed_has_its_own_entry(self, client, raw):
        for path in FEEDS:
            client.get(path)
            client.get(path)
        assert {name: c.count for name, c in raw.items()} == {name: 1 for name in raw}


class TestAccess:
    @pytest.mark.parametrize('path', FEEDS)
    def test_partials_stay_public(self, client, raw, path):
        resp = client.get(path)
        assert resp.status_code == 200          # not redirected to the login page

    def test_the_landing_blueprint_still_calls_the_public_names(self):
        from app.routes import landing
        for public, _raw in FEEDS.values():
            assert getattr(landing, public) is getattr(scraper, public)


class TestFailingUpstream:
    def test_a_failing_upstream_is_contacted_once_per_ttl(self, client, monkeypatch, frozen_clock):
        calls = []

        def broken_get(*args, **kwargs):
            calls.append(args[0])
            raise RuntimeError('upstream down')

        monkeypatch.setattr(scraper.requests, 'get', broken_get)
        for _ in range(4):
            resp = client.get('/api/noticias')
            assert resp.status_code == 200            # placeholders
        assert len(calls) == 1
        frozen_clock.advance(seconds=301)
        client.get('/api/noticias')
        assert len(calls) == 2

    def test_an_exception_from_the_feed_is_not_cached(self, app, monkeypatch):
        state = {'calls': 0}

        def flaky():
            state['calls'] += 1
            if state['calls'] == 1:
                raise RuntimeError('boom')
            return scraper._placeholder_noticias()

        monkeypatch.setattr(scraper, '_raw_noticias', flaky)
        with pytest.raises(RuntimeError):
            scraper.fetch_noticias()
        assert scraper.fetch_noticias()
        assert scraper.fetch_noticias()
        assert state['calls'] == 2


class TestConcurrency:
    def test_simultaneous_misses_call_the_feed_once(self, app, monkeypatch):
        state = {'calls': 0}

        def slow():
            state['calls'] += 1
            time.sleep(0.2)
            return scraper._placeholder_noticias()

        monkeypatch.setattr(scraper, '_raw_noticias', slow)
        results = []

        def worker():
            with app.app_context():
                results.append(scraper.fetch_noticias())

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert state['calls'] == 1
        assert len(results) == 8 and all(r == results[0] for r in results)

    def test_a_slow_feed_does_not_block_another_feed(self, app, monkeypatch):
        release = threading.Event()
        started = threading.Event()

        def slow():
            started.set()
            release.wait(5)
            return scraper._placeholder_noticias()

        monkeypatch.setattr(scraper, '_raw_noticias', slow)
        monkeypatch.setattr(scraper, '_raw_decks', lambda: scraper._placeholder_decks())

        def worker():
            with app.app_context():
                scraper.fetch_noticias()

        thread = threading.Thread(target=worker)
        thread.start()
        assert started.wait(5)
        began = time.monotonic()
        assert scraper.fetch_decks()                       # must not wait for noticias
        assert time.monotonic() - began < 1
        release.set()
        thread.join()

    def test_callers_cannot_corrupt_the_cached_list(self, app, monkeypatch):
        monkeypatch.setattr(scraper, '_raw_videos', lambda: scraper._placeholder_videos())
        first = scraper.fetch_videos()
        first.clear()
        assert scraper.fetch_videos()
