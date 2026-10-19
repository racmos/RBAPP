/*
 * CSRF wrapper for fetch (CSRF-3, D14).
 *
 * Adds the `X-CSRFToken` header (token from <meta name="csrf-token">) to every
 * same-origin request whose method is not safe, unless the caller already set
 * it. Cross-origin requests never get the token, so it cannot leak to another
 * site. Loaded from base.html's <head>, before any page script runs, so the
 * existing fetch call sites need no edits.
 */
(function () {
    'use strict';

    var meta = document.querySelector('meta[name="csrf-token"]');
    if (!meta || typeof window.fetch !== 'function') {
        return;
    }

    var HEADER = 'X-CSRFToken';
    var SAFE_METHODS = { GET: true, HEAD: true, OPTIONS: true, TRACE: true };
    var nativeFetch = window.fetch;

    function isSameOrigin(url) {
        try {
            return new URL(url, window.location.href).origin === window.location.origin;
        } catch (e) {
            return false;
        }
    }

    window.fetch = function (input, init) {
        var request = (typeof Request !== 'undefined' && input instanceof Request) ? input : null;
        var method = String((init && init.method) || (request && request.method) || 'GET').toUpperCase();
        var url = request ? request.url : String(input);

        if (!SAFE_METHODS[method] && isSameOrigin(url)) {
            var headers = new Headers((init && init.headers) || (request && request.headers) || undefined);
            if (!headers.has(HEADER)) {
                headers.set(HEADER, meta.getAttribute('content'));
                init = Object.assign({}, init, { headers: headers });
            }
        }
        return nativeFetch.call(this, input, init);
    };
})();
