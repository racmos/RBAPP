import { queryOptions } from '@tanstack/react-query';
import { ApiError } from '@/api/errors';
import { fetchSession } from '@/api/endpoints';
import type { Session } from '@/api/types';
import { clearSignedInHint, setSignedInHint } from './hint';

export const SESSION_STALE_MS = 5 * 60 * 1000;

/** No retry on 4xx or server answers; one retry when the network or the clock failed (D11). */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (!(error instanceof ApiError)) return false;
  return (error.kind === 'network' || error.kind === 'timeout') && failureCount < 1;
}

export const ANONYMOUS: Session = { authenticated: false, user: null, prefs: null };

/**
 * The single source of "who am I" (D11). Refetching on every focus picks up a logout made in a
 * Jinja page or another tab. The CSRF token is stored by `fetchSession`, not in this cache.
 */
export const sessionQuery = queryOptions({
  queryKey: ['session'] as const,
  queryFn: async (): Promise<Session> => {
    const session = await fetchSession();
    if (session.authenticated) setSignedInHint();
    else clearSignedInHint();
    return session;
  },
  staleTime: SESSION_STALE_MS,
  refetchOnWindowFocus: 'always',
  retry: shouldRetry,
});
