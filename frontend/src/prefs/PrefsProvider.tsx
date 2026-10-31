import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { useCachedSession, useOffline } from '@/auth';
import { pushToast } from '@/components/ui/toastStore';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { applyPrefs } from './apply';
import { PrefsContext, type PrefsApi } from './context';
import { PHONE_QUERY, resolvePrefs } from './resolve';
import { readMirror, writeMirror } from './storage';
import { createPrefsSync, type PrefsSync } from './sync';

/**
 * The live side of the preferences (design 4.5). The session query holds the server copy, which
 * `sync` updates optimistically; this provider turns it into `<html>` attributes, keeps the
 * mirror (`rb_prefs_v1`) equal to the server copy and re-resolves Auto when the viewport crosses
 * 860 px. The app is English-only, so no language handling lives here.
 */
export function PrefsProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const { i18n } = useTranslation();
  const session = useCachedSession(); // passive: a cleared cache must not trigger a refetch
  const phone = useMediaQuery(PHONE_QUERY);
  const offline = useOffline();

  const signedIn = session?.authenticated === true;
  const serverPrefs = signedIn ? session.prefs : null;
  // The mirror is the stand-in until the session loads and for anonymous visits.
  // Re-read when the account state flips: after a logout it holds the last server copy.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const mirror = useMemo(() => readMirror(), [signedIn]);
  const prefs = serverPrefs ?? mirror;
  const effective = useMemo(() => resolvePrefs(prefs, { phone }), [prefs, phone]);

  const sync = useMemo<PrefsSync>(
    () =>
      createPrefsSync({
        queryClient,
        onError: (_error, retry) =>
          pushToast({
            kind: 'error',
            message: i18n.t('prefs:saveFailed'),
            action: { label: i18n.t('common:actions.retry'), onAction: retry },
          }),
      }),
    [queryClient, i18n],
  );
  useEffect(() => {
    const flush = () => sync.flush();
    window.addEventListener('pagehide', flush);
    return () => {
      window.removeEventListener('pagehide', flush);
      sync.dispose();
    };
  }, [sync]);

  // Server wins (PREF-7): its copy replaces the mirror whenever it changes.
  useEffect(() => {
    if (!serverPrefs) return;
    writeMirror(serverPrefs);
  }, [serverPrefs]);

  useEffect(() => {
    applyPrefs(document.documentElement, effective);
  }, [effective]);

  // Read-only while offline (PWA-7): a change would be applied and then fail to save.
  const set = useCallback<PrefsSync['set']>(
    (key, value, options) => {
      if (!offline) sync.set(key, value, options);
    },
    [offline, sync],
  );

  const value = useMemo<PrefsApi>(
    () => ({
      prefs,
      effective,
      phone,
      signedIn,
      offline,
      set,
      flush: sync.flush,
    }),
    [prefs, effective, phone, signedIn, offline, set, sync],
  );

  return <PrefsContext value={value}>{children}</PrefsContext>;
}
