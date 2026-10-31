import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { dismissToast, getToasts, pushToast } from '@/components/ui/toastStore';
import { useUpdatePrompt } from './useUpdatePrompt';

/** The rollback build ships a worker that removes itself; registering one would loop (PWA-5). */
const selfDestroying = () => import.meta.env.VITE_PWA_SELF_DESTROY === 'true';

function UpdateWatcher() {
  const { t } = useTranslation('common');
  const { needRefresh, checks, update } = useUpdatePrompt();
  const toastId = useRef<number | null>(null);

  useEffect(() => {
    if (!needRefresh) return;
    const showing = getToasts().some((toast) => toast.id === toastId.current);
    if (showing) return;
    // Persistent (duration 0): it stays until answered. Dismissing keeps the current version
    // running and the page untouched; the next check offers the update again.
    toastId.current = pushToast({
      kind: 'info',
      message: t('pwa.update.message'),
      duration: 0,
      action: { label: t('pwa.update.action'), onAction: update },
    });
    // `update` and `t` change identity on every render and must not re-offer by themselves.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [needRefresh, checks]);

  useEffect(
    () => () => {
      if (toastId.current !== null) dismissToast(toastId.current);
      toastId.current = null;
    },
    [],
  );

  return null;
}

/** Mounted once in `AppProviders`: the "New version" toast (PWA-4). Renders nothing itself. */
export function UpdateToast() {
  return selfDestroying() ? null : <UpdateWatcher />;
}
