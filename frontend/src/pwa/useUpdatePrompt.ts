import { useEffect, useRef, useState } from 'react';
import { useRegisterSW } from 'virtual:pwa-register/react';

/** How often a running app asks the server for a new service worker (PWA-4). */
export const UPDATE_CHECK_INTERVAL_MS = 60 * 60 * 1000;

/**
 * Registers the service worker in prompt mode and reports when a new one is waiting. A new worker
 * never takes control or reloads the page by itself: `update()` is the user's decision. Checks
 * run every hour and when the window becomes visible again, only while online.
 *
 * `checks` counts the checks made so far: it lets the toast be offered again after it was
 * dismissed.
 */
export function useUpdatePrompt() {
  const registration = useRef<ServiceWorkerRegistration | undefined>(undefined);
  const [checks, setChecks] = useState(0);
  const {
    needRefresh: [needRefresh],
    updateServiceWorker,
  } = useRegisterSW({
    onRegisteredSW: (_url, registered) => {
      registration.current = registered;
    },
  });

  useEffect(() => {
    const check = () => {
      setChecks((count) => count + 1);
      if (navigator.onLine) registration.current?.update().catch(() => undefined);
    };
    const onVisibility = () => {
      if (document.visibilityState === 'visible') check();
    };
    const timer = setInterval(check, UPDATE_CHECK_INTERVAL_MS);
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, []);

  return {
    needRefresh,
    checks,
    /** Activate the waiting worker; the plugin reloads the page once it controls it. */
    update: () => void updateServiceWorker(true),
  };
}
