import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { createBrowserRouter } from 'react-router';
import { App } from './App';
import { installChunkReload } from './chunkReload';
import { createQueryClient } from './queryClient';
import { createAppRoutes } from './routes';
import { BG_DEFAULT_PERCENT, applyBackground } from '@/lib/background';
import { createI18n, initialLang } from '@/i18n';

export const BASENAME = '/riftbound/app';

type StartOptions = { reload?: () => void };

/**
 * Boot the app into `host` (D13, D18): language from `rb_lang` or the browser, the background
 * layer, the stale-chunk listener, then the router. The preferences bootstrap that precedes
 * this arrives with unit e. Returns a function that tears everything down.
 */
export async function startApp(
  host: HTMLElement,
  { reload }: StartOptions = {},
): Promise<() => void> {
  applyBackground(document.documentElement, BG_DEFAULT_PERCENT);
  const uninstallChunkReload = installChunkReload({ reload });
  const i18n = await createI18n(initialLang());
  const queryClient = createQueryClient();
  const router = createBrowserRouter(createAppRoutes(queryClient), { basename: BASENAME });

  const root = createRoot(host);
  root.render(
    <StrictMode>
      <App router={router} queryClient={queryClient} i18n={i18n} />
    </StrictMode>,
  );

  return () => {
    root.unmount();
    router.dispose();
    queryClient.clear();
    uninstallChunkReload();
  };
}
