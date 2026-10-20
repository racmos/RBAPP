import { fileURLToPath } from 'node:url';
import react from '@vitejs/plugin-react';
import { loadEnv } from 'vite';
import { VitePWA } from 'vite-plugin-pwa';
import { defineConfig } from 'vitest/config';
import { buildPwaOptions } from './pwa-options.ts';

// VITE_BASE: public path of the app (Flask serves the build at /riftbound/app/, D1).
// VITE_DEV_PROXY: Flask dev server that receives /riftbound/api and /riftbound/static.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_');
  const target = env.VITE_DEV_PROXY || 'http://127.0.0.1:5000';
  return {
    base: env.VITE_BASE || '/riftbound/app/',
    plugins: [react(), VitePWA(buildPwaOptions(env))],
    resolve: {
      alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
    },
    build: { sourcemap: false, emptyOutDir: true, manifest: true },
    server: {
      proxy: {
        '/riftbound/api': { target, changeOrigin: false },
        '/riftbound/static': { target, changeOrigin: false },
      },
    },
    test: {
      environment: 'jsdom',
      // The build plugin generates this module; tests mock it (src/pwa/*.test.tsx).
      alias: {
        'virtual:pwa-register/react': fileURLToPath(
          new URL('./src/test/pwa-register.ts', import.meta.url),
        ),
      },
      setupFiles: ['./src/test/setup.ts'],
      include: ['src/**/*.test.{ts,tsx}', 'scripts/**/*.test.ts', '*.test.ts'],
    },
  };
});
