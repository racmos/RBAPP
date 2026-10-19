import type { QueryClient } from '@tanstack/react-query';
import type { RouteObject } from 'react-router';
import { useTranslation } from 'react-i18next';
import { requireAnon, requireAuth } from '@/auth/guards';
import { Skeleton } from '@/components/ui/Skeleton';
import { NotFound } from '@/shell/NotFound';
import { HomePlaceholder } from './HomePlaceholder';
import { RouteError } from './RouteError';

/** Shown by the router while the loaders (session first) run, so nothing flashes (FAUTH-1). */
function LoadingScreen() {
  const { t } = useTranslation('common');
  return (
    <main
      style={{ display: 'grid', placeItems: 'center', minHeight: '100dvh', padding: 'var(--pad)' }}
    >
      <div style={{ width: 'min(320px, 100%)' }}>
        <Skeleton label={t('loadingRegion')} />
      </div>
    </main>
  );
}

type RouteOptions = { extraRoutes?: RouteObject[] };

/**
 * The route table (D13, basename `/riftbound/app`). Route modules load lazily; `altcha` lives
 * only in the register module (D22). Unit e wraps the guarded group in the app shell.
 */
export function createAppRoutes(
  queryClient: QueryClient,
  { extraRoutes = [] }: RouteOptions = {},
): RouteObject[] {
  return [
    {
      errorElement: <RouteError />,
      HydrateFallback: LoadingScreen,
      children: [
        {
          loader: requireAnon(queryClient),
          lazy: async () => ({ Component: (await import('@/auth/AuthLayout')).AuthLayout }),
          children: [
            {
              path: '/login',
              lazy: async () => ({ Component: (await import('@/auth/LoginPage')).LoginPage }),
            },
            {
              path: '/register',
              lazy: async () => ({ Component: (await import('@/auth/RegisterPage')).RegisterPage }),
            },
          ],
        },
        {
          loader: requireAuth(queryClient),
          children: [
            { path: '/', Component: HomePlaceholder },
            { path: '*', Component: NotFound },
          ],
        },
        ...extraRoutes,
      ],
    },
  ];
}
