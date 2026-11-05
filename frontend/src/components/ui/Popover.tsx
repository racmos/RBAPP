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
  children: ReactNode;
};

/**
 * A non-modal panel anchored under its trigger button (F5-i step 3): a disclosure whose panel is
 * a labelled dialog. Opening moves focus into the panel; Escape and the close button close it and
 * focus goes back to the trigger; a press outside closes it too.
 */
export function Popover({ title, trigger, triggerLabel, children }: PopoverProps) {
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

  return (
    <div ref={wrapRef} className={styles.wrap}>
      <button
        ref={triggerRef}
        type="button"
        className={styles.trigger}
        aria-expanded={open}
        aria-controls={open ? `${id}-panel` : undefined}
        aria-label={triggerLabel}
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
          className={styles.panel}
        >
          <div className={styles.header}>
            <h3 id={`${id}-title`} className={styles.title}>
              {title}
            </h3>
            <button
              type="button"
              className={styles.close}
              aria-label={t('actions.close')}
              onClick={() => {
                setOpen(false);
                triggerRef.current?.focus();
              }}
            >
              <Icon name="close" size={16} />
            </button>
          </div>
          {children}
        </div>
      )}
    </div>
  );
}
