import {
  useEffect,
  useId,
  useRef,
  type KeyboardEvent,
  type PointerEvent,
  type ReactNode,
  type RefObject,
  type SyntheticEvent,
} from 'react';
import { useTranslation } from 'react-i18next';
import { Icon } from './Icon';
import styles from './Modal.module.css';

export type ModalProps = {
  open: boolean;
  /** The dialog closed (Escape, close button, backdrop): update the parent state. */
  onClose: () => void;
  /** Heading and accessible name. */
  title: string;
  children: ReactNode;
  /** Close on a backdrop click (default). A ConfirmDialog turns it off. */
  dismissOnBackdrop?: boolean;
  variant?: 'modal' | 'sheet' | 'side';
  /** Width preset; full screen below 680 px (S10). */
  size?: 'md' | 'lg' | 'xl';
  /** Keep the heading for assistive technology only. */
  hideTitle?: boolean;
  /** Leave out the corner close button (the content has its own buttons). */
  hideClose?: boolean;
  /**
   * `false` while the user must finish something first (F9-j S6): Escape, the backdrop and the
   * browser's cancel do nothing and there is no close button. The parent closes it with `open`.
   */
  dismissible?: boolean;
  /**
   * Where focus goes on close. Defaults to what had focus on open; pass the opener when the
   * browser does not focus buttons on click (Safari), so `activeElement` is not the opener.
   */
  returnFocusRef?: RefObject<HTMLElement | null>;
};

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Native `showModal()` gives the focus trap, Escape and the top layer; we add the rest. */
function focusInside(dialog: HTMLDialogElement): void {
  const wanted = dialog.querySelector<HTMLElement>('[data-autofocus]');
  if (wanted) return wanted.focus();
  if (dialog.contains(document.activeElement)) return;
  (dialog.querySelector<HTMLElement>(FOCUSABLE) ?? dialog).focus();
}

/**
 * A modal dialog on the native `<dialog>` (D17). Escape and the close button close it, a
 * backdrop click closes it only when the press both started and ended on the backdrop (so
 * dragging a selection out of the content does not), and focus returns to the opener.
 */
export function Modal({
  open,
  onClose,
  title,
  children,
  dismissOnBackdrop = true,
  variant = 'modal',
  size = 'md',
  hideTitle = false,
  hideClose = false,
  dismissible = true,
  returnFocusRef,
}: ModalProps) {
  const { t } = useTranslation('common');
  const headingId = useId();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const pressedOnBackdrop = useRef(false);
  const latest = useRef({ open, onClose });
  useEffect(() => {
    latest.current = { open, onClose };
  });

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      opener.current = document.activeElement as HTMLElement | null;
      dialog.showModal();
      focusInside(dialog);
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  // Native close, from Escape, the close button or the backdrop; or our own dialog.close().
  // React passes a nested modal's close up the tree: only this dialog's own close counts.
  const handleClose = (event: SyntheticEvent<HTMLDialogElement>) => {
    if (event.target !== event.currentTarget) return;
    const target = returnFocusRef?.current ?? opener.current;
    opener.current = null;
    if (latest.current.open) latest.current.onClose();
    target?.focus?.();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDialogElement>) => {
    if (event.key !== 'Escape') return;
    event.preventDefault(); // we close it ourselves, the same way in every browser
    event.stopPropagation(); // a modal under this one stays open
    if (dismissible) event.currentTarget.close();
  };

  // The browser's own cancel (Escape, a close request on mobile): never closes a locked dialog.
  const handleCancel = (event: SyntheticEvent<HTMLDialogElement>) => {
    if (!dismissible && event.target === event.currentTarget) event.preventDefault();
  };

  const handlePointerDown = (event: PointerEvent<HTMLDialogElement>) => {
    pressedOnBackdrop.current = event.target === event.currentTarget;
  };
  const handlePointerUp = (event: PointerEvent<HTMLDialogElement>) => {
    const complete = pressedOnBackdrop.current && event.target === event.currentTarget;
    pressedOnBackdrop.current = false;
    if (complete && dismissOnBackdrop && dismissible) event.currentTarget.close();
  };

  return (
    <dialog
      ref={dialogRef}
      className={[styles.dialog, styles[variant], styles[size]].join(' ')}
      aria-labelledby={headingId}
      onClose={handleClose}
      onCancel={handleCancel}
      onKeyDown={handleKeyDown}
      onPointerDown={handlePointerDown}
      onPointerUp={handlePointerUp}
    >
      {open && (
        <div className={styles.surface}>
          <div className={styles.head}>
            <h2 id={headingId} className={hideTitle ? 'sr-only' : styles.title}>
              {title}
            </h2>
            {!hideClose && dismissible && (
              <button
                type="button"
                className={styles.close}
                aria-label={t('actions.close')}
                onClick={() => dialogRef.current?.close()}
              >
                <Icon name="close" size={18} />
              </button>
            )}
          </div>
          <div className={styles.body}>{children}</div>
        </div>
      )}
    </dialog>
  );
}
