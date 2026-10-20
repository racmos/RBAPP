// Checks a build output directory (CI-5, CI-9, DS-6, PWA-1..3, PWA-5, FAUTH-3). Node built-ins only.
//   node scripts/check-dist.mjs [dir]                  (default: dist) a normal build
//   node scripts/check-dist.mjs --self-destroy [dir]   a build made with VITE_PWA_SELF_DESTROY=true
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';

const args = process.argv.slice(2);
const selfDestroy = args.includes('--self-destroy');
const dir = args.find((arg) => !arg.startsWith('--')) ?? 'dist';
const THIRD_PARTY_FONTS = /fonts\.(googleapis|gstatic)\.com/;
const LAYER_ORDER = ['reset', 'tokens', 'base', 'layout', 'components', 'utilities'];
const TEXT_FILES = /\.(html|css|js|mjs)$/;

function walk(root) {
  return readdirSync(root, { withFileTypes: true }).flatMap((entry) =>
    entry.isDirectory() ? walk(join(root, entry.name)) : [join(root, entry.name)],
  );
}

/** Layers fix their order where they first appear; it must match the order declared in styles/index.css. */
function layerOrderProblem(css) {
  const seen = [];
  for (const [, name] of css.matchAll(/@layer\s+([\w-]+)\s*[{;]/g)) {
    if (LAYER_ORDER.includes(name) && !seen.includes(name)) seen.push(name);
  }
  const expected = LAYER_ORDER.filter((name) => seen.includes(name));
  return seen.join() === expected.join()
    ? null
    : `cascade layers first appear as ${seen.join(', ')}`;
}

// Identity and scope of the installed app (PWA-1).
const BASE = '/riftbound/app/';
const EXPECTED_MANIFEST = {
  name: 'Rift Manager',
  short_name: 'Rift Manager',
  id: '/riftbound/',
  scope: '/riftbound/',
  start_url: BASE,
  display: 'standalone',
  theme_color: '#06222c',
  background_color: '#06222c',
};
const PNG_SIGNATURE = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

const problems = [];

const read = (name) => readFileSync(join(dir, name), 'utf8');

/** A path from the manifest or the HTML ("pwa.png", "/riftbound/app/pwa.png") as a file name in dist. */
const inDist = (url) => url.replace(BASE, '').replace(/^\//, '').split(/[?#]/)[0];

/** Width and height from the IHDR chunk of a PNG, or null when the file is not a PNG. */
function pngSize(name) {
  const bytes = readFileSync(join(dir, name));
  if (bytes.length < 24 || !bytes.subarray(0, 8).equals(PNG_SIGNATURE)) return null;
  if (bytes.subarray(12, 16).toString('latin1') !== 'IHDR') return null;
  return { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) };
}

/** Checks that `name` is a PNG of exactly `width`x`height`; reports under `label`. */
function checkPng(name, label, width, height) {
  if (!existsSync(join(dir, name))) return problems.push(`${label}: ${name} does not exist`);
  const size = pngSize(name);
  if (!size) return problems.push(`${label}: ${name} is not a PNG`);
  if (size.width !== width || size.height !== height)
    problems.push(`${label}: ${name} is ${size.width}x${size.height}, declared ${width}x${height}`);
}

/** Attributes of every `<tag ...>` in the HTML, lower-cased names. */
function tags(html, tag) {
  return [...html.matchAll(new RegExp(`<${tag}\\b([^>]*)>`, 'gi'))].map(([, attrs]) =>
    Object.fromEntries(
      [...attrs.matchAll(/([\w:-]+)\s*=\s*"([^"]*)"/g)].map(([, name, value]) => [
        name.toLowerCase(),
        value,
      ]),
    ),
  );
}

