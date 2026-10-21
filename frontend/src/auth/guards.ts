import type { QueryClient } from '@tanstack/react-query';
import { data, redirect, redirectDocument, type LoaderFunctionArgs } from 'react-router';
import { ApiError } from '@/api/errors';
import type { Session } from '@/api/types';
import { hasSignedInHint } from './hint';
import { markBootedOffline } from './offline';
import { safeNext } from './safeNext';
import { sessionQuery } from './session';
import { resetToAnonymous } from './signOut';

/** Route loaders (D13). They run before anything renders, so the login form never flashes. */
type Loader = (args: LoaderFunctionArgs) => Promise<null>;

/** `next` is always an absolute path (`/riftbound/app/...`), the same shape as Jinja's. */
const absolutePath = (request: Request): string => {
  const url = new URL(request.url);
  return url.pathname + url.search;
};

const unreachable = (error: unknown): boolean =>
  error instanceof ApiError && (error.kind === 'network' || error.kind === 'timeout');

export const requireAuth =
  (queryClient: QueryClient): Loader =>
  async ({ request }) => {
    const toLogin = () => redirect(`/login?next=${encodeURIComponent(absolutePath(request))}`);
    let session: Session;
    try {
      session = await queryClient.ensureQueryData(sessionQuery);
    } catch (error) {
      // PWA-7: the server cannot be reached. A browser that was signed in gets the shell from the
      // precache with the offline banner; one that was not gets the error screen with a retry.
      if (unreachable(error) && hasSignedInHint()) {
        markBootedOffline();
        return null;
      }
      // A 401 always means "sign in again", hint or not (FAUTH-7).
      if (error instanceof ApiError && error.status === 401) {
        resetToAnonymous(queryClient);
        throw toLogin();
      }
      throw error;
    }
    if (!session.authenticated) throw toLogin();
    return null;
  };

/** An authenticated user has no business on /login or /register: send them on (FAUTH-8). */
export const requireAnon =
  (queryClient: QueryClient): Loader =>
  async ({ request }) => {
    const session = await queryClient.ensureQueryData(sessionQuery);
    if (session.authenticated) {
      const target = safeNext(new URL(request.url).searchParams.get('next'));
      throw target.kind === 'router' ? redirect(target.to) : redirectDocument(target.href);
    }
    return null;
  };

/** UX only: the server stays the authority for admin actions. A non-admin sees the 404 view. */
export const requireAdmin =
  (queryClient: QueryClient): Loader =>
  async (args) => {
    await requireAuth(queryClient)(args);
    const session = await queryClient.ensureQueryData(sessionQuery);
    if (!session.user?.is_admin) throw data(null, { status: 404 });
    return null;
  };
