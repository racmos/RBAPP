import type { QueryClient } from '@tanstack/react-query';
import type { i18n as I18n } from 'i18next';
import type { DataRouter } from 'react-router';
import { RouterProvider } from 'react-router/dom';
import { AppProviders } from './AppProviders';

type AppProps = {
  router: DataRouter;
  queryClient: QueryClient;
  i18n: I18n;
};

export function App({ router, queryClient, i18n }: AppProps) {
  return (
    <AppProviders router={router} queryClient={queryClient} i18n={i18n}>
      <RouterProvider router={router} />
    </AppProviders>
  );
}
