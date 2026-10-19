// @vitest-environment node
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const root = fileURLToPath(new URL('../../', import.meta.url));
const read = (file: string) => readFileSync(root + file, 'utf8');

type Manifest = {
  engines?: { node?: string };
  scripts?: Record<string, string>;
  dependencies?: Record<string, string>;
  devDependencies?: Record<string, string>;
};
const pkg = JSON.parse(read('package.json')) as Manifest;
const deps: Record<string, string> = { ...pkg.dependencies, ...pkg.devDependencies };

// DS-10: required now (the packages every unit-a feature stands on).
const REQUIRED: Record<string, string> = {
  react: '19.3.0',
  'react-dom': '19.3.0',
  vite: '8.3.2',
  '@vitejs/plugin-react': '6.1.1',
  typescript: '6.0.3',
};
// DS-10: pinned for later units; checked only once they are installed.
const EXPECTED_IF_PRESENT: Record<string, string> = {
  'react-router': '8.4.0',
  'vite-plugin-pwa': '1.3.0',
  'workbox-window': '7.4.1',
  altcha: '2.3.0',
};
const REQUIRED_PACKAGES = ['@fontsource-variable/manrope', '@fontsource-variable/space-grotesk'];
const REQUIRED_SCRIPTS = [
  'dev',
  'build',
  'preview',
  'lint',
  'typecheck',
  'test',
  'icons',
  'brand:trace',
  'check:dist',
];

describe('exact pins (DS-10)', () => {
  it('has no range specifier on any dependency', () => {
    const names = Object.keys(deps);
    expect(names.length).toBeGreaterThan(10);
    const ranged = Object.entries(deps).filter(([, v]) => /^[\^~>]/.test(v));
    expect(ranged).toEqual([]);
  });

  it('accepts only exact x.y.z versions', () => {
    const inexact = Object.entries(deps).filter(([, v]) => !/^\d+\.\d+\.\d+$/.test(v));
    expect(inexact).toEqual([]);
  });

  it.each(Object.entries(REQUIRED))('pins %s to %s', (name, version) => {
    expect(deps[name]).toBe(version);
  });

  it.each(REQUIRED_PACKAGES)('depends on %s', (name) => {
    expect(deps[name]).toMatch(/^\d+\.\d+\.\d+$/);
  });

  it.each(Object.entries(EXPECTED_IF_PRESENT))('pins %s to %s when installed', (name, version) => {
    if (name in deps) expect(deps[name]).toBe(version);
  });

  it('keeps TanStack Query on an exact version when installed', () => {
    const version = deps['@tanstack/react-query'];
    if (version !== undefined) expect(version).toMatch(/^5\.\d+\.\d+$/);
  });
});

describe('toolchain files (DS-10)', () => {
  it('configures npm to save exact versions and enforce engines (R8)', () => {
    const npmrc = read('.npmrc');
    expect(npmrc).toMatch(/^save-exact=true$/m);
    expect(npmrc).toMatch(/^engine-strict=true$/m);
  });

  it('declares the Node engine floor', () => {
    expect(pkg.engines?.node).toBe('>=22.22');
  });

  it.each(REQUIRED_SCRIPTS)('has the %s script', (script) => {
    expect(pkg.scripts?.[script]).toBeTruthy();
  });

  it('builds with tsc -b then vite build', () => {
    expect(pkg.scripts?.build).toBe('tsc -b && vite build');
  });

  it('commits a lockfile', () => {
    expect(existsSync(root + 'package-lock.json')).toBe(true);
  });

  it('uses the pinned versions in the lockfile', () => {
    const lock = JSON.parse(read('package-lock.json')) as {
      packages: Record<string, { version?: string }>;
    };
    for (const [name, version] of Object.entries(REQUIRED)) {
      expect(lock.packages[`node_modules/${name}`]?.version).toBe(version);
    }
  });
});
