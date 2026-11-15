import { queryOptions, type QueryClient } from '@tanstack/react-query';
import { getApiKey, getMe, getMetaConfig, listSessions } from '@/api/endpoints';
import type { MeData, ProfileData, Session, UserPayload } from '@/api/types';
import { sessionQuery } from '@/auth';

/** `GET /me` (F9-b S7): the private profile and the security summary. */
export const meQuery = queryOptions({
  queryKey: ['me'] as const,
  queryFn: ({ signal }) => getMe(signal),
});

/** `GET /me/sessions` (F9-j S9): under `['me']`, so refreshing `GET /me` refreshes it too. */
export const sessionsQuery = queryOptions({
  queryKey: ['me', 'sessions'] as const,
  queryFn: ({ signal }) => listSessions(signal),
});

/** `GET /me/api-key` (F9-j S10): the key's info, never the key. */
export const apiKeyQuery = queryOptions({
  queryKey: ['me', 'api-key'] as const,
  queryFn: ({ signal }) => getApiKey(signal),
});

/** `GET /meta/config`: the profile country codes (F9-b S12) do not change while the app runs. */
export const metaConfigQuery = queryOptions({
  queryKey: ['meta', 'config'] as const,
  queryFn: ({ signal }) => getMetaConfig(signal),
  staleTime: Infinity,
});

/**
 * A saved change of the signed-in user reaches every place that shows it: the session (topbar,
 * home hub, sidebar) and the cached `GET /me`.
 */
export function applyUserChange(
  queryClient: QueryClient,
  user: Partial<UserPayload>,
  profile: Partial<ProfileData> = {},
): void {
  queryClient.setQueryData<Session>(sessionQuery.queryKey, (old) =>
    old?.user ? { ...old, user: { ...old.user, ...user } } : old,
  );
  queryClient.setQueryData<MeData>(meQuery.queryKey, (old) =>
    old ? { ...old, user: { ...old.user, ...user }, profile: { ...old.profile, ...profile } } : old,
  );
}
