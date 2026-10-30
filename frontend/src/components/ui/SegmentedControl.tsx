import { useId, type ReactNode } from 'react';
import styles from './SegmentedControl.module.css';

export type SegmentedOption<T extends string> = {
  value: T;
  label: ReactNode;
  disabled?: boolean;
};

type SegmentedControlProps<T extends string> = {
  options: readonly SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
  /** Accessible name of the group (a string)... */
  label?: string;
  /** ...or the id of a visible element that names it. */
  labelledBy?: string;
  /** Show `label` above the options: a filter must say what it filters (owner feedback S24). */
  showLabel?: boolean;
  disabled?: boolean;
};

/**
 * One choice out of a few. A radiogroup of native radio inputs, so arrow keys move the
 * selection and exactly one option is checked, with no key handling of our own.
 */
export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  label,
  labelledBy,
  showLabel = false,
  disabled,
}: SegmentedControlProps<T>) {
  const name = useId();
  const labelId = useId();
  const visible = showLabel && label !== undefined && !labelledBy;
  const group = (
    <div
      role="radiogroup"
      aria-label={labelledBy || visible ? undefined : label}
      aria-labelledby={visible ? labelId : labelledBy}
      className={styles.group}
    >
      {options.map((option) => (
        <label key={option.value} className={styles.option}>
          <input
            type="radio"
            name={name}
            className={styles.input}
            checked={option.value === value}
            disabled={disabled || option.disabled}
            onChange={() => onChange(option.value)}
          />
          <span className={styles.text}>{option.label}</span>
        </label>
      ))}
    </div>
  );
  if (!visible) return group;
  return (
    <div className={styles.field}>
      <span id={labelId} className={styles.label}>
        {label}
      </span>
      {group}
    </div>
  );
}
