import type { QueryClient } from '@tanstack/react-query';
import { data, redirect, redirectDocument, type LoaderFunctionArgs } from 'react-router';
import { sessionQuery } from './session';
import { safeNext } from './safeNext';

/** Route loaders (D13). They run before anything renders, so the login form never flashes. */
type Loader = (args: LoaderFunctionArgs) => Promise<null>;

/** `next` is always an absolute path (`/riftbound/app/...`), the same shape as Jinja's. */
const absolutePath = (request: Request): string => {
  const url = new URL(request.url);
  return url.pathname + url.search;
};

export const requireAuth =
  (queryClient: QueryClient): Loader =>
  async ({ request }) => {
    const session = await queryClient.ensureQueryData(sessionQuery);
    if (!session.authenticated) {
      throw redirect(`/login?next=${encodeURIComponent(absolutePath(request))}`);
    }
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
