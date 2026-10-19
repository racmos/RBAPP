import type { QueryClient } from '@tanstack/react-query';
import { clearCsrfToken } from '@/api/csrf';
import { clearSignedInHint } from './hint';
import { ANONYMOUS, sessionQuery } from './session';

/**
 * Forget everything that belongs to the signed-in user (FAUTH-5, FAUTH-7): the query cache, the
 * was-signed-in hint and the CSRF token, then record an anonymous session so guards agree.
 */
export function resetToAnonymous(queryClient: QueryClient): void {
  queryClient.clear();
  clearSignedInHint();
  clearCsrfToken();
  queryClient.setQueryData(sessionQuery.queryKey, ANONYMOUS);
}
