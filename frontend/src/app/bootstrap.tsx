import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { createBrowserRouter } from 'react-router';
import { App } from './App';
import { installChunkReload } from './chunkReload';
import { createQueryClient } from './queryClient';
import { createAppRoutes } from './routes';
import { createI18n } from '@/i18n';
import { bootstrapPrefs } from '@/prefs';
import { listenForInstallPrompt } from '@/pwa';

export const BASENAME = '/riftbound/app';

type StartOptions = { reload?: () => void };

/**
 * Boot the app into `host` (D13, D18): the stored preferences are applied to `<html>` first (no
 * theme flash), then the install-prompt listener (the browser may fire `beforeinstallprompt`
 * before React renders), the language, the stale-chunk listener and the router. Returns a
 * function that tears everything down.
 */
export async function startApp(
  host: HTMLElement,
  { reload }: StartOptions = {},
): Promise<() => void> {
  bootstrapPrefs();
  const stopInstallListener = listenForInstallPrompt();
  const uninstallChunkReload = installChunkReload({ reload });
  const i18n = await createI18n();
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
    stopInstallListener();
  };
}
