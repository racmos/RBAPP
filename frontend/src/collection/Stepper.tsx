import { useId } from 'react';
import { useTranslation } from 'react-i18next';
import { DebouncedInput } from '@/catalog';
import styles from './Stepper.module.css';

type StepperProps = {
  label: string;
  value: number;
  min: number;
  max: number;
  disabled?: boolean;
  /** Called with a valid whole number: at once for the buttons, after a pause when typing. */
  onCommit: (next: number) => void;
};

/** A whole number with minus and plus buttons (F3-g S6). */
export function Stepper({ label, value, min, max, disabled, onCommit }: StepperProps) {
  const { t } = useTranslation('collection');
  const id = useId();
  return (
    <div role="group" aria-labelledby={id} className={styles.stepper}>
      <span id={id} className={styles.label}>
        {label}
      </span>
      <div className={styles.controls}>
        <button
          type="button"
          className={styles.button}
          aria-label={`${t('line.fewer')}: ${label}`}
          disabled={disabled || value <= min}
          onClick={() => onCommit(value - 1)}
        >
          −
        </button>
        <DebouncedInput
          type="number"
          inputMode="numeric"
          className={styles.input}
          aria-label={label}
          min={min}
          max={max}
          disabled={disabled}
          value={String(value)}
          delay={500}
          onCommit={(next) => {
            const parsed = Number(next);
            if (next !== '' && Number.isInteger(parsed) && parsed >= min && parsed <= max) {
              onCommit(parsed);
            }
          }}
        />
        <button
          type="button"
          className={styles.button}
          aria-label={`${t('line.more')}: ${label}`}
          disabled={disabled || value >= max}
          onClick={() => onCommit(value + 1)}
        >
          +
        </button>
      </div>
    </div>
  );
}
