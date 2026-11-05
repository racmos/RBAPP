import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Icon } from './Icon';
import styles from './Popover.module.css';

type PopoverProps = {
  /** Heading and accessible name of the panel. */
  title: string;
  /** Visible content of the trigger button. */
  trigger: ReactNode;
  /** Accessible name of the trigger when its content is not enough (a count, an icon). */
  triggerLabel?: string;
  /** The trigger cannot be pressed (offline, for example). */
  disabled?: boolean;
  /** `sm`: a narrow panel for a short list of actions. */
  size?: 'md' | 'sm';
  /** The content, or a function of `close` (closes the panel and focuses the trigger). */
  children: ReactNode | ((close: () => void) => ReactNode);
};

/**
 * A non-modal panel anchored under its trigger button (F5-i step 3): a disclosure whose panel is
 * a labelled dialog. Opening moves focus into the panel; Escape and the close button close it and
 * focus goes back to the trigger; a press outside closes it too.
 */
export function Popover({
  title,
  trigger,
  triggerLabel,
  disabled = false,
  size = 'md',
  children,
}: PopoverProps) {
  const { t } = useTranslation('common');
  const id = useId();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    panelRef.current?.focus();
    const onPointerDown = (event: PointerEvent) => {
      if (!wrapRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      setOpen(false);
      triggerRef.current?.focus();
    };
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  // Closing from the content focuses the trigger after the render (no ref read while rendering).
  const [refocus, setRefocus] = useState(0);
  useEffect(() => {
    if (refocus > 0) triggerRef.current?.focus();
  }, [refocus]);
  const close = () => {
    setOpen(false);
    setRefocus((count) => count + 1);
  };

  return (
    <div ref={wrapRef} className={styles.wrap}>
      <button
        ref={triggerRef}
        type="button"
        className={styles.trigger}
        aria-expanded={open}
        aria-controls={open ? `${id}-panel` : undefined}
        aria-label={triggerLabel}
        disabled={disabled}
        onClick={() => setOpen((value) => !value)}
      >
        {trigger}
      </button>
      {open && (
        <div
          ref={panelRef}
          id={`${id}-panel`}
          role="dialog"
          aria-labelledby={`${id}-title`}
          tabIndex={-1}
          className={[styles.panel, size === 'sm' && styles.sm].filter(Boolean).join(' ')}
        >
          <div className={styles.header}>
            <h3 id={`${id}-title`} className={styles.title}>
              {title}
            </h3>
            <button
              type="button"
              className={styles.close}
              aria-label={t('actions.close')}
              onClick={close}
            >
              <Icon name="close" size={16} />
            </button>
          </div>
          {typeof children === 'function' ? children(close) : children}
        </div>
      )}
    </div>
  );
}
