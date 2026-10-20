import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useSyncExternalStore } from 'react';
import { useNavigate } from 'react-router';
import { useOnline } from '@/lib/useOnline';
import { sessionQuery } from './session';
import { useCachedSession } from './useAuth';

/**
 * "The app booted without the session" (PWA-7): the session request failed with a network error
 * and the browser had a signed-in hint, so the shell was rendered from the precache without the
 * user. It lasts until a session request succeeds.
 */
let bootedOffline = false;
const listeners = new Set<() => void>();
const set = (next: boolean) => {
  if (bootedOffline === next) return;
  bootedOffline = next;
  listeners.forEach((listener) => listener());
};

export const markBootedOffline = (): void => set(true);
export const clearBootedOffline = (): void => set(false);
const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};
export const useBootedOffline = (): boolean => useSyncExternalStore(subscribe, () => bootedOffline);

/** True while the browser is offline or the app booted without reaching the server. */
export function useOffline(): boolean {
  const online = useOnline();
  const booted = useBootedOffline();
  return !online || booted;
}

/**
 * After an offline boot: ask for the session again whenever the browser comes back online (and
 * so does the session query on window focus), and leave offline mode once an answer arrives. An
 * expired session goes to the login screen.
 */
export function useOfflineRecovery(): void {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const online = useOnline();
  const booted = useBootedOffline();
  const session = useCachedSession();

  useEffect(() => {
    if (!booted || !online) return;
    // Still unreachable: stay in offline mode, the next online event or focus tries again.
    queryClient.fetchQuery({ ...sessionQuery, staleTime: 0 }).catch(() => undefined);
  }, [booted, online, queryClient]);

  useEffect(() => {
    if (!booted || !session) return;
    clearBootedOffline();
    if (!session.authenticated) void navigate('/login', { replace: true });
  }, [booted, session, navigate]);
}
