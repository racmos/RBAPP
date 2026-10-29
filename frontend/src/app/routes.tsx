import type { QueryClient } from '@tanstack/react-query';
import { redirect, type RouteObject } from 'react-router';
import { useTranslation } from 'react-i18next';
import { requireAdmin, requireAnon, requireAuth } from '@/auth/guards';
import { Skeleton } from '@/components/ui/Skeleton';
import { AppShell } from '@/shell/AppShell';
import { HomeHub } from '@/shell/HomeHub';
import { NotFound } from '@/shell/NotFound';
import { ShellError } from '@/shell/ShellError';
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

const kitchenRoute: RouteObject = {
  path: '/_kitchen',
  lazy: async () => ({ Component: (await import('@/dev/KitchenSink')).KitchenSink }),
};

type RouteOptions = {
  /** Routes next to the shell (tests: a route guarded by `requireAdmin`). */
  extraRoutes?: RouteObject[];
  /** Routes inside the shell and its error boundary (tests: a page that throws). */
  shellRoutes?: RouteObject[];
};

/**
 * The route table (D13, basename `/riftbound/app`). Route modules load lazily; `altcha` lives
 * only in the register module (D22). Signed-in pages render inside `AppShell`; their errors
 * render inside it too (a pathless route carries the `errorElement`), so the topbar survives.
 */
export function createAppRoutes(
  queryClient: QueryClient,
  { extraRoutes = [], shellRoutes = [] }: RouteOptions = {},
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
          Component: AppShell,
          children: [
            {
              errorElement: <ShellError />,
              children: [
                { path: '/', Component: HomeHub },
                { path: '/account', loader: () => redirect('/account/interface') },
                {
                  path: '/account/interface',
                  lazy: async () => ({
                    Component: (await import('@/account/InterfacePage')).InterfacePage,
                  }),
                },
                {
                  path: '/cards',
                  lazy: async () => ({
                    Component: (await import('@/catalog/CatalogPage')).CatalogPage,
                  }),
                  children: [
                    {
                      path: ':setId/:cardId',
                      lazy: async () => ({
                        Component: (await import('@/catalog/CardDetailRoute')).CardDetailRoute,
                      }),
                    },
                  ],
                },
                {
                  path: '/collection',
                  lazy: async () => ({
                    Component: (await import('@/collection')).CollectionPage,
                  }),
                },
                {
                  path: '/collection/import',
                  lazy: async () => ({
                    Component: (await import('@/collection')).ImportWizard,
                  }),
                },
                {
                  path: '/admin',
                  loader: requireAdmin(queryClient),
                  lazy: async () => ({
                    Component: (await import('@/admin/AdminLayout')).AdminLayout,
                  }),
                  children: [
                    {
                      index: true,
                      lazy: async () => ({
                        Component: (await import('@/admin/OverviewPage')).OverviewPage,
                      }),
                    },
                    {
                      path: 'sets',
                      lazy: async () => ({
                        Component: (await import('@/admin/SetsPage')).SetsPage,
                      }),
                    },
                    {
                      path: 'cards',
                      lazy: async () => ({
                        Component: (await import('@/admin/CardsAdminPage')).CardsAdminPage,
                      }),
                    },
                    {
                      path: 'products',
                      lazy: async () => ({
                        Component: (await import('@/admin/ProductsAdminPage')).ProductsAdminPage,
                      }),
                    },
                    {
                      path: 'riot',
                      lazy: async () => ({
                        Component: (await import('@/admin/RiotPage')).RiotPage,
                      }),
                    },
                    {
                      path: 'riot/changes',
                      lazy: async () => ({
                        Component: (await import('@/admin/ChangesPage')).ChangesPage,
                      }),
                    },
                  ],
                },
                // Development only; Vite replaces the flag at build time and drops the branch.
                ...(import.meta.env.DEV ? [kitchenRoute] : []),
                ...shellRoutes,
                { path: '*', Component: NotFound },
              ],
            },
          ],
        },
        ...extraRoutes,
      ],
    },
  ];
}