function checkManifest() {
  const file = 'manifest.webmanifest';
  if (!existsSync(join(dir, file))) return problems.push(`${file} is missing`);
  let manifest;
  try {
    manifest = JSON.parse(read(file));
  } catch {
    return problems.push(`${file} is not valid JSON`);
  }
  for (const [field, expected] of Object.entries(EXPECTED_MANIFEST)) {
    if (manifest[field] !== expected)
      problems.push(
        `${file}: ${field} is ${JSON.stringify(manifest[field])}, expected "${expected}"`,
      );
  }
  if (!manifest.categories?.includes?.('games'))
    problems.push(`${file}: categories must contain "games"`);
  if (!String(manifest.start_url).startsWith(String(manifest.scope)))
    problems.push(
      `${file}: start_url ${manifest.start_url} is outside the scope ${manifest.scope}`,
    );

  // Icons (PWA-2): declared sizes equal the real PNG size; 192 and 512 for any; a 512 maskable.
  const icons = Array.isArray(manifest.icons) ? manifest.icons : [];
  const has = (sizes, purpose) =>
    icons.some(
      (icon) => icon.sizes === sizes && (icon.purpose ?? 'any').split(/\s+/).includes(purpose),
    );
  for (const sizes of ['192x192', '512x512'])
    if (!has(sizes, 'any')) problems.push(`${file}: no ${sizes} icon with purpose "any"`);
  if (!has('512x512', 'maskable'))
    problems.push(`${file}: no 512x512 icon with purpose "maskable"`);
  for (const icon of icons) {
    const match = /^(\d+)x(\d+)$/.exec(icon.sizes ?? '');
    if (!match) problems.push(`${file}: icon ${icon.src} has no single size`);
    else checkPng(inDist(icon.src), `${file} icon`, Number(match[1]), Number(match[2]));
  }
}

function checkHead() {
  if (!existsSync(join(dir, 'index.html'))) return;
  const html = read('index.html');
  const where = 'index.html';
  const meta = (name) => tags(html, 'meta').find((tag) => tag.name === name);
  const link = (rel) => tags(html, 'link').filter((tag) => tag.rel === rel);

  if (link('manifest').length === 0) problems.push(`${where}: no <link rel="manifest">`);
  if (meta('theme-color')?.content !== '#06222c')
    problems.push(`${where}: theme-color must be #06222c`);
  if (!/<title>\s*Rift Manager\s*<\/title>/.test(html))
    problems.push(`${where}: the title must be "Rift Manager"`);
  if (meta('apple-mobile-web-app-title')?.content !== 'Rift Manager')
    problems.push(`${where}: apple-mobile-web-app-title must be "Rift Manager"`);
  if (!meta('apple-mobile-web-app-capable'))
    problems.push(`${where}: apple-mobile-web-app-capable is missing`);

  const touch = link('apple-touch-icon')[0];
  if (!touch) problems.push(`${where}: no <link rel="apple-touch-icon">`);
  else checkPng(inDist(touch.href ?? ''), `${where} apple-touch-icon`, 180, 180);
  for (const favicon of ['favicon.ico', 'favicon.svg'])
    if (!existsSync(join(dir, favicon))) problems.push(`${favicon} is missing`);
}

