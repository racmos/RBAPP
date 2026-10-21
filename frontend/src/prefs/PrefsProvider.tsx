import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { hasSignedInHint, useCachedSession, useOffline } from '@/auth';
import { pushToast } from '@/components/ui/toastStore';
import { clearStoredLang, resolveLang, storeLang, type Lang } from '@/i18n';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { applyPrefs } from './apply';
import { PrefsContext, type PrefsApi } from './context';
import { PHONE_QUERY, resolvePrefs } from './resolve';
import { readMirror, writeMirror } from './storage';
import { createPrefsSync, type PrefsSync } from './sync';

/**
 * The live side of the preferences (design 4.5). The session query holds the server copy, which
 * `sync` updates optimistically; this provider turns it into `<html>` attributes, keeps the
 * mirror (`rb_prefs_v1`) equal to the server copy, re-resolves Auto when the viewport crosses
 * 860 px, and lets the account language drive i18next.
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

  // The account language drives i18next (R4): the mirror's while the session is pending (only
  // for a browser that was signed in), the server's afterwards. With no account language (Auto,
  // anonymous) i18next keeps what the bootstrap or the device toggle chose.
  const pending = session === undefined;
  const accountLang: Lang | null = pending
    ? hasSignedInHint()
      ? mirror.lang
      : null
    : signedIn
      ? (serverPrefs?.lang ?? null)
      : null;
  useEffect(() => {
    if (accountLang && accountLang !== i18n.language) void i18n.changeLanguage(accountLang);
  }, [accountLang, i18n]);

  const lang = i18n.language === 'en' ? 'en' : 'es';
  useEffect(() => {
    applyPrefs(document.documentElement, { ...effective, lang });
  }, [effective, lang]);

  // Read-only while offline (PWA-7): a change would be applied and then fail to save.
  const set = useCallback<PrefsSync['set']>(
    (key, value, options) => {
      if (!offline) sync.set(key, value, options);
    },
    [offline, sync],
  );

  const setLanguage = useCallback(
    (next: Lang | null) => {
      if (next) {
        storeLang(next);
        void i18n.changeLanguage(next);
      } else {
        clearStoredLang();
        void i18n.changeLanguage(
          resolveLang({
            accountLang: null,
            storedLang: null,
            browserLanguages: navigator.languages,
          }),
        );
      }
      set('lang', next);
    },
    [i18n, set],
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
      setLanguage,
    }),
    [prefs, effective, phone, signedIn, offline, set, sync, setLanguage],
  );

  return <PrefsContext value={value}>{children}</PrefsContext>;
}
