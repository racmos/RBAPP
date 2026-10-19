import type { QueryClient } from '@tanstack/react-query';
import type { DataRouter } from 'react-router';
import { resetToAnonymous } from '@/auth/signOut';

const ANONYMOUS_SCREENS = new Set(['/login', '/register']);

/**
 * What a 401 from any API call does (FAUTH-7): drop everything of the user and go to
 * `/login?next=<where I was>`. A burst of concurrent 401s navigates once.
 */
export function createUnauthorizedHandler(
  router: DataRouter,
  queryClient: QueryClient,
): () => void {
  let handling = false;
  return () => {
    const { pathname, search } = router.state.location;
    if (handling || ANONYMOUS_SCREENS.has(stripBasename(router, pathname))) return;
    handling = true;
    resetToAnonymous(queryClient);
    const next = pathname.startsWith(basenameOf(router)) ? pathname : basenameOf(router) + pathname;
    void router.navigate(`/login?next=${encodeURIComponent(next + search)}`).finally(() => {
      handling = false;
    });
  };
}

const basenameOf = (router: DataRouter): string => router.basename ?? '';
const stripBasename = (router: DataRouter, pathname: string): string => {
  const basename = basenameOf(router);
  return basename && pathname.startsWith(basename)
    ? pathname.slice(basename.length) || '/'
    : pathname;
};
