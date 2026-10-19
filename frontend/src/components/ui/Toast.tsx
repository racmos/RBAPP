import { useEffect, useRef, useSyncExternalStore } from 'react';
import { useTranslation } from 'react-i18next';
import styles from './Toast.module.css';
import {
  DEFAULT_DURATION_MS,
  dismissToast,
  getToasts,
  subscribeToasts,
  type Toast as ToastModel,
} from './toastStore';

/** One toast. The timer stops while the pointer is over it or focus is inside it. */
function ToastItem({ toast }: { toast: ToastModel }) {
  const { t } = useTranslation('common');
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const holds = useRef(0);
  const duration = toast.duration ?? DEFAULT_DURATION_MS;

  const start = () => {
    clearTimeout(timer.current);
    if (duration > 0 && holds.current === 0) {
      timer.current = setTimeout(() => dismissToast(toast.id), duration);
    }
  };
  const hold = () => {
    holds.current += 1;
    clearTimeout(timer.current);
  };
  const release = () => {
    holds.current = Math.max(0, holds.current - 1);
    start();
  };

  useEffect(() => {
    start();
    return () => clearTimeout(timer.current);
    // The timer is armed once per toast; hold/release re-arm it by hand.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [toast.id]);

  return (
    <div
      data-toast={toast.kind}
      className={[styles.toast, styles[toast.kind]].join(' ')}
      onPointerEnter={hold}
      onPointerLeave={release}
      onFocus={hold}
      onBlur={release}
    >
      <p className={styles.message}>{toast.message}</p>
      {toast.action && (
        <button
          type="button"
          className={styles.action}
          onClick={() => {
            toast.action?.onAction();
            dismissToast(toast.id);
          }}
        >
          {toast.action.label}
        </button>
      )}
      <button
        type="button"
        className={styles.close}
        aria-label={t('actions.close')}
        onClick={() => dismissToast(toast.id)}
      >
        <span aria-hidden="true">×</span>
      </button>
    </div>
  );
}

/**
 * The toast stack (D17): a manual popover re-shown on every push so it paints above any open
 * `<dialog>`. Spoken text goes through `LiveAnnouncer`, not through this element.
 */
export function ToastStack() {
  const { t } = useTranslation('common');
  const toasts = useSyncExternalStore(subscribeToasts, getToasts);
  const stack = useRef<HTMLDivElement>(null);
  const latest = toasts.at(-1)?.id;

  useEffect(() => {
    const element = stack.current;
    if (!element || latest === undefined || typeof element.showPopover !== 'function') return;
    try {
      element.hidePopover();
    } catch {
      // Not showing yet.
    }
    element.showPopover();
  }, [latest]);

  if (toasts.length === 0) return null;
  return (
    <div
      ref={stack}
      popover="manual"
      role="region"
      aria-label={t('toast.region')}
      className={styles.stack}
    >
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} />
      ))}
    </div>
  );
}
