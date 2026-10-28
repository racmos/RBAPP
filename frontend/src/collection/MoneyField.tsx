import { useTranslation } from 'react-i18next';
import { DebouncedInput } from '@/catalog';
import { Field } from '@/components/ui/Field';
import styles from './MoneyField.module.css';

type MoneyFieldProps = {
  label: string;
  value: number | null;
  disabled?: boolean;
  /** `null` for an empty box, else a number of 0 or more. Called after a pause when typing. */
  onCommit: (next: number | null) => void;
};

/** A price in euros (F3-g S6, S7): empty means "no price". */
export function MoneyField({ label, value, disabled, onCommit }: MoneyFieldProps) {
  const { t } = useTranslation('collection');
  return (
    <Field label={label}>
      {(control) => (
        <span className={styles.wrap}>
          <DebouncedInput
            {...control}
            type="number"
            inputMode="decimal"
            min={0}
            step="0.01"
            disabled={disabled}
            value={value === null ? '' : String(value)}
            delay={500}
            onCommit={(next) => {
              if (next === '') return onCommit(null);
              const parsed = Number(next);
              if (Number.isFinite(parsed) && parsed >= 0) onCommit(parsed);
            }}
          />
          <span className={styles.unit} aria-hidden="true">
            €
          </span>
          <span className="sr-only">{t('line.euro')}</span>
        </span>
      )}
    </Field>
  );
}
