"""Behaviour of the fetch wrapper `app/static/js/csrf.js` (CSRF-3 wrapper scenario).

The browser scenario is [MANUAL] in the spec; here the real file runs under
Node (global `Headers`, `Request`, `URL`) with a fake `window`/`document`, so
the rules are checked on every test run. Skipped when `node` is not installed.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / 'app' / 'static' / 'js' / 'csrf.js'

pytestmark = pytest.mark.skipif(shutil.which('node') is None, reason='node is not installed')

HARNESS = r"""
const fs = require('fs');
const vm = require('vm');
const source = fs.readFileSync(process.argv[2], 'utf8');
const hasMeta = process.argv[3] === 'meta';

const calls = [];
const window = {
    location: { href: 'https://app.example/riftbound/page', origin: 'https://app.example' },
    fetch: function (input, init) { calls.push({ input, init }); return Promise.resolve('ok'); },
};
const document = {
    querySelector: (sel) => (hasMeta && sel === 'meta[name="csrf-token"]')
        ? { getAttribute: () => 'TOKEN123' } : null,
};
const original = window.fetch;
vm.runInNewContext(source, { window, document, Headers, Request, URL, Object, String, console });

function headerOf(call) {
    const init = call.init || {};
    const h = new Headers(init.headers || (call.input instanceof Request ? call.input.headers : undefined));
    return h.get('X-CSRFToken');
}

(async () => {
    const out = {};
    out.wrapped = window.fetch !== original;

    const run = async (input, init) => { calls.length = 0; await window.fetch(input, init); return headerOf(calls[0]); };

    out.same_origin_post = await run('/riftbound/set/add', { method: 'POST', body: '{}' });
    out.absolute_same_origin = await run('https://app.example/riftbound/x', { method: 'delete' });
    out.get = await run('/riftbound/set', {});
    out.get_no_init = await run('/riftbound/set');
    out.head = await run('/riftbound/set', { method: 'HEAD' });
    out.cross_origin_post = await run('https://evil.example/collect', { method: 'POST' });
    out.protocol_relative_cross = await run('//evil.example/collect', { method: 'POST' });
    out.other_port = await run('https://app.example:8443/x', { method: 'POST' });
    out.keeps_caller_header = await run('/riftbound/x', { method: 'POST', headers: { 'X-CSRFToken': 'MINE' } });
    out.keeps_other_headers = await (async () => {
        calls.length = 0;
        await window.fetch('/riftbound/x', { method: 'PUT', headers: { 'Content-Type': 'application/json' } });
        const h = new Headers(calls[0].init.headers);
        return [h.get('Content-Type'), h.get('X-CSRFToken')];
    })();
    out.request_object = await run(new Request('https://app.example/riftbound/x', { method: 'POST', body: 'a' }));
    out.request_cross_origin = await run(new Request('https://evil.example/x', { method: 'POST', body: 'a' }));
    out.formdata_style_init_kept = await (async () => {
        calls.length = 0;
        const body = { marker: 'body' };
        await window.fetch('/riftbound/upload', { method: 'POST', body });
        return calls[0].init.body === body;
    })();
    console.log(JSON.stringify(out));
})();
"""


def run_harness(tmp_path, with_meta=True):
    harness = tmp_path / 'harness.js'
    harness.write_text(HARNESS, encoding='utf-8')
    done = subprocess.run(['node', str(harness), str(SCRIPT), 'meta' if with_meta else 'nometa'],
                          capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


@pytest.fixture
def result(tmp_path):
    return run_harness(tmp_path)


class TestWrapper:
    def test_fetch_is_wrapped(self, result):
        assert result['wrapped'] is True

    @pytest.mark.parametrize('key', ['same_origin_post', 'absolute_same_origin', 'request_object'])
    def test_same_origin_unsafe_requests_carry_the_token(self, result, key):
        assert result[key] == 'TOKEN123'

    @pytest.mark.parametrize('key', ['get', 'get_no_init', 'head'])
    def test_safe_methods_do_not(self, result, key):
        assert result[key] is None

    @pytest.mark.parametrize('key', ['cross_origin_post', 'protocol_relative_cross', 'other_port',
                                     'request_cross_origin'])
    def test_cross_origin_requests_never_get_the_token(self, result, key):
        assert result[key] is None

    def test_a_header_set_by_the_caller_wins(self, result):
        assert result['keeps_caller_header'] == 'MINE'

    def test_other_headers_and_the_body_are_kept(self, result):
        assert result['keeps_other_headers'] == ['application/json', 'TOKEN123']
        assert result['formdata_style_init_kept'] is True

    def test_without_the_meta_tag_fetch_is_left_alone(self, tmp_path):
        assert run_harness(tmp_path, with_meta=False)['wrapped'] is False
