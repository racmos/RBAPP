// Options of vite-plugin-pwa (D23, PWA-1..5), kept apart from vite.config.ts so a test can read them.
import type { VitePWAOptions } from 'vite-plugin-pwa';

const BRAND_COLOR = '#06222c';
const SCOPE = '/riftbound/';
const START_URL = '/riftbound/app/';

// Fontsource ships every unicode subset as its own file; only latin and latin-ext are imported
// (fonts.css), the rest must never reach the precache. `-cyrillic-` also covers `-cyrillic-ext-`.
const UNUSED_FONT_SUBSETS = ['cyrillic', 'greek', 'vietnamese', 'math', 'symbols'];

type PwaEnv = { VITE_PWA_SELF_DESTROY?: string };

/**
 * `VITE_PWA_SELF_DESTROY=true` builds a service worker that unregisters itself and clears its
 * caches on every client: the rollback of the PWA (PWA-5). A plain revert would leave the old
 * worker installed.
 */
export function buildPwaOptions(env: PwaEnv): Partial<VitePWAOptions> {
  return {
    strategies: 'generateSW',
    registerType: 'prompt',
    // Registration is done by pwa/useUpdatePrompt.ts through `virtual:pwa-register/react`.
    injectRegister: false,
    selfDestroying: env.VITE_PWA_SELF_DESTROY === 'true',
    devOptions: { enabled: false },
    // The workbox glob already precaches every icon and favicon in dist; listing them here as
    // well (includeAssets, manifest icons) put each URL twice in the precache (F1 unit g).
    includeManifestIcons: false,
    manifest: {
      name: 'Rift Manager',
      short_name: 'Rift Manager',
      id: SCOPE,
      // Wider than the service worker scope (/riftbound/app/): the installed window may still
      // open the legacy Jinja pages, which the worker never controls.
      scope: SCOPE,
      start_url: START_URL,
      display: 'standalone',
      lang: 'es',
      theme_color: BRAND_COLOR,
      background_color: BRAND_COLOR,
      categories: ['games'],
      icons: [
        { src: 'pwa-192x192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
        { src: 'pwa-512x512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
        {
          src: 'maskable-icon-512x512.png',
          sizes: '512x512',
          type: 'image/png',
          purpose: 'maskable',
        },
      ],
    },
    workbox: {
      // No `webmanifest`: the plugin adds manifest.webmanifest to the precache itself.
      globPatterns: ['**/*.{js,css,html,svg,png,ico,webp,woff2}'],
      globIgnores: [...UNUSED_FONT_SUBSETS.map((subset) => `**/*-${subset}-*.woff2`), '**/*.map'],
      navigateFallback: `${START_URL}index.html`,
      navigateFallbackAllowlist: [/^\/riftbound\/app\//],
      // API and static files are never answered with the shell; neither is anything that looks
      // like a file (a missing asset must stay a 404, HOST-3). Legacy Jinja pages are outside the
      // worker scope by construction.
      navigateFallbackDenylist: [
        /^\/riftbound\/api\//,
        /^\/riftbound\/static\//,
        /\/[^/?]+\.[A-Za-z0-9]{1,8}$/,
      ],
      cleanupOutdatedCaches: true,
      // Prompt mode: a new worker waits until the user accepts (PWA-4).
      skipWaiting: false,
      clientsClaim: false,
      maximumFileSizeToCacheInBytes: 3 * 1024 * 1024,
    },
  };
}
