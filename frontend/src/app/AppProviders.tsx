import { QueryClientProvider, type QueryClient } from '@tanstack/react-query';
import type { i18n as I18n } from 'i18next';
import { useEffect, type ReactNode } from 'react';
import { I18nextProvider } from 'react-i18next';
import type { DataRouter } from 'react-router';
import { setUnauthorizedHandler } from '@/api/client';
import { LiveAnnouncer } from '@/components/ui/LiveAnnouncer';
import { ToastStack } from '@/components/ui/Toast';
import { PrefsProvider } from '@/prefs';
import { UpdateToast } from '@/pwa';
import { createUnauthorizedHandler } from './unauthorized';

type AppProvidersProps = {
  router: DataRouter;
  queryClient: QueryClient;
  i18n: I18n;
  children: ReactNode;
};

/** Everything the screens share: query cache, translations, preferences, live region, toasts, update prompt, 401 hook. */
export function AppProviders({ router, queryClient, i18n, children }: AppProvidersProps) {
  useEffect(() => {
    setUnauthorizedHandler(createUnauthorizedHandler(router, queryClient));
    return () => setUnauthorizedHandler(null);
  }, [router, queryClient]);

  return (
    <QueryClientProvider client={queryClient}>
      <I18nextProvider i18n={i18n}>
        <PrefsProvider>
          {children}
          <LiveAnnouncer />
          <ToastStack />
          <UpdateToast />
        </PrefsProvider>
      </I18nextProvider>
    </QueryClientProvider>
  );
}