function checkServiceWorker() {
  if (!existsSync(join(dir, 'sw.js'))) return problems.push('sw.js is missing');
  const sw = read('sw.js');

  const precache = [...sw.matchAll(/\burl:\s*"([^"]*)"/g)].map(([, url]) => url);
  const has = (pattern) => precache.some((url) => pattern.test(inDist(url)));
  if (!has(/^index\.html$/)) problems.push('sw.js: the precache lacks index.html');
  for (const size of ['1920', '1280'])
    if (!has(new RegExp(`(^|/)new_rift-${size}[-.]`)))
      problems.push(`sw.js: the precache lacks the background image new_rift-${size}`);
  for (const url of precache)
    if (/riftbound\/api/.test(url))
      problems.push(`sw.js: precache URL ${url} is under /riftbound/api`);

  // No runtime caching: the only route is the navigation fallback (F1 is read-only offline).
  for (const match of sw.matchAll(/registerRoute\(/g)) {
    const rest = sw.slice(match.index + match[0].length);
    if (!/^new\s+(\w+\.)?NavigationRoute\(/.test(rest))
      problems.push(
        'sw.js: registerRoute for something other than the navigation route (runtime caching)',
      );
  }
  const navigation = sw.indexOf('NavigationRoute(');
  if (navigation < 0) return problems.push('sw.js: the navigation route is missing');
  const options = sw.slice(navigation);
  const allow = /allowlist:\[(.*?)\](?=[,}])/.exec(options)?.[1];
  if (allow !== '/^\\/riftbound\\/app\\//')
    problems.push('sw.js: the navigation allowlist must be only /^\\/riftbound\\/app\\//');
  const deny = options.slice(Math.max(options.indexOf('denylist:'), 0));
  if (!deny.startsWith('denylist:')) problems.push('sw.js: the navigation denylist is missing');
  else
    for (const area of ['api', 'static'])
      if (!deny.includes(`\\/riftbound\\/${area}\\/`))
        problems.push(`sw.js: the navigation denylist does not cover /riftbound/${area}/`);
}

/** FAUTH-3: the register page, and altcha with it, is loaded lazily and never by the entry chunk. */
function checkAltchaIsLazy() {
  const file = '.vite/manifest.json';
  if (!existsSync(join(dir, file)))
    return problems.push(`${file} is missing (build.manifest), so FAUTH-3 cannot be checked`);
  const chunks = JSON.parse(read(file));
  const seen = new Set();
  const visit = (key) => {
    if (seen.has(key) || !chunks[key]) return;
    seen.add(key);
    (chunks[key].imports ?? []).forEach(visit);
  };
  Object.entries(chunks)
    .filter(([, chunk]) => chunk.isEntry)
    .forEach(([key]) => visit(key));
  for (const key of seen) {
    const chunk = chunks[key];
    const path = join(dir, chunk.file);
    const defines =
      existsSync(path) && /define\(\s*[`'"]altcha-widget[`'"]/.test(readFileSync(path, 'utf8'));
    if (defines || /node_modules\/altcha/.test(key))
      problems.push(`${chunk.file}: the entry chunk statically imports altcha (FAUTH-3)`);
  }
}

/** PWA-5: the rollback worker unregisters itself, clears the caches and precaches nothing. */
function checkSelfDestroyingWorker() {
  if (!existsSync(join(dir, 'sw.js'))) return problems.push('sw.js is missing');
  const sw = read('sw.js');
  if (!/\.unregister\(/.test(sw)) problems.push('sw.js: does not unregister itself');
  if (!/caches\.keys\(/.test(sw) || !/caches\.delete\(/.test(sw))
    problems.push('sw.js: does not clear the caches');
  if (/precacheAndRoute|revision\s*:/.test(sw))
    problems.push('sw.js: still has a precache manifest');
}

if (!existsSync(join(dir, 'index.html'))) {
  problems.push('index.html is missing');
}

if (existsSync(dir)) {
  for (const file of walk(dir)) {
    const name = relative(dir, file);
    const base = name.split('/').pop();
    if (name.endsWith('.map')) problems.push(`${name}: source maps must not be shipped`);
    if (base === '.env' || base.startsWith('.env.'))
      problems.push(`${name}: environment files must not be shipped`);
    if (!TEXT_FILES.test(name)) continue;
    const text = readFileSync(file, 'utf8');
    if (THIRD_PARTY_FONTS.test(text)) problems.push(`${name}: references a third-party font host`);
    const layers = name.endsWith('.css') ? layerOrderProblem(text) : null;
    if (layers) problems.push(`${name}: ${layers}`);
  }
} else {
  problems.push(`${dir} does not exist`);
}

if (existsSync(dir)) {
  if (selfDestroy) checkSelfDestroyingWorker();
  else {
    checkManifest();
    checkHead();
    checkServiceWorker();
    checkAltchaIsLazy();
  }
}

if (problems.length > 0) {
  console.error(`check-dist failed for ${dir}:\n` + problems.map((p) => `  - ${p}`).join('\n'));
  process.exit(1);
}
console.log(`check-dist: ${dir} is clean`);
