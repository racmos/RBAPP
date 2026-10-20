import type { QueryClient } from '@tanstack/react-query';
import { patchPrefs } from '@/api/endpoints';
import { ApiError } from '@/api/errors';
import type { Session } from '@/api/types';
import { sessionQuery } from '@/auth';
import { PREF_KEYS } from './domain';
import type { PrefKey, Prefs } from './types';

/** Quiet time after the last slider value before it is sent (PREF-8). */
export const SLIDER_DEBOUNCE_MS = 400;

type SyncOptions = {
  queryClient: QueryClient;
  /** A save failed (never called for a 401: the global handler owns it). `retry` sends it again. */
  onError: (error: unknown, retry: () => void) => void;
  debounceMs?: number;
  send?: (changes: Partial<Prefs>) => Promise<Prefs>;
};

export type PrefsSync = {
  /** Apply `value` now (optimistic) and schedule the save; `null` is Auto. */
  set<K extends PrefKey>(key: K, value: Prefs[K], options?: { debounce?: boolean }): void;
  /** Send what is waiting, without waiting for the debounce (pointerup, blur, pagehide). */
  flush(): void;
  dispose(): void;
};

const keysOf = (changes: Partial<Prefs>): PrefKey[] => PREF_KEYS.filter((key) => key in changes);

/**
 * Optimistic preference saving (PREF-8, design 4.5). The session query holds the prefs the UI
 * shows, so a change is written there first. Only one PATCH is in flight; changes made meanwhile
 * wait and go out together, and each request carries only the fields that differ from the last
 * state the server confirmed. A failure puts the failed fields back.
 */
export function createPrefsSync({
  queryClient,
  onError,
  debounceMs = SLIDER_DEBOUNCE_MS,
  send = patchPrefs,
}: SyncOptions): PrefsSync {
  let confirmed: Prefs | null = null;
  let pending: Partial<Prefs> = {};
  let inFlight: Partial<Prefs> | null = null;
  let timer: ReturnType<typeof setTimeout> | undefined;

  const cachedPrefs = (): Prefs | null =>
    queryClient.getQueryData<Session>(sessionQuery.queryKey)?.prefs ?? null;

  const writePrefs = (update: (prefs: Prefs) => Prefs) =>
    queryClient.setQueryData<Session>(sessionQuery.queryKey, (session) =>
      session?.prefs ? { ...session, prefs: update(session.prefs) } : session,
    );

  const hasPending = () => keysOf(pending).length > 0;

  function flush(): void {
    clearTimeout(timer);
    timer = undefined;
    if (inFlight || !hasPending()) return; // the answer of the request in flight re-flushes
    const changes: Record<string, unknown> = {};
    for (const key of keysOf(pending)) {
      if (confirmed?.[key] !== pending[key]) changes[key] = pending[key];
    }
    pending = {};
    if (Object.keys(changes).length === 0) return;
    inFlight = changes as Partial<Prefs>;
    send(inFlight).then(succeeded, failed);
  }

  function settle(): void {
    if (hasPending() && timer === undefined) flush();
  }

  function succeeded(prefs: Prefs): void {
    confirmed = prefs;
    inFlight = null;
    writePrefs(() => ({ ...prefs, ...pending })); // a newer, unsent value stays on screen
    settle();
  }

  function failed(error: unknown): void {
    const lost = inFlight ?? {};
    inFlight = null;
    writePrefs((prefs) => {
      const reverted = { ...prefs };
      for (const key of keysOf(lost)) {
        if (!(key in pending) && confirmed)
          (reverted as Record<string, unknown>)[key] = confirmed[key];
      }
      return reverted;
    });
    if (!(error instanceof ApiError && error.status === 401)) {
      onError(error, () => {
        for (const key of keysOf(lost)) set(key, lost[key] as Prefs[typeof key]);
      });
    }
    settle();
  }

  function set<K extends PrefKey>(key: K, value: Prefs[K], options?: { debounce?: boolean }) {
    const current = cachedPrefs();
    if (!current) return;
    if (!inFlight && !hasPending()) confirmed = current;
    writePrefs((prefs) => ({ ...prefs, [key]: value }));
    pending = { ...pending, [key]: value };
    clearTimeout(timer);
    timer = undefined;
    if (options?.debounce) {
      timer = setTimeout(() => {
        timer = undefined;
        flush();
      }, debounceMs);
    } else {
      flush();
    }
  }

  return {
    set,
    flush,
    dispose: () => {
      clearTimeout(timer);
      timer = undefined;
    },
  };
}
