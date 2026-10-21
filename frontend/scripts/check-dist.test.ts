// @vitest-environment node
import { spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { crc32 } from 'node:zlib';
import { describe, expect, it } from 'vitest';

const script = fileURLToPath(new URL('./check-dist.mjs', import.meta.url));

/** Smallest PNG the checker can read: signature plus an IHDR chunk with the given size. */
function png(width: number, height: number) {
  const ihdr = Buffer.alloc(25);
  ihdr.writeUInt32BE(13, 0);
  ihdr.write('IHDR', 4, 'ascii');
  ihdr.writeUInt32BE(width, 8);
  ihdr.writeUInt32BE(height, 12);
  ihdr.writeUInt32BE(crc32(ihdr.subarray(4, 21)), 21);
  return Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), ihdr]);
}

const MANIFEST = {
  name: 'Rift Manager',
  short_name: 'Rift Manager',
  id: '/riftbound/',
  scope: '/riftbound/',
  start_url: '/riftbound/app/',
  display: 'standalone',
  theme_color: '#06222c',
  background_color: '#06222c',
  categories: ['games'],
  icons: [
    { src: 'pwa-192x192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
    { src: 'pwa-512x512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
    { src: 'maskable-icon-512x512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
  ],
};

const INDEX = `<!doctype html><html lang="es"><head>
<meta charset="UTF-8" />
<meta name="theme-color" content="#06222c" />
<meta name="apple-mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-title" content="Rift Manager" />
<title>Rift Manager</title>
<link rel="icon" href="/riftbound/app/favicon.ico" sizes="48x48" />
<link rel="icon" href="/riftbound/app/favicon.svg" type="image/svg+xml" />
<link rel="apple-touch-icon" href="/riftbound/app/apple-touch-icon-180x180.png" />
<link rel="manifest" href="/riftbound/app/manifest.webmanifest" />
</head><body><div id="root"></div></body></html>`;

/** What the Workbox generateSW output looks like (trimmed): precache list plus the navigation route. */
function serviceWorker({
  precache = [
    'index.html',
    'assets/index-abc.js',
    'assets/new_rift-1920-abc.webp',
    'assets/new_rift-1280-abc.webp',
  ],
  routes = `s.registerRoute(new s.NavigationRoute(s.createHandlerBoundToURL("/riftbound/app/index.html"),{allowlist:[/^\\/riftbound\\/app\\//],denylist:[/^\\/riftbound\\/api\\//,/^\\/riftbound\\/static\\//,/\\/[^/?]+\\.[A-Za-z0-9]{1,8}$/]}))`,
} = {}) {
  const entries = precache.map((url) => `{url:"${url}",revision:null}`).join(',');
  return `define(["./workbox-1"],function(s){"use strict";s.precacheAndRoute([${entries}],{}),s.cleanupOutdatedCaches(),${routes}});`;
}

const SELF_DESTROYING_SW = `self.addEventListener('install', (e) => { self.skipWaiting(); });
self.addEventListener('activate', (e) => {
  self.registration.unregister().then(() => self.clients.matchAll()).then(() => {
    self.caches.keys().then((names) => Promise.all(names.map((n) => self.caches.delete(n))));
  });
});`;

/** `.vite/manifest.json` of a build whose entry statically imports only `vendor`. */
const VITE_MANIFEST = {
  'index.html': {
    file: 'assets/index-abc.js',
    isEntry: true,
    imports: ['_vendor-abc.js'],
    dynamicImports: ['src/auth/RegisterPage.tsx'],
  },
  '_vendor-abc.js': { file: 'assets/vendor-abc.js' },
  'src/auth/RegisterPage.tsx': {
    file: 'assets/RegisterPage-abc.js',
    imports: ['_vendor-abc.js', 'index.html'],
  },
};

const VALID: Record<string, string | Buffer> = {
  'index.html': INDEX,
  'manifest.webmanifest': JSON.stringify(MANIFEST),
  'pwa-192x192.png': png(192, 192),
  'pwa-512x512.png': png(512, 512),
  'maskable-icon-512x512.png': png(512, 512),
  'apple-touch-icon-180x180.png': png(180, 180),
  'favicon.ico': 'ico',
  'favicon.svg': '<svg xmlns="http://www.w3.org/2000/svg"/>',
  'sw.js': serviceWorker(),
  'workbox-1.js': '//workbox',
  'assets/index-abc.js': 'console.log("app")',
  'assets/vendor-abc.js': 'export const react = 1',
  'assets/RegisterPage-abc.js': 'customElements.define(`altcha-widget`, class {})',
  '.vite/manifest.json': JSON.stringify(VITE_MANIFEST),
};

/** A complete valid build with `files` laid over it; a `null` value removes the file. */
function dist(files: Record<string, string | Buffer | null> = {}) {
  const dir = mkdtempSync(join(tmpdir(), 'dist-'));
  for (const [name, content] of Object.entries({ ...VALID, ...files })) {
    if (content === null) continue;
    mkdirSync(dirname(join(dir, name)), { recursive: true });
    writeFileSync(join(dir, name), content);
  }
  return dir;
}

const run = (dir: string, ...flags: string[]) =>
  spawnSync('node', [script, ...flags, dir], { encoding: 'utf8' });

/** The manifest with some fields replaced. */
const withManifest = (changes: Record<string, unknown>) =>
  JSON.stringify({ ...MANIFEST, ...changes });

describe('check-dist.mjs (CI-5, CI-9, DS-6)', () => {
  it('passes a complete valid build', () => {
    const result = run(dist());
    expect(result.stderr).toBe('');
    expect(result.status).toBe(0);
  });

  it('passes with hashed assets that reference no third-party host', () => {
    const result = run(
      dist({ 'assets/app-abc.js': 'console.log("hi")', 'assets/app-abc.css': 'body{color:red}' }),
    );
    expect(result.status).toBe(0);
  });

  it('fails when index.html is missing', () => {
    const result = run(dist({ 'index.html': null }));
    expect(result.status).toBe(1);
    expect(result.stderr).toContain('index.html');
  });

  it('fails on a source map, even in a subfolder', () => {
    const result = run(dist({ 'assets/app.js.map': '{}' }));
    expect(result.status).toBe(1);
    expect(result.stderr).toContain('assets/app.js.map');
  });

  it('fails on a .env file', () => {
    const result = run(dist({ '.env': 'SECRET=1' }));
    expect(result.status).toBe(1);
    expect(result.stderr).toContain('.env');
  });

  it.each([
    [
      'index.html',
      'index.html',
      INDEX + '<link href="https://fonts.googleapis.com/css2?family=Manrope">',
    ],
    ['a css file', 'assets/a.css', '@import url(https://fonts.gstatic.com/s/x.woff2);'],
    ['a js file', 'assets/a.js', 'fetch("https://fonts.googleapis.com/css")'],
  ])('fails on a Google Fonts reference in %s', (_label, file, content) => {
    const result = run(dist({ [file]: content }));
    expect(result.status).toBe(1);
    expect(result.stderr).toContain(file);
    expect(result.stderr).toContain('third-party font');
  });

  it('passes when the cascade layers first appear in the declared order (D15)', () => {
    const css =
      '@layer reset{a{b:c}}@layer tokens{a{b:c}}@layer base{a{b:c}}@layer layout;@layer components{a{b:c}}@layer reset{a{b:c}}';
    expect(run(dist({ 'assets/a.css': css })).status).toBe(0);
  });

  it('fails when a layer first appears before one that must precede it', () => {
    // a component module imported before the stylesheet fixes the wrong order
    const css = '@layer components{a{b:c}}@layer reset{a{b:c}}';
    const result = run(dist({ 'assets/a.css': css }));
    expect(result.status).toBe(1);
    expect(result.stderr).toContain('assets/a.css');
    expect(result.stderr).toContain('layer');
  });

  it('fails when the directory does not exist', () => {
    const result = run(join(tmpdir(), 'dist-does-not-exist'));
    expect(result.status).toBe(1);
  });
});

describe('manifest (CI-5 "Manifest check", PWA-1)', () => {
  it('fails when manifest.webmanifest is missing', () => {
    const result = run(dist({ 'manifest.webmanifest': null }));
    expect(result.status).toBe(1);
    expect(result.stderr).toContain('manifest.webmanifest');
  });

  it('fails on a manifest that is not JSON', () => {
    const result = run(dist({ 'manifest.webmanifest': '{nope' }));
    expect(result.status).toBe(1);
    expect(result.stderr).toContain('manifest.webmanifest');
  });

  it.each([
    ['name', { name: 'Riftbound Manager' }],
    ['short_name', { short_name: 'Riftbound' }],
    ['id', { id: '/riftbound/app/' }],
    ['scope', { scope: '/riftbound/app/' }],
    ['start_url', { start_url: '/riftbound/' }],
    ['display', { display: 'browser' }],
    ['theme_color', { theme_color: '#013951' }],
    ['background_color', { background_color: '#000000' }],
    ['categories', { categories: ['utilities'] }],
  ])('fails when %s has the wrong value', (field, change) => {
    const result = run(dist({ 'manifest.webmanifest': withManifest(change) }));
    expect(result.status).toBe(1);
    expect(result.stderr).toContain(field);
  });

  it('fails when start_url falls outside the scope', () => {
    const result = run(
      dist({
        'manifest.webmanifest': withManifest({ scope: '/other/', start_url: '/riftbound/app/' }),
      }),
    );
    expect(result.status).toBe(1);
    expect(result.stderr).toMatch(/start_url/);
  });
});

describe('icons (PWA-2)', () => {
  it('fails when a manifest icon file is missing', () => {
    const result = run(dist({ 'pwa-192x192.png': null }));
    expect(result.status).toBe(1);
    expect(result.stderr).toContain('pwa-192x192.png');
  });

  it('fails when the PNG size differs from the declared size', () => {
    const result = run(dist({ 'pwa-512x512.png': png(500, 500) }));
    expect(result.status).toBe(1);
    expect(result.stderr).toContain('pwa-512x512.png');
    expect(result.stderr).toMatch(/500x500/);
  });

  it('fails when an icon is not a PNG', () => {
    const result = run(dist({ 'pwa-192x192.png': 'not a png' }));
    expect(result.status).toBe(1);
    expect(result.stderr).toContain('pwa-192x192.png');
  });

  it('fails without a 512 maskable icon', () => {
    const icons = MANIFEST.icons.map((icon) => ({ ...icon, purpose: 'any' }));
    const result = run(dist({ 'manifest.webmanifest': withManifest({ icons }) }));
    expect(result.status).toBe(1);
    expect(result.stderr).toContain('maskable');
  });

  it('fails without 192 and 512 icons for purpose any', () => {
    const icons = MANIFEST.icons.filter((icon) => icon.sizes !== '192x192');
    const result = run(dist({ 'manifest.webmanifest': withManifest({ icons }) }));
    expect(result.status).toBe(1);
    expect(result.stderr).toContain('192x192');
  });

  it('fails when the apple-touch icon is missing or not 180x180', () => {
    const missing = run(dist({ 'apple-touch-icon-180x180.png': null }));
    expect(missing.status).toBe(1);
    expect(missing.stderr).toContain('apple-touch-icon');
    const wrong = run(dist({ 'apple-touch-icon-180x180.png': png(120, 120) }));
    expect(wrong.status).toBe(1);
    expect(wrong.stderr).toContain('apple-touch-icon');
  });

  it('fails when the favicons are missing', () => {
    expect(run(dist({ 'favicon.ico': null })).stderr).toContain('favicon.ico');
    expect(run(dist({ 'favicon.svg': null })).stderr).toContain('favicon.svg');
  });
});

describe('document head (PWA-1)', () => {
  const without = (pattern: RegExp) => INDEX.replace(pattern, '');

  it.each([
    ['the manifest link', /<link rel="manifest"[^>]*>/, 'manifest'],
    ['theme-color', /<meta name="theme-color"[^>]*>/, 'theme-color'],
    ['the title', /<title>[^<]*<\/title>/, 'title'],
    [
      'the apple title',
      /<meta name="apple-mobile-web-app-title"[^>]*>/,
      'apple-mobile-web-app-title',
    ],
    [
      'the apple capable tag',
      /<meta name="apple-mobile-web-app-capable"[^>]*>/,
      'apple-mobile-web-app-capable',
    ],
    ['the apple-touch-icon link', /<link rel="apple-touch-icon"[^>]*>/, 'apple-touch-icon'],
  ])('fails without %s', (_label, pattern, word) => {
    const result = run(dist({ 'index.html': without(pattern) }));
    expect(result.status).toBe(1);
    expect(result.stderr).toContain(word);
  });

  it('fails on another title or theme colour', () => {
    expect(
      run(dist({ 'index.html': INDEX.replace('<title>Rift Manager', '<title>Riftbound Manager') }))
        .status,
    ).toBe(1);
    expect(
      run(dist({ 'index.html': INDEX.replace('content="#06222c"', 'content="#013951"') })).status,
    ).toBe(1);
  });
});

describe('service worker (PWA-3)', () => {
  it('fails when sw.js is missing', () => {
    const result = run(dist({ 'sw.js': null }));
    expect(result.status).toBe(1);
    expect(result.stderr).toContain('sw.js');
  });

  it.each([
    [
      'index.html',
      ['assets/index-abc.js', 'assets/new_rift-1920-abc.webp', 'assets/new_rift-1280-abc.webp'],
    ],
    ['new_rift-1920', ['index.html', 'assets/new_rift-1280-abc.webp']],
    ['new_rift-1280', ['index.html', 'assets/new_rift-1920-abc.webp']],
  ])('fails when the precache lacks %s', (word, precache) => {
    const result = run(dist({ 'sw.js': serviceWorker({ precache }) }));
    expect(result.status).toBe(1);
    expect(result.stderr).toContain(word);
  });

  it.each(['/riftbound/api/v1/health', 'riftbound/api/v1/health'])(
    'fails when a precache URL is under the API (%s)',
    (url) => {
      const precache = [
        'index.html',
        'assets/new_rift-1920-a.webp',
        'assets/new_rift-1280-a.webp',
        url,
      ];
      const result = run(dist({ 'sw.js': serviceWorker({ precache }) }));
      expect(result.status).toBe(1);
      expect(result.stderr).toContain('/riftbound/api');
    },
  );

  it('fails when a route is registered for the API (runtime caching)', () => {
    const routes = `s.registerRoute(/\\/riftbound\\/api\\/.*/,new s.NetworkFirst({cacheName:"api"}),"GET")`;
    const result = run(dist({ 'sw.js': serviceWorker({ routes }) }));
    expect(result.status).toBe(1);
    expect(result.stderr).toContain('registerRoute');
  });

  it('fails when the navigation denylist does not cover the API and static paths', () => {
    const routes = `s.registerRoute(new s.NavigationRoute(s.createHandlerBoundToURL("/riftbound/app/index.html"),{allowlist:[/^\\/riftbound\\/app\\//]}))`;
    const result = run(dist({ 'sw.js': serviceWorker({ routes }) }));
    expect(result.status).toBe(1);
    expect(result.stderr).toContain('denylist');
  });

  it('fails when the navigation route allows more than /riftbound/app/', () => {
    const routes = `s.registerRoute(new s.NavigationRoute(s.createHandlerBoundToURL("/riftbound/app/index.html"),{allowlist:[/^\\/riftbound\\//],denylist:[/^\\/riftbound\\/api\\//,/^\\/riftbound\\/static\\//]}))`;
    const result = run(dist({ 'sw.js': serviceWorker({ routes }) }));
    expect(result.status).toBe(1);
    expect(result.stderr).toContain('allowlist');
  });
});

describe('altcha stays out of the entry chunk (FAUTH-3)', () => {
  it('fails when the entry chunk imports a chunk that defines the widget', () => {
    const result = run(
      dist({ 'assets/vendor-abc.js': 'customElements.define(`altcha-widget`, class {})' }),
    );
    expect(result.status).toBe(1);
    expect(result.stderr).toContain('altcha');
    expect(result.stderr).toContain('assets/vendor-abc.js');
  });

  it('fails when the entry chunk itself defines the widget', () => {
    const result = run(dist({ 'assets/index-abc.js': 'customElements.define("altcha-widget",1)' }));
    expect(result.status).toBe(1);
    expect(result.stderr).toContain('altcha');
  });

  it('passes when only a dynamically imported chunk has it', () => {
    expect(run(dist()).status).toBe(0);
  });

  it('fails when the Vite manifest is missing (the check could not run)', () => {
    const result = run(dist({ '.vite/manifest.json': null }));
    expect(result.status).toBe(1);
    expect(result.stderr).toContain('.vite/manifest.json');
  });
});

describe('--self-destroy (PWA-5)', () => {
  const destroying = (extra: Record<string, string | null> = {}) =>
    dist({ 'sw.js': SELF_DESTROYING_SW, 'workbox-1.js': null, ...extra });

  it('passes a self-destroying worker with no precache manifest', () => {
    const result = run(destroying(), '--self-destroy');
    expect(result.stderr).toBe('');
    expect(result.status).toBe(0);
  });

  it('fails on the normal worker (it has a precache manifest and no unregister)', () => {
    const result = run(dist(), '--self-destroy');
    expect(result.status).toBe(1);
    expect(result.stderr).toMatch(/unregister|precache/);
  });

  it('fails when the worker does not clear the caches', () => {
    const sw = SELF_DESTROYING_SW.replace(/self\.caches\.keys[^\n]*/, '');
    const result = run(destroying({ 'sw.js': sw }), '--self-destroy');
    expect(result.status).toBe(1);
    expect(result.stderr).toContain('caches');
  });

  it('fails when sw.js is missing', () => {
    const result = run(destroying({ 'sw.js': null }), '--self-destroy');
    expect(result.status).toBe(1);
    expect(result.stderr).toContain('sw.js');
  });

  it('does not require the manifest, icons or head of a full build', () => {
    const result = run(
      destroying({ 'manifest.webmanifest': null, 'pwa-192x192.png': null }),
      '--self-destroy',
    );
    expect(result.status).toBe(0);
  });
});
