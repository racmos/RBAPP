import { render } from '@testing-library/react';
import type { QueryClient } from '@tanstack/react-query';
import type { DataRouter, RouteObject } from 'react-router';
import { createMemoryRouter } from 'react-router';
import { App } from '@/app/App';
import { createQueryClient } from '@/app/queryClient';
import { createAppRoutes } from '@/app/routes';
import { createI18n, type Lang } from '@/i18n';
import { setViewport } from './viewport';

export const BASENAME = '/riftbound/app';

type Options = {
  /** Path inside the app, for example `/login` (the basename is added). */
  path?: string;
  lang?: Lang;
  /** Viewport width in px; defaults to a desktop. */
  width?: number;
  /** Routes added next to the real ones (test-only pages); they get the query client. */
  extraRoutes?: (queryClient: QueryClient) => RouteObject[];
  /** Test-only pages inside the app shell (and its error boundary), next to the real ones. */
  shellRoutes?: (queryClient: QueryClient) => RouteObject[];
};

export type RenderedApp = ReturnType<typeof render> & {
  router: DataRouter;
  queryClient: QueryClient;
  i18n: Awaited<ReturnType<typeof createI18n>>;
  /** The router location without the basename, e.g. `/login?next=...`. */
  where: () => string;
};

/** The whole app (router, query cache, i18n, toasts) on a memory history, fed by MSW. */
export async function renderApp({
  path = '/',
  lang = 'es',
  width,
  extraRoutes,
  shellRoutes,
}: Options = {}): Promise<RenderedApp> {
  if (width !== undefined) setViewport(width);
  const queryClient = createQueryClient();
  const i18n = await createI18n(lang);
  const router = createMemoryRouter(
    createAppRoutes(queryClient, {
      extraRoutes: extraRoutes?.(queryClient),
      shellRoutes: shellRoutes?.(queryClient),
    }),
    {
      initialEntries: [`${BASENAME}${path}`],
      basename: BASENAME,
    },
  );
  const result = render(<App router={router} queryClient={queryClient} i18n={i18n} />);
  const where = () => {
    const { pathname, search } = router.state.location;
    return (
      (pathname.startsWith(BASENAME) ? pathname.slice(BASENAME.length) || '/' : pathname) + search
    );
  };
  return { ...result, router, queryClient, i18n, where };
}
