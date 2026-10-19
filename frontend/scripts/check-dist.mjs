// Checks a build output directory (CI-5, CI-9, DS-6). Node built-ins only.
//   node scripts/check-dist.mjs [dir]      (default: dist)
// Unit f adds the manifest, icon, service worker and altcha checks here.
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';

const dir = process.argv[2] ?? 'dist';
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

const problems = [];

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

if (problems.length > 0) {
  console.error(`check-dist failed for ${dir}:\n` + problems.map((p) => `  - ${p}`).join('\n'));
  process.exit(1);
}
console.log(`check-dist: ${dir} is clean`);
