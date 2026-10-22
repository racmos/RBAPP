// @vitest-environment node
import { describe, expect, it } from 'vitest';
import { buildPwaOptions } from './pwa-options.ts';

const options = buildPwaOptions({});
const workbox = options.workbox!;
const manifest = options.manifest as Record<string, unknown>;

const matches = (patterns: RegExp[] | undefined, path: string) =>
  (patterns ?? []).some((pattern) => pattern.test(path));

describe('registration (PWA-4, D23)', () => {
  it('uses generateSW in prompt mode, registered by the app and disabled in dev', () => {
    expect(options.strategies).toBe('generateSW');
    expect(options.registerType).toBe('prompt');
    expect(options.injectRegister).toBe(false);
    expect(options.devOptions?.enabled).toBe(false);
  });

  it('never takes control by itself', () => {
    expect(workbox.skipWaiting).toBe(false);
    expect(workbox.clientsClaim).toBe(false);
  });

  it('keeps the manifest in the build output file the Flask host serves', () => {
    expect(options.manifestFilename ?? 'manifest.webmanifest').toBe('manifest.webmanifest');
  });
});

describe('manifest (PWA-1)', () => {
  it('names the app Rift Manager', () => {
    expect(manifest.name).toBe('Rift Manager');
    expect(manifest.short_name).toBe('Rift Manager');
  });

  it('has an id and scope covering the legacy pages and a start_url inside the scope', () => {
    expect(manifest.id).toBe('/riftbound/');
    expect(manifest.scope).toBe('/riftbound/');
    expect(manifest.start_url).toBe('/riftbound/app/');
    expect(String(manifest.start_url).startsWith(String(manifest.scope))).toBe(true);
  });

  it('opens standalone on the brand colours, as a game', () => {
    expect(manifest.display).toBe('standalone');
    expect(manifest.theme_color).toBe('#06222c');
    expect(manifest.background_color).toBe('#06222c');
    expect(manifest.categories).toContain('games');
  });

  it('lists 192 and 512 icons, and a separate maskable 512 (PWA-2)', () => {
    const icons = manifest.icons as {
      src: string;
      sizes: string;
      type: string;
      purpose?: string;
    }[];
    const key = (icon: { sizes: string; purpose?: string }) =>
      `${icon.sizes}:${icon.purpose ?? 'any'}`;
    expect(icons.map(key).sort()).toEqual(['192x192:any', '512x512:any', '512x512:maskable']);
    for (const icon of icons) expect(icon.type).toBe('image/png');
  });
});

describe('workbox (PWA-3)', () => {
  it('falls back to the app shell only below /riftbound/app/', () => {
    expect(workbox.navigateFallback).toBe('/riftbound/app/index.html');
    const allow = workbox.navigateFallbackAllowlist;
    expect(matches(allow, '/riftbound/app/')).toBe(true);
    expect(matches(allow, '/riftbound/app/account/interface')).toBe(true);
    expect(matches(allow, '/riftbound/login')).toBe(false);
    expect(matches(allow, '/riftbound/api/v1/health')).toBe(false);
    expect(matches(allow, '/riftbound/appendix')).toBe(false);
  });

  it('denies API, static and file-like paths, and not the SPA routes', () => {
    const deny = workbox.navigateFallbackDenylist;
    expect(matches(deny, '/riftbound/api/x')).toBe(true);
    expect(matches(deny, '/riftbound/static/x')).toBe(true);
    expect(matches(deny, '/riftbound/app/a.js')).toBe(true);
    expect(matches(deny, '/riftbound/app/account')).toBe(false);
    expect(matches(deny, '/riftbound/app/account/interface')).toBe(false);
  });

  it('cleans outdated caches and registers no runtime caching', () => {
    expect(workbox.cleanupOutdatedCaches).toBe(true);
    expect(workbox.runtimeCaching).toBeUndefined();
  });

  it('precaches the app shell assets, capped at 3 MiB', () => {
    expect(workbox.maximumFileSizeToCacheInBytes).toBe(3 * 1024 * 1024);
    const patterns = workbox.globPatterns ?? [];
    expect(patterns).toHaveLength(1);
    for (const extension of ['js', 'css', 'html', 'svg', 'png', 'ico', 'webp', 'woff2']) {
      expect(patterns[0]).toContain(extension);
    }
  });

  it('lists each precache source once: the glob for files, the plugin for the manifest', () => {
    expect(options.includeAssets).toBeUndefined();
    expect(options.includeManifestIcons).toBe(false);
    expect(workbox.globPatterns?.[0]).not.toContain('webmanifest');
  });

  it('leaves out the non-latin font subsets and source maps', () => {
    const ignores = workbox.globIgnores ?? [];
    // enough of a glob matcher for the patterns used here: `**/` any folders, `*` within a name
    const toRegExp = (glob: string) =>
      new RegExp(
        '^' +
          glob
            .replace(/\./g, '\\.')
            .replace(/\*\*\//g, '\0')
            .replace(/\*/g, '[^/]*')
            .replace(/\0/g, '(.*/)?') +
          '$',
      );
    const ignored = (file: string) => ignores.some((glob) => toRegExp(glob).test(file));
    expect(ignored('assets/manrope-latin-wght-normal-abc.woff2')).toBe(false);
    expect(ignored('assets/manrope-latin-ext-wght-normal-abc.woff2')).toBe(false);
    expect(ignored('assets/space-grotesk-latin-wght-normal-abc.woff2')).toBe(false);
    for (const subset of ['cyrillic', 'cyrillic-ext', 'greek', 'vietnamese', 'math', 'symbols']) {
      expect(ignored(`assets/manrope-${subset}-wght-normal-abc.woff2`)).toBe(true);
    }
    expect(ignored('assets/app-abc.js.map')).toBe(true);
    expect(ignored('assets/new_rift-1920-abc.webp')).toBe(false);
  });
});

describe('self-destroying build (PWA-5)', () => {
  it('is off by default and follows VITE_PWA_SELF_DESTROY', () => {
    expect(options.selfDestroying).toBe(false);
    expect(buildPwaOptions({ VITE_PWA_SELF_DESTROY: 'false' }).selfDestroying).toBe(false);
    expect(buildPwaOptions({ VITE_PWA_SELF_DESTROY: 'true' }).selfDestroying).toBe(true);
  });
});
